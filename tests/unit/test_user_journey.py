from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from tests.user_journey import positive_seconds, run_user_journey


def wallets():
    source = SimpleNamespace(
        load_data=AsyncMock(), get_balance=Mock(side_effect=[100, 107]),
        send_ecash_transfer=AsyncMock(return_value={"event_id": "funding"}),
        sweep_ecash_transfers=AsyncMock(return_value={"confirmed_count": 1, "accepted_amount": 7}),
    )
    wallet = SimpleNamespace(
        create_instance=AsyncMock(), load_data=AsyncMock(),
        get_balance=Mock(side_effect=[0, 31, 22, 22]),
        sweep_ecash_transfers=AsyncMock(return_value={"confirmed_count": 1, "accepted_amount": 31}),
        send_ecash_transfer=AsyncMock(return_value={"event_id": "return"}),
        put_record=AsyncMock(return_value="note"),
        get_record_safebox=AsyncMock(side_effect=[
            SimpleNamespace(tag=["note"], payload="My first private note"),
            SimpleNamespace(tag=["note"], payload="My edited private note"),
        ]),
        delete_record=AsyncMock(return_value={"status": "DELETE_REQUESTED", "delete_event_id": "delete"}),
        get_user_record_labels=AsyncMock(return_value=[]),
    )
    return source, wallet


async def journey(source, wallet, sleep):
    return await run_user_journey(source, wallet, relay="wss://test.example",
                                  recipient="new", source_recipient="source",
                                  label="note", sleep=sleep)


@pytest.mark.asyncio
async def test_journey_spaces_every_operation_and_verifies_net_fees():
    source, wallet = wallets()
    sleep = AsyncMock()
    result = await journey(source, wallet, sleep)
    assert result == {"received": 31, "returned": 7, "remaining": 22}
    assert [call.args[0] for call in sleep.await_args_list] == [
        30, 5, 30, 30, 5, 5, 30, 30, 5, 5, 30, 5, 30, 5, 30, 5,
    ]
    assert wallet.put_record.await_args_list[1].args == ("note", "My edited private note")
    wallet.sweep_ecash_transfers.assert_awaited_once_with(relays=["wss://test.example"], event_id="funding")
    source.sweep_ecash_transfers.assert_awaited_once_with(relays=["wss://test.example"], event_id="return")


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [RuntimeError("HTTP 429 Too Many Requests"), TimeoutError()])
async def test_failed_send_is_not_retried_and_records_are_untouched(error):
    source, wallet = wallets()
    wallet.send_ecash_transfer.side_effect = error
    with pytest.raises(type(error)):
        await journey(source, wallet, AsyncMock())
    wallet.send_ecash_transfer.assert_awaited_once()
    source.sweep_ecash_transfers.assert_not_awaited()
    wallet.put_record.assert_not_awaited()
    wallet.delete_record.assert_not_awaited()


@pytest.mark.asyncio
async def test_pending_receipt_stops_without_resending_or_spending():
    source, wallet = wallets()
    wallet.sweep_ecash_transfers.return_value = {"confirmed_count": 0, "provisional_count": 1}
    with pytest.raises(AssertionError, match="not finalized"):
        await journey(source, wallet, AsyncMock())
    source.send_ecash_transfer.assert_awaited_once()
    wallet.send_ecash_transfer.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_edited_record_is_not_a_pass():
    source, wallet = wallets()
    wallet.get_record_safebox.side_effect = None
    wallet.get_record_safebox.return_value = SimpleNamespace(tag=["note"], payload="My first private note")
    with pytest.raises(AssertionError):
        await journey(source, wallet, AsyncMock())
    wallet.delete_record.assert_not_awaited()


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "4.9"])
def test_invalid_action_pacing(value):
    with pytest.raises(ValueError):
        positive_seconds(value, 5)


@pytest.mark.asyncio
async def test_live_journey_requires_explicit_opt_in(monkeypatch):
    from tests.integration import test_user_journey_live as live
    monkeypatch.delenv("ACORN_RUN_USER_JOURNEY", raising=False)
    source_config = Mock()
    monkeypatch.setattr(live, "require_source_config", source_config)
    with pytest.raises(pytest.skip.Exception, match="authorize"):
        await live.test_live_first_time_user_journey({"relay": "wss://test.example"})
    source_config.assert_not_called()


@pytest.mark.asyncio
async def test_bootstrap_failure_reports_stage_before_any_funding():
    source, wallet = wallets()
    wallet.load_data.side_effect = RuntimeError("All relay queries failed: 503, message='Invalid response status'")
    stages = []
    with pytest.raises(RuntimeError):
        await run_user_journey(source, wallet, relay="wss://test.example", recipient="new",
                               source_recipient="source", label="note", sleep=AsyncMock(),
                               on_step=stages.append)
    assert stages == ["create wallet", "wallet bootstrap readback"]
    source.send_ecash_transfer.assert_not_awaited()


@pytest.mark.parametrize("error,expected", [
    (RuntimeError("All relay queries failed: 503, message='Invalid response status', url='wss://relay.damus.io/'"), "HTTP 503"),
    (RuntimeError("HTTP 502"), "HTTP 502"),
    (TimeoutError(), "timed out"),
    (RuntimeError("HTTP 429 Too Many Requests"), "HTTP 429"),
    (AssertionError("private payload"), "verification incomplete"),
    (RuntimeError("balance 503"), "verification incomplete"),
])
def test_incomplete_journey_is_not_protocol_incompatibility(monkeypatch, error, expected):
    from tests import helpers
    monkeypatch.setattr(helpers, "RELAY_SUITABILITY_RESULTS", {})
    monkeypatch.setattr(helpers, "UNSUITABLE_RELAYS", {})
    helpers.relay_suitable({"relay": "wss://test.example", "name": "third-party"}, "earlier-capability")
    helpers.report_user_journey_failure("wss://test.example", "wallet bootstrap readback", error, funding_started=False)
    row = helpers.relay_suitability_summary_rows()[0]
    assert row["status"] == "Inconclusive user suitability; journey incomplete"
    assert expected in row["observed"]
    assert "wallet bootstrap readback" in row["observed"]
    assert "no payment sent" in row["observed"]
    assert "earlier-capability" in row["observed"]
    assert "private payload" not in row["observed"]
    assert not helpers.UNSUITABLE_RELAYS


