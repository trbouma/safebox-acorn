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
    get_receive_nsec,
    get_test_transfer_relay,
    live_progress,
    live_relay_scenarios,
    relay_suitable,
    remove_test_wallet_config,
    require_source_config,
    should_burn_test_wallet,
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
        live_progress("SKIPPED ecash transfer test step timed out", step=label, timeout=f"{timeout:g}s")
        pytest.skip(f"{label} timed out after {timeout:g}s")


@pytest_asyncio.fixture(autouse=True)
async def cleanup_monstr_clients():
    yield
    await _drain_monstr_tasks()


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.parametrize("relay_scenario", live_relay_scenarios())
async def test_live_gift_wrapped_ecash_transfer_round_trip(relay_scenario):
    live_progress(
        "ecash transfer test: loading configuration",
        scenario=relay_scenario["name"],
        relay=relay_scenario["relay"],
    )
    source_config = require_source_config()
    amount = int(os.getenv("ACORN_TEST_AMOUNT", "1"))
    timeout = float(os.getenv("ACORN_TEST_TIMEOUT", "15"))
    live_progress("ecash transfer test: ensuring disposable wallet", timeout=f"{timeout:g}s")
    test_wallet_config = await _await_or_skip(
        ensure_test_wallet_config(
            relay=relay_scenario["relay"],
            config_suffix=relay_scenario["config_suffix"],
        ),
        "test wallet init",
        timeout,
    )
    source_nsec = source_config["nsec"]
    source_relay = source_config["home_relay"]
    test_nsec = test_wallet_config["nsec"]
    test_relay = test_wallet_config["home_relay"]
    transfer_relay = get_test_transfer_relay(test_relay, relay=relay_scenario["relay"])
    receive_nsec_explicit = bool(os.getenv("ACORN_RECEIVE_NSEC"))
    receive_nsec = get_receive_nsec(source_config)
    recipient = (
        os.getenv("ACORN_RECIPIENT_NIP05")
        if receive_nsec_explicit and os.getenv("ACORN_RECIPIENT_NIP05")
        else Keys(priv_k=receive_nsec).public_key_bech32()
    )
    receive_uses_source_wallet = receive_nsec == source_nsec

    live_progress("ecash transfer test: loading source wallet", relay=source_relay)
    sender = Acorn(
        nsec=source_nsec,
        home_relay=source_relay,
        relays=[source_relay],
    )
    try:
        await _await_or_skip(sender.load_data(), "sender wallet load", timeout)
    except RuntimeError as exc:
        pytest.skip(
            "source wallet config must point to an initialized, funded Acorn wallet "
            f"on {source_relay}: {exc}"
        )
    before = sender.get_balance()
    live_progress("ecash transfer test: source balance loaded", balance=f"{before} sats")
    if before < amount:
        pytest.skip(
            "source wallet must have enough spendable balance for the live "
            f"test: balance={before}, amount={amount}"
        )

    receiver_wallet = sender if receive_uses_source_wallet else Acorn(
        nsec=test_nsec,
        home_relay=test_relay,
        relays=[test_relay],
    )

    try:
        live_progress("ecash transfer test: publishing gift-wrapped transfer", amount=f"{amount} sat", relay=transfer_relay)
        transfer = await _await_or_skip(
            sender.send_ecash_transfer(
                amount=amount,
                recipient=recipient,
                relay=transfer_relay,
                comment="pytest live gift-wrapped transfer",
            ),
            "ecash transfer publish",
            timeout,
        )

        assert transfer["kind"] == 1059
        assert transfer["transfer_kind"] == 7378
        assert transfer["mode"] == "gift-wrapped"
        assert transfer["deletable_by_sender"] is False
        assert transfer["event_id"]
        assert transfer["recipient_pubkey"] == Keys(priv_k=receive_nsec).public_key_hex(), (
            "ecash transfer recipient does not match receive key; set "
            "ACORN_RECEIVE_NSEC to the recipient key or unset ACORN_RECIPIENT_NIP05"
        )
        sender_debit_history = await _await_or_skip(
            wait_for_tx_history_entry(
                sender,
                lambda entry: entry.get("tx_type") == "D"
                and entry.get("amount") == amount
                and "pytest live gift-wrapped transfer" in entry.get("comment", ""),
                timeout,
                "source debit for gift-wrapped transfer",
            ),
            "source debit transaction history readback",
            timeout + 2,
        )
        assert any(
            entry.get("tx_type") == "D"
            and entry.get("amount") == amount
            and "pytest live gift-wrapped transfer" in entry.get("comment", "")
            for entry in sender_debit_history
        )

        live_progress(
            "ecash transfer test: loading receiver wallet",
            relay=(source_relay if receive_uses_source_wallet else test_relay),
            wallet=("source" if receive_uses_source_wallet else "disposable"),
        )
        await _await_or_skip(receiver_wallet.load_data(), "receiver wallet load", timeout)
        receiver_before = receiver_wallet.get_balance()

        live_progress("ecash transfer test: receiving transfer", event=transfer["event_id"][:12])
        sweep_receive_nsec = None if receive_uses_source_wallet else receive_nsec
        receive = await _await_or_skip(
            receiver_wallet.sweep_ecash_transfers(
                relays=[transfer_relay],
                receive_nsec=sweep_receive_nsec,
                event_id=transfer["event_id"],
            ),
            "ecash transfer receive",
            timeout,
        )
        live_progress(
            "ecash transfer test: receive result",
            accepted=receive["accepted_count"],
            skipped=len(receive.get("skipped", [])),
            failed=len(receive.get("failed", [])),
            receive_pubkey=receive.get("receive_pubkey", "")[:12],
            wallet_pubkey=receive.get("wallet_pubkey", "")[:12],
        )

        assert receive["accepted_count"] == 1, receive
        assert receive["accepted_amount"] == amount, receive
        assert receive["accepted"][0]["mode"] == "gift-wrapped"
        assert receive["accepted"][0]["outer_kind"] == 1059
        assert receive["accepted"][0]["inner_kind"] == 7378

        live_progress("ecash transfer test: reloading receiver wallet")
        await _await_or_skip(receiver_wallet.load_data(), "final wallet reload", timeout)
        assert receiver_wallet.get_balance() >= receiver_before + amount
        tx_history = await _await_or_skip(
            receiver_wallet.get_tx_history(),
            "receiver transaction history readback",
            timeout,
        )
        assert any(
            entry.get("tx_type") == "C"
            and entry.get("amount") == amount
            and "pytest live gift-wrapped transfer" in entry.get("comment", "")
            for entry in tx_history
        )
        relay_suitable(
            relay_scenario,
            "gift-wrapped-ecash-transfer",
            accepted=f"{receive['accepted_amount']} sats",
        )

    finally:
        if should_burn_test_wallet(test_wallet_config):
            live_progress("ecash transfer test: cleaning up disposable wallet")
            cleanup_wallet = Acorn(
                nsec=test_nsec,
                home_relay=test_relay,
                relays=[test_relay],
            )
            with contextlib.suppress(Exception):
                await _await_or_skip(cleanup_wallet.load_data(), "cleanup wallet load", timeout)
            source_recipient = Keys(priv_k=source_nsec).public_key_bech32()
            burn_result = None
            with contextlib.suppress(Exception):
                burn_result = await _await_or_skip(
                    cleanup_wallet.burn_wallet(
                        send_to=source_recipient,
                        send_relay=transfer_relay,
                        relays=[test_relay],
                        allow_funded=True,
                    ),
                    "test wallet burn cleanup",
                    timeout,
                )
            sweep = burn_result.get("sweep") if isinstance(burn_result, dict) else None
            if isinstance(sweep, dict) and sweep.get("event_id"):
                with contextlib.suppress(Exception):
                    live_progress("ecash transfer test: receiving cleanup sweep-back")
                    await _await_or_skip(
                        sender.sweep_ecash_transfers(
                            relays=[transfer_relay],
                            event_id=sweep["event_id"],
                        ),
                        "source wallet sweep-back receive",
                        timeout,
                    )
            remove_test_wallet_config(test_wallet_config)
