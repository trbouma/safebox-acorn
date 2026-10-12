"""Non-destructive, record-only migration between Acorn identities."""
import asyncio
import hashlib
import json
import os
import re
from contextlib import contextmanager
from urllib.parse import urlsplit

import requests
from cryptography.exceptions import InvalidTag

from stroma import ClientPool, NIP44Encrypt, Keys, BlossomPool, BlossomError

from acorn.acorn import INTERNAL_RECORD_LABELS
from acorn.models import SafeboxRecord, WalletConfig, EncryptionParms
from acorn.func_utils import recover_nsec_from_seed, encrypt_bytes, decrypt_bytes


class CopyFailure(ValueError):
    """Only fixed, non-sensitive diagnostics may be supplied here."""
    def __init__(self, stage, detail):
        self.stage = stage
        self.detail = detail
        super().__init__(detail)


def safe_failure(exc):
    if isinstance(exc, BlossomError) and exc.outcomes:
        return pool_failures(exc.outcomes)
    code = getattr(exc, "status_code", None)
    if code is None:
        code = getattr(getattr(exc, "response", None), "status_code", None)
    if type(code) is int and 400 <= code <= 599:
        description = {401: "authorization required", 402: "payment required",
                       403: "access refused", 404: "file or endpoint not found",
                       413: "file too large", 429: "rate limited"}.get(code, "server rejected the request")
        return f"HTTP {code}: {description}"
    if isinstance(exc, (TimeoutError, requests.exceptions.Timeout)):
        return "Request timed out"
    if isinstance(exc, (ConnectionError, requests.exceptions.ConnectionError)):
        return "Connection failed; check endpoint and network access"
    if isinstance(exc, InvalidTag):
        return "Attachment authentication failed; key, nonce, or ciphertext does not match"
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return "Invalid data, encryption parameters, or digest"
    return "Operation failed; no private exception details displayed"


def pool_failures(outcomes):
    details = []
    approved = {"Blob SHA-256 mismatch", "Blob exceeds the size limit",
                "Operation deadline exceeded", "Upload authorization failed",
                "Operation deadline exceeded; storage may have occurred"}
    for outcome in outcomes:
        host = urlsplit(outcome.server).hostname or "unknown server"
        code = re.fullmatch(r"(?:Retrieval|Upload) returned HTTP ([0-9]{3})", outcome.message)
        reason = (f"HTTP {code.group(1)}" if code else outcome.message
                  if outcome.message in approved else "Request failed or unconfirmed")
        details.append(f"{host}: {reason}")
    return "; ".join(details) or "No confirmed Blossom result"


@contextmanager
def copy_stage(name):
    try:
        yield
    except CopyFailure:
        raise
    except Exception as exc:
        raise CopyFailure(name, safe_failure(exc)) from None


def failure_row(row, exc):
    return {**row, "status": "failed or unverified; inspect destination before retrying",
            "error_stage": exc.stage, "error_detail": exc.detail}


def destination_nsec(secret: str, *, legacy: bool = False) -> str:
    value = " ".join(secret.split())
    if " " in value:
        return recover_nsec_from_seed(seed_phrase=value, legacy=legacy)
    if legacy:
        raise ValueError("Legacy derivation applies only to a recovery phrase")
    if not (value.startswith("nsec1") or
            (len(value) == 64 and all(c in "0123456789abcdefABCDEF" for c in value))):
        raise ValueError("Expected an nsec, hexadecimal private key, or recovery phrase")
    return Keys(priv_k=value).private_key_bech32()


def endpoint(value: str, schemes: tuple[str, ...]) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme not in schemes or not parsed.hostname or parsed.username
            or parsed.password or parsed.fragment or parsed.query
            or any(c.isspace() for c in value)):
        raise ValueError("Invalid destination endpoint")
    _ = parsed.port
    return value.rstrip("/")


