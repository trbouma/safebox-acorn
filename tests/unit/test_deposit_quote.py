from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
import requests
from monstr.encrypt import Keys

from acorn import acorn as acorn_module
from acorn.acorn import Acorn


def wallet_with_key() -> Acorn:
    wallet = object.__new__(Acorn)
    wallet.k = Keys(priv_k="11" * 32)
    wallet.home_mint = "https://mint.example/"
    wallet.logger = logging.getLogger("deposit-quote-test")
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