def test_failure_after_funding_never_claims_no_payment(monkeypatch):
    from tests import helpers
    monkeypatch.setattr(helpers, "RELAY_SUITABILITY_RESULTS", {})
    helpers.report_user_journey_failure("wss://test.example", "receive payment", TimeoutError(), funding_started=True)
    row = helpers.relay_suitability_summary_rows()[0]
    assert "inspect retained wallet and transfers" in row["observed"]
    assert "no payment sent" not in row["observed"]


def test_nested_preflight_timeout_is_reported_without_private_details(monkeypatch):
    from tests import helpers
    monkeypatch.setattr(helpers, "RELAY_SUITABILITY_RESULTS", {})
    timeout = TimeoutError("private payload")
    preflight = RuntimeError("Record preflight query timed out on: wss://test.example")
    preflight.__cause__ = timeout
    issuing = RuntimeError("Error issuing token: private payload")
    issuing.__cause__ = preflight
    helpers.report_user_journey_failure("wss://test.example", "send payment back", issuing, funding_started=True)
    row = helpers.relay_suitability_summary_rows()[0]
    assert row["status"] == "Inconclusive user suitability; journey incomplete"
    assert "send payment back: operation timed out" in row["observed"]
    assert "inspect retained wallet and transfers" in row["observed"]
    assert "private payload" not in row["observed"]


def test_implicit_timeout_context_is_recognized():
    from tests.helpers import is_timeout_error
    error = RuntimeError("wrapped")
    error.__context__ = TimeoutError()
    assert is_timeout_error(error)


def test_suppressed_timeout_context_is_not_classified():
    from tests.helpers import is_timeout_error
    error = RuntimeError("unrelated failure")
    error.__context__ = TimeoutError()
    error.__suppress_context__ = True
    assert not is_timeout_error(error)


def test_explicit_cause_takes_precedence_over_timeout_context():
    from tests.helpers import is_timeout_error
    error = RuntimeError("wrapped")
    error.__context__ = TimeoutError()
    error.__cause__ = ValueError("actual cause")
    assert not is_timeout_error(error)


def test_exception_chain_cycles_terminate_without_text_guessing():
    from tests.helpers import is_timeout_error
    outer = RuntimeError("timed out text alone is not a typed timeout")
    inner = RuntimeError("other failure")
    outer.__cause__ = inner
    inner.__cause__ = outer
    assert not is_timeout_error(outer)


@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("error,expected", [
    (RuntimeError("All relay queries failed: Relay wss://relay.notoshi.win/ closed before EOSE"), "connection closed before query completion (EOSE)"),
    (RuntimeError("Event was acknowledged by 0/1 relays; Relay wss://relay.trustroots.org/ rejected " + "a" * 64 + ": 403"), "access/policy blocked (status 403)"),
    (RuntimeError("401, message='Invalid response status'"), "access/policy blocked (status 401)"),
    (RuntimeError("HTTP 429 Too Many Requests"), "HTTP 429 rate-limited"),
    (RuntimeError("503, message='Invalid response status'"), "HTTP 503 service unavailable"),
    (ConnectionResetError("private payload"), "connection closed or interrupted"),
    (TimeoutError("private payload"), "operation timed out"),
])
def test_transport_categories_preserve_funding_and_stage(monkeypatch, wrapped, error, expected):
    from tests import helpers
    monkeypatch.setattr(helpers, "RELAY_SUITABILITY_RESULTS", {})
    monkeypatch.setattr(helpers, "UNSUITABLE_RELAYS", {})
    if wrapped:
        outer = RuntimeError("private payload")
        outer.__cause__ = error
        error = outer
    helpers.report_user_journey_failure("wss://test.example", "create wallet", error, funding_started=False)
    row = helpers.relay_suitability_summary_rows()[0]
    assert expected in row["observed"]
    assert "create wallet" in row["observed"]
    assert "no payment sent" in row["observed"]
    assert "private payload" not in row["observed"]
    assert row["status"] == "Inconclusive user suitability; journey incomplete"
    assert not helpers.UNSUITABLE_RELAYS


@pytest.mark.parametrize("attribute,code,expected", [
    ("status", 403, "access/policy blocked"),
    ("status_code", 429, "rate-limited"),
    ("status", 503, "service unavailable"),
])
def test_structured_transport_status(attribute, code, expected):
    from tests.helpers import user_journey_failure_reason
    error = RuntimeError("private payload")
    setattr(error, attribute, code)
    assert expected in user_journey_failure_reason(error)


@pytest.mark.parametrize("message", ["balance 403", "record contains closed before EOSE", "403 credits", "connection information"])
def test_unrelated_text_is_not_a_transport_classification(message):
    from tests.helpers import user_journey_failure_reason
    assert "verification incomplete" in user_journey_failure_reason(RuntimeError(message))


def test_transport_categories_respect_suppressed_context_and_cycles():
    from tests.helpers import user_journey_failure_reason
    error = RuntimeError("unrelated")
    error.__context__ = RuntimeError("HTTP 403")
    error.__suppress_context__ = True
    assert "verification incomplete" in user_journey_failure_reason(error)
    error.__cause__ = error
    assert "verification incomplete" in user_journey_failure_reason(error)
