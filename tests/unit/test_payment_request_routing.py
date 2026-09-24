import logging
from unittest.mock import AsyncMock

import pytest

from acorn.acorn import Acorn, RetryablePreSwapError
from acorn.payment_request import decode_payment_request, is_public_relay_url


def wallet():
    result = Acorn.__new__(Acorn)
    result.pubkey_hex = "11" * 32
    result.home_relay = "ws://spurline:8080"
    result.public_relays = ["wss://discovery.example.com"]
    result.logger = logging.getLogger("request-routing-test")
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize("mint,balance,error,expected", [
    ("http://clear:3339", None, False, "mint must be accessible"),
    ("https://clear.example.com", None, False, "no matching Clear balance"),
    ("http://clear:3339", 1, False, "No single Clear keyset has enough credits"),
    ("https://clear.example.com", 1, False, "No single Clear keyset has enough credits"),
    ("http://clear:3339", 10, True, "internal mint that isn't accessible"),
    ("https://clear.example.com", 10, True, "isn't accessible from your wallet right now"),
])
async def test_request_errors_distinguish_accessibility_from_balance(mint, balance, error, expected):
    acorn = wallet()
    acorn.known_mints = {}
    acorn.get_clear_balances = AsyncMock(return_value=[] if balance is None else [{
        "mint": mint, "unit": "cmu-test",
        "keysets": [{"keyset": "test-keyset", "amount": balance}],
    }])
    acorn._keyset_input_fee_ppk = AsyncMock(return_value=0,
        side_effect=RetryablePreSwapError("connection failed") if error else None)
    request = acorn.create_payment_request(5, unit="cmu-test", mint=mint,
        relays=["wss://inbox.example.com"])
    with pytest.raises(ValueError, match=expected):
        await acorn.inspect_payment_request(request)
    if balance is None:
        acorn._keyset_input_fee_ppk.assert_not_awaited()


def test_internal_request_requires_explicit_operator_policy():
    acorn = wallet()
    with pytest.raises(ValueError, match="public inbox"):
        acorn.create_payment_request(5, mint="http://clear:3339",
            relays=["ws://spurline:8080"])
    encoded = acorn.create_payment_request(5, unit="cmu-test",
        mint="http://clear:3339", relays=["ws://spurline:8080"],
        allow_internal_relays=True)
    decoded = decode_payment_request(encoded)
    assert decoded.mints == ("http://clear:3339",)
    assert acorn._nut18_nostr_destination(decoded)[1] == ["ws://spurline:8080"]


@pytest.mark.parametrize("url", [
    "ws://spurline:8080", "ws://localhost:8080", "ws://127.0.0.1:8080",
    "ws://10.0.0.1", "ws://[::1]", "ws://relay.local", "ws://relay.internal",
    "https://relay.example.com", "wss://user:password@relay.example.com",
])
def test_internal_routes_are_not_advertised(url):
    assert not is_public_relay_url(url)


@pytest.mark.asyncio
async def test_request_uses_public_inbox_not_internal_home_or_discovery_relays():
    acorn = wallet()
    acorn.resolve_inbox_relays = AsyncMock(return_value={"relays": [
        "ws://spurline:8080", "wss://inbox.example.com",
    ]})
    relays = await acorn.get_payment_request_relays()
    encoded = acorn.create_payment_request(1, unit="cmu-test",
        mint="https://clear.example.com", relays=relays)
    _, advertised = acorn._nut18_nostr_destination(decode_payment_request(encoded))
    assert advertised == ["wss://inbox.example.com"]
    assert acorn.home_relay == "ws://spurline:8080"


@pytest.mark.asyncio
async def test_no_public_inbox_fails_without_advertising_discovery_relays():
    acorn = wallet()
    acorn.resolve_inbox_relays = AsyncMock(return_value={"relays": []})
    with pytest.raises(ValueError, match="No public inbox"):
        await acorn.get_payment_request_relays()
    with pytest.raises(ValueError, match="public inbox"):
        acorn.create_payment_request(1, mint="https://mint.example.com")


@pytest.mark.asyncio
async def test_public_home_is_valid_fallback():
    acorn = wallet()
    acorn.home_relay = "wss://home.example.com"
    acorn.resolve_inbox_relays = AsyncMock(return_value={"relays": []})
    assert await acorn.get_payment_request_relays() == [acorn.home_relay]


@pytest.mark.asyncio
async def test_unreachable_request_does_not_export_credits():
    acorn = wallet()
    request = acorn.create_payment_request(1, unit="cmu-test",
        mint="https://mint.example.com", relays=["wss://inbox.example.com"])
    acorn.inspect_payment_request = AsyncMock(return_value={"relays": ["wss://inbox.example.com"]})
    acorn._require_reachable_transfer_relays = AsyncMock(side_effect=RuntimeError("unreachable"))
    acorn.export_clear_token = AsyncMock()
    with pytest.raises(RuntimeError, match="unreachable"):
        await acorn.send_payment_request(request)
    acorn.export_clear_token.assert_not_awaited()
