from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock

import pytest
from monstr.encrypt import Keys
from monstr.event.event import Event

from acorn.acorn import (
    Acorn,
    CONTINUITY_RECEIPTS_LABEL,
    ECASH_TRANSFER_CURSOR_LABEL,
    ECASH_TRANSFER_KIND,
)
from acorn.models import Proof, TokenV3, TokenV3Token, TokenV4


KEYSET = "00f300c64b950282"
MINT = "https://mint.example"


def proof(amount: int, suffix: str) -> Proof:
    return Proof(
        amount=amount,
        id=KEYSET,
        secret=f"secret-{suffix}",
        C="02" + suffix.zfill(64),
    )


def wallet() -> Acorn:
    result = object.__new__(Acorn)
    result.k = Keys(priv_k="11" * 32)
    result.pubkey_hex = result.k.public_key_hex()
    result.privkey_hex = result.k.private_key_hex()
    result.home_relay = "ws://home:7777"
    result.known_mints = {KEYSET: MINT}
    result.proofs = []
    result.balance = 0
    result.logger = logging.getLogger("continuity-payment-test")
    result.acquire_lock = AsyncMock()
    result.release_lock = AsyncMock()
    result._reconcile_spent_proofs_locked = AsyncMock(
        return_value={"removed": 0, "amount": 0, "balance": 0}
    )
    result._load_proofs = AsyncMock()
    result.write_proofs = AsyncMock()
    result.add_tx_history = AsyncMock()
    result.get_wallet_info = AsyncMock(return_value=None)
    result.set_wallet_info = AsyncMock(return_value={"status": "OK"})
    return result


def serialized_token(proofs: list[Proof]) -> str:
    return TokenV4.from_tokenv3(
        TokenV3(
            token=[TokenV3Token(mint=MINT, proofs=proofs)],
            memo="continuity",
            unit="sat",
        )
    ).serialize()


def incoming_transfer_event(
    acorn: Acorn,
    *,
    event_id: str,
    created_at: int,
    amount: int = 1,
) -> Event:
    return Event(
        id=event_id,
        sig="00" * 64,
        kind=ECASH_TRANSFER_KIND,
        content=json.dumps(
            {
                "type": "cashu-token",
                "token": serialized_token([proof(amount, event_id[:1])]),
                "amount": amount,
                "unit": "sat",
                "payment_mode": "confirmed",
            }
        ),
        tags=[["p", acorn.pubkey_hex]],
        pub_key="22" * 32,
        created_at=created_at,
    )


def install_filtering_transfer_pool(monkeypatch, events: list[Event]) -> list[dict]:
    from acorn import acorn as acorn_module

    observed_filters: list[dict] = []

    class FilteringPool:
        def __init__(self, _relays):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def query(self, filters):
            query_filter = dict(filters[0])
            observed_filters.append(query_filter)
            def event_timestamp(event: Event) -> int:
                value = event.created_at
                return int(value.timestamp()) if hasattr(value, "timestamp") else int(value)

            candidates = [
                event
                for event in events
                if int(query_filter.get("since", 0)) <= event_timestamp(event)
                and event_timestamp(event) <= int(query_filter.get("until", 2**63 - 1))
            ]
            candidates.sort(
                key=lambda event: (event_timestamp(event), str(event.id)),
                reverse=True,
            )
            return candidates[: int(query_filter.get("limit", len(candidates)))]

    class PlaintextNip44:
        def __init__(self, _keys):
            pass

        def decrypt(self, content, _pubkey):
            return content

    class NoGiftWrap:
        def __init__(self, *_args, **_kwargs):
            pass

        async def unwrap(self, _event):
            raise ValueError("not gift wrapped")

    monkeypatch.setattr(acorn_module, "ClientPool", FilteringPool)
    monkeypatch.setattr(acorn_module, "NIP44Encrypt", PlaintextNip44)
    monkeypatch.setattr(acorn_module, "KindOtherGiftWrap", NoGiftWrap)
    return observed_filters