async def inventory(wallet, *, limit=10000):
    """Fail closed on relay failure/saturation, without load_data side effects."""
    async with ClientPool([wallet.home_relay]) as client:
        events = await asyncio.wait_for(client.query([{
            "authors": [wallet.pubkey_hex], "kinds": [37375], "limit": limit,
        }]), timeout=30)
    if len(events) >= limit:
        raise ValueError("Record query reached its limit; completeness cannot be established")
    for event in events:
        if (event.pub_key != wallet.pubkey_hex or event.kind != 37375
                or not event.is_valid()
                or not wallet._record_event_tag(event, "d")):
            raise ValueError("Relay returned an invalid record event")
    return {wallet._record_event_tag(e, "d"): e
            for e in wallet._canonical_record_events(events)}


def decrypt(wallet, event):
    return json.loads(NIP44Encrypt(wallet.k).decrypt(event.content, wallet.pubkey_hex))


def verify_destination(target, events):
    # load_data uses "wallet"; web-created Acorns need not have the separate
    # wallet_config object written by the older CLI initializer.
    wallet = events.get(target._record_label_hash("wallet"))
    config = events.get(target._record_label_hash("wallet_config"))
    if wallet is None and config is None:
        raise ValueError("No destination Acorn configuration found on the specified relay")
    try:
        if wallet is not None:
            data = decrypt(target, wallet)
            if not isinstance(data, list) or not data:
                raise ValueError()
            tags = {}
            for tag in data:
                if (not isinstance(tag, list) or len(tag) < 2
                        or not all(isinstance(value, str) for value in tag)
                        or tag[0] in tags):
                    raise ValueError()
                tags[tag[0]] = tag[1:]
            if (len(tags.get("balance", [])) != 2
                    or not tags["balance"][0].isascii()
                    or not tags["balance"][0].isdigit()
                    or not tags["balance"][1].strip()
                    or len(tags.get("name", [])) != 1 or not tags["name"][0].strip()
                    or len(tags.get("mint", [])) != 1):
                raise ValueError()
            mint = urlsplit(tags["mint"][0])
            if mint.scheme not in {"http", "https"} or not mint.hostname:
                raise ValueError()
        else:
            data = decrypt(target, config)
            if not isinstance(data, dict) or "kind_cashu" not in data:
                raise ValueError()
            WalletConfig.model_validate(data)
    except Exception:
        # Do not expose decrypted tags, which may include keys/recovery phrases.
        raise ValueError("Destination configuration is invalid or unreadable") from None


async def prepare(source, target, *, blossom=None, source_blossoms=(), allow_private=False):
    if source.pubkey_hex == target.pubkey_hex:
        raise ValueError("Source and destination are the same identity; use relay replication")
    destination = await inventory(target)
    verify_destination(target, destination)
    origin = await inventory(source)
    reserved = {source._record_label_hash(label) for label in INTERNAL_RECORD_LABELS}
    rows = []
    for coordinate, event in origin.items():
        if coordinate in reserved:
            continue
        row = {"source_id": event.id, "coordinate": coordinate}
        try:
            data = decrypt(source, event)
            record = SafeboxRecord.model_validate(data)
            if record.blobsha256 and not re.fullmatch(r"[0-9a-f]{64}", record.blobsha256):
                raise ValueError()
            if (record.blobref or record.blob_service_npubs or record.encryptparms) and not record.blobsha256:
                raise ValueError()
            label = record.tag[0]
            if (not label or source._record_label_hash(label) != coordinate
                    or label in INTERNAL_RECORD_LABELS
                    or label.split(":")[-1] in INTERNAL_RECORD_LABELS
                    or label.startswith("__acorn_") or record.type == "internal"):
                raise ValueError()
            row.update(label=label, data=data)
            current = destination.get(target._record_label_hash(label))
            if current is not None:
                matches = await matches_copy(source, data, decrypt(target, current), blossom, source_blossoms=source_blossoms, allow_private=allow_private)
                row["status"] = "already present" if matches else "conflict (skipped)"
            elif record.blobsha256 and not blossom:
                row["status"] = "attachment needs --destination-blossom (skipped)"
            else:
                row["status"] = "copy"
        except CopyFailure as exc:
            row = failure_row(row, exc)
        except Exception:
            row["status"] = "unreadable, reserved, or unlabeled record (skipped)"
        rows.append(row)
    return rows


