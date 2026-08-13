from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest
from monstr.encrypt import Keys

from acorn import acorn as acorn_module
from acorn.acorn import Acorn


def history_wallet() -> Acorn:
    wallet = object.__new__(Acorn)
    wallet.k = Keys(priv_k="11" * 32)
    wallet.pubkey_hex = wallet.k.public_key_hex()
    wallet.privkey_hex = wallet.k.private_key_hex()
    wallet.home_relay = "ws://home:7777"
    wallet.balance = 25
    wallet.logger = logging.getLogger("transaction-history-test")
    return wallet


class PlaintextNip44:
    def __init__(self, keys):
        pass

    def encrypt(self, content, to_pub_k):
        return content


@pytest.mark.asyncio
async def test_add_tx_history_verifies_exact_event_readback(monkeypatch):
    wallet = history_wallet()
    stored = []
    publish_count = 0

    class DelayedMemoryPool:
        def __init__(self, relays):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        def publish(self, event):
            nonlocal publish_count
            publish_count += 1
            # Simulate a relay whose first accepted write is not yet visible.
            if publish_count >= 2 and all(str(each.id) != str(event.id) for each in stored):
                stored.append(event)

        async def query(self, filters):
            event_ids = set(filters[0].get("ids", []))
            return [
                event for event in stored
                if not event_ids or str(event.id) in event_ids
            ]

    monkeypatch.setattr(acorn_module, "NIP44Encrypt", PlaintextNip44)
    monkeypatch.setattr(acorn_module, "ClientPool", DelayedMemoryPool)
    monkeypatch.setattr(acorn_module.asyncio, "sleep", AsyncMock())

    result = await wallet.add_tx_history(
        tx_type="C",
        amount=25,
        comment="acorn deposit",
        verify_timeout=1,
    )

    assert result["verified"] is True
    assert result["event_id"] == str(stored[0].id)
    assert publish_count == 2


@pytest.mark.asyncio
async def test_add_tx_history_fails_clearly_when_readback_never_arrives(monkeypatch):
    wallet = history_wallet()

    class MissingMemoryPool:
        def __init__(self, relays):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        def publish(self, event):
            pass

        async def query(self, filters):
            return []

    clock = iter([0.0, 0.0, 2.0])
    monkeypatch.setattr(acorn_module, "NIP44Encrypt", PlaintextNip44)
    monkeypatch.setattr(acorn_module, "ClientPool", MissingMemoryPool)
    monkeypatch.setattr(acorn_module, "monotonic", lambda: next(clock))
    monkeypatch.setattr(acorn_module.asyncio, "sleep", AsyncMock())

    with pytest.raises(
        RuntimeError,
        match="Transaction-history publish could not be verified",
    ):
        await wallet.add_tx_history(
            tx_type="C",
            amount=25,
            comment="acorn deposit",
            verify_timeout=1,
        )
