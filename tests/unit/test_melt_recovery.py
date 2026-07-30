from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from acorn.acorn import (
    Acorn,
    PaymentFinalizationError,
    PaymentOutcomeUnknownError,
)
from acorn.models import Proof


class MeltResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class MeltClient:
    post_result = None
    post_calls = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, **kwargs):
        type(self).post_calls += 1
        if isinstance(type(self).post_result, Exception):
            raise type(self).post_result
        return MeltResponse(type(self).post_result)


def bare_wallet(proofs=None):
    wallet = object.__new__(Acorn)
    wallet.proofs = list(proofs or [])
    wallet.balance = sum(each.amount for each in wallet.proofs)
    return wallet


@pytest.mark.asyncio
async def test_melt_timeout_is_resolved_by_quote_query(monkeypatch):
    from acorn import acorn as acorn_module

    wallet = bare_wallet()
    MeltClient.post_calls = 0
    MeltClient.post_result = httpx.ReadTimeout("response timed out")
    monkeypatch.setattr(acorn_module.httpx, "AsyncClient", MeltClient)
    monkeypatch.setattr(acorn_module.asyncio, "sleep", AsyncMock())
    wallet._query_melt_quote = AsyncMock(
        side_effect=[
            {"state": "PENDING"},
            {"state": "PAID", "payment_preimage": "preimage"},
        ]
    )

    result = await wallet._resolve_melt_submission(
        melt_url="https://mint.example/v1/melt/bolt11",
        mint="https://mint.example",
        quote="quote-1",
        request_payload={"quote": "quote-1", "inputs": []},
        headers={"Content-Type": "application/json"},
        timeout=httpx.Timeout(1),
        attempts=3,
    )

    assert result["state"] == "PAID"
    assert result["source"] == "quote-query"
    assert MeltClient.post_calls == 1
    assert wallet._query_melt_quote.await_count == 2


@pytest.mark.asyncio
async def test_melt_timeout_never_reposts_or_claims_failure(monkeypatch):
    from acorn import acorn as acorn_module

    wallet = bare_wallet()
    MeltClient.post_calls = 0
    MeltClient.post_result = httpx.ReadTimeout("response timed out")
    monkeypatch.setattr(acorn_module.httpx, "AsyncClient", MeltClient)
    monkeypatch.setattr(acorn_module.asyncio, "sleep", AsyncMock())
    wallet._query_melt_quote = AsyncMock(return_value={"state": "PENDING"})

    with pytest.raises(PaymentOutcomeUnknownError, match="Do not retry"):
        await wallet._resolve_melt_submission(
            melt_url="https://mint.example/v1/melt/bolt11",
            mint="https://mint.example",
            quote="quote-2",
            request_payload={"quote": "quote-2", "inputs": []},
            headers={"Content-Type": "application/json"},
            timeout=httpx.Timeout(1),
            attempts=4,
        )

    assert MeltClient.post_calls == 1
    assert wallet._query_melt_quote.await_count == 4


@pytest.mark.asyncio
async def test_definitive_unpaid_response_does_not_query_or_retry(monkeypatch):
    from acorn import acorn as acorn_module

    wallet = bare_wallet()
    MeltClient.post_calls = 0
    MeltClient.post_result = {"state": "UNPAID", "paid": False}
    monkeypatch.setattr(acorn_module.httpx, "AsyncClient", MeltClient)
    wallet._query_melt_quote = AsyncMock()

    result = await wallet._resolve_melt_submission(
        melt_url="https://mint.example/v1/melt/bolt11",
        mint="https://mint.example",
        quote="quote-3",
        request_payload={"quote": "quote-3", "inputs": []},
        headers={"Content-Type": "application/json"},
        timeout=httpx.Timeout(1),
    )

    assert result["state"] == "UNPAID"
    assert MeltClient.post_calls == 1
    wallet._query_melt_quote.assert_not_awaited()


