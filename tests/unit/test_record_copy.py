import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from stroma import Keys, Event, NIP44Encrypt

from acorn.acorn import Acorn
from acorn import record_copy as copy
from acorn.func_utils import recover_nsec_from_seed


class FakePool:
    def __init__(self, servers, **kwargs):
        self.servers = tuple(dict.fromkeys(s.rstrip('/') for s in servers))


def test_pool_private_network_opt_in():
    with pytest.raises(ValueError):
        copy.BlossomPool(["https://127.0.0.1"])
    assert copy.BlossomPool(["https://127.0.0.1"], allow_private=True).servers
    with pytest.raises(ValueError):
        copy.BlossomPool(["http://127.0.0.1"], allow_private=True)


@pytest.mark.asyncio
async def test_real_pool_transport_roundtrip(wallets, monkeypatch):
    from contextlib import asynccontextmanager
    import base64
    source, target, stored, add = wallets
    original = b"private original content"
    digest = hashlib.sha256(original).hexdigest()
    blobs = {digest: original}
    source.resolve_blob_servers = AsyncMock(return_value=["https://old.example"])

    class Response:
        def __init__(self, raw, status=200):
            self.status, self.raw = status, raw
            self.content_length = len(raw)
            self.headers = {}
            self.content = self
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def iter_chunked(self, size): yield self.raw

    class Session:
        def get(self, url, **kwargs):
            sha = url.rsplit('/', 1)[-1]
            return Response(blobs.get(sha, b''), 200 if sha in blobs else 404)
        def put(self, url, *, data, headers, **kwargs):
            auth = headers['Authorization'].split()[1]
            event = Event.load(json.loads(base64.urlsafe_b64decode(auth + '=' * (-len(auth) % 4))))
            assert event.is_valid() and event.pub_key == target.pubkey_hex
            assert data != original
            blobs[hashlib.sha256(data).hexdigest()] = data
            return Response(b'')

    @asynccontextmanager
    async def session(self): yield Session()
    monkeypatch.setattr(copy.BlossomPool, '_session', session)
    result = await copy.copy_attachment(source, target, record(blobsha256=digest), "https://new.example")
    assert copy.plaintext(result, blobs[result['blobsha256']]) == original


@pytest.fixture
def wallets(monkeypatch):
    source = Acorn(nsec=Keys().private_key_bech32(), home_relay="wss://source.example")
    target = Acorn(nsec=Keys().private_key_bech32(), home_relay="wss://target.example")
    stored = {source.pubkey_hex: [], target.pubkey_hex: []}

    def add(wallet, label, data):
        event = Event(kind=37375, pub_key=wallet.pubkey_hex,
                      tags=[["d", wallet._record_label_hash(label)]],
                      content=NIP44Encrypt(wallet.k).encrypt(json.dumps(data), to_pub_k=wallet.pubkey_hex))
        event.sign(wallet.privkey_hex)
        stored[wallet.pubkey_hex].append(event)
        return event

    class Pool:
        def __init__(self, relays): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def query(self, filters): return stored[filters[0]["authors"][0]]
    monkeypatch.setattr(copy, "ClientPool", Pool)
    async def publish(label, content, **kwargs):
        assert kwargs["verify"] and kwargs["record_kind"] == 37375
        add(target, label, json.loads(content))
    target.set_wallet_info = AsyncMock(side_effect=publish)
    source.load_data = AsyncMock(side_effect=AssertionError("No wallet loading"))
    target.load_data = AsyncMock(side_effect=AssertionError("No wallet loading"))
    add(target, "wallet_config", {"kind_cashu": 7375, "user_records": []})
    return source, target, stored, add


def record(label="note", **kwargs):
    return {"tag": [label], "type": "generic", "payload": {"signed": "preserve-exactly"},
            "custom_provenance": {"issuer": "original"}, **kwargs}


def wallet_tags(target):
    return [["balance", "0", "sat"], ["privkey", Keys().private_key_hex()],
            ["mint", "https://mint.example.com"], ["name", "wallet"],
            ["owner", target.pubkey_bech32], ["local_currency", "CAD"]]


