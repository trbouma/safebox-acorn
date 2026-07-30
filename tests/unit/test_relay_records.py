from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest

from monstr.encrypt import Keys
from monstr.event.event import Event

from acorn.acorn import Acorn


def wallet_with_key() -> Acorn:
    wallet = object.__new__(Acorn)
    wallet.k = Keys(priv_k="11" * 32)
    wallet.pubkey_hex = wallet.k.public_key_hex()
    wallet.privkey_hex = wallet.k.private_key_hex()
    wallet.privkey_bech32 = wallet.k.private_key_bech32()
    wallet.home_relay = "ws://home:7777"
    wallet.relays = [wallet.home_relay]
    wallet.blossom_servers = ["https://blossom.example"]
    wallet.logger = logging.getLogger("relay-record-test")
    return wallet


def record_event(
    *,
    event_id: str,
    created_at: int,
    kind: int = 37375,
    d_tag: str = "d",
    content: str = "encrypted",
):
    return Event(
        id=event_id,
        sig="00" * 64,
        kind=kind,
        content=content,
        tags=[["d", d_tag]],
        pub_key="22" * 32,
        created_at=created_at,
    )


def test_canonical_record_selection_uses_newest_then_lowest_id():
    wallet = wallet_with_key()
    older = record_event(event_id="f" * 64, created_at=10)
    same_time_high_id = record_event(event_id="e" * 64, created_at=20)
    same_time_low_id = record_event(event_id="a" * 64, created_at=20)

    selected = wallet._canonical_record_events(
        [same_time_high_id, older, same_time_low_id, same_time_low_id]
    )

    assert selected == [same_time_low_id]


@pytest.mark.asyncio
async def test_get_record_safebox_scopes_lookup_by_kind_and_relays(monkeypatch):
    from acorn import acorn as acorn_module

    wallet = wallet_with_key()
    event = record_event(
        event_id="a" * 64,
        created_at=20,
        kind=34002,
        content=(
            '{"tag":["credential"],"type":"private_record",'
            '"payload":"signed payload"}'
        ),
    )
    captured = {}

    class PlaintextNip44:
        def __init__(self, keys):
            pass

        def decrypt(self, content, pubkey):
            return content

    async def get_event(filters, label_hash, relays=None):
        captured["filters"] = filters
        captured["relays"] = relays
        return event

    monkeypatch.setattr(acorn_module, "NIP44Encrypt", PlaintextNip44)
    wallet._async_get_wallet_info = get_event

    record = await wallet.get_record_safebox(
        "credential",
        record_kind=34002,
        relays=["ws://replica:7777"],
    )

    assert captured["filters"][0]["kinds"] == [34002]
    assert captured["relays"] == ["ws://replica:7777"]
    assert record.payload == "signed payload"


@pytest.mark.asyncio
async def test_put_record_rejects_internal_record_names():
    wallet = wallet_with_key()

    with pytest.raises(ValueError, match="reserved for Acorn internal state"):
        await wallet.put_record("pending_melts", "corrupt journal")

    with pytest.raises(ValueError, match="reserved for Acorn internal state"):
        await wallet.put_record("__acorn_future_state", "corrupt state")


@pytest.mark.asyncio
async def test_standard_record_listing_applies_since_and_preserves_ws_relay(monkeypatch):
    from acorn import acorn as acorn_module

    wallet = wallet_with_key()
    captured = {}

    class EmptyPool:
        def __init__(self, relays):
            captured["relays"] = relays

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def query(self, filters):
            captured["filters"] = filters
            return []

    monkeypatch.setattr(acorn_module, "ClientPool", EmptyPool)

    records = await wallet.get_user_records(
        record_kind=37375,
        since=1234,
        relays=["ws://beelink:8735"],
    )

    assert records == []
    assert captured["relays"] == ["ws://beelink:8735"]
    assert captured["filters"][0]["since"] == 1234


@pytest.mark.asyncio
async def test_record_listing_reconciles_versions_and_excludes_internal_state(monkeypatch):
    from acorn import acorn as acorn_module

    wallet = wallet_with_key()
    wallet.name = "Acorn"
    user_hash = wallet._record_label_hash("Field Notes")
    internal_hash = wallet._record_label_hash("pending_melts")
    events = [
        record_event(
            event_id="c" * 64,
            created_at=10,
            d_tag=user_hash,
            content='{"tag":["Field Notes"],"type":"generic","payload":"old"}',
        ),
        record_event(
            event_id="b" * 64,
            created_at=20,
            d_tag=user_hash,
            content='{"tag":["Field Notes"],"type":"generic","payload":"new"}',
        ),
        record_event(
            event_id="a" * 64,
            created_at=30,
            d_tag=internal_hash,
            content='[{"quote":"private operational state"}]',
        ),
    ]

    class RecordPool:
        def __init__(self, relays):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def query(self, filters):
            return events

    class PlaintextNip44:
        def __init__(self, keys):
            pass

        def decrypt(self, content, pubkey):
            return content

    monkeypatch.setattr(acorn_module, "ClientPool", RecordPool)
    monkeypatch.setattr(acorn_module, "NIP44Encrypt", PlaintextNip44)

    records = await wallet.get_user_records(record_kind=37375)

    assert len(records) == 1
    assert records[0]["tag"] == ["Field Notes"]
    assert records[0]["payload"] == "new"