def test_exact_proof_subset_is_exact_and_deterministic() -> None:
    proofs = [proof(1, "1"), proof(2, "2"), proof(4, "4"), proof(8, "8")]

    selected = Acorn._exact_proof_subset(proofs, 11)

    assert selected is not None
    assert [item.amount for item in selected] == [8, 2, 1]


def test_nearest_proof_amounts_reports_attainable_totals() -> None:
    proofs = [proof(2, "2"), proof(4, "4"), proof(8, "8")]

    lower, higher = Acorn._nearest_proof_amounts(proofs, 11)

    assert lower == 10
    assert higher == 12


@pytest.mark.asyncio
async def test_issue_continuity_token_removes_exact_proofs_without_mint_call() -> None:
    acorn = wallet()
    acorn.proofs = [proof(1, "1"), proof(2, "2"), proof(4, "4")]
    acorn.balance = 7

    token = await acorn.issue_continuity_token(5, comment="local supplies")

    parsed = TokenV4.deserialize(token)
    assert parsed.amount == 5
    assert [item.amount for item in acorn.proofs] == [2]
    assert acorn.balance == 2
    acorn.write_proofs.assert_awaited_once()
    acorn.add_tx_history.assert_awaited_once()
    acorn.release_lock.assert_awaited_once()


@pytest.mark.asyncio
async def test_issue_continuity_token_leaves_wallet_unchanged_without_exact_amount() -> None:
    acorn = wallet()
    acorn.proofs = [proof(2, "2"), proof(4, "4")]
    acorn.balance = 6

    with pytest.raises(RuntimeError) as exc_info:
        await acorn.issue_continuity_token(5)

    assert "nearest lower amount: 4 sats" in str(exc_info.value)
    assert "nearest higher amount: 6 sats" in str(exc_info.value)
    assert "No funds were changed" in str(exc_info.value)
    assert [item.amount for item in acorn.proofs] == [2, 4]
    assert acorn.balance == 6
    acorn.write_proofs.assert_not_awaited()
    acorn.add_tx_history.assert_not_awaited()


@pytest.mark.asyncio
async def test_store_continuity_receipt_quarantines_token_idempotently() -> None:
    acorn = wallet()
    stored = []
    async def save(_label, value, **_kwargs):
        stored[:] = json.loads(value)
        return {"status": "OK"}

    acorn.set_wallet_info = AsyncMock(side_effect=save)
    token = serialized_token([proof(1, "1"), proof(4, "4")])
    payload = {"amount": 5, "comment": "market", "nonce": "abc"}

    receipt = await acorn._store_continuity_receipt(
        event_id="event-1",
        sender_pubkey="22" * 32,
        token=token,
        payload=payload,
        timestamp=123,
    )

    assert receipt["status"] == "provisional"
    assert receipt["amount"] == 5
    assert receipt["payment_mode"] == "confirmed"
    assert len(stored) == 1
    acorn.set_wallet_info.assert_awaited_once_with(
        CONTINUITY_RECEIPTS_LABEL,
        json.dumps(stored, separators=(",", ":")),
        verify=True,
    )
    assert acorn.acquire_lock.await_count == 1
    assert acorn.release_lock.await_count == 1


@pytest.mark.asyncio
async def test_store_continuity_receipt_refuses_unreadable_existing_journal() -> None:
    acorn = wallet()
    acorn.get_wallet_info = AsyncMock(return_value="not-json")
    token = serialized_token([proof(1, "1")])

    with pytest.raises(RuntimeError, match="journal is unreadable"):
        await acorn._store_continuity_receipt(
            event_id="event-1",
            sender_pubkey="22" * 32,
            token=token,
            payload={"amount": 1},
            timestamp=123,
        )

    acorn.set_wallet_info.assert_not_awaited()
    acorn.release_lock.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_continuity_receipts_hides_bearer_tokens_and_sorts_newest() -> None:
    acorn = wallet()
    acorn.get_wallet_info = AsyncMock(
        return_value=json.dumps(
            [
                {"event_id": "older", "amount": 2, "timestamp": 10, "token": "secret-a"},
                {"event_id": "newer", "amount": 4, "timestamp": 20, "token": "secret-b"},
            ]
        )
    )

    receipts = await acorn.get_continuity_receipts()

    assert [receipt["event_id"] for receipt in receipts] == ["newer", "older"]
    assert all("token" not in receipt for receipt in receipts)

    receipts_with_tokens = await acorn.get_continuity_receipts(include_tokens=True)
    assert receipts_with_tokens[0]["token"] == "secret-b"


