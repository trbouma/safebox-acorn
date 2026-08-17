from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock

import pytest
from monstr.encrypt import Keys
from monstr.event.event import Event

from acorn import acorn as acorn_module
from acorn.acorn import Acorn, CLEAR_HISTORY_KIND, CLEAR_PROOF_KIND
from acorn.models import Proof, TokenV3, TokenV3Token


class PlaintextNip44:
    def __init__(self, _keys):
        pass

    def encrypt(self, content, to_pub_k):
        return content

    def decrypt(self, content, _pubkey):
        return content


class MemoryPool:
    events: list[Event] = []

    def __init__(self, _relays):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def publish(self, event):
        if all(str(existing.id) != str(event.id) for existing in self.events):
            self.events.append(event)

    async def query(self, filters):
        query = filters[0]
        kinds = set(query.get("kinds") or [])
        ids = {str(event_id) for event_id in query.get("ids") or []}
        authors = set(query.get("authors") or [])
        return [
            event
            for event in self.events
            if (not kinds or event.kind in kinds)
            and (not ids or str(event.id) in ids)
            and (not authors or str(event.pub_key) in authors)
        ]


def wallet() -> Acorn:
    result = object.__new__(Acorn)
    result.k = Keys(priv_k="11" * 32)
    result.pubkey_hex = result.k.public_key_hex()
    result.privkey_hex = result.k.private_key_hex()
    result.home_relay = "ws://home:7777"
    result.logger = logging.getLogger("clear-wallet-state-test")
    result.proofs = [Proof(amount=999, id="cash-keyset", secret="cash", C="cash-C")]
    result.balance = 999
    return result


def proof(amount: int, keyset: str, suffix: str) -> Proof:
    return Proof(
        amount=amount,
        id=keyset,
        secret=f"clear-secret-{suffix}",
        C=f"02{suffix.zfill(64)}",
    )


@pytest.fixture(autouse=True)
def memory_relay(monkeypatch):
    MemoryPool.events = []
    monkeypatch.setattr(acorn_module, "NIP44Encrypt", PlaintextNip44)
    monkeypatch.setattr(acorn_module, "ClientPool", MemoryPool)
    monkeypatch.setattr(acorn_module.asyncio, "sleep", AsyncMock())


@pytest.mark.asyncio
async def test_clear_balances_partition_mints_units_keysets_and_rollovers():
    acorn = wallet()
    cash_proofs = list(acorn.proofs)

    old = await acorn.add_clear_proof_event(
        mint="https://clear.one/",
        unit="cmu-one",
        proofs=[proof(1, "keyset-a", "1"), proof(2, "keyset-b", "2")],
    )
    await acorn.add_clear_proof_event(
        mint="https://clear.two",
        unit="cmu-one",
        proofs=[proof(8, "keyset-c", "3")],
    )
    await acorn.add_clear_proof_event(
        mint="https://clear.one",
        unit="cmu-two",
        proofs=[proof(4, "keyset-d", "4")],
    )
    replacement = proof(16, "keyset-b", "5")
    await acorn.add_clear_proof_event(
        mint="https://clear.one",
        unit="cmu-one",
        proofs=[replacement],
        deleted_event_ids=[old["event_id"]],
    )
    duplicate = await acorn.add_clear_proof_event(
        mint="https://clear.one",
        unit="cmu-one",
        proofs=[replacement.model_copy(deep=True)],
    )
    deleted = await acorn.add_clear_proof_event(
        mint="https://clear.three",
        unit="cmu-deleted",
        proofs=[proof(32, "keyset-e", "6")],
    )
    await acorn.delete_clear_proof_events([deleted["event_id"]])

    balances = await acorn.get_clear_balances()

    assert [(row["mint"], row["unit"], row["amount"]) for row in balances] == [
        ("https://clear.one", "cmu-one", 16),
        ("https://clear.one", "cmu-two", 4),
        ("https://clear.two", "cmu-one", 8),
    ]
    first = balances[0]
    assert first["proof_count"] == 1
    assert first["keysets"] == [
        {"keyset": "keyset-b", "amount": 16, "proof_count": 1}
    ]
    assert duplicate["event_id"] in first["event_ids"]
    assert len(await acorn.get_clear_proofs("https://clear.one", "cmu-one")) == 1
    assert acorn.balance == 999
    assert acorn.proofs == cash_proofs


