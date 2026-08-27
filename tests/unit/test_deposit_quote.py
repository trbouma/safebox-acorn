from __future__ import annotations

import logging
from types import SimpleNamespace

import httpx
import pytest
import requests
from monstr.encrypt import Keys

from acorn import acorn as acorn_module
from acorn.acorn import Acorn
from acorn.models import PostMeltQuoteResponse, Proof


def wallet_with_key() -> Acorn:
    wallet = object.__new__(Acorn)
    wallet.k = Keys(priv_k="11" * 32)
    wallet.home_mint = "https://mint.example/"
    wallet.logger = logging.getLogger("deposit-quote-test")
    wallet.known_mints = {}
    wallet.proofs = []
    return wallet


def successful_quote_response():
    return SimpleNamespace(
        status_code=200,
        raise_for_status=lambda: None,
        json=lambda: {
            "quote": "quote-id",
            "request": "lnbc1test",
            "paid": False,
            "expiry": 0,
        },
    )


class FakeAsyncQuoteResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "quote": "quote-id",
            "request": "lnbc1test",
            "amount": 21,
            "unit": "sat",
            "method": "bolt11",
            "amount_paid": 21,
            "amount_issued": 0,
            "updated_at": 1787169463,
            "state": "PAID",
            "expiry": None,
            "pubkey": "",
        }


class FakeAsyncQuoteClient:
    requested_urls = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def get(self, url, **kwargs):
        self.requested_urls.append(url)
        return FakeAsyncQuoteResponse()


def test_deposit_strips_trailing_slashes_from_explicit_mint(monkeypatch):
    wallet = wallet_with_key()
    requested_urls = []

    def fake_post(url, **kwargs):
        requested_urls.append(url)
        return successful_quote_response()

    monkeypatch.setattr(acorn_module.requests, "post", fake_post)

    quote = wallet.deposit(21, "https://testnut.cashu.space/")

    assert requested_urls == ["https://testnut.cashu.space/v1/mint/quote/bolt11"]
    assert quote.mint_url == "https://testnut.cashu.space/v1/mint/quote/bolt11"


def test_deposit_strips_trailing_slashes_from_home_mint(monkeypatch):
    wallet = wallet_with_key()
    requested_urls = []

    def fake_post(url, **kwargs):
        requested_urls.append(url)
        return successful_quote_response()

    monkeypatch.setattr(acorn_module.requests, "post", fake_post)

    wallet.deposit(21)

    assert requested_urls == ["https://mint.example/v1/mint/quote/bolt11"]


def test_deposit_does_not_retry_permanent_http_error(monkeypatch):
    wallet = wallet_with_key()
    attempts = 0

    def fake_post(url, **kwargs):
        nonlocal attempts
        attempts += 1
        return SimpleNamespace(status_code=404)

    monkeypatch.setattr(acorn_module.requests, "post", fake_post)

    with pytest.raises(RuntimeError, match=r"rejected with HTTP 404") as exc_info:
        wallet.deposit(21, "https://testnut.cashu.space/")

    assert attempts == 1
    assert "//v1" not in str(exc_info.value)
    assert "timed out" not in str(exc_info.value)


def test_deposit_retries_transient_timeout(monkeypatch):
    wallet = wallet_with_key()
    attempts = 0

    def fake_post(url, **kwargs):
        nonlocal attempts
        attempts += 1
        raise requests.exceptions.Timeout("test timeout")

    monkeypatch.setattr(acorn_module.requests, "post", fake_post)
    monkeypatch.setattr(acorn_module, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match=r"timed out after 4 attempts"):
        wallet.deposit(21)

    assert attempts == 4