@pytest.mark.asyncio
async def test_update_continuity_receipts_batch_uses_one_verified_write() -> None:
    acorn = wallet()
    existing = [
        {"event_id": "event-1", "status": "provisional", "token": "secret-a"},
        {"event_id": "event-2", "status": "provisional", "token": "secret-b"},
        {"event_id": "event-3", "status": "provisional", "token": "secret-c"},
    ]
    acorn.get_wallet_info = AsyncMock(return_value=json.dumps(existing))

    updated = await acorn._update_continuity_receipts_batch(
        ["event-1", "event-2"],
        status="mint-confirmed",
        token=None,
    )

    assert {item["event_id"] for item in updated} == {"event-1", "event-2"}
    written = json.loads(acorn.set_wallet_info.await_args.args[1])
    assert written[0]["status"] == "mint-confirmed"
    assert written[0]["token"] is None
    assert written[1]["status"] == "mint-confirmed"
    assert written[1]["token"] is None
    assert written[2] == existing[2]
    assert acorn.set_wallet_info.await_count == 1
    assert acorn.set_wallet_info.await_args.kwargs["verify"] is True


@pytest.mark.asyncio
async def test_reconcile_continuity_receipts_confirms_and_clears_bearer_token() -> None:
    acorn = wallet()
    receipt = {
        "event_id": "event-1",
        "amount": 5,
        "unit": "sat",
        "comment": "market",
        "status": "provisional",
        "token": "cashuB-test",
    }
    acorn.get_continuity_receipts = AsyncMock(return_value=[receipt])
    acorn.accept_token = AsyncMock(return_value=("accepted", 5))
    acorn._update_continuity_receipt = AsyncMock(return_value={})

    result = await acorn.reconcile_continuity_receipts()

    assert result["confirmed_count"] == 1
    assert result["confirmed_amount"] == 5
    assert result["pending_count"] == 0
    acorn.accept_token.assert_awaited_once_with(
        cashu_token="cashuB-test",
        comment="continuity payment confirmed: market",
        tendered_amount=5,
        tendered_currency="SAT",
    )
    update = acorn._update_continuity_receipt.await_args
    assert update.args == ("event-1",)
    assert update.kwargs["status"] == "mint-confirmed"
    assert update.kwargs["token"] is None