@pytest.mark.asyncio
async def test_clear_history_is_append_only_sorted_and_filterable():
    acorn = wallet()
    created_id = "a" * 64
    destroyed_id = "b" * 64
    source_id = "c" * 64

    await acorn.add_clear_transaction_history(
        direction="in",
        operation="accept",
        amount=25,
        mint="https://clear.one",
        unit="cmu-one",
        memo="community supplies",
        created=[created_id],
        source_event=source_id,
        timestamp=100,
    )
    await acorn.add_clear_transaction_history(
        direction="out",
        operation="send",
        amount=5,
        mint="https://clear.one",
        unit="cmu-one",
        destroyed=[destroyed_id],
        timestamp=200,
    )
    await acorn.add_clear_transaction_history(
        direction="in",
        operation="receive",
        amount=7,
        mint="https://clear.two",
        unit="cmu-two",
        timestamp=150,
    )

    history = await acorn.get_clear_transaction_history()
    incoming = await acorn.get_clear_transaction_history(direction="in")
    one_balance = await acorn.get_clear_transaction_history(
        mint="https://clear.one/",
        unit="cmu-one",
    )

    assert [entry["timestamp"] for entry in history] == [200, 150, 100]
    assert [entry["operation"] for entry in incoming] == ["receive", "accept"]
    assert [entry["operation"] for entry in one_balance] == ["send", "accept"]
    assert history[-1]["memo"] == "community supplies"
    assert history[-1]["source_event"] == source_id
    assert len(
        [event for event in MemoryPool.events if event.kind == CLEAR_HISTORY_KIND]
    ) == 3
    assert not [event for event in MemoryPool.events if event.kind == Event.KIND_DELETE]


@pytest.mark.asyncio
async def test_malformed_clear_proof_event_fails_without_changing_cash_state():
    acorn = wallet()
    malformed = Event(
        kind=CLEAR_PROOF_KIND,
        content='{"type":"clear-proof-state","version":1,"mint":"https://clear.one"}',
        pub_key=acorn.pubkey_hex,
    )
    malformed.sign(acorn.privkey_hex)
    MemoryPool.events.append(malformed)

    with pytest.raises(RuntimeError, match="Clear proof-state event"):
        await acorn.get_clear_balances()

    assert acorn.balance == 999
    assert acorn.proofs[0].id == "cash-keyset"


@pytest.mark.asyncio
async def test_accept_pending_clear_receipt_refreshes_into_separate_state():
    acorn = wallet()
    acorn.known_mints = {}
    acorn.acquire_lock = AsyncMock()
    acorn.release_lock = AsyncMock()
    event_id = "d" * 64
    incoming = proof(25, "incoming-keyset", "7")
    refreshed = proof(25, "active-keyset", "8")
    token = TokenV3(
        token=[TokenV3Token(mint="https://clear.example", proofs=[incoming])],
        memo="guest passes",
        unit="cmu-example",
    ).serialize()
    receipts = [{
        "event_id": event_id,
        "sender_pubkey": "sender-pubkey",
        "token": token,
        "mint": "https://clear.example",
        "amount": 25,
        "unit": "cmu-example",
        "comment": "guest passes",
        "timestamp": 1_786_430_400,
        "status": "pending",
    }]
    written: list[list[dict]] = []

    acorn.get_wallet_info = AsyncMock(return_value=json.dumps(receipts))

    async def save_receipts(_label, value, verify):
        assert verify is True
        written.append(json.loads(value))

    acorn.set_wallet_info = AsyncMock(side_effect=save_receipts)
    acorn._load_clear_proof_state = AsyncMock(return_value=[])
    acorn.swap_proofs = AsyncMock(return_value=[refreshed])
    acorn.add_clear_proof_event = AsyncMock(
        return_value={"event_id": "e" * 64, "verified": True}
    )
    acorn.get_clear_transaction_history = AsyncMock(return_value=[])
    acorn.add_clear_transaction_history = AsyncMock(
        return_value={"event_id": "f" * 64, "verified": True}
    )
    cash_proofs = list(acorn.proofs)

    result = await acorn.accept_pending_clear_receipt(event_id)

    assert result["accepted"] is True
    assert result["amount"] == 25
    acorn.swap_proofs.assert_awaited_once_with(
        [incoming],
        mint_base="https://clear.example",
        unit="cmu-example",
    )
    acorn.add_clear_proof_event.assert_awaited_once_with(
        mint="https://clear.example",
        unit="cmu-example",
        proofs=[refreshed],
        source_receipts=[event_id],
        verify=True,
    )
    acorn.add_clear_transaction_history.assert_awaited_once()
    assert written[0][0]["status"] == "accepted"
    assert "token" not in written[0][0]
    assert acorn.balance == 999
    assert acorn.proofs == cash_proofs
