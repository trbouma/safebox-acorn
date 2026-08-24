from __future__ import annotations

import requests
import pytest

from acorn.lightning import (
    InvalidLightningAddressError,
    lightning_address_pay,
)


def test_lightning_address_lookup_failure_raises_clear_error(monkeypatch) -> None:
    def failed_get(*args, **kwargs):
        raise requests.HTTPError("404 Not Found")

    monkeypatch.setattr("acorn.lightning.requests.get", failed_get)

    with pytest.raises(InvalidLightningAddressError, match="Not a valid Lightning address"):
        lightning_address_pay(21, "ordinary@example.com")


def test_lightning_address_pay_always_returns_three_values(monkeypatch) -> None:
    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return self.payload

    responses = iter(
        (
            Response(
                {
                    "callback": "https://pay.example.com/callback",
                    "safebox": False,
                    "nonce": "nonce-1",
                }
            ),
            Response({"pr": "lnbc210n1test"}),
        )
    )
    monkeypatch.setattr(
        "acorn.lightning.requests.get",
        lambda *args, **kwargs: next(responses),
    )

    callback, safebox, nonce = lightning_address_pay(
        21,
        "alice@example.com",
        comment="test",
    )

    assert callback == {"pr": "lnbc210n1test"}
    assert safebox is False
    assert nonce == "nonce-1"