@pytest.mark.asyncio
async def test_accept_continuity_token_batch_uses_one_swap_and_proof_write() -> None:
    acorn = wallet()
    receipts = [
        {
            "event_id": "event-1",
            "amount": 5,
            "token": serialized_token([proof(1, "1"), proof(4, "4")]),
        },
        {
            "event_id": "event-2",
            "amount": 2,
            "token": serialized_token([proof(2, "2")]),
        },
    ]
    refreshed = [proof(1, "new-1"), proof(2, "new-2"), proof(4, "new-4")]
    acorn.swap_proofs = AsyncMock(return_value=refreshed)
    acorn.add_proofs_obj = AsyncMock(return_value={"verified": True})

    result = await acorn.accept_continuity_token_batch(receipts)

    assert result["receipt_count"] == 2
    assert result["amount"] == 7
    assert result["receipt_amounts"] == {"event-1": 5, "event-2": 2}
    assert acorn.balance == 7
    assert acorn.swap_proofs.await_count == 1
    assert len(acorn.swap_proofs.await_args.args[0]) == 3
    acorn.add_proofs_obj.assert_awaited_once_with(refreshed, verify=True)
    acorn.acquire_lock.assert_awaited_once()
    acorn.release_lock.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconcile_continuity_receipts_batches_same_mint() -> None:
    acorn = wallet()
    receipts = [
        {
            "event_id": "event-1",
            "sender_pubkey": "22" * 32,
            "amount": 5,
            "unit": "sat",
            "comment": "first",
            "payment_mode": "confirmed",
            "status": "provisional",
            "token": serialized_token([proof(1, "1"), proof(4, "4")]),
        },
        {
            "event_id": "event-2",
            "sender_pubkey": "33" * 32,
            "amount": 2,
            "unit": "sat",
            "comment": "second",
            "payment_mode": "confirmed",
            "status": "provisional",
            "token": serialized_token([proof(2, "2")]),
        },
    ]
    acorn.get_continuity_receipts = AsyncMock(return_value=receipts)
    acorn.accept_continuity_token_batch = AsyncMock(
        return_value={
            "status": "OK",
            "mint": MINT,
            "receipt_count": 2,
            "amount": 7,
            "receipt_amounts": {"event-1": 5, "event-2": 2},
        }
    )
    acorn._update_continuity_receipts_batch = AsyncMock(return_value=receipts)
    acorn.accept_token = AsyncMock()

    result = await acorn.reconcile_continuity_receipts()

    assert result["confirmed_count"] == 2
    assert result["confirmed_amount"] == 7
    assert result["pending_count"] == 0
    acorn.accept_continuity_token_batch.assert_awaited_once_with(receipts)
    batch_update = acorn._update_continuity_receipts_batch.await_args
    assert batch_update.args[0] == ["event-1", "event-2"]
    assert batch_update.kwargs["status"] == "mint-confirmed"
    assert batch_update.kwargs["token"] is None
    acorn.accept_token.assert_not_awaited()
    assert acorn.add_tx_history.await_count == 2


@pytest.mark.asyncio
async def test_reconcile_batch_mint_outage_keeps_entire_group_pending() -> None:
    acorn = wallet()
    receipts = [
        {
            "event_id": "event-1",
            "amount": 5,
            "unit": "sat",
            "status": "provisional",
            "token": serialized_token([proof(1, "1"), proof(4, "4")]),
        },
        {
            "event_id": "event-2",
            "amount": 2,
            "unit": "sat",
            "status": "provisional",
            "token": serialized_token([proof(2, "2")]),
        },
    ]
    acorn.get_continuity_receipts = AsyncMock(return_value=receipts)
    acorn.accept_continuity_token_batch = AsyncMock(
        side_effect=RuntimeError("mint gateway unavailable")
    )
    acorn._update_continuity_receipts_batch = AsyncMock()
    acorn.accept_token = AsyncMock()

    result = await acorn.reconcile_continuity_receipts()

    assert result["confirmed_count"] == 0
    assert result["pending_count"] == 2
    assert result["pending_amount"] == 7
    assert all("mint gateway unavailable" in item["reason"] for item in result["pending"])
    acorn._update_continuity_receipts_batch.assert_not_awaited()
    acorn.accept_token.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconcile_spent_batch_falls_back_to_individual_isolation() -> None:
    acorn = wallet()
    receipts = [
        {
            "event_id": "event-valid",
            "amount": 5,
            "unit": "sat",
            "status": "provisional",
            "token": serialized_token([proof(1, "1"), proof(4, "4")]),
        },
        {
            "event_id": "event-spent",
            "amount": 2,
            "unit": "sat",
            "status": "provisional",
            "token": serialized_token([proof(2, "2")]),
        },
    ]
    acorn.get_continuity_receipts = AsyncMock(return_value=receipts)
    acorn.accept_continuity_token_batch = AsyncMock(
        side_effect=RuntimeError("Token already spent (code 11001)")
    )
    acorn.accept_token = AsyncMock(
        side_effect=[("accepted", 5), RuntimeError("Token already spent")]
    )
    acorn._update_continuity_receipt = AsyncMock(return_value={})
    acorn.get_tx_history = AsyncMock(return_value=[])

    result = await acorn.reconcile_continuity_receipts()

    assert result["confirmed_count"] == 1
    assert result["confirmed_amount"] == 5
    assert result["terminal_error_count"] == 1
    assert result["terminal_error_amount"] == 2
    assert acorn.accept_token.await_count == 2