@pytest.mark.asyncio
@pytest.mark.parametrize("keep_old_config", [False, True])
async def test_web_created_destination_can_receive_records(wallets, keep_old_config):
    source, target, stored, add = wallets
    if not keep_old_config:
        stored[target.pubkey_hex] = []
    add(target, "wallet", wallet_tags(target))
    add(source, "note", record())
    rows = await copy.prepare(source, target)
    assert rows[0]["status"] == "copy"
    target.set_wallet_info.assert_not_awaited()
    results = await copy.execute(source, target, rows)
    assert results[0]["status"] == "copied and verified"
    target.load_data.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [[], {}, [["name", "wallet"]],
    [["balance", "secret-content", "sat"], ["name", "wallet"], ["mint", "https://mint.example.com"]],
    [["balance", "0", "sat"], ["name", "wallet"], ["name", "duplicate"], ["mint", "https://mint.example.com"]]])
async def test_invalid_wallet_does_not_fall_back_to_config(wallets, bad):
    source, target, stored, add = wallets
    add(target, "wallet", bad)
    with pytest.raises(ValueError, match="invalid or unreadable") as error:
        await copy.prepare(source, target)
    assert "secret-content" not in str(error.value)
    target.set_wallet_info.assert_not_awaited()


@pytest.mark.asyncio
async def test_destination_wallet_requires_decryptable_signed_event(wallets):
    source, target, stored, add = wallets
    stored[target.pubkey_hex] = []
    event = add(target, "wallet", wallet_tags(target))
    event.content = NIP44Encrypt(source.k).encrypt("secret-content", to_pub_k=source.pubkey_hex)
    event.sign(target.privkey_hex)
    with pytest.raises(ValueError, match="invalid or unreadable"):
        await copy.prepare(source, target)
    event.content = "unsigned tampering"
    with pytest.raises(ValueError, match="invalid record event"):
        await copy.prepare(source, target)
    target.set_wallet_info.assert_not_awaited()


def test_secret_detection():
    key = Keys()
    assert copy.destination_nsec(key.private_key_bech32()) == key.private_key_bech32()
    assert copy.destination_nsec(key.private_key_hex()) == key.private_key_bech32()
    phrase = "abandon " * 11 + "about"
    for legacy in (False, True):
        assert copy.destination_nsec(phrase, legacy=legacy) == recover_nsec_from_seed(phrase, legacy=legacy)
    for bad in ("invalid", key.public_key_bech32(), "not a valid phrase"):
        with pytest.raises(Exception): copy.destination_nsec(bad)


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback", [False, True])
async def test_explicit_source_order_and_digest_fallback(wallets, monkeypatch, fallback):
    source, target, stored, add = wallets
    raw = b"verified source file"
    data = record("file", blobsha256=hashlib.sha256(raw).hexdigest())
    source.resolve_blob_servers = AsyncMock(return_value=["https://first.example", "https://stored.example"])
    attempts = []
    class Pool(FakePool):
        async def retrieve(self, digest):
            attempts.extend(self.servers)
            if "https://stored.example" in self.servers or not fallback:
                return SimpleNamespace(content=raw)
            raise copy.BlossomError("No verified result")
    monkeypatch.setattr(copy, "BlossomPool", Pool)
    actual = await copy.read_attachment(source, data, source_blossoms=("https://first.example/", "https://first.example", "https://second.example"))
    assert actual == raw
    assert attempts == ["https://first.example", "https://second.example"] + (["https://stored.example"] if fallback else [])
    assert source.resolve_blob_servers.await_count == int(fallback)


