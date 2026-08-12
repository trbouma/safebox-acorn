from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock

import pytest
from monstr.encrypt import Keys

from acorn.acorn import Acorn, CONTINUITY_RECEIPTS_LABEL
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