@pytest.mark.asyncio
async def test_reconcile_continuity_receipts_keeps_unavailable_mint_pending() -> None:
    acorn = wallet()
    acorn.get_continuity_receipts = AsyncMock(
        return_value=[
            {
                "event_id": "event-1",
                "amount": 5,
                "unit": "sat",
                "status": "provisional",
                "token": "cashuB-test",
            }
        ]
    )
    acorn.accept_token = AsyncMock(side_effect=RuntimeError("mint unavailable"))
    acorn._update_continuity_receipt = AsyncMock()

    result = await acorn.reconcile_continuity_receipts()

    assert result["confirmed_count"] == 0
    assert result["pending_count"] == 1
    assert result["pending_amount"] == 5
    assert "mint unavailable" in result["pending"][0]["reason"]
    acorn._update_continuity_receipt.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconcile_spent_token_records_terminal_error_and_clears_receipt() -> None:
    acorn = wallet()
    receipt = {
        "event_id": "event-spent",
        "amount": 21,
        "unit": "sat",
        "status": "provisional",
        "token": "cashuB-spent",
    }
    acorn.get_continuity_receipts = AsyncMock(return_value=[receipt])
    acorn.accept_token = AsyncMock(
        side_effect=RuntimeError(
            'Unable to accept token safely: {"detail":"Token already spent.","code":11001}'
        )
    )
    acorn.get_tx_history = AsyncMock(return_value=[])
    acorn.add_tx_history = AsyncMock()
    acorn._update_continuity_receipt = AsyncMock(return_value={})

    result = await acorn.reconcile_continuity_receipts()

    assert result["confirmed_count"] == 0
    assert result["pending_count"] == 0
    assert result["terminal_error_count"] == 1
    assert result["terminal_error_amount"] == 21
    history = acorn.add_tx_history.await_args.kwargs
    assert history["tx_type"] == "X"
    assert history["amount"] == 21
    assert "were not credited" in history["comment"]
    assert history["description_hash"] == "cashu-receipt-error:event-spent"
    update = acorn._update_continuity_receipt.await_args
    assert update.args == ("event-spent",)
    assert update.kwargs["status"] == "terminal-error"
    assert update.kwargs["token"] is None


@pytest.mark.asyncio
async def test_reconcile_spent_token_does_not_duplicate_existing_error_history() -> None:
    acorn = wallet()
    receipt = {
        "event_id": "event-spent",
        "amount": 21,
        "unit": "sat",
        "status": "provisional",
        "token": "cashuB-spent",
    }
    acorn.get_continuity_receipts = AsyncMock(return_value=[receipt])
    acorn.accept_token = AsyncMock(side_effect=RuntimeError("Token already spent"))
    acorn.get_tx_history = AsyncMock(
        return_value=[{"description_hash": "cashu-receipt-error:event-spent"}]
    )
    acorn.add_tx_history = AsyncMock()
    acorn._update_continuity_receipt = AsyncMock(return_value={})

    result = await acorn.reconcile_continuity_receipts()

    assert result["terminal_error_count"] == 1
    acorn.add_tx_history.assert_not_awaited()
    assert acorn._update_continuity_receipt.await_args.kwargs["token"] is None


