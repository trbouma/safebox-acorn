from __future__ import annotations

import asyncio
import contextlib
import os

import pytest
import pytest_asyncio
from monstr.encrypt import Keys

from acorn.acorn import Acorn

from tests.helpers import (
    ensure_test_wallet_config,
    get_test_transfer_relay,
    remove_test_wallet_config,
    require_env,
    require_source_config,
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
        pytest.skip(f"{label} timed out after {timeout:g}s")


@pytest_asyncio.fixture(autouse=True)
async def cleanup_monstr_clients():
    yield
    await _drain_monstr_tasks()


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_burn_wallet_sweeps_remaining_funds(monkeypatch):
    env = require_env("ACORN_RECEIVE_NSEC")
    source_config = require_source_config()
    amount = int(os.getenv("ACORN_TEST_AMOUNT", "1"))
    timeout = float(os.getenv("ACORN_TEST_TIMEOUT", "15"))

    configured_path = os.getenv("ACORN_TEST_WALLET_CONFIG", "./.acorn-test/test-wallet.yml")
    if configured_path.endswith(".yml"):
        burn_config_path = configured_path[:-4] + "-burn.yml"
    else:
        burn_config_path = configured_path + ".burn.yml"
    monkeypatch.setenv("ACORN_TEST_WALLET_CONFIG", burn_config_path)

    test_wallet_config = await _await_or_skip(
        ensure_test_wallet_config(),
        "burn test wallet init",
        timeout,
    )

    source_nsec = source_config["nsec"]
    source_relay = source_config["home_relay"]
    test_nsec = test_wallet_config["nsec"]
    test_relay = test_wallet_config["home_relay"]
    transfer_relay = get_test_transfer_relay(test_relay)
    test_recipient = Keys(priv_k=env["ACORN_RECEIVE_NSEC"]).public_key_bech32()
    source_recipient = Keys(priv_k=source_nsec).public_key_bech32()

    source_wallet = Acorn(
        nsec=source_nsec,
        home_relay=source_relay,
        relays=[source_relay],
    )
    await _await_or_skip(source_wallet.load_data(), "source wallet load", timeout)
    if source_wallet.get_balance() < amount:
        pytest.skip(
            "source wallet must have enough spendable balance for the burn live "
            f"test: balance={source_wallet.get_balance()}, amount={amount}"
        )

    test_wallet = Acorn(
        nsec=test_nsec,
        home_relay=test_relay,
        relays=[test_relay],
    )

    try:
        fund_transfer = await _await_or_skip(
            source_wallet.send_ecash_transfer(
                amount=amount,
                recipient=test_recipient,
                relay=transfer_relay,
                comment="pytest burn test funding",
            ),
            "burn test funding transfer",
            timeout,
        )
        assert fund_transfer["event_id"]

        await _await_or_skip(test_wallet.load_data(), "funded test wallet load", timeout)
        receiver_before = test_wallet.get_balance()
        receive = await _await_or_skip(
            test_wallet.sweep_ecash_transfers(
                relays=[transfer_relay],
                receive_nsec=env["ACORN_RECEIVE_NSEC"],
                event_id=fund_transfer["event_id"],
            ),
            "burn test wallet receive funding",
            timeout,
        )
        assert receive["accepted_amount"] == amount

        await _await_or_skip(test_wallet.load_data(), "funded test wallet reload", timeout)
        assert test_wallet.get_balance() >= receiver_before + amount

        burn_result = await _await_or_skip(
            test_wallet.burn_wallet(
                send_to=source_recipient,
                send_relay=transfer_relay,
                relays=[test_relay],
            ),
            "burn wallet",
            timeout,
        )

        assert burn_result["balance_before"] >= amount
        assert burn_result["sweep"] is not None
        assert burn_result["sweep"]["amount"] >= amount
        assert burn_result["sweep"]["event_id"]
        assert burn_result["delete_event_id"]

        sweep_back = await _await_or_skip(
            source_wallet.sweep_ecash_transfers(
                relays=[transfer_relay],
                event_id=burn_result["sweep"]["event_id"],
            ),
            "source wallet receive burn sweep",
            timeout,
        )
        assert sweep_back["accepted_amount"] >= amount

    finally:
        with contextlib.suppress(Exception):
            await _await_or_skip(
                test_wallet.burn_wallet(allow_funded=True, relays=[test_relay]),
                "burn test cleanup",
                timeout,
            )
        remove_test_wallet_config(test_wallet_config)