@pytest.mark.asyncio
async def test_source_errors_include_only_hostname(wallets, monkeypatch):
    source, target, stored, add = wallets
    source.resolve_blob_servers = AsyncMock(return_value=[])
    class Pool(FakePool):
        async def retrieve(self, digest):
            raise copy.BlossomError("sensitive-server-error", outcomes=[SimpleNamespace(
                server="https://source.example/private-path", message="sensitive-server-error")])
    monkeypatch.setattr(copy, "BlossomPool", Pool)
    with pytest.raises(copy.CopyFailure) as caught:
        await copy.read_attachment(source, record(blobsha256="a" * 64), source_blossoms=("https://source.example",))
    assert "source.example" in caught.value.detail
    assert "private-path" not in caught.value.detail and "sensitive-server-error" not in caught.value.detail


@pytest.mark.asyncio
async def test_copy_excludes_state_preserves_records_and_is_repeatable(wallets):
    source, target, stored, add = wallets
    for label in ("wallet_config", "lock", "pending_swaps", "quote", "continuity_receipts", "clear_receipts", "service_bindings"):
        add(source, label, {"secret": "operational"})
    add(source, "note", record())
    old_events = list(stored[source.pubkey_hex])
    rows = await copy.prepare(source, target)
    assert len(rows) == 1 and rows[0]["status"] == "copy"
    target.set_wallet_info.assert_not_awaited()
    result = await copy.execute(source, target, rows)
    assert result[0]["status"] == "copied and verified"
    copied = (await copy.inventory(target))[target._record_label_hash("note")]
    assert copy.decrypt(target, copied) == record()
    assert copied.pub_key == target.pubkey_hex and copied.is_valid()
    assert stored[source.pubkey_hex] == old_events
    assert (await copy.prepare(source, target))[0]["status"] == "already present"
    source.load_data.assert_not_awaited()
    target.load_data.assert_not_awaited()


@pytest.mark.asyncio
async def test_target_missing_unreadable_or_same_identity_stops(wallets):
    source, target, stored, add = wallets
    with pytest.raises(ValueError, match="same identity"):
        await copy.prepare(source, source)
    stored[target.pubkey_hex] = []
    with pytest.raises(ValueError, match="No destination"):
        await copy.prepare(source, target)
    add(target, "wallet_config", "wrong schema")
    with pytest.raises(ValueError, match="invalid or unreadable"):
        await copy.prepare(source, target)
    target.set_wallet_info.assert_not_awaited()


@pytest.mark.asyncio
async def test_conflicts_attachments_and_unknown_labels_are_reported(wallets):
    source, target, stored, add = wallets
    add(source, "note", record())
    add(target, "note", record(payload="different"))
    add(source, "file", record("file", blobsha256="a" * 64))
    add(source, "unlabeled", {"value": "legacy"})
    rows = await copy.prepare(source, target)
    statuses = {r.get("label", "unknown"): r["status"] for r in rows}
    assert "conflict" in statuses["note"]
    assert "destination-blossom" in statuses["file"]
    assert "unlabeled" in statuses["unknown"]
    await copy.execute(source, target, rows)
    target.set_wallet_info.assert_not_awaited()


@pytest.mark.asyncio
async def test_changed_destination_is_not_overwritten(wallets):
    source, target, stored, add = wallets
    add(source, "note", record())
    rows = await copy.prepare(source, target)
    add(target, "note", record(payload="new"))
    result = await copy.execute(source, target, rows)
    assert "changed" in result[0]["status"]
    target.set_wallet_info.assert_not_awaited()


@pytest.mark.asyncio
async def test_bad_signature_and_saturation_stop(wallets):
    source, target, stored, add = wallets
    with pytest.raises(ValueError, match="limit"):
        await copy.inventory(target, limit=1)
    stored[target.pubkey_hex][0].content = "tampered"
    with pytest.raises(ValueError, match="invalid"):
        await copy.inventory(target)


@pytest.mark.asyncio
async def test_failed_readback_is_not_reported_as_success(wallets):
    source, target, stored, add = wallets
    add(source, "note", record())
    rows = await copy.prepare(source, target)
    target.set_wallet_info = AsyncMock()
    results = await copy.execute(source, target, rows)
    assert "failed or unverified" in results[0]["status"]
    assert results[0]["error_stage"] == "destination record readback"