@pytest.mark.asyncio
async def test_reconcile_standard_receipt_keeps_unavailable_mint_pending() -> None:
    acorn = wallet()
    acorn.get_continuity_receipts = AsyncMock(
        return_value=[
            {
                "event_id": "event-1",
                "sender_pubkey": "22" * 32,
                "amount": 5,
                "unit": "sat",
                "comment": "invoice payment",
                "payment_mode": "confirmed",
                "status": "provisional",
                "token": "cashuB-test",
            }
        ]
    )
    acorn.accept_token = AsyncMock(side_effect=RuntimeError("mint unavailable"))
    acorn._update_continuity_receipt = AsyncMock()

    result = await acorn.reconcile_continuity_receipts()

    assert result["confirmed_count"] == 0
    assert result["pending_count"] == 1
    assert result["pending_amount"] == 5
    acorn.accept_token.assert_awaited_once_with(
        cashu_token="cashuB-test",
        comment="funds transfer received from 222222222222: invoice payment",
        tendered_amount=5,
        tendered_currency="SAT",
    )
    acorn._update_continuity_receipt.assert_not_awaited()


@pytest.mark.asyncio
async def test_sweep_persists_standard_payment_before_unavailable_mint(
    monkeypatch,
) -> None:
    from acorn import acorn as acorn_module

    acorn = wallet()
    token = serialized_token([proof(1, "1"), proof(4, "4")])
    event = Event(
        id="a" * 64,
        sig="00" * 64,
        kind=ECASH_TRANSFER_KIND,
        content=json.dumps(
            {
                "type": "cashu-token",
                "token": token,
                "amount": 5,
                "unit": "sat",
                "comment": "invoice payment",
                "payment_mode": "confirmed",
                "settlement": "mint-confirmed",
            }
        ),
        tags=[["p", acorn.pubkey_hex]],
        pub_key="22" * 32,
        created_at=123,
    )
    operations = []

    class MemoryPool:
        def __init__(self, _relays):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def query(self, _filters):
            return [event]

    class PlaintextNip44:
        def __init__(self, _keys):
            pass

        def decrypt(self, content, _pubkey):
            return content

    class NoGiftWrap:
        def __init__(self, *_args, **_kwargs):
            pass

        async def unwrap(self, _event):
            raise ValueError("not gift wrapped")

    async def save(label, value, **_kwargs):
        operations.append(("store", label, value))
        return {"status": "OK"}

    async def unavailable_mint(**_kwargs):
        operations.append(("mint",))
        raise RuntimeError("mint unavailable")

    monkeypatch.setattr(acorn_module, "ClientPool", MemoryPool)
    monkeypatch.setattr(acorn_module, "NIP44Encrypt", PlaintextNip44)
    monkeypatch.setattr(acorn_module, "KindOtherGiftWrap", NoGiftWrap)
    acorn.set_wallet_info = AsyncMock(side_effect=save)
    acorn.accept_token = AsyncMock(side_effect=unavailable_mint)
    acorn._update_continuity_receipt = AsyncMock()

    result = await acorn.sweep_ecash_transfers()

    assert result["status"] == "OK"
    assert result["confirmed_count"] == 0
    assert result["provisional_count"] == 1
    assert result["provisional_amount"] == 5
    assert result["failed"] == []
    assert operations[0][0:2] == ("store", CONTINUITY_RECEIPTS_LABEL)
    stored_receipts = json.loads(operations[0][2])
    assert stored_receipts[0]["payment_mode"] == "confirmed"
    assert stored_receipts[0]["token"] == token
    assert operations[1] == ("mint",)
    assert operations[2][0:2] == ("store", ECASH_TRANSFER_CURSOR_LABEL)
    assert json.loads(operations[2][2]) == {
        "version": 2,
        "created_at": 123,
        "event_id": "a" * 64,
    }
    acorn._update_continuity_receipt.assert_not_awaited()


