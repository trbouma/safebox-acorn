from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock
from binascii import unhexlify

import httpx
import pytest

from acorn.acorn import (
    Acorn,
    PaymentFailedError,
    PaymentFees,
    PaymentFinalizationError,
    PaymentOutcomeUnknownError,
)
from acorn.models import Proof
from acorn.b_dhke import step2_bob, verify
from acorn.secp import PrivateKey, PublicKey


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
        if isinstance(type(self).post_result, httpx.Response):
            return type(self).post_result
        return MeltResponse(type(self).post_result)


class ChangeClient:
    key_payload = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def get(self, url):
        return MeltResponse(type(self).key_payload)


def bare_wallet(proofs=None):
    wallet = object.__new__(Acorn)
    wallet.proofs = list(proofs or [])
    wallet.balance = sum(each.amount for each in wallet.proofs)
    return wallet


@pytest.mark.parametrize(
    ("base_amount", "input_fee_ppk", "expected_total", "expected_fee"),
    [
        (21, 0, 21, 0),
        (21, 100, 22, 1),
        (31, 100, 32, 1),
        (6, 1000, 8, 1),
    ],
)
def test_melt_amount_includes_fee_for_generated_input_proofs(
    base_amount,
    input_fee_ppk,
    expected_total,
    expected_fee,
):
    wallet = bare_wallet()

    assert wallet._melt_amount_with_input_fee(
        base_amount,
        input_fee_ppk,
    ) == (expected_total, expected_fee)


def test_select_proofs_covers_preparatory_swap_input_fee():
    wallet = bare_wallet()
    proofs = [
        Proof(id="keyset", amount=1, secret="one", C="c1"),
        Proof(id="keyset", amount=2, secret="two", C="c2"),
        Proof(id="keyset", amount=4, secret="four", C="c4"),
        Proof(id="keyset", amount=16, secret="sixteen", C="c16"),
    ]

    selected, remaining, input_fee = wallet._select_proofs_for_net_amount(
        proofs,
        21,
        100,
    )

    assert sum(proof.amount for proof in selected) == 22
    assert [proof.amount for proof in remaining] == [1]
    assert input_fee == 1
    assert sum(proof.amount for proof in selected) - input_fee >= 21


def test_select_proofs_rejects_exact_balance_consumed_by_fee():
    wallet = bare_wallet()
    proofs = [
        Proof(id="keyset", amount=1, secret="one", C="c1"),
        Proof(id="keyset", amount=4, secret="four", C="c4"),
        Proof(id="keyset", amount=16, secret="sixteen", C="c16"),
    ]

    with pytest.raises(ValueError, match="after mint input fees"):
        wallet._select_proofs_for_net_amount(proofs, 21, 100)


def test_lightning_fee_breakdown_separates_mint_and_lightning_fees():
    wallet = bare_wallet()

    assert wallet._format_lightning_fee_breakdown(
        mint_fees=2,
        lightning_fee_reserve=10,
        lightning_fee=1,
        lightning_fee_return=9,
    ) == (
        "Fee breakdown:\n"
        "- Mint fees: 2 sats\n"
        "- Lightning fee: 1 sats\n"
        "- Lightning fee reserve: 10 sats\n"
        "- Lightning fee returned: 9 sats"
    )


def test_payment_fees_remain_numeric_with_structured_breakdown():
    fees = PaymentFees(
        3,
        mint_fees=2,
        lightning_fee_reserve=10,
        lightning_fee=1,
        lightning_fee_return=9,
    )

    assert isinstance(fees, int)
    assert fees == 3
    assert fees + 2 == 5
    assert fees.mint_fees == 2
    assert fees.lightning_fee_reserve == 10
    assert fees.lightning_fee == 1
    assert fees.lightning_fee_return == 9


@pytest.mark.parametrize(
    ("fee_reserve", "expected"),
    [(0, 0), (1, 1), (2, 1), (3, 2), (10, 4), (1000, 10)],
)
def test_nut08_blank_output_count(fee_reserve, expected):
    assert Acorn._melt_blank_output_count(fee_reserve) == expected


def test_nut08_change_material_is_durable_and_outputs_hide_secrets():
    outputs, recovery = Acorn._prepare_melt_change_outputs(
        keyset="keyset",
        fee_reserve=10,
    )

    assert len(outputs) == 4
    assert len(recovery) == 4
    assert all(output["amount"] == 1 for output in outputs)
    assert all(output["id"] == "keyset" for output in outputs)
    assert all("secret" not in output and "r" not in output for output in outputs)
    assert all(len(item["secret"]) == 64 for item in recovery)
    assert all(len(item["r"]) == 64 for item in recovery)