@pytest.mark.asyncio
async def test_check_quote_accepts_paid_state_response(monkeypatch):
    wallet = wallet_with_key()
    minted = {}
    FakeAsyncQuoteClient.requested_urls = []

    async def fake_mint_proofs(quote, amount, mint):
        minted["quote"] = quote
        minted["amount"] = amount
        minted["mint"] = mint
        return True

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncQuoteClient)
    wallet._mint_proofs = fake_mint_proofs

    paid, invoice = await wallet.check_quote(
        "quote-id",
        21,
        "https://mint.safebox.dev",
    )

    assert paid is True
    assert invoice == "lnbc1test"
    assert FakeAsyncQuoteClient.requested_urls == [
        "https://mint.safebox.dev/v1/mint/quote/bolt11/quote-id"
    ]
    assert minted == {
        "quote": "quote-id",
        "amount": 21,
        "mint": "https://mint.safebox.dev",
    }


def relay_backed_pending_deposit_wallet() -> tuple[Acorn, dict[str, str]]:
    wallet = wallet_with_key()
    storage: dict[str, str] = {}

    async def get_wallet_info(*, label: str):
        return storage.get(label)

    async def set_wallet_info(*, label: str, label_info: str, **_kwargs):
        storage[label] = label_info
        return {"status": "OK"}

    async def acquire_lock():
        return True

    async def release_lock():
        return None

    wallet.get_wallet_info = get_wallet_info
    wallet.set_wallet_info = set_wallet_info
    wallet.acquire_lock = acquire_lock
    wallet.release_lock = release_lock
    return wallet, storage


@pytest.mark.asyncio
async def test_pending_deposit_is_persisted_with_its_issuing_mint():
    wallet, storage = relay_backed_pending_deposit_wallet()

    entry = await wallet.register_pending_deposit(
        quote="quote-old-mint",
        amount=2500,
        invoice="lnbc25u1test",
        mint="https://mint.getsafebox.app/",
    )

    assert entry["mint"] == "https://mint.getsafebox.app"
    assert entry["status"] == "pending"
    assert storage[acorn_module.PENDING_DEPOSITS_LABEL]
    assert await wallet.get_pending_deposits() == [entry]


@pytest.mark.asyncio
async def test_multiple_pending_deposits_are_retained_independently():
    wallet, _storage = relay_backed_pending_deposit_wallet()

    await wallet.register_pending_deposit(
        quote="quote-one",
        amount=21,
        invoice="lnbc210n1one",
        mint="https://mint.safebox.dev",
    )
    await wallet.register_pending_deposit(
        quote="quote-two",
        amount=34,
        invoice="lnbc340n1two",
        mint="https://mint.getsafebox.app",
    )

    pending = await wallet.get_pending_deposits()
    assert {entry["quote"] for entry in pending} == {"quote-one", "quote-two"}
    assert {entry["mint"] for entry in pending} == {
        "https://mint.safebox.dev",
        "https://mint.getsafebox.app",
    }


@pytest.mark.asyncio
async def test_pending_deposit_finalization_is_idempotent_and_mint_bound():
    wallet, _storage = relay_backed_pending_deposit_wallet()
    await wallet.register_pending_deposit(
        quote="quote-new-mint",
        amount=21,
        invoice="lnbc210n1test",
        mint="https://mint.safebox.dev",
    )
    quote_checks = []
    history = []

    async def check_quote(quote, amount, mint):
        quote_checks.append((quote, amount, mint))
        return True, "lnbc210n1test"

    async def get_tx_history():
        return list(history)

    async def add_tx_history(**entry):
        history.append(entry)
        return {"status": "OK"}

    wallet.check_quote = check_quote
    wallet.get_tx_history = get_tx_history
    wallet.add_tx_history = add_tx_history

    result = await wallet.finalize_pending_deposit("quote-new-mint")
    repeated = await wallet.finalize_pending_deposit("quote-new-mint")

    assert result["status"] == "COMPLETE"
    assert repeated["status"] == "NOT_FOUND"
    assert quote_checks == [
        ("quote-new-mint", 21, "https://mint.safebox.dev")
    ]
    assert len(history) == 1
    assert history[0]["description_hash"] == (
        "cashu-mint:https://mint.safebox.dev:quote-new-mint"
    )
    assert await wallet.get_pending_deposits() == []