@pytest.mark.asyncio
async def test_sweep_can_collect_standard_payment_without_contacting_mint(
    monkeypatch,
) -> None:
    from acorn import acorn as acorn_module

    acorn = wallet()
    token = serialized_token([proof(1, "1")])
    event = Event(
        id="b" * 64,
        sig="00" * 64,
        kind=ECASH_TRANSFER_KIND,
        content=json.dumps(
            {
                "type": "cashu-token",
                "token": token,
                "amount": 1,
                "unit": "sat",
                "payment_mode": "confirmed",
            }
        ),
        tags=[["p", acorn.pubkey_hex]],
        pub_key="22" * 32,
        created_at=124,
    )

    class MemoryPool:
        def __init__(self, _relays):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def query(self, _filters):
            return [event]

    class PlaintextNip44:
        def __init__(self, _keys):
            pass

        def decrypt(self, content, _pubkey):
            return content

    class NoGiftWrap:
        def __init__(self, *_args, **_kwargs):
            pass

        async def unwrap(self, _event):
            raise ValueError("not gift wrapped")

    monkeypatch.setattr(acorn_module, "ClientPool", MemoryPool)
    monkeypatch.setattr(acorn_module, "NIP44Encrypt", PlaintextNip44)
    monkeypatch.setattr(acorn_module, "KindOtherGiftWrap", NoGiftWrap)
    acorn._store_continuity_receipt = AsyncMock(
        return_value={"amount": 1, "status": "provisional"}
    )
    acorn.accept_token = AsyncMock()

    result = await acorn.sweep_ecash_transfers(finalize=False)

    assert result["finalize"] is False
    assert result["confirmed_count"] == 0
    assert result["provisional_count"] == 1
    acorn._store_continuity_receipt.assert_awaited_once()
    acorn.accept_token.assert_not_awaited()


@pytest.mark.asyncio
async def test_sweep_journals_malformed_event_and_continues_to_later_transfer(
    monkeypatch,
) -> None:
    from acorn import acorn as acorn_module

    acorn = wallet()
    malformed = Event(
        id="c" * 64,
        sig="00" * 64,
        kind=ECASH_TRANSFER_KIND,
        content="not-json",
        tags=[["p", acorn.pubkey_hex]],
        pub_key="22" * 32,
        created_at=125,
    )
    valid = Event(
        id="d" * 64,
        sig="00" * 64,
        kind=ECASH_TRANSFER_KIND,
        content=json.dumps(
            {
                "type": "cashu-token",
                "token": serialized_token([proof(1, "1")]),
                "amount": 1,
                "unit": "sat",
                "payment_mode": "confirmed",
            }
        ),
        tags=[["p", acorn.pubkey_hex]],
        pub_key="33" * 32,
        created_at=126,
    )

    class MemoryPool:
        def __init__(self, _relays):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def query(self, _filters):
            return [valid, malformed]

    class PlaintextNip44:
        def __init__(self, _keys):
            pass

        def decrypt(self, content, _pubkey):
            return content

    class NoGiftWrap:
        def __init__(self, *_args, **_kwargs):
            pass

        async def unwrap(self, _event):
            raise ValueError("not gift wrapped")

    monkeypatch.setattr(acorn_module, "ClientPool", MemoryPool)
    monkeypatch.setattr(acorn_module, "NIP44Encrypt", PlaintextNip44)
    monkeypatch.setattr(acorn_module, "KindOtherGiftWrap", NoGiftWrap)
    acorn.get_tx_history = AsyncMock(return_value=[])
    acorn._store_continuity_receipt = AsyncMock(
        return_value={"amount": 1, "status": "provisional"}
    )

    result = await acorn.sweep_ecash_transfers(finalize=False)

    assert result["status"] == "PARTIAL"
    assert result["accepted_count"] == 1
    assert len(result["failed"]) == 1
    assert result["failed"][0]["event_id"] == malformed.id
    assert result["failed"][0]["status"] == "terminal-error"
    assert result["failed"][0]["error_logged"] is True
    assert result["latest_processed"] == 126
    history = acorn.add_tx_history.await_args.kwargs
    assert history["tx_type"] == "X"
    assert history["amount"] == 0
    assert history["description_hash"] == f"cashu-transfer-error:{malformed.id}"
    assert "malformed and was skipped" in history["comment"]
    acorn._store_continuity_receipt.assert_awaited_once()
    cursor_write = acorn.set_wallet_info.await_args_list[-1]
    assert cursor_write.args[0] == ECASH_TRANSFER_CURSOR_LABEL
    assert json.loads(cursor_write.args[1]) == {
        "version": 2,
        "created_at": 126,
        "event_id": "d" * 64,
    }