@pytest.mark.asyncio
async def test_invoice_payment_prepares_durable_nut08_change(monkeypatch):
    from acorn import acorn as acorn_module

    class QuoteResponse:
        is_error = False

        def json(self):
            return {
                "quote": "invoice-quote",
                "amount": 21,
                "fee_reserve": 2,
                "state": "UNPAID",
                "expiry": None,
            }

    class QuoteClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, **kwargs):
            return QuoteResponse()

    wallet = bare_wallet(
        [Proof(id="keyset", amount=32, secret="source", C="02source", Y="03source")]
    )
    wallet.known_mints = {"keyset": "https://mint.example"}
    wallet.logger = logging.getLogger("invoice-change-test")
    wallet.acquire_lock = AsyncMock()
    wallet.release_lock = AsyncMock()
    wallet._reconcile_spent_proofs_locked = AsyncMock()
    wallet._require_resolved_pending_melts = AsyncMock()
    wallet._keyset_input_fee_ppk = AsyncMock(return_value=0)
    wallet.swap_for_payment_multi = AsyncMock(
        return_value=[
            Proof(id="keyset", amount=16, secret="a", C="02a", Y="03a"),
            Proof(id="keyset", amount=4, secret="b", C="02b", Y="03b"),
            Proof(id="keyset", amount=2, secret="c", C="02c", Y="03c"),
            Proof(id="keyset", amount=1, secret="d", C="02d", Y="03d"),
        ]
    )
    wallet._mint_supports_nut08 = AsyncMock(return_value=True)
    wallet._prepare_melt_change_outputs = lambda **kwargs: (
        [{"amount": 1, "id": "keyset", "B_": "02blind"}],
        [{"id": "keyset", "secret": "secret", "r": "factor", "Y": "03y"}],
    )
    wallet.write_proofs = AsyncMock()
    wallet._upsert_pending_melt = AsyncMock()

    async def resolve_melt_submission(**kwargs):
        assert kwargs["request_payload"]["outputs"] == [
            {"amount": 1, "id": "keyset", "B_": "02blind"}
        ]
        return {
            "state": "PAID",
            "source": "submission",
            "payload": {"payment_preimage": "preimage", "change": []},
        }

    wallet._resolve_melt_submission = resolve_melt_submission
    wallet._finalize_paid_melt = AsyncMock(
        return_value={
            "total_fees": 0,
            "mint_fees": 0,
            "lightning_fee_reserve": 2,
            "lightning_fee": 0,
            "lightning_fee_return": 2,
        }
    )
    monkeypatch.setattr(acorn_module.httpx, "AsyncClient", QuoteClient)
    monkeypatch.setattr(
        acorn_module.bolt11,
        "decode",
        lambda invoice: SimpleNamespace(
            amount_msat=21_000,
            payment_hash="payment-hash",
            description_hash=None,
        ),
    )

    result = await wallet.pay_multi_invoice(
        "lnbc-test",
        comment="invoice test",
        tendered_amount=0.03,
        tendered_currency="CAD",
    )

    pending_entry = wallet._upsert_pending_melt.await_args.args[0]
    assert pending_entry["change_outputs"] == [
        {"id": "keyset", "secret": "secret", "r": "factor", "Y": "03y"}
    ]
    assert pending_entry["tendered_amount"] == 0.03
    assert pending_entry["tendered_currency"] == "CAD"
    assert result[0].startswith("Paid 21 sats")


@pytest.mark.asyncio
async def test_nut08_change_is_unblinded_into_a_valid_proof(monkeypatch):
    from acorn import acorn as acorn_module

    outputs, recovery = Acorn._prepare_melt_change_outputs(
        keyset="keyset",
        fee_reserve=2,
    )
    mint_private_key = PrivateKey()
    blinded_message = PublicKey()
    blinded_message.deserialize(unhexlify(outputs[0]["B_"]))
    blinded_signature, _e, _s = step2_bob(
        blinded_message,
        mint_private_key,
    )
    ChangeClient.key_payload = {
        "keysets": [
            {
                "id": "keyset",
                "keys": {"2": mint_private_key.pubkey.serialize().hex()},
            }
        ]
    }
    monkeypatch.setattr(acorn_module.httpx, "AsyncClient", ChangeClient)
    wallet = bare_wallet()

    proofs = await wallet._unblind_melt_change(
        {
            "mint": "https://mint.example",
            "lightning_fee_reserve": 2,
            "change_outputs": recovery,
        },
        {
            "change": [
                {
                    "id": "keyset",
                    "amount": 2,
                    "C_": blinded_signature.serialize().hex(),
                }
            ]
        },
    )

    assert len(proofs) == 1
    assert proofs[0].amount == 2
    assert proofs[0].secret == recovery[0]["secret"]
    signature = PublicKey()
    signature.deserialize(unhexlify(proofs[0].C))
    assert verify(mint_private_key, signature, proofs[0].secret)


