from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests import helpers


@pytest.fixture(autouse=True)
def isolated_results(monkeypatch):
    monkeypatch.setattr(helpers, "RELAY_SUITABILITY_RESULTS", {})
    monkeypatch.setattr(helpers, "UNSUITABLE_RELAYS", {})


@pytest.mark.parametrize("earlier_pass", [False, True])
def test_rate_limit_is_inconclusive_not_unsuitable(earlier_pass):
    relay = "wss://nos.lol"
    if earlier_pass:
        helpers.relay_suitable({"relay": relay, "name": "third-party"}, "private-records")
    helpers.relay_unsuitable(relay, "bootstrap", "unreadable",
        error=RuntimeError("All relay queries failed: 429, message='Invalid response status'"))
    row = helpers.relay_suitability_summary_rows()[0]
    assert row["status"] == "Rate-limited; suitability not fully reassessed"
    assert relay not in helpers.UNSUITABLE_RELAYS
    if earlier_pass: assert "Passed private-records" in row["observed"]
    with pytest.raises(pytest.skip.Exception, match="rate-limited"):
        helpers.skip_if_relay_unsuitable(relay)


def test_actual_incompatibility_not_hidden_by_later_rate_limit():
    helpers.relay_unsuitable("wss://nos.lol", "bootstrap", "unsupported kind")
    helpers.relay_rate_limited("wss://nos.lol", "records", "HTTP 429")
    assert helpers.relay_suitability_summary_rows()[0]["status"] == "Unsuitable as tested"


@pytest.mark.asyncio
async def test_initial_rate_limit_does_not_attempt_wallet_creation(monkeypatch):
    wallet = SimpleNamespace(load_data=AsyncMock(side_effect=RuntimeError(
        "All relay queries failed: 429, message='Invalid response status'")), create_instance=AsyncMock())
    monkeypatch.setattr("acorn.acorn.Acorn", lambda **kwargs: wallet)
    with pytest.raises(pytest.skip.Exception, match="rate-limited"):
        await helpers.initialize_test_wallet_config({"nsec": "test", "home_relay": "wss://nos.lol"})
    wallet.create_instance.assert_not_awaited()


def test_incoming_rate_limit_skips_without_claiming_finalization():
    result = {"relays": ["wss://nos.lol"], "failed": [{"reason":
        "Unable to read wallet lock: 429, message='Invalid response status', url='wss://nos.lol'"}]}
    with pytest.raises(pytest.skip.Exception, match="rate-limited"):
        helpers.confirmed_transfer_amount(result, 10)


def test_mint_rate_limit_not_misattributed_to_relay():
    with pytest.raises(AssertionError):
        helpers.confirmed_transfer_amount({"relays": ["wss://nos.lol"], "failed": [
            {"reason": "HTTP 429 from https://mint.example"}]}, 10)
    assert not helpers.RELAY_SUITABILITY_RESULTS