@pytest.mark.asyncio
async def test_verified_record_write_reads_back_canonical_event(monkeypatch):
    from acorn import acorn as acorn_module

    wallet = wallet_with_key()
    stored = {"ws://home:7777": []}

    class MemoryPool:
        def __init__(self, relays):
            self.relays = relays if isinstance(relays, list) else [relays]

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        def publish(self, event):
            for relay in self.relays:
                stored.setdefault(relay, []).append(event)

        async def query(self, filters):
            events = []
            for relay in self.relays:
                events.extend(stored.get(relay, []))
            return events

    monkeypatch.setattr(acorn_module, "ClientPool", MemoryPool)
    monkeypatch.setattr(acorn_module.asyncio, "sleep", AsyncMock())

    result = await wallet.set_wallet_info(
        "Field Notes",
        "encrypted content",
        verify=True,
    )

    assert result["status"] == "OK"
    assert result["verified"] is True
    assert result["verification"]["ws://home:7777"]["canonical"] is True
    assert result["event_id"] == str(stored["ws://home:7777"][0].id)


@pytest.mark.asyncio
async def test_get_ecash_dm_awaits_cursor_write():
    wallet = wallet_with_key()
    wallet.wallet_reserved_records = {"last_dm": "0"}
    wallet._async_query_ecash_dm = AsyncMock(return_value=(42, []))
    wallet.set_wallet_info = AsyncMock(return_value={"status": "OK"})

    result = await wallet.get_ecash_dm()

    assert result == 42
    wallet.set_wallet_info.assert_awaited_once_with("last_dm", "42")


@pytest.mark.asyncio
async def test_delete_uses_event_address_and_kind_tags(monkeypatch):
    from acorn import acorn as acorn_module

    wallet = wallet_with_key()
    target = record_event(event_id="a" * 64, created_at=20)
    published = []

    class DeletePool:
        def __init__(self, relays):
            self.relays = relays

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        def publish(self, event):
            published.append(event)

        async def query(self, filters):
            return []

    wallet._async_get_wallet_info = AsyncMock(return_value=target)
    monkeypatch.setattr(acorn_module, "ClientPool", DeletePool)
    monkeypatch.setattr(acorn_module.asyncio, "sleep", AsyncMock())

    result = await wallet.delete_record(
        "Field Notes",
        relays=["ws://home:7777", "ws://backup:7777"],
    )

    assert result["status"] == "DELETE_REQUESTED"
    assert result["hidden_on"] == ["ws://home:7777", "ws://backup:7777"]
    deletion = published[0]
    assert deletion.kind == 5
    assert ["e", "a" * 64] in deletion.tags
    assert ["k", "37375"] in deletion.tags
    assert any(tag[0] == "a" and tag[1].startswith("37375:") for tag in deletion.tags)


@pytest.mark.asyncio
async def test_replication_requires_target_readback_and_reports_limit(monkeypatch):
    from acorn import acorn as acorn_module

    wallet = wallet_with_key()
    source_event = record_event(
        event_id="a" * 64,
        created_at=20,
        content="ciphertext",
    )
    stored = {
        "ws://source:7777": [source_event],
        "ws://target:7777": [],
    }

    class ReplicationPool:
        def __init__(self, relays):
            self.relays = relays if isinstance(relays, list) else [relays]

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        def publish(self, event):
            for relay in self.relays:
                stored.setdefault(relay, []).append(event)

        async def query(self, filters):
            events = []
            for relay in self.relays:
                events.extend(stored.get(relay, []))
            return events

    monkeypatch.setattr(acorn_module, "ClientPool", ReplicationPool)
    monkeypatch.setattr(acorn_module.asyncio, "sleep", AsyncMock())

    verified = await wallet.replicate_to_relay(
        target_relay="ws://target:7777",
        source_relay="ws://source:7777",
        kinds=[37375],
        limit=10,
    )

    assert verified["status"] == "OK"
    assert verified["verified"] is True
    assert verified["missing_event_ids"] == []

    limited = await wallet.replicate_to_relay(
        target_relay="ws://target:7777",
        source_relay="ws://source:7777",
        kinds=[37375],
        limit=1,
    )

    assert limited["status"] == "PARTIAL"
    assert limited["source_may_be_truncated"] is True
