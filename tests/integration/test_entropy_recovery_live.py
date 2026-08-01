from __future__ import annotations

import asyncio
import contextlib
import os
import secrets
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio

from acorn.acorn import Acorn
from acorn.func_utils import (
    recover_nsec_from_seed,
    seed_phrase_and_nsec_from_entropy,
)
from tests.helpers import (
    configured_test_mints,
    live_progress,
    live_relay_scenarios,
    relay_suitable,
    relay_unsuitable,
    remove_test_wallet_config,
    skip_if_relay_unsuitable,
    start_relay_suitability,
    write_test_wallet_config,
)


async def _drain_monstr_tasks():
    current = asyncio.current_task()
    pending = []
    for task in asyncio.all_tasks():
        if task is current or task.done():
            continue
        qualname = getattr(task.get_coro(), "__qualname__", "")
        if qualname.startswith(("Client.", "ClientPool.")):
            pending.append(task)

    for task in pending:
        task.cancel()

    if pending:
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(
                asyncio.gather(*pending, return_exceptions=True),
                timeout=2,
            )


async def _await_or_skip(awaitable, label: str, timeout: float):
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout)
    except asyncio.TimeoutError:
        await _drain_monstr_tasks()
        live_progress(
            "SKIPPED external entropy test step timed out",
            step=label,
            timeout=f"{timeout:g}s",
        )
        pytest.skip(f"{label} timed out after {timeout:g}s")


@pytest_asyncio.fixture(autouse=True)
async def cleanup_monstr_clients():
    yield
    await _drain_monstr_tasks()


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("relay_scenario", live_relay_scenarios())
async def test_live_external_entropy_init_recover_and_burn(relay_scenario):
    """Prove external entropy continuity against a live relay without funds."""

    timeout = float(os.getenv("ACORN_TEST_TIMEOUT", "15"))
    relay = relay_scenario["relay"]
    skip_if_relay_unsuitable(relay)
    start_relay_suitability(relay_scenario)
    config_suffix = (
        f"{relay_scenario['config_suffix']}-entropy-{uuid4().hex[:8]}"
    )
    entropy_hex = secrets.token_hex(32)
    seed_phrase, expected_nsec = seed_phrase_and_nsec_from_entropy(entropy_hex)
    test_mints = configured_test_mints()
    wallet_config = write_test_wallet_config(
        expected_nsec,
        relay,
        config_suffix=config_suffix,
        mints=test_mints,
    )
    config_path = Path(wallet_config["_path"])
    config_text = config_path.read_text(encoding="utf-8")
    if entropy_hex in config_text or seed_phrase in config_text:
        pytest.fail("temporary config exposed external entropy or its seed phrase")
    wallet = Acorn(
        nsec=expected_nsec,
        home_relay=relay,
        relays=[relay],
        mints=test_mints,
    )
    burned = False

    live_progress(
        "external entropy test: initializing disposable wallet",
        scenario=relay_scenario["name"],
        relay=relay,
        config=wallet_config["_path"],
        timeout=f"{timeout:g}s",
    )

    try:
        try:
            initialized_nsec = await _await_or_skip(
                wallet.create_instance(seed_phrase=seed_phrase),
                "external entropy wallet init",
                timeout,
            )
            if initialized_nsec != expected_nsec:
                pytest.fail("initialized wallet key did not match external entropy")

            live_progress("external entropy test: reading wallet bootstrap state")
            await _await_or_skip(
                wallet.load_data(),
                "external entropy wallet readback",
                timeout,
            )
        except RuntimeError as exc:
            relay_unsuitable(
                relay=relay,
                capability="external-entropy-bootstrap-recovery",
                reason="external-entropy wallet bootstrap state was not readable",
                error=exc,
            )
            pytest.skip(
                "relay compatibility: external-entropy wallet bootstrap state "
                f"was not readable on {relay}: {exc}"
            )

        if wallet.seed_phrase != seed_phrase:
            pytest.fail("wallet readback did not preserve the external-entropy phrase")
        if recover_nsec_from_seed(wallet.seed_phrase) != expected_nsec:
            pytest.fail("wallet readback phrase did not recover the expected identity")
        original_npub = wallet.pubkey_bech32

        live_progress("external entropy test: recovering identity from 24-word phrase")
        recovered_nsec = recover_nsec_from_seed(seed_phrase)
        if recovered_nsec != expected_nsec:
            pytest.fail("24-word phrase did not recover the expected identity")
        recovered_wallet = Acorn(
            nsec=recovered_nsec,
            home_relay=relay,
            relays=[relay],
            mints=test_mints,
        )
        try:
            await _await_or_skip(
                recovered_wallet.load_data(),
                "external entropy recovered wallet load",
                timeout,
            )
        except RuntimeError as exc:
            relay_unsuitable(
                relay=relay,
                capability="external-entropy-bootstrap-recovery",
                reason="recovered external-entropy identity could not read wallet state",
                error=exc,
            )
            pytest.skip(
                "relay compatibility: recovered external-entropy identity could "
                f"not read wallet state on {relay}: {exc}"
            )
        if recovered_wallet.pubkey_bech32 != original_npub:
            pytest.fail("recovered wallet did not preserve the original public identity")
        if recovered_wallet.seed_phrase != seed_phrase:
            pytest.fail("recovered wallet did not preserve the 24-word phrase")
        assert recovered_wallet.get_balance() == 0

        live_progress("external entropy test: burning unfunded disposable wallet")
        burn_result = await _await_or_skip(
            recovered_wallet.burn_wallet(relays=[relay]),
            "external entropy wallet burn",
            timeout,
        )
        assert burn_result["status"] == "OK"
        assert burn_result["balance_before"] == 0
        assert burn_result["sweep"] is None
        assert burn_result["matched"] >= 1
        assert burn_result["delete_event_id"]
        burned = True

        relay_suitable(
            relay_scenario,
            "external-entropy-bootstrap-recovery-burn",
            words=len(seed_phrase.split()),
            funded="no",
        )

    finally:
        if not burned:
            live_progress("external entropy test: cleanup burn disposable wallet")
            with contextlib.suppress(Exception):
                await _await_or_skip(
                    wallet.burn_wallet(allow_funded=True, relays=[relay]),
                    "external entropy wallet cleanup",
                    timeout,
                )
        remove_test_wallet_config(wallet_config)
        live_progress("external entropy test: temporary config removed")

    assert not config_path.exists()