def plaintext(data, raw, stage="attachment verification"):
    record = SafeboxRecord.model_validate(data)
    if hashlib.sha256(raw).hexdigest() != record.blobsha256:
        raise CopyFailure(stage, "Attachment ciphertext digest mismatch")
    if record.encryptparms:
        if record.encryptparms.aad:
            raise CopyFailure(stage, "Attachment uses unsupported additional authenticated data")
        if not record.origsha256:
            raise CopyFailure(stage, "Source record is missing the plaintext digest (origsha256)")
        if record.encryptparms.alg != "AES-256-GCM":
            raise CopyFailure(stage, "Unsupported attachment encryption algorithm")
        clear = decrypt_bytes(raw, bytes.fromhex(record.encryptparms.key),
                              bytes.fromhex(record.encryptparms.iv))
        if hashlib.sha256(clear).hexdigest() != record.origsha256:
            raise CopyFailure(stage, "Attachment plaintext digest mismatch")
        return clear
    if record.origsha256 and hashlib.sha256(raw).hexdigest() != record.origsha256:
        raise CopyFailure(stage, "Attachment plaintext digest mismatch")
    return raw


async def matches_copy(source, data, existing, blossom, *, source_blossoms=(), allow_private=False):
    if not data.get("blobsha256"):
        return existing == data
    if not blossom or not isinstance(existing, dict):
        return False
    changed = {"blobref", "blobsha256", "blob_service_npubs", "encryptparms", "origsha256"}
    if ({k: v for k, v in data.items() if k not in changed}
            != {k: v for k, v in existing.items() if k not in changed}):
        return False
    params = existing.get("encryptparms") or {}
    if (not params.get("key") or params.get("key") == (data.get("encryptparms") or {}).get("key")
            or existing.get("blobsha256") == data["blobsha256"]
            or existing.get("blobref") != f"{blossom}/{existing.get('blobsha256')}"
            or existing.get("blob_service_npubs")):
        return False
    # Verify actual plaintext, not just a claimed source digest or marker.
    original = await read_attachment(source, data, source_blossoms=source_blossoms, allow_private=allow_private)
    with copy_stage("destination attachment readback"):
        blob = await BlossomPool([blossom], allow_private=allow_private).retrieve(existing["blobsha256"])
    with copy_stage("destination attachment verification"):
        return plaintext(existing, blob.content, "destination attachment verification") == original


async def read_attachment(source, data, *, source_blossoms=(), allow_private=False):
    record = SafeboxRecord.model_validate(data)
    overrides = [endpoint(server, ("https",)) for server in source_blossoms]
    failures = []
    tried = set()

    async def download(servers):
        candidates = []
        for server in servers:
            try:
                server = BlossomPool([server], allow_private=allow_private).servers[0]
            except ValueError:
                failures.append("Source endpoint rejected by Blossom URL/network policy")
                continue
            if server in tried:
                continue
            tried.add(server)
            candidates.append(server)
        if candidates:
            try:
                result = await BlossomPool(candidates, allow_private=allow_private).retrieve(record.blobsha256)
                return result.content
            except Exception as exc:
                failures.append(safe_failure(exc))
        return None

    # Overrides can rescue a record even if its old service-resolution metadata
    # is unavailable or invalid. Never contact discovery until these are tried.
    raw = await download(overrides)
    if raw is None:
        try:
            servers = await source.resolve_blob_servers(record, capability="blossom.read")
        except Exception as exc:
            if not tried:
                raise CopyFailure("source attachment resolution", safe_failure(exc)) from None
            failures.append("Stored source resolution: " + safe_failure(exc))
            servers = []
        raw = await download(servers)
    if raw is None:
        if not tried and not failures:
            raise CopyFailure("source attachment resolution", "No source Blossom endpoint could be resolved")
        raise CopyFailure("source attachment download", "; ".join(dict.fromkeys(failures)))
    with copy_stage("source attachment decryption"):
        return plaintext(data, raw, "source attachment decryption")


