import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from stroma import Keys, Event, NIP44Encrypt

from acorn.acorn import Acorn
from acorn import record_copy as copy
from acorn.func_utils import recover_nsec_from_seed


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
    class BlobClient:
        def __init__(self, **kwargs): pass
        def get_blob(self, **kwargs): return SimpleNamespace(get_bytes=lambda: blobs[kwargs["sha256"]])
        def upload_blob(self, server, **kwargs):
            assert kwargs["data"] != data and kwargs["data"] != raw
            sha = hashlib.sha256(kwargs["data"]).hexdigest()
            blobs[sha] = kwargs["data"]
            return {"sha256": sha}
    monkeypatch.setattr(copy, "BlossomClient", BlobClient)
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
@pytest.mark.parametrize("failure", ["plaintext_digest", "authentication", "upload_digest", "readback"])
async def test_reencryption_failures_do_not_publish_records(wallets, monkeypatch, failure):
    source, target, stored, add = wallets
    data = b"private attachment"
    encrypted = copy.encrypt_bytes(data, b"s" * 32)
    raw = encrypted.cipherbytes
    digest = hashlib.sha256(raw).hexdigest()
    original = record("file", blobsha256=digest, origsha256=hashlib.sha256(data).hexdigest(),
                      encryptparms={"alg": encrypted.alg, "key": (b"s" * 32).hex(), "iv": encrypted.iv.hex()})
    if failure == "plaintext_digest": original["origsha256"] = "0" * 64
    if failure == "authentication": original["encryptparms"]["key"] = (b"x" * 32).hex()
    add(source, "file", original)
    source.resolve_blob_servers = AsyncMock(return_value=["https://old.example"])
    class BlobClient:
        def __init__(self, **kwargs): pass
        def get_blob(self, server, **kwargs):
            return SimpleNamespace(get_bytes=lambda: raw if server == "https://old.example" else b"corrupt")
        def upload_blob(self, server, **kwargs):
            assert failure in {"upload_digest", "readback"}
            return {"sha256": "0" * 64 if failure == "upload_digest" else hashlib.sha256(kwargs["data"]).hexdigest()}
    monkeypatch.setattr(copy, "BlossomClient", BlobClient)
    blossom = "https://new.example"
    result = await copy.execute(source, target, await copy.prepare(source, target, blossom=blossom), blossom=blossom)
    assert "failed" in result[0]["status"]
    target.set_wallet_info.assert_not_awaited()


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
    class BlobClient:
        def __init__(self, **kwargs): pass
        def get_blob(self, **kwargs): return SimpleNamespace(get_bytes=lambda: b"corrupt")
        def upload_blob(self, *args, **kwargs): raise AssertionError("Must not upload corrupt bytes")
    monkeypatch.setattr(copy, "BlossomClient", BlobClient)
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
