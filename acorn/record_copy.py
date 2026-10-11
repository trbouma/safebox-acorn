"""Non-destructive, record-only migration between Acorn identities."""
import asyncio
import hashlib
import json
import os
import re
from urllib.parse import urlsplit

from stroma import ClientPool, NIP44Encrypt, Keys

from acorn.acorn import INTERNAL_RECORD_LABELS, BlossomClient
from acorn.models import SafeboxRecord, WalletConfig, EncryptionParms
from acorn.func_utils import recover_nsec_from_seed, encrypt_bytes, decrypt_and_verify_record_blob


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


async def prepare(source, target, *, blossom=None):
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
                matches = await matches_copy(source, data, decrypt(target, current), blossom)
                row["status"] = "already present" if matches else "conflict (skipped)"
            elif record.blobsha256 and not blossom:
                row["status"] = "attachment needs --destination-blossom (skipped)"
            else:
                row["status"] = "copy"
        except Exception:
            row["status"] = "unreadable, reserved, or unlabeled record (skipped)"
        rows.append(row)
    return rows


def plaintext(data, raw):
    record = SafeboxRecord.model_validate(data)
    if hashlib.sha256(raw).hexdigest() != record.blobsha256:
        raise ValueError("Attachment ciphertext digest mismatch")
    if record.encryptparms:
        if record.encryptparms.aad:
            raise ValueError("Attachment uses unsupported additional authenticated data")
        return decrypt_and_verify_record_blob(
            cipherbytes=raw, encryptparms=record.encryptparms,
            blobsha256=record.blobsha256, origsha256=record.origsha256)
    if record.origsha256 and hashlib.sha256(raw).hexdigest() != record.origsha256:
        raise ValueError("Attachment plaintext digest mismatch")
    return raw


async def matches_copy(source, data, existing, blossom):
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
    original = await read_attachment(source, data)
    client = BlossomClient(nsec=None, default_servers=[blossom])
    blob = await asyncio.to_thread(client.get_blob, server=blossom, sha256=existing["blobsha256"])
    return plaintext(existing, blob.get_bytes()) == original


async def read_attachment(source, data):
    record = SafeboxRecord.model_validate(data)
    servers = await source.resolve_blob_servers(record, capability="blossom.read")
    client = BlossomClient(nsec=None, default_servers=servers)
    raw = None
    for server in servers:
        try:
            blob = await asyncio.to_thread(client.get_blob, server=server, sha256=record.blobsha256)
            candidate = blob.get_bytes()
            if hashlib.sha256(candidate).hexdigest() == record.blobsha256:
                raw = candidate
                break
        except Exception:
            continue
    if raw is None:
        raise ValueError("Attachment unavailable or digest verification failed")
    return plaintext(data, raw)


async def copy_attachment(source, target, data, blossom):
    original = await read_attachment(source, data)
    key = os.urandom(32)
    encrypted = encrypt_bytes(original, key)
    digest = hashlib.sha256(encrypted.cipherbytes).hexdigest()
    result = {**data, "blobsha256": digest,
              "origsha256": hashlib.sha256(original).hexdigest(),
              "blobref": f"{blossom}/{digest}", "blob_service_npubs": [],
              "encryptparms": EncryptionParms(alg=encrypted.alg, key=key.hex(),
                                              iv=encrypted.iv.hex()).model_dump()}
    destination = BlossomClient(nsec=target.privkey_bech32, default_servers=[blossom])
    uploaded = await asyncio.to_thread(destination.upload_blob, blossom, data=encrypted.cipherbytes,
                                      mime_type="application/octet-stream", description="Private record copy")
    if uploaded.get("sha256") != digest:
        raise ValueError("Attachment upload returned the wrong digest")
    observed = await asyncio.to_thread(destination.get_blob, server=blossom, sha256=digest)
    if plaintext(result, observed.get_bytes()) != original:
        raise ValueError("Destination attachment verification failed")
    return result


async def execute(source, target, rows, *, blossom=None):
    """Recheck both inventories; never overwrite or delete anything."""
    fresh = await prepare(source, target, blossom=blossom)
    fresh_by_id = {r["source_id"]: r for r in fresh}
    results = []
    for row in rows:
        if row["status"] != "copy":
            results.append(row)
            continue
        current = fresh_by_id.get(row["source_id"])
        if current is None or current["status"] != "copy":
            results.append({**row, "status": "source or destination changed (skipped)"})
            continue
        try:
            # Recheck immediately before publishing as well. Nostr does not
            # provide compare-and-swap; users must pause destination writers.
            target_events = await inventory(target)
            if target._record_label_hash(row["label"]) in target_events:
                raise ValueError("Destination record appeared during copy")
            data = dict(row["data"])
            if data.get("blobsha256"):
                data = await copy_attachment(source, target, data, blossom)
            await target.set_wallet_info(row["label"], json.dumps(data),
                                         record_kind=37375, verify=True)
            observed = (await inventory(target)).get(target._record_label_hash(row["label"]))
            if observed is None or decrypt(target, observed) != data:
                raise ValueError("Destination record readback failed")
            results.append({**row, "status": "copied and verified"})
        except Exception:
            # Do not expose exception text that could contain decrypted data.
            results.append({**row, "status": "failed or unverified; inspect destination before retrying"})
    return results
