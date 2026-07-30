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
    live_progress,
    live_relay_scenarios,
    relay_suitable,
    relay_unsuitable,
    remove_test_wallet_config,
    require_source_config,
    wait_for_tx_history_entry,
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
        live_progress("SKIPPED burn test step timed out", step=label, timeout=f"{timeout:g}s")
        pytest.skip(f"{label} timed out after {timeout:g}s")


@pytest_asyncio.fixture(autouse=True)
async def cleanup_monstr_clients():
    yield
    await _drain_monstr_tasks()


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("relay_scenario", live_relay_scenarios())
async def test_live_burn_wallet_sweeps_remaining_funds(monkeypatch, relay_scenario):
    live_progress(
        "burn test: loading configuration",
        scenario=relay_scenario["name"],
        relay=relay_scenario["relay"],
    )
    source_config = require_source_config()
    amount = int(os.getenv("ACORN_TEST_AMOUNT", "1"))
    timeout = float(os.getenv("ACORN_TEST_TIMEOUT", "15"))

    configured_path = os.getenv("ACORN_TEST_WALLET_CONFIG", "./.acorn-test/test-wallet.yml")
    if configured_path.endswith(".yml"):
        burn_config_path = configured_path[:-4] + "-burn.yml"
    else:
        burn_config_path = configured_path + ".burn.yml"
    monkeypatch.setenv("ACORN_TEST_WALLET_CONFIG", burn_config_path)

    live_progress("burn test: ensuring disposable burn wallet", config=burn_config_path, timeout=f"{timeout:g}s")
    test_wallet_config = await _await_or_skip(
        ensure_test_wallet_config(
            relay=relay_scenario["relay"],
            config_suffix=relay_scenario["config_suffix"],
        ),
        "burn test wallet init",
        timeout,
    )

    source_nsec = source_config["nsec"]
    source_relay = source_config["home_relay"]
    test_nsec = test_wallet_config["nsec"]
    test_relay = test_wallet_config["home_relay"]
    transfer_relay = get_test_transfer_relay(test_relay, relay=relay_scenario["relay"])
    receive_nsec = os.getenv("ACORN_RECEIVE_NSEC") or test_nsec
    if receive_nsec == test_nsec:
        live_progress("burn test: receive nsec inherited from disposable wallet")
    test_recipient = Keys(priv_k=receive_nsec).public_key_bech32()
    source_recipient = Keys(priv_k=source_nsec).public_key_bech32()

    live_progress("burn test: loading source wallet", relay=source_relay)
    source_wallet = Acorn(
        nsec=source_nsec,
        home_relay=source_relay,
        relays=[source_relay],
    )
    await _await_or_skip(source_wallet.load_data(), "source wallet load", timeout)
    live_progress("burn test: source balance loaded", balance=f"{source_wallet.get_balance()} sats")
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
        live_progress("burn test: funding disposable wallet", amount=f"{amount} sat", relay=transfer_relay)
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
        source_debit_history = await _await_or_skip(
            wait_for_tx_history_entry(
                source_wallet,
                lambda entry: entry.get("tx_type") == "D"
                and entry.get("amount") == amount
                and "pytest burn test funding" in entry.get("comment", ""),
                timeout,
                "source debit for burn test funding",
            ),
            "source debit transaction history readback",
            timeout + 2,
        )
        assert any(
            entry.get("tx_type") == "D"
            and entry.get("amount") == amount
            and "pytest burn test funding" in entry.get("comment", "")
            for entry in source_debit_history
        )

        live_progress("burn test: loading funded wallet")
        await _await_or_skip(test_wallet.load_data(), "funded test wallet load", timeout)
        receiver_before = test_wallet.get_balance()
        live_progress("burn test: receiving funding transfer", event=fund_transfer["event_id"][:12])
        receive = await _await_or_skip(
            test_wallet.sweep_ecash_transfers(
                relays=[transfer_relay],
                receive_nsec=receive_nsec,
                event_id=fund_transfer["event_id"],
            ),
            "burn test wallet receive funding",
            timeout,
        )
        assert receive["accepted_amount"] == amount

        live_progress("burn test: reloading funded wallet")
        await _await_or_skip(test_wallet.load_data(), "funded test wallet reload", timeout)
        assert test_wallet.get_balance() >= receiver_before + amount

        live_progress("burn test: burning wallet and sweeping funds back")
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

        live_progress("burn test: receiving burn sweep in source wallet", event=burn_result["sweep"]["event_id"][:12])
        sweep_back = await _await_or_skip(
            source_wallet.sweep_ecash_transfers(
                relays=[transfer_relay],
                event_id=burn_result["sweep"]["event_id"],
            ),
            "source wallet receive burn sweep",
            timeout,
        )
        if sweep_back["accepted_amount"] < amount:
            relay_unsuitable(
                relay=relay_scenario["relay"],
                capability="burn-sweep-transfer",
                reason="burn sweep transfer was published but not accepted",
                transfer_relay=transfer_relay,
                event=burn_result["sweep"]["event_id"][:12],
                expected=f"{amount} sats",
                accepted=f"{sweep_back['accepted_amount']} sats",
                queried=sweep_back.get("queried_count"),
        )
        assert sweep_back["accepted_amount"] >= amount, (
            "relay compatibility: burn sweep transfer was published but the "
            "source wallet did not accept the expected sats. "
            f"scenario={relay_scenario['name']} "
            f"relay={relay_scenario['relay']} "
            f"transfer_relay={transfer_relay} "
            f"event_id={burn_result['sweep']['event_id']} "
            f"expected_amount={amount} "
            f"accepted_amount={sweep_back['accepted_amount']} "
            f"queried_count={sweep_back.get('queried_count')}. "
            "This relay may not reliably return kind 1059 gift wraps or "
            "direct/legacy kind 7378 events, may have delayed propagation, "
            "or may apply filtering/"
            "retention policies that make it unsuitable as an Acorn relay."
        )
        source_credit_history = await _await_or_skip(
            wait_for_tx_history_entry(
                source_wallet,
                lambda entry: entry.get("tx_type") == "C"
                and entry.get("amount") >= amount
                and "acorn wallet burn sweep" in entry.get("comment", ""),
                timeout,
                "source credit for burn sweep",
            ),
            "source credit transaction history readback",
            timeout + 2,
        )
        assert any(
            entry.get("tx_type") == "C"
            and entry.get("amount") >= amount
            and "acorn wallet burn sweep" in entry.get("comment", "")
            for entry in source_credit_history
        )
        relay_suitable(
            relay_scenario,
            "burn-sweep-transfer",
            swept=f"{sweep_back['accepted_amount']} sats",
        )

    finally:
        live_progress("burn test: cleanup")
        with contextlib.suppress(Exception):
            await _await_or_skip(
                test_wallet.burn_wallet(allow_funded=True, relays=[test_relay]),
                "burn test cleanup",
                timeout,
            )
        remove_test_wallet_config(test_wallet_config)
