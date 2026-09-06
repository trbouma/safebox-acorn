from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest
from monstr.encrypt import Keys
from monstr.event.event import Event

from acorn import acorn as acorn_module
from acorn.acorn import Acorn, NIP17_INBOX_RELAYS_KIND


class MemoryPool:
    events: list[Event] = []
    connections: list[list[str]] = []

    def __init__(self, relays):
        self.relays = list(relays)
        type(self).connections.append(self.relays)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def publish(self, event):
        self.events.append(event)

    async def query(self, filters):
        query = filters[0]
        return [
            event
            for event in self.events
            if event.kind in set(query.get("kinds") or [])
            and str(event.pub_key) in set(query.get("authors") or [])
        ]


def wallet() -> Acorn:
    result = object.__new__(Acorn)
    result.k = Keys(priv_k="11" * 32)
    result.pubkey_hex = result.k.public_key_hex()
    result.privkey_hex = result.k.private_key_hex()
    result.home_relay = "ws://grove:8080"
    result.relays = []
    result.public_relays = ["wss://discovery.example"]
    result.logger = logging.getLogger("inbox-relay-routing-test")
    return result


@pytest.fixture(autouse=True)
def memory_pool(monkeypatch):
    MemoryPool.events = []
    MemoryPool.connections = []
    monkeypatch.setattr(acorn_module, "ClientPool", MemoryPool)
    monkeypatch.setattr(acorn_module.asyncio, "sleep", AsyncMock())


@pytest.mark.asyncio
async def test_publish_and_resolve_signed_nip17_inbox_relays() -> None:
    acorn = wallet()

    published = await acorn.publish_inbox_relays(
        ["federation.example", "wss://backup.example"],
    )
    resolved = await acorn.resolve_inbox_relays(acorn.pubkey_hex)

    assert published["kind"] == NIP17_INBOX_RELAYS_KIND
    assert published["relays"] == [
        "wss://federation.example",
        "wss://backup.example",
    ]
    assert published["published_to"] == [
        "ws://grove:8080",
        "wss://discovery.example",
        "wss://federation.example",
        "wss://backup.example",
    ]
    assert resolved["found"] is True
    assert resolved["event_id"] == published["event_id"]
    assert resolved["relays"] == published["relays"]
    assert MemoryPool.events[0].is_valid()


@pytest.mark.asyncio
async def test_resolve_inbox_relays_ignores_invalid_signature() -> None:
    acorn = wallet()
    forged = Event(
        kind=NIP17_INBOX_RELAYS_KIND,
        content="",
        pub_key=acorn.pubkey_hex,
        tags=[["relay", "wss://forged.example"]],
    )
    forged.sign(Keys(priv_k="22" * 32).private_key_hex())
    forged.pub_key = acorn.pubkey_hex
    MemoryPool.events.append(forged)

    resolved = await acorn.resolve_inbox_relays(acorn.pubkey_hex)

    assert resolved["found"] is False
    assert resolved["reason"] == "kind10050_not_found"


@pytest.mark.asyncio
async def test_transfer_destination_prefers_nip17_over_nip05(monkeypatch) -> None:
    acorn = wallet()
    recipient = Keys(priv_k="22" * 32).public_key_hex()
    monkeypatch.setattr(
        acorn,
        "_resolve_pubkey_and_relays",
        lambda _identifier: (recipient, ["wss://nip05.example"]),
    )
    acorn.resolve_inbox_relays = AsyncMock(
        return_value={
            "recipient_pubkey": recipient,
            "relays": ["wss://recipient-inbox.example"],
            "event_id": "a" * 64,
            "found": True,
        }
    )

    result = await acorn._resolve_transfer_destination("person@example.com")

    assert result["recipient_pubkey"] == recipient
    assert result["relays"] == ["wss://recipient-inbox.example"]
    assert result["relay_source"] == "nip17-inbox"
    acorn.resolve_inbox_relays.assert_awaited_once_with(
        recipient,
        lookup_relays=[
            "wss://nip05.example",
            "ws://grove:8080",
            "wss://discovery.example",
        ],
    )


@pytest.mark.asyncio
async def test_transfer_destination_uses_caller_hints_for_discovery_and_fallback(
    monkeypatch,
) -> None:
    acorn = wallet()
    recipient = Keys(priv_k="22" * 32).public_key_hex()
    monkeypatch.setattr(
        acorn,
        "_resolve_pubkey_and_relays",
        lambda _identifier: (recipient, []),
    )
    acorn.resolve_inbox_relays = AsyncMock(
        return_value={
            "recipient_pubkey": recipient,
            "relays": [],
            "found": False,
            "reason": "kind10050_not_found",
        }
    )

    result = await acorn._resolve_transfer_destination(
        recipient,
        relay_hints=["wss://nip05-directory.example"],
    )

    assert result["relays"] == ["wss://nip05-directory.example"]
    assert result["relay_source"] == "recipient-hint"
    acorn.resolve_inbox_relays.assert_awaited_once_with(
        recipient,
        lookup_relays=[
            "wss://nip05-directory.example",
            "ws://grove:8080",
            "wss://discovery.example",
        ],
    )


@pytest.mark.asyncio
async def test_receive_pool_combines_internal_and_external_inboxes() -> None:
    acorn = wallet()
    acorn.resolve_inbox_relays = AsyncMock(
        return_value={
            "recipient_pubkey": acorn.pubkey_hex,
            "relays": ["wss://federation.example"],
            "event_id": "b" * 64,
            "found": True,
        }
    )

    relays, discovery = await acorn._resolve_receive_relay_pool(acorn.pubkey_hex)

    assert relays == ["ws://grove:8080", "wss://federation.example"]
    assert discovery["source"] == "nip17-inbox"