@pytest.mark.asyncio
@pytest.mark.parametrize("encrypted_source", [False, True])
async def test_attachment_copy_verifies_digest_and_preserves_payload(wallets, monkeypatch, encrypted_source):
    source, target, stored, add = wallets
    data = b"attachment bytes"
    digest = hashlib.sha256(data).hexdigest()
    original = record("file", blobsha256=digest, blobref="https://old.example/" + digest)
    raw = data
    if encrypted_source:
        encrypted = copy.encrypt_bytes(data, b"s" * 32)
        raw = encrypted.cipherbytes
        digest = hashlib.sha256(raw).hexdigest()
        original.update(blobsha256=digest, origsha256=hashlib.sha256(data).hexdigest(),
                        encryptparms={"alg": encrypted.alg, "key": (b"s" * 32).hex(), "iv": encrypted.iv.hex()})
    blobs = {digest: raw}
    add(source, "file", original)
    source.resolve_blob_servers = AsyncMock(return_value=["https://old.example"])
    class Pool(FakePool):
        async def retrieve(self, digest): return SimpleNamespace(content=blobs[digest])
        async def store(self, content, *, signer, require):
            assert signer is target.k and require == "all"
            assert content != data and content != raw
            sha = hashlib.sha256(content).hexdigest()
            blobs[sha] = content
            return SimpleNamespace(ok=True, digest=sha)
    monkeypatch.setattr(copy, "BlossomPool", Pool)
    blossom = "https://new.example"
    results = await copy.execute(source, target, await copy.prepare(source, target, blossom=blossom), blossom=blossom)
    assert results[0]["status"] == "copied and verified"
    event = (await copy.inventory(target))[target._record_label_hash("file")]
    migrated = copy.decrypt(target, event)
    assert migrated["payload"] == original["payload"]
    assert migrated["custom_provenance"] == original["custom_provenance"]
    assert migrated["blobsha256"] != digest
    assert migrated["encryptparms"]["key"] != (b"s" * 32).hex()
    if encrypted_source:
        assert migrated["encryptparms"]["iv"] != original["encryptparms"]["iv"]
    assert copy.plaintext(migrated, blobs[migrated["blobsha256"]]) == data
    assert (await copy.prepare(source, target, blossom=blossom))[0]["status"] == "already present"
    assert blobs[digest] == raw
    old_copy = {**original, "blobref": blossom + "/" + digest, "blob_service_npubs": []}
    assert not await copy.matches_copy(source, original, old_copy, blossom)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing_digest", "plaintext_digest", "authentication", "upload_digest", "unconfirmed", "readback"])
async def test_reencryption_failures_do_not_publish_records(wallets, monkeypatch, failure):
    source, target, stored, add = wallets
    data = b"private attachment"
    encrypted = copy.encrypt_bytes(data, b"s" * 32)
    raw = encrypted.cipherbytes
    digest = hashlib.sha256(raw).hexdigest()
    original = record("file", blobsha256=digest, origsha256=hashlib.sha256(data).hexdigest(),
                      encryptparms={"alg": encrypted.alg, "key": (b"s" * 32).hex(), "iv": encrypted.iv.hex()})
    if failure == "plaintext_digest": original["origsha256"] = "0" * 64
    if failure == "missing_digest": original.pop("origsha256")
    if failure == "authentication": original["encryptparms"]["key"] = (b"x" * 32).hex()
    add(source, "file", original)
    source.resolve_blob_servers = AsyncMock(return_value=["https://old.example"])
    class Pool(FakePool):
        async def retrieve(self, digest):
            return SimpleNamespace(content=raw if self.servers == ("https://old.example",) else b"corrupt")
        async def store(self, content, **kwargs):
            assert failure in {"upload_digest", "unconfirmed", "readback"}
            return SimpleNamespace(ok=failure != "unconfirmed", outcomes=[],
                digest="0" * 64 if failure == "upload_digest" else hashlib.sha256(content).hexdigest())
    monkeypatch.setattr(copy, "BlossomPool", Pool)
    blossom = "https://new.example"
    result = await copy.execute(source, target, await copy.prepare(source, target, blossom=blossom), blossom=blossom)
    assert "failed" in result[0]["status"]
    expected_stage = {"missing_digest": "source attachment decryption",
                      "plaintext_digest": "source attachment decryption",
                      "authentication": "source attachment decryption",
                      "upload_digest": "destination attachment upload",
                      "unconfirmed": "destination attachment upload",
                      "readback": "destination attachment verification"}[failure]
    assert result[0]["error_stage"] == expected_stage
    if failure == "missing_digest":
        assert "missing the plaintext digest (origsha256)" in result[0]["error_detail"]
    target.set_wallet_info.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [401, 403, 404, 413, 429])