@pytest.mark.asyncio
async def test_nut08_is_used_only_when_mint_advertises_support(monkeypatch):
    from acorn import acorn as acorn_module

    monkeypatch.setattr(acorn_module.httpx, "AsyncClient", ChangeClient)
    wallet = bare_wallet()

    ChangeClient.key_payload = {"nuts": {"8": {"supported": True}}}
    assert await wallet._mint_supports_nut08("https://mint.example") is True

    ChangeClient.key_payload = {"nuts": {"8": {"supported": False}}}
    assert await wallet._mint_supports_nut08("https://mint.example") is False


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
async def test_melt_http_400_preserves_rejection_body(monkeypatch):
    from acorn import acorn as acorn_module

    wallet = bare_wallet()
    MeltClient.post_calls = 0
    MeltClient.post_result = httpx.Response(
        400,
        request=httpx.Request(
            "POST",
            "https://mint.example/v1/melt/bolt11",
        ),
        json={
            "detail": "not enough inputs provided for melt. Provided: 21, needed: 22",
            "code": 11000,
        },
    )
    monkeypatch.setattr(acorn_module.httpx, "AsyncClient", MeltClient)
    wallet._query_melt_quote = AsyncMock()

    with pytest.raises(
        PaymentFailedError,
        match=r"Melt rejected before Lightning submission: HTTP 400:.*needed: 22",
    ):
        await wallet._resolve_melt_submission(
            melt_url="https://mint.example/v1/melt/bolt11",
            mint="https://mint.example",
            quote="quote-rejected",
            request_payload={"quote": "quote-rejected", "inputs": []},
            headers={"Content-Type": "application/json"},
            timeout=httpx.Timeout(1),
        )

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
async def test_paid_melt_restores_nut08_change_and_records_actual_fee():
    spend = Proof(id="keyset", amount=32, secret="spend", C="02a", Y="03spend")
    keep = Proof(id="keyset", amount=4, secret="keep", C="02b", Y="03keep")
    change = Proof(id="keyset", amount=9, secret="change", C="02c", Y="03change")
    wallet = bare_wallet([spend, keep])
    entry = {
        "quote": "quote-change",
        "mint": "https://mint.example",
        "keyset": "keyset",
        "spend_ys": ["03spend"],
        "amount": 21,
        "fee_reserve": 12,
        "lightning_fee_reserve": 10,
        "mint_input_fee": 1,
        "swap_input_fee": 1,
        "comment": "change test",
        "tendered_currency": "SAT",
    }
    history = []

    wallet._unblind_melt_change = AsyncMock(return_value=[change])
    wallet.write_proofs = AsyncMock()
    wallet.get_tx_history = AsyncMock(return_value=[])
    wallet.add_tx_history = AsyncMock(
        side_effect=lambda **kwargs: history.append(kwargs)
    )
    wallet._remove_pending_melt = AsyncMock()

    result = await wallet._finalize_paid_melt(
        entry,
        {"state": "PAID", "change": [{"amount": 9}]},
    )

    assert [(proof.secret, proof.amount) for proof in wallet.proofs] == [
        ("keep", 4),
        ("change", 9),
    ]
    assert wallet.balance == 13
    assert result == {
        "total_fees": 3,
        "mint_fees": 2,
        "lightning_fee_reserve": 10,
        "lightning_fee_return": 9,
        "lightning_fee": 1,
        "change_amount": 9,
    }
    assert history[0]["fees"] == 3
    wallet._remove_pending_melt.assert_awaited_once_with("quote-change")


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
            "lightning_fee_reserve": 1,
            "swap_input_fee": 1,
            "comment": "unpaid test",
        }
    ]

    async def load_pending():
        return [dict(each) for each in journal]

    async def save_pending(entries):
        journal[:] = [dict(each) for each in entries]

    wallet._load_pending_melts = load_pending
    wallet._save_pending_melts = save_pending
    wallet._query_melt_quote = AsyncMock(return_value={"state": "UNPAID"})
    wallet.get_tx_history = AsyncMock(return_value=[])
    wallet.add_tx_history = AsyncMock()

    result = await wallet.reconcile_pending_melts()

    assert result["unpaid"] == 1
    assert wallet.proofs == [spend]
    assert wallet.balance == 2
    assert journal == []
    history = wallet.add_tx_history.await_args.kwargs
    assert history["tx_type"] == "X"
    assert history["amount"] == 1
    assert history["fees"] == 1
    assert history["description_hash"] == "cashu-melt-failed:quote-unpaid"
    assert history["comment"] == "unpaid test"
    assert history["error_code"] == "payment_failed"


def test_unpaid_melt_reports_only_consumed_preparatory_swap_fee():
    fees = Acorn._failed_melt_fees(
        {
            "swap_input_fee": 2,
            "mint_input_fee": 3,
            "lightning_fee_reserve": 10,
        }
    )

    assert fees == 2
    assert fees.mint_fees == 2
    assert fees.lightning_fee == 0
    assert fees.lightning_fee_reserve == 10
    assert fees.lightning_fee_return == 10


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
