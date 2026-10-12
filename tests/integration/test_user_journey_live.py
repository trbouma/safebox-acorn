"""Explicitly enabled, paced relay suitability test using real funds."""
import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest
from stroma import Keys

from acorn.acorn import Acorn
from tests.helpers import (
    is_rate_limit_error, live_progress, live_relay_scenarios,
    relay_rate_limited, relay_suitable, require_source_config, report_user_journey_failure,
    skip_if_relay_unsuitable, start_relay_suitability, write_test_wallet_config,
)
from tests.user_journey import positive_seconds, run_user_journey


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("relay_scenario", live_relay_scenarios())
async def test_live_first_time_user_journey(relay_scenario):
    if os.getenv("ACORN_RUN_USER_JOURNEY") != "1":
        pytest.skip("Set ACORN_RUN_USER_JOURNEY=1 to authorize the paced, funded journey")
    action_pause = positive_seconds(os.getenv("ACORN_USER_ACTION_PAUSE", "30"), 5)
    read_pause = positive_seconds(os.getenv("ACORN_USER_READ_PAUSE", "5"), 1)
    timeout = positive_seconds(os.getenv("ACORN_USER_STEP_TIMEOUT", "120"), 1)
    amount = int(os.getenv("ACORN_USER_RECEIVE_AMOUNT", "32"))
    send_amount = int(os.getenv("ACORN_USER_SEND_AMOUNT", "8"))
    if not 0 < send_amount < amount:
        raise ValueError("Require 0 < send amount < receive amount, with headroom for mint fees")
    relay = relay_scenario["relay"]
    skip_if_relay_unsuitable(relay)
    config = require_source_config()
    skip_if_relay_unsuitable(config["home_relay"])
    source = Acorn(nsec=config["nsec"], home_relay=config["home_relay"],
                   relays=[config["home_relay"]], mints=config.get("mints"))
    await asyncio.wait_for(source.load_data(), timeout=timeout)
    if source.get_balance() <= amount:
        pytest.skip(f"Funding wallet needs more than {amount} sats, including mint fee headroom")

    keys = Keys()
    run_id = uuid4().hex
    disposable = write_test_wallet_config(
        keys.private_key_bech32(), relay,
        config_suffix=f"-user-journey-{run_id}", mints=[source.home_mint],
    )
    Path(disposable["_path"]).chmod(0o600)
    wallet = Acorn(nsec=disposable["nsec"], home_relay=relay,
                   relays=[relay], mints=disposable["mints"])
    start_relay_suitability(relay_scenario)
    live_progress("user journey: recovery configuration saved", config=disposable["_path"])
    progress = {"stage": "before wallet creation", "funding_started": False}

    def on_step(stage):
        progress["stage"] = stage
        if stage == "send funding payment":
            progress["funding_started"] = True

    try:
        result = await run_user_journey(
            source, wallet, relay=relay, recipient=keys.public_key_bech32(),
            source_recipient=Keys(priv_k=config["nsec"]).public_key_bech32(),
            label=f"user-journey-{run_id}", amount=amount, send_amount=send_amount,
            action_pause=action_pause, read_pause=read_pause, timeout=timeout, on_step=on_step,
        )
        relay_suitable(relay_scenario, "paced-first-time-user-journey", **result)
    except Exception as exc:
        report_user_journey_failure(relay, progress["stage"], exc,
                                    funding_started=progress["funding_started"])
        if is_rate_limit_error(exc):
            # A mint or the source relay may be responsible; do not misattribute it.
            live_progress("user journey: rate limited; stopped without retry", error_type=type(exc).__name__)
            if relay in str(exc):
                relay_rate_limited(relay, "paced-first-time-user-journey", "HTTP 429 during journey")
        raise
    finally:
        live_progress("user journey: wallet retained; inspect before retrying",
                      config=disposable["_path"])