async def copy_attachment(source, target, data, blossom, *, source_blossoms=(), allow_private=False):
    original = await read_attachment(source, data, source_blossoms=source_blossoms, allow_private=allow_private)
    with copy_stage("destination attachment encryption"):
        key = os.urandom(32)
        encrypted = encrypt_bytes(original, key)
    digest = hashlib.sha256(encrypted.cipherbytes).hexdigest()
    result = {**data, "blobsha256": digest,
              "origsha256": hashlib.sha256(original).hexdigest(),
              "blobref": f"{blossom}/{digest}", "blob_service_npubs": [],
              "encryptparms": EncryptionParms(alg=encrypted.alg, key=key.hex(),
                                              iv=encrypted.iv.hex()).model_dump()}
    with copy_stage("destination attachment upload"):
        destination = BlossomPool([blossom], allow_private=allow_private)
        uploaded = await destination.store(encrypted.cipherbytes, signer=target.k, require="all")
        if not uploaded.ok:
            raise CopyFailure("destination attachment upload", pool_failures(uploaded.outcomes))
        if uploaded.digest != digest:
            raise CopyFailure("destination attachment upload", "Attachment upload returned the wrong digest")
    with copy_stage("destination attachment readback"):
        observed = await destination.retrieve(digest)
    with copy_stage("destination attachment verification"):
        if plaintext(result, observed.content, "destination attachment verification") != original:
            raise CopyFailure("destination attachment verification", "Destination plaintext differs from the source")
    return result


async def execute(source, target, rows, *, blossom=None, source_blossoms=(), allow_private=False, on_result=None):
    """Recheck both inventories; never overwrite or delete anything."""
    fresh = await prepare(source, target, blossom=blossom, source_blossoms=source_blossoms, allow_private=allow_private)
    fresh_by_id = {r["source_id"]: r for r in fresh}
    results = []
    def report(row):
        results.append(row)
        if on_result:
            on_result({key: row[key] for key in ("label", "source_id", "status", "error_stage", "error_detail") if key in row})
    for row in rows:
        if row["status"] != "copy":
            report(row)
            continue
        current = fresh_by_id.get(row["source_id"])
        if current is None or current["status"] != "copy":
            report(current if current and current.get("error_stage") else {**row, "status": "source or destination changed (skipped)"})
            continue
        try:
            stage = "destination record conflict check"
            # Recheck immediately before publishing as well. Nostr does not
            # provide compare-and-swap; users must pause destination writers.
            target_events = await inventory(target)
            if target._record_label_hash(row["label"]) in target_events:
                raise ValueError("Destination record appeared during copy")
            data = dict(row["data"])
            if data.get("blobsha256"):
                stage = "attachment migration"
                data = await copy_attachment(source, target, data, blossom, source_blossoms=source_blossoms, allow_private=allow_private)
            stage = "destination record publication"
            await target.set_wallet_info(row["label"], json.dumps(data),
                                         record_kind=37375, verify=True)
            stage = "destination record readback"
            observed = (await inventory(target)).get(target._record_label_hash(row["label"]))
            if observed is None or decrypt(target, observed) != data:
                raise ValueError("Destination record readback failed")
            result = {**row, "status": "copied and verified"}
        except CopyFailure as exc:
            result = failure_row(row, exc)
        except Exception as exc:
            result = failure_row(row, CopyFailure(stage, safe_failure(exc)))
        report(result)
    return results
