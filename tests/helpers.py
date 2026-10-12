from __future__ import annotations

import os
import re
import asyncio
from pathlib import Path
from time import monotonic
from time import strftime
from typing import Callable

import pytest
import yaml


UNSUITABLE_RELAYS: dict[str, str] = {}
RELAY_SUITABILITY_RESULTS: dict[str, dict] = {}
DEFAULT_TEST_MINT = "https://mint.getsafebox.app"


def confirmed_transfer_amount(result: dict, tendered: int) -> int:
    """Require finalized value, not merely a stored provisional receipt."""
    for failure in result.get("failed", []):
        reason = str(failure.get("reason", ""))
        if is_rate_limit_error(reason):
            for relay in result.get("relays", []):
                if relay in reason:
                    relay_rate_limited(relay, "incoming-transfer", "HTTP 429 while accessing relay")
                    skip_if_relay_unsuitable(relay)
    assert result.get("confirmed_count") == 1, (
        "Transfer was not finalized. Check op=sweep_ecash_transfers status=pending "
        "logs for the matching event_id; acceptance_error_type identifies the exception class.", result
    )
    assert result.get("provisional_count", 0) == 0, result
    assert not result.get("failed"), result
    amount = int(result["accepted_amount"])
    assert 0 < amount <= tendered, result
    return amount


def _relay_result(relay: str) -> dict:
    relay = normalize_relay(relay)
    result = RELAY_SUITABILITY_RESULTS.setdefault(
        relay,
        {
            "relay": relay,
            "scenario": None,
            "started_at": monotonic(),
            "capabilities": {},
            "unsuitable": [],
        },
    )
    return result


def live_progress(message: str, **details) -> None:
    """Print live-test progress when pytest output capture is disabled."""

    suffix = ""
    if details:
        rendered = ", ".join(f"{key}={value}" for key, value in details.items())
        suffix = f" ({rendered})"
    print(f"[{strftime('%H:%M:%S')}] {message}{suffix}", flush=True)


async def wait_for_tx_history_entry(
    wallet,
    predicate: Callable[[dict], bool],
    timeout: float,
    label: str,
    interval: float = 1.0,
) -> list[dict]:
    """Poll relay-backed tx history until a matching entry is readable."""

    deadline = monotonic() + timeout
    last_history: list[dict] = []
    while monotonic() < deadline:
        last_history = await wallet.get_tx_history()
        if any(predicate(entry) for entry in last_history):
            live_progress("transaction history readback passed", label=label)
            return last_history
        await asyncio.sleep(interval)

    live_progress(
        "transaction history readback missing",
        label=label,
        entries=len(last_history),
        timeout=f"{timeout:g}s",
    )
    return last_history


def is_source_wallet_environment_error(exc: Exception) -> bool:
    """Return true for failures outside the relay currently under test."""

    message = str(exc)
    return (
        "already spent" in message
        or "Local wallet proof state is stale" in message
        or "Retry payment after wallet state refresh" in message
        or "Proof publish could not be verified" in message
        or "error writing proofs" in message
    )


def relay_suitable(scenario: dict, capability: str, **details) -> None:
    result = _relay_result(scenario["relay"])
    result["scenario"] = scenario["name"]
    result["capabilities"][capability] = {
        "status": "suitable",
        "details": details,
    }
    live_progress(
        "SUITABLE relay capability",
        scenario=scenario["name"],
        relay=scenario["relay"],
        capability=capability,
        **details,
    )


def start_relay_suitability(scenario: dict) -> None:
    """Start timing a relay scenario before its first live capability check."""

    result = _relay_result(scenario["relay"])
    result["scenario"] = scenario["name"]


def relay_unsuitable(relay: str, capability: str, reason: str, **details) -> None:
    if is_rate_limit_error(details.get("error", "")):
        relay_rate_limited(relay, capability, "HTTP 429 while accessing relay")
        return
    relay = normalize_relay(relay)
    UNSUITABLE_RELAYS[relay] = f"{capability}: {reason}"
    result = _relay_result(relay)
    result["capabilities"][capability] = {
        "status": "unsuitable",
        "reason": reason,
        "details": details,
    }
    result["unsuitable"].append(f"{capability}: {reason}")
    live_progress(
        "UNSUITABLE relay capability",
        relay=relay,
        capability=capability,
        reason=reason,
        **details,
    )