@pytest.mark.asyncio
async def test_unpaid_pending_deposit_remains_recoverable():
    wallet, _storage = relay_backed_pending_deposit_wallet()
    await wallet.register_pending_deposit(
        quote="quote-unpaid",
        amount=34,
        invoice="lnbc340n1test",
        mint="https://mint.safebox.dev",
    )
    async def history():
        return []

    async def check_quote(_quote, _amount, _mint):
        return False, None

    wallet.get_tx_history = history
    wallet.check_quote = check_quote

    result = await wallet.finalize_pending_deposit("quote-unpaid")

    assert result["status"] == "PENDING"
    assert [entry["quote"] for entry in await wallet.get_pending_deposits()] == [
        "quote-unpaid"
    ]


def test_source_mint_keysets_filters_and_sorts_by_mint():
    wallet = wallet_with_key()
    wallet.known_mints = {
        "source-small": "https://mint.source",
        "source-large": "https://mint.source/",
        "other": "https://mint.other",
    }
    wallet.proofs = [
        Proof(id="source-small", amount=2, secret="a", C="c", Y="ya"),
        Proof(id="source-large", amount=8, secret="b", C="c", Y="yb"),
        Proof(id="other", amount=32, secret="c", C="c", Y="yc"),
    ]

    rows = wallet._source_mint_keysets("mint.source")

    assert [row["keyset"] for row in rows] == ["source-large", "source-small"]
    assert [row["amount"] for row in rows] == [8, 2]


def test_melt_quote_response_accepts_state_without_paid_boolean():
    quote = PostMeltQuoteResponse(
        quote="melt-quote",
        amount=21,
        fee_reserve=2,
        state="UNPAID",
        expiry=None,
    )

    assert quote.paid is False
    assert quote.state == "UNPAID"


@pytest.mark.asyncio
async def test_prepare_mint_transfer_full_amount_reduces_for_source_fee():
    wallet = wallet_with_key()
    requested_amounts = []

    def fake_deposit(amount, mint):
        requested_amounts.append(amount)
        return SimpleNamespace(quote=f"dest-{amount}", invoice=f"invoice-{amount}")

    async def fake_melt_quote(mint, invoice):
        return SimpleNamespace(quote=f"source-{invoice}", fee_reserve=2)

    wallet.deposit = fake_deposit
    wallet._request_melt_quote_for_invoice = fake_melt_quote

    result = await wallet._prepare_mint_transfer_quotes(
        source_mint="https://mint.source",
        destination_mint="https://mint.dest",
        receive_amount=10,
        source_available=10,
        full_amount=True,
    )

    assert requested_amounts == [10, 8]
    assert result["receive_amount"] == 8
    assert result["source_fee_reserve"] == 2
    assert result["source_debit"] == 10
    assert result["destination_quote"].quote == "dest-8"


@pytest.mark.asyncio
async def test_prepare_mint_transfer_reserves_melt_input_fee():
    wallet = wallet_with_key()
    requested_amounts = []

    def fake_deposit(amount, mint):
        requested_amounts.append(amount)
        return SimpleNamespace(quote=f"dest-{amount}", invoice=f"invoice-{amount}")

    async def fake_melt_quote(mint, invoice):
        return SimpleNamespace(quote=f"source-{invoice}", fee_reserve=2)

    wallet.deposit = fake_deposit
    wallet._request_melt_quote_for_invoice = fake_melt_quote

    result = await wallet._prepare_mint_transfer_quotes(
        source_mint="https://mint.source",
        destination_mint="https://mint.dest",
        receive_amount=10,
        source_available=10,
        full_amount=True,
        input_fee_ppk=100,
    )

    assert requested_amounts == [10, 7]
    assert result["receive_amount"] == 7
    assert result["source_fee_reserve"] == 2
    assert result["source_melt_input_fee"] == 1
    assert result["source_debit"] == 10