def test_transfer_checkpoint_migrates_legacy_timestamp_without_replaying_second() -> None:
    acorn = wallet()

    assert acorn._parse_ecash_transfer_checkpoint("123") == (123, "f" * 64)
    assert acorn._parse_ecash_transfer_checkpoint(None) == (0, "")


def test_transfer_checkpoint_round_trips_versioned_value() -> None:
    acorn = wallet()
    checkpoint = (456, "a" * 64)

    encoded = acorn._serialize_ecash_transfer_checkpoint(checkpoint)

    assert json.loads(encoded) == {
        "version": 2,
        "created_at": 456,
        "event_id": "a" * 64,
    }
    assert acorn._parse_ecash_transfer_checkpoint(encoded) == checkpoint


@pytest.mark.asyncio
async def test_sweep_uses_event_id_to_resume_within_same_second(monkeypatch) -> None:
    acorn = wallet()
    events = [
        incoming_transfer_event(acorn, event_id="a" * 64, created_at=200),
        incoming_transfer_event(acorn, event_id="b" * 64, created_at=200),
        incoming_transfer_event(acorn, event_id="c" * 64, created_at=200),
    ]
    observed_filters = install_filtering_transfer_pool(monkeypatch, events)
    acorn.get_wallet_info = AsyncMock(
        return_value=acorn._serialize_ecash_transfer_checkpoint((200, "b" * 64))
    )
    acorn._store_continuity_receipt = AsyncMock(
        return_value={"amount": 1, "status": "provisional"}
    )

    result = await acorn.sweep_ecash_transfers(finalize=False, limit=10)

    assert observed_filters[0]["since"] == 200
    assert result["accepted_count"] == 1
    assert result["accepted"][0]["event_id"] == "c" * 64
    assert result["cursor_checkpoint"] == {
        "created_at": 200,
        "event_id": "b" * 64,
    }
    assert result["latest_checkpoint"] == {
        "created_at": 200,
        "event_id": "c" * 64,
    }


@pytest.mark.asyncio
async def test_sweep_pages_with_inclusive_boundaries_and_deduplicates(monkeypatch) -> None:
    acorn = wallet()
    events = [
        incoming_transfer_event(acorn, event_id="a" * 64, created_at=101),
        incoming_transfer_event(acorn, event_id="b" * 64, created_at=102),
        incoming_transfer_event(acorn, event_id="c" * 64, created_at=103),
    ]
    observed_filters = install_filtering_transfer_pool(monkeypatch, events)
    acorn._store_continuity_receipt = AsyncMock(
        return_value={"amount": 1, "status": "provisional"}
    )

    result = await acorn.sweep_ecash_transfers(
        since=100,
        finalize=False,
        limit=2,
        max_pages=10,
    )

    assert result["accepted_count"] == 3
    assert [entry["event_id"] for entry in result["accepted"]] == [
        "a" * 64,
        "b" * 64,
        "c" * 64,
    ]
    assert result["queried"] == 3
    assert result["page_count"] == 3
    assert observed_filters[1]["until"] == 102
    assert observed_filters[2]["until"] == 101
    assert result["latest_checkpoint"] == {
        "created_at": 103,
        "event_id": "c" * 64,
    }


@pytest.mark.asyncio
async def test_sweep_stops_safely_when_same_second_page_is_saturated(monkeypatch) -> None:
    acorn = wallet()
    events = [
        incoming_transfer_event(acorn, event_id="a" * 64, created_at=500),
        incoming_transfer_event(acorn, event_id="b" * 64, created_at=500),
        incoming_transfer_event(acorn, event_id="c" * 64, created_at=500),
    ]
    install_filtering_transfer_pool(monkeypatch, events)

    with pytest.raises(RuntimeError, match="saturated same-second page"):
        await acorn.sweep_ecash_transfers(
            since=499,
            finalize=False,
            limit=2,
            max_pages=10,
        )

    acorn.set_wallet_info.assert_not_awaited()