def is_rate_limit_error(error) -> bool:
    if getattr(error, "status", None) == 429 or getattr(error, "status_code", None) == 429:
        return True
    return bool(re.search(r"\b429(?:, message=|\s+Too Many Requests|\s+Client Error)|HTTP\s+429\b", str(error), re.I))


def relay_rate_limited(relay: str, capability: str, reason: str) -> None:
    result = _relay_result(relay)
    result.setdefault("rate_limited", []).append(f"{capability}: {reason}")
    live_progress("RATE-LIMITED relay; suitability not fully reassessed",
                  relay=normalize_relay(relay), capability=capability)


def exception_chain(error: BaseException):
    """Walk visible causes/contexts once, respecting suppressed context."""
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        yield error
        error = error.__cause__ if error.__cause__ is not None else (
            None if error.__suppress_context__ else error.__context__
        )


def is_timeout_error(error: BaseException) -> bool:
    """Recognize wrapped timeouts using the displayed exception chain, not text."""
    return any(isinstance(cause, TimeoutError) for cause in exception_chain(error))


def user_journey_failure_reason(error: Exception) -> str:
    """Classify known transport errors without exposing arbitrary error payloads."""
    causes = list(exception_chain(error))
    for cause in causes:
        code = getattr(cause, "status", None) or getattr(cause, "status_code", None)
        if code is None:
            # Stroma may flatten HTTP exceptions or event-rejection responses.
            match = re.search(
                r"HTTP\s+([45]\d\d)\b|"
                r"\b([45]\d\d)(?=, message=|\s+(?:Server Error|Client Error|Service Unavailable|Bad Gateway|Gateway Timeout|Forbidden|Unauthorized|Too Many Requests))|"
                r"\bRelay\s+wss?://\S+\s+rejected\s+[0-9a-f]{64}:\s*(401|403|429)(?=$|[;\s])",
                str(cause), re.I,
            )
            code = next((int(group) for group in match.groups() if group), None) if match else None
        if str(code).isdigit() and 500 <= int(code) <= 599:
            return f"HTTP {code} service unavailable/server error; responsible service requires investigation"
        if str(code) in {"401", "403"}:
            return f"access/policy blocked (status {code}); inspect authentication and publication policies"
        if str(code) == "429" or is_rate_limit_error(cause):
            return "HTTP 429 rate-limited; responsible service requires investigation"
    if is_timeout_error(error):
        return "operation timed out; outcome requires inspection"
    for cause in causes:
        if re.search(r"\bRelay\s+wss?://\S+\s+closed before EOSE\b", str(cause), re.I):
            return "connection closed before query completion (EOSE); response is incomplete, not an empty result"
        if isinstance(cause, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return "connection closed or interrupted; operation outcome requires inspection"
    return f"operation or verification incomplete ({type(error).__name__})"


def report_user_journey_failure(relay: str, stage: str, error: Exception, *, funding_started: bool) -> None:
    """Record incomplete user evidence without declaring protocol incompatibility.

    Do not echo exception text: it can contain private wallet data or payloads.
    A service error can originate at the relay, mint, or another dependency.
    """
    reason = user_journey_failure_reason(error)
    funding = "funding may have started; inspect retained wallet and transfers" if funding_started else "funding not started; no payment sent by this journey"
    detail = f"paced-first-time-user-journey: {stage}: {reason}; {funding}"
    _relay_result(relay).setdefault("incomplete_user_journeys", []).append(detail)
    live_progress("INCONCLUSIVE user suitability", relay=normalize_relay(relay),
                  stage=stage, reason=reason, funding=funding)


def relay_suitability_summary_rows() -> list[dict]:
    rows = []
    for relay, result in sorted(RELAY_SUITABILITY_RESULTS.items()):
        capabilities = result["capabilities"]
        suitable_caps = [
            capability
            for capability, capability_result in capabilities.items()
            if capability_result.get("status") == "suitable"
        ]
        unsuitable = result["unsuitable"]
        rate_limited = result.get("rate_limited", [])
        elapsed = max(0.0, monotonic() - result["started_at"])
        status = "Suitable" if suitable_caps and not unsuitable else "Unsuitable as tested"
        if not suitable_caps and not unsuitable:
            status = "No suitability result"
        if unsuitable:
            observed = "; ".join(unsuitable)
        elif suitable_caps:
            observed = "Passed " + ", ".join(sorted(suitable_caps))
        else:
            observed = "No relay capabilities completed"
        if rate_limited:
            if not unsuitable:
                status = "Rate-limited; suitability not fully reassessed"
            observed += "; " + "; ".join(rate_limited)
        incomplete = result.get("incomplete_user_journeys", [])
        if incomplete:
            if not unsuitable:
                status = "Inconclusive user suitability; journey incomplete"
            observed += "; " + "; ".join(incomplete)
        rows.append(
            {
                "relay": relay,
                "scenario": result.get("scenario") or "",
                "status": status,
                "observed": observed,
                "elapsed": elapsed,
            }
        )
    return rows


def skip_if_relay_unsuitable(relay: str) -> None:
    relay = normalize_relay(relay)
    if RELAY_SUITABILITY_RESULTS.get(relay, {}).get("rate_limited"):
        pytest.skip(f"{relay} rate-limited this run (HTTP 429); suitability not fully reassessed. Later checks skipped to avoid additional load.")
    reason = UNSUITABLE_RELAYS.get(relay)
    if not reason:
        return
    live_progress(
        "SKIPPED relay scenario previously marked unsuitable",
        relay=relay,
        reason=reason,
    )
    pytest.skip(
        f"relay scenario skipped because {relay} was already marked "
        f"unsuitable in this pytest run: {reason}"
    )


def live_relay_scenarios() -> list:
    """Return relay scenarios for live tests.

    The controlled scenario always runs. If ACORN_THIRD_PARTY_RELAY is set, the
    same live tests run again using that relay and a separate disposable wallet
    config suffix.
    """
    selected = os.getenv("ACORN_RELAY_SCENARIO", "all").strip().lower()
    valid = {"all", "controlled", "third-party", "third_party"}
    if selected not in valid:
        pytest.skip(
            "ACORN_RELAY_SCENARIO must be one of: all, controlled, third-party"
        )

    scenarios = []
    if selected in {"all", "controlled"}:
        scenarios.append(
            pytest.param(
                {
                    "name": "controlled",
                    "relay": normalize_relay(os.getenv("ACORN_TEST_RELAY", "ws://beelink:7777")),
                    "config_suffix": "",
                },
                id="controlled-relay",
            )
        )
    third_party_relay = os.getenv("ACORN_THIRD_PARTY_RELAY")
    if selected in {"all", "third-party", "third_party"} and third_party_relay:
        scenarios.append(
            pytest.param(
                {
                    "name": "third-party",
                    "relay": normalize_relay(third_party_relay),
                    "config_suffix": "-third-party",
                },
                id="third-party-relay",
            )
        )
    if selected in {"third-party", "third_party"} and not third_party_relay:
        pytest.skip("ACORN_THIRD_PARTY_RELAY is required when ACORN_RELAY_SCENARIO=third-party")
    return scenarios


def normalize_relay(relay: str) -> str:
    relay = str(relay).strip()
    if relay.startswith(("wss://", "ws://")):
        return relay
    return f"wss://{relay}"


def normalize_mint(mint: str) -> str:
    mint = str(mint).strip()
    if mint.startswith(("https://", "http://")):
        return mint
    return f"https://{mint}"


def truthy_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def require_env(*names: str) -> dict[str, str]:
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        pytest.skip(f"missing env vars: {', '.join(missing)}")
    return {name: os.environ[name] for name in names}


def require_env_value(name: str, *fallback_names: str) -> str:
    for candidate in (name, *fallback_names):
        value = os.getenv(candidate)
        if value:
            return value

    expected = ", ".join((name, *fallback_names))
    pytest.skip(f"missing env var: one of {expected}")


def require_config(path: str | Path, label: str) -> dict:
    config_path = Path(path).expanduser()
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    if not config_path.exists():
        pytest.skip(f"{label} config file does not exist: {config_path}")

    with config_path.open("r") as file:
        config = yaml.safe_load(file) or {}

    if not config.get("nsec"):
        pytest.skip(f"{label} config is missing nsec: {config_path}")
    if not config.get("home_relay"):
        pytest.skip(f"{label} config is missing home_relay: {config_path}")

    config["_path"] = str(config_path)
    return config


def optional_config(path: str | Path) -> dict | None:
    config_path = Path(path).expanduser()
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    if not config_path.exists():
        return None

    with config_path.open("r") as file:
        config = yaml.safe_load(file) or {}

    if not config.get("nsec") or not config.get("home_relay"):
        return None

    config["_path"] = str(config_path)
    return config


def require_source_config() -> dict:
    source_path = os.getenv("ACORN_SOURCE_CONFIG", "~/.acorn/config.yml")
    return require_config(source_path, "source wallet")


def optional_source_config() -> dict | None:
    source_path = os.getenv("ACORN_SOURCE_CONFIG", "~/.acorn/config.yml")
    return optional_config(source_path)


def _add_config_suffix(path: Path, suffix: str = "") -> Path:
    if not suffix:
        return path
    return path.with_name(f"{path.stem}{suffix}{path.suffix}")


def require_test_wallet_config(relay: str | None = None, config_suffix: str = "") -> dict:
    test_path = get_test_wallet_config_path(config_suffix=config_suffix)
    config = require_config(test_path, "test wallet")
    if relay:
        config["home_relay"] = normalize_relay(relay)
    elif os.getenv("ACORN_TEST_RELAY"):
        config["home_relay"] = normalize_relay(os.environ["ACORN_TEST_RELAY"])
    return config


def get_test_transfer_relay(default_relay: str, relay: str | None = None) -> str:
    return normalize_relay(os.getenv("ACORN_TEST_TRANSFER_RELAY") or relay or os.getenv("ACORN_TEST_RELAY") or default_relay)


def get_test_wallet_config_path(config_suffix: str = "") -> Path:
    config_path = Path(os.getenv("ACORN_TEST_WALLET_CONFIG", "./.acorn-test/test-wallet.yml")).expanduser()
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    return _add_config_suffix(config_path, config_suffix)


def configured_test_mints(fallback_mints: list[str] | None = None) -> list[str]:
    if os.getenv("ACORN_TEST_MINT"):
        return [normalize_mint(each) for each in os.environ["ACORN_TEST_MINT"].split(",") if each.strip()]
    if fallback_mints:
        return [normalize_mint(each) for each in fallback_mints if str(each).strip()]
    return [DEFAULT_TEST_MINT]


async def resolve_test_mints(fallback_mints: list[str] | None = None) -> list[str]:
    explicit_mints = configured_test_mints(fallback_mints=None)
    if os.getenv("ACORN_TEST_MINT"):
        return explicit_mints

    source_config = optional_source_config()
    if source_config:
        try:
            from acorn.acorn import Acorn

            source_wallet = Acorn(
                nsec=source_config["nsec"],
                home_relay=normalize_relay(source_config["home_relay"]),
                relays=[normalize_relay(source_config["home_relay"])],
                mints=source_config.get("mints"),
            )
            await source_wallet.load_data()
            if source_wallet.home_mint:
                resolved = normalize_mint(source_wallet.home_mint)
                live_progress("test mint inherited from source wallet", mint=resolved)
                return [resolved]
        except Exception as exc:
            live_progress("test mint inheritance unavailable", source=source_config.get("_path"), error=exc)

    return configured_test_mints(fallback_mints=fallback_mints)


def write_test_wallet_config(
    nsec: str,
    home_relay: str,
    config_suffix: str = "",
    mints: list[str] | None = None,
) -> dict:
    config_path = get_test_wallet_config_path(config_suffix=config_suffix)
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        pytest.skip(f"could not create test wallet config directory {config_path.parent}: {exc}")
    config = {
        "nsec": nsec,
        "home_relay": normalize_relay(home_relay),
        "mints": configured_test_mints(fallback_mints=mints),
        "test_wallet": True,
    }
    try:
        with config_path.open("w") as file:
            yaml.safe_dump(config, file)
    except OSError as exc:
        pytest.skip(f"could not write test wallet config {config_path}: {exc}")
    config["_path"] = str(config_path)
    return config


async def ensure_test_wallet_config(relay: str | None = None, config_suffix: str = "") -> dict:
    config_path = get_test_wallet_config_path(config_suffix=config_suffix)
    if relay:
        skip_if_relay_unsuitable(relay)
    if config_path.exists():
        config = require_test_wallet_config(relay=relay, config_suffix=config_suffix)
        config.setdefault("test_wallet", True)
        config["mints"] = await resolve_test_mints(fallback_mints=config.get("mints"))
        if relay:
            config["home_relay"] = normalize_relay(relay)
        elif os.getenv("ACORN_TEST_RELAY"):
            config["home_relay"] = normalize_relay(os.environ["ACORN_TEST_RELAY"])
        skip_if_relay_unsuitable(config["home_relay"])
        if truthy_env("ACORN_TEST_CREATE_WALLET", "true"):
            config["test_wallet"] = True
            try:
                with config_path.open("w") as file:
                    yaml.safe_dump({k: v for k, v in config.items() if not k.startswith("_")}, file)
            except OSError as exc:
                pytest.skip(f"could not update disposable test wallet config {config_path}: {exc}")
            await initialize_test_wallet_config(config)
        return config

    if not truthy_env("ACORN_TEST_CREATE_WALLET", "true"):
        pytest.skip(f"test wallet config file does not exist: {config_path}")

    from stroma import Keys

    test_relay = normalize_relay(relay or os.getenv("ACORN_TEST_RELAY", "ws://beelink:7777"))
    test_mints = await resolve_test_mints()
    config = write_test_wallet_config(
        Keys().private_key_bech32(),
        test_relay,
        config_suffix=config_suffix,
        mints=test_mints,
    )
    await initialize_test_wallet_config(config)
    return config


async def initialize_test_wallet_config(config: dict) -> None:
    from acorn.acorn import Acorn

    acorn = Acorn(
        nsec=config["nsec"],
        home_relay=config["home_relay"],
        relays=[config["home_relay"]],
        mints=config.get("mints"),
    )
    try:
        await acorn.load_data()
        return
    except Exception as exc:
        if is_rate_limit_error(exc):
            relay_rate_limited(config["home_relay"], "wallet-bootstrap-readback", "HTTP 429 on initial read")
            skip_if_relay_unsuitable(config["home_relay"])

    try:
        await acorn.create_instance(keepkey=True)
        await acorn.load_data()
    except Exception as exc:
        relay_unsuitable(
            relay=config["home_relay"],
            capability="wallet-bootstrap-readback",
            reason="wallet bootstrap state was not readable after initialization",
            error=exc,
        )
        if is_rate_limit_error(exc):
            skip_if_relay_unsuitable(config["home_relay"])
        pytest.skip(
            "relay compatibility: wallet bootstrap state was not readable "
            f"after initialization on {config['home_relay']}. "
            "This relay may reject, filter, fail to retain, or fail to return "
            f"Acorn wallet events. Original error: {exc}"
        )


def should_burn_test_wallet(config: dict) -> bool:
    if not truthy_env("ACORN_TEST_BURN_AFTER", "true"):
        return False
    return bool(config.get("test_wallet")) or truthy_env("ACORN_TEST_BURN_EXISTING", "false")


def remove_test_wallet_config(config: dict) -> None:
    path_value = config.get("_path")
    if not path_value:
        return
    path = Path(path_value)
    if path.exists():
        path.unlink()


async def cleanup_empty_test_wallet(wallet, config: dict, relays: list[str], timeout: float) -> bool:
    """Only remove a disposable wallet after confirmed empty, settled readback."""
    try:
        await asyncio.wait_for(wallet.load_data(), timeout)
        receipts = await asyncio.wait_for(wallet.get_continuity_receipts(status="provisional"), timeout)
        if wallet.get_balance() or receipts:
            raise RuntimeError("wallet has funds or pending receipts")
        await asyncio.wait_for(wallet.burn_wallet(relays=relays), timeout)
    except Exception as exc:
        live_progress("Cleanup retained wallet records and config for recovery",
                      config=config.get("_path"), error_type=type(exc).__name__)
        return False
    remove_test_wallet_config(config)
    return True