async def test_source_http_failure_reports_code_not_private_exception(wallets, monkeypatch, code):
    source, target, stored, add = wallets
    add(source, "file", record("file", blobsha256="a" * 64))
    source.resolve_blob_servers = AsyncMock(return_value=["https://source.example"])
    class Pool(FakePool):
        async def retrieve(self, digest):
            raise copy.BlossomError("nsec-secret file-key-secret decrypted-content", outcomes=[
                SimpleNamespace(server=self.servers[0], message=f"Retrieval returned HTTP {code}")])
    monkeypatch.setattr(copy, "BlossomPool", Pool)
    rows = await copy.prepare(source, target, blossom="https://target.example")
    callbacks = []
    result = await copy.execute(source, target, rows, blossom="https://target.example", on_result=callbacks.append)
    assert result[0]["error_stage"] == "source attachment download"
    assert f"HTTP {code}" in result[0]["error_detail"]
    assert len(callbacks) == 1 and "data" not in callbacks[0]
    assert "secret" not in json.dumps(callbacks) and "decrypted-content" not in json.dumps(callbacks)
    target.set_wallet_info.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_publication_error_has_safe_stage_and_live_result(wallets):
    source, target, stored, add = wallets
    add(source, "note", record())
    target.set_wallet_info = AsyncMock(side_effect=RuntimeError("sensitive-key-content"))
    callbacks = []
    result = await copy.execute(source, target, await copy.prepare(source, target), on_result=callbacks.append)
    assert result[0]["error_stage"] == "destination record publication"
    assert "sensitive" not in json.dumps(callbacks)
    assert callbacks[0]["status"].startswith("failed")


@pytest.mark.asyncio
async def test_unreachable_relay_is_not_empty_inventory(monkeypatch, wallets):
    source, target, stored, add = wallets
    class Pool:
        def __init__(self, *args): pass
        async def __aenter__(self): raise ConnectionError("offline")
        async def __aexit__(self, *args): pass
    monkeypatch.setattr(copy, "ClientPool", Pool)
    with pytest.raises(ConnectionError): await copy.prepare(source, target)
    target.set_wallet_info.assert_not_awaited()


@pytest.mark.asyncio
async def test_corrupt_attachment_never_publishes_record(wallets, monkeypatch):
    source, target, stored, add = wallets
    add(source, "file", record("file", blobsha256="a" * 64))
    source.resolve_blob_servers = AsyncMock(return_value=["https://old.example"])
    class Pool(FakePool):
        async def retrieve(self, digest): return SimpleNamespace(content=b"corrupt")
        async def store(self, *args, **kwargs): raise AssertionError("Must not upload corrupt bytes")
    monkeypatch.setattr(copy, "BlossomPool", Pool)
    blossom = "https://new.example"
    rows = await copy.prepare(source, target, blossom=blossom)
    result = await copy.execute(source, target, rows, blossom=blossom)
    assert "failed" in result[0]["status"]
    target.set_wallet_info.assert_not_awaited()


@pytest.mark.parametrize("url,schemes", [
    ("https://user:password@example.com", ("https",)),
    ("file:///tmp/relay", ("wss", "ws")),
    ("https://example.com/?secret=1", ("https",)),
])
def test_destination_endpoints_reject_credentials_and_invalid_schemes(url, schemes):
    with pytest.raises(ValueError): copy.endpoint(url, schemes)