@pytest.mark.asyncio
async def test_restart_reconciliation_finalizes_paid_melt_once():
    spend = Proof(id="keyset", amount=2, secret="spend", C="02a", Y="03spend")
    keep = Proof(id="keyset", amount=4, secret="keep", C="02b", Y="03keep")
    wallet = bare_wallet([spend, keep])
    entry = {
        "quote": "quote-restart",
        "mint": "https://mint.example",
        "keyset": "keyset",
        "spend_ys": ["03spend"],
        "amount": 1,
        "fee_reserve": 1,
        "comment": "restart test",
        "tendered_amount": None,
        "tendered_currency": "SAT",
        "invoice": "lnbc...",
    }
    journal = [entry]
    history = []

    async def load_pending():
        return [dict(each) for each in journal]

    async def save_pending(entries):
        journal[:] = [dict(each) for each in entries]

    async def write_proofs():
        return None

    async def get_history():
        return list(history)

    async def add_history(**kwargs):
        history.append(kwargs)

    wallet._load_pending_melts = load_pending
    wallet._save_pending_melts = save_pending
    wallet._query_melt_quote = AsyncMock(
        return_value={"state": "PAID", "payment_preimage": "preimage"}
    )
    wallet.write_proofs = AsyncMock(side_effect=write_proofs)
    wallet.get_tx_history = AsyncMock(side_effect=get_history)
    wallet.add_tx_history = AsyncMock(side_effect=add_history)

    result = await wallet.reconcile_pending_melts()

    assert result["paid"] == 1
    assert result["unresolved"] == 0
    assert [proof.Y for proof in wallet.proofs] == ["03keep"]
    assert wallet.balance == 4
    assert journal == []
    assert history[0]["description_hash"] == "cashu-melt:quote-restart"
    assert history[0]["payment_preimage"] == "preimage"


@pytest.mark.asyncio
async def test_restart_reconciliation_preserves_proofs_for_unpaid_melt():
    spend = Proof(id="keyset", amount=2, secret="spend", C="02a", Y="03spend")
    wallet = bare_wallet([spend])
    journal = [
        {
            "quote": "quote-unpaid",
            "mint": "https://mint.example",
            "spend_ys": ["03spend"],
            "amount": 1,
            "fee_reserve": 1,
        }
    ]

    async def load_pending():
        return [dict(each) for each in journal]

    async def save_pending(entries):
        journal[:] = [dict(each) for each in entries]

    wallet._load_pending_melts = load_pending
    wallet._save_pending_melts = save_pending
    wallet._query_melt_quote = AsyncMock(return_value={"state": "UNPAID"})

    result = await wallet.reconcile_pending_melts()

    assert result["unpaid"] == 1
    assert wallet.proofs == [spend]
    assert wallet.balance == 2
    assert journal == []


@pytest.mark.asyncio
async def test_pending_journal_requires_relay_readback(monkeypatch):
    from acorn import acorn as acorn_module

    wallet = bare_wallet()
    entry = {"quote": "quote-durable", "mint": "https://mint.example"}
    wallet.set_wallet_info = AsyncMock()
    wallet._load_pending_melts = AsyncMock(side_effect=[[], [entry]])
    monkeypatch.setattr(acorn_module.asyncio, "sleep", AsyncMock())

    await wallet._save_pending_melts([entry])

    wallet.set_wallet_info.assert_awaited_once()
    assert wallet._load_pending_melts.await_count == 2


@pytest.mark.asyncio
async def test_unreadable_pending_journal_prevents_melt_submission(monkeypatch):
    from acorn import acorn as acorn_module

    wallet = bare_wallet()
    entry = {"quote": "quote-not-durable", "mint": "https://mint.example"}
    wallet.set_wallet_info = AsyncMock()
    wallet._load_pending_melts = AsyncMock(return_value=[])
    monkeypatch.setattr(acorn_module.asyncio, "sleep", AsyncMock())

    with pytest.raises(PaymentFinalizationError, match="could not be read back"):
        await wallet._save_pending_melts([entry])

    assert wallet._load_pending_melts.await_count == 5


@pytest.mark.asyncio
async def test_unresolved_previous_melt_blocks_spending():
    wallet = bare_wallet()
    wallet.reconcile_pending_melts = AsyncMock(
        return_value={
            "paid": 0,
            "unpaid": 0,
            "unresolved": 1,
            "quotes": [{"quote": "quote-pending", "state": "PENDING", "error": None}],
        }
    )

    with pytest.raises(PaymentOutcomeUnknownError, match="Do not spend"):
        await wallet._require_resolved_pending_melts()
