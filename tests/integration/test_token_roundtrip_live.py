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
    is_source_wallet_environment_error,
    live_progress,
    live_relay_scenarios,
    relay_suitable,
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
        live_progress(
            "SKIPPED token round-trip test step timed out",
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
async def test_live_disposable_wallet_token_and_proof_maintenance_round_trip(
    monkeypatch,
    relay_scenario,
):
    live_progress(
        "token round-trip test: loading configuration",
        scenario=relay_scenario["name"],
        relay=relay_scenario["relay"],
    )
    source_config = require_source_config()
    amount = int(os.getenv("ACORN_TEST_AMOUNT", "1"))
    timeout = float(os.getenv("ACORN_TEST_TIMEOUT", "15"))

    configured_path = os.getenv(
        "ACORN_TEST_WALLET_CONFIG",
        "./.acorn-test/test-wallet.yml",
    )
    if configured_path.endswith(".yml"):
        roundtrip_path = configured_path[:-4] + "-token-roundtrip.yml"
    else:
        roundtrip_path = configured_path + ".token-roundtrip.yml"
    monkeypatch.setenv("ACORN_TEST_WALLET_CONFIG", roundtrip_path)

    test_wallet_config = await _await_or_skip(
        ensure_test_wallet_config(
            relay=relay_scenario["relay"],
            config_suffix=relay_scenario["config_suffix"],
        ),
        "token round-trip wallet init",
        timeout,
    )

    source_nsec = source_config["nsec"]
    source_relay = source_config["home_relay"]
    test_nsec = test_wallet_config["nsec"]
    test_relay = test_wallet_config["home_relay"]
    transfer_relay = get_test_transfer_relay(
        test_relay,
        relay=relay_scenario["relay"],
    )
    test_recipient = Keys(priv_k=test_nsec).public_key_bech32()
    source_recipient = Keys(priv_k=source_nsec).public_key_bech32()

    source_wallet = Acorn(
        nsec=source_nsec,
        home_relay=source_relay,
        relays=[source_relay],
    )
    test_wallet = Acorn(
        nsec=test_nsec,
        home_relay=test_relay,
        relays=[test_relay],
        mints=test_wallet_config.get("mints"),
    )

    cleanup_sweep_event = None
    issued_token = None
    issued_token_accepted = False
    try:
        live_progress("token round-trip test: loading source wallet")
        await _await_or_skip(source_wallet.load_data(), "source wallet load", timeout)
        if source_wallet.get_balance() < amount:
            pytest.skip(
                "source wallet must have enough spendable balance for the "
                f"token round-trip test: balance={source_wallet.get_balance()}, "
                f"amount={amount}"
            )

        live_progress(
            "token round-trip test: funding disposable wallet",
            amount=f"{amount} sat",
            relay=transfer_relay,
        )
        try:
            funding = await _await_or_skip(
                source_wallet.send_ecash_transfer(
                    amount=amount,
                    recipient=test_recipient,
                    relay=transfer_relay,
                    comment="pytest token round-trip funding",
                ),
                "token round-trip funding transfer",
                timeout,
            )
        except RuntimeError as exc:
            if is_source_wallet_environment_error(exc):
                pytest.skip(
                    "source wallet proof state or home relay is not ready; run "
                    "`acorn check-proofs`, `acorn repair-proofs`, and "
                    "`acorn balance --verify` before retrying the token relay test"
                )
            raise

        await _await_or_skip(test_wallet.load_data(), "test wallet load", timeout)
        received = await _await_or_skip(
            test_wallet.sweep_ecash_transfers(
                relays=[transfer_relay],
                receive_nsec=test_nsec,
                event_id=funding["event_id"],
            ),
            "test wallet receive funding",
            timeout,
        )
        assert received["accepted_amount"] == amount, received

        await _await_or_skip(test_wallet.load_data(), "funded wallet reload", timeout)
        balance_before = test_wallet.get_balance()
        assert balance_before >= amount

        live_progress(
            "token round-trip test: issuing token from disposable wallet",
            amount=f"{amount} sat",
        )
        issued_token = await _await_or_skip(
            test_wallet.issue_token(
                amount,
                comment="pytest disposable token issue",
            ),
            "disposable wallet token issue",
            timeout,
        )
        assert issued_token.startswith("cashuB")
        assert test_wallet.get_balance() == balance_before - amount

        live_progress("token round-trip test: accepting issued token")
        message, accepted_amount = await _await_or_skip(
            test_wallet.accept_token(
                issued_token,
                comment="pytest disposable token accept",
            ),
            "disposable wallet token accept",
            timeout,
        )
        assert accepted_amount == amount
        assert str(amount) in message
        issued_token_accepted = True

        await _await_or_skip(test_wallet.load_data(), "round-trip wallet reload", timeout)
        assert test_wallet.get_balance() == balance_before

        history = await _await_or_skip(
            wait_for_tx_history_entry(
                test_wallet,
                lambda entry: entry.get("tx_type") == "C"
                and entry.get("amount") == amount
                and "pytest disposable token accept" in entry.get("comment", ""),
                timeout,
                "disposable token acceptance credit",
            ),
            "token acceptance history readback",
            timeout + 2,
        )
        assert any(
            entry.get("tx_type") == "D"
            and entry.get("amount") == amount
            and "pytest disposable token issue" in entry.get("comment", "")
            for entry in history
        )
        assert any(
            entry.get("tx_type") == "C"
            and entry.get("amount") == amount
            and "pytest disposable token accept" in entry.get("comment", "")
            for entry in history
        )

        proof_identity_before_swap = {
            (str(proof.id), str(proof.secret))
            for proof in test_wallet.proofs
        }
        live_progress(
            "token round-trip test: refreshing all disposable wallet proofs",
            proofs=len(test_wallet.proofs),
            balance=f"{test_wallet.get_balance()} sats",
        )
        swap_result = await _await_or_skip(
            test_wallet.swap_multi_each(),
            "disposable wallet swap proofs",
            timeout,
        )
        assert str(swap_result).startswith("multi swap ok")

        await _await_or_skip(test_wallet.load_data(), "post-swap wallet reload", timeout)
        assert test_wallet.get_balance() == balance_before
        proof_identity_after_swap = {
            (str(proof.id), str(proof.secret))
            for proof in test_wallet.proofs
        }
        assert proof_identity_after_swap
        assert proof_identity_after_swap != proof_identity_before_swap

        swap_check = await _await_or_skip(
            test_wallet.check_proofs(),
            "post-swap proof check",
            timeout,
        )
        assert swap_check["status"] == "clean", swap_check
        assert swap_check["mint_confirmed_unspent"]["amount"] == balance_before
        relay_suitable(
            relay_scenario,
            "disposable-swap-proofs",
            balance=f"{balance_before} sats",
            proofs=len(test_wallet.proofs),
        )

        live_progress(
            "token round-trip test: repairing disposable wallet proofs",
            proofs=len(test_wallet.proofs),
            balance=f"{test_wallet.get_balance()} sats",
        )
        repair_result = await _await_or_skip(
            test_wallet.repair_proofs(),
            "disposable wallet repair proofs",
            timeout,
        )
        assert "repair-proofs" in repair_result

        await _await_or_skip(test_wallet.load_data(), "post-repair wallet reload", timeout)
        assert test_wallet.get_balance() == balance_before
        proof_identity_after_repair = {
            (str(proof.id), str(proof.secret))
            for proof in test_wallet.proofs
        }
        assert proof_identity_after_repair
        assert proof_identity_after_repair != proof_identity_after_swap

        repair_check = await _await_or_skip(
            test_wallet.check_proofs(),
            "post-repair proof check",
            timeout,
        )
        assert repair_check["status"] == "clean", repair_check
        assert repair_check["requires_repair"] is False
        assert repair_check["mint_confirmed_unspent"]["amount"] == balance_before
        relay_suitable(
            relay_scenario,
            "disposable-repair-proofs",
            balance=f"{balance_before} sats",
            proofs=len(test_wallet.proofs),
        )

        relay_suitable(
            relay_scenario,
            "disposable-token-issue-accept",
            amount=f"{amount} sats",
            balance=f"{balance_before} sats",
        )
        live_progress(
            "PASSED disposable wallet token and proof-maintenance round-trip",
            scenario=relay_scenario["name"],
            relay=relay_scenario["relay"],
            amount=f"{amount} sats",
        )

    finally:
        live_progress("token round-trip test: cleanup")
        if issued_token and not issued_token_accepted:
            try:
                live_progress(
                    "token round-trip test: recovering locally issued token before cleanup"
                )
                await asyncio.wait_for(
                    test_wallet.accept_token(
                        issued_token,
                        comment="pytest disposable token cleanup recovery",
                    ),
                    timeout=timeout,
                )
                issued_token_accepted = True
            except Exception as exc:
                live_progress(
                    "token round-trip issued-token recovery was not confirmed",
                    error=exc,
                )
        try:
            await _await_or_skip(test_wallet.load_data(), "cleanup wallet load", timeout)
            if test_wallet.get_balance() > 0:
                burn_result = await _await_or_skip(
                    test_wallet.burn_wallet(
                        send_to=source_recipient,
                        send_relay=transfer_relay,
                        relays=[test_relay],
                    ),
                    "token round-trip cleanup burn",
                    timeout,
                )
                cleanup_sweep_event = burn_result.get("sweep", {}).get("event_id")
            else:
                await _await_or_skip(
                    test_wallet.burn_wallet(
                        allow_funded=True,
                        relays=[test_relay],
                    ),
                    "token round-trip cleanup burn",
                    timeout,
                )
        except Exception as exc:
            live_progress("token round-trip cleanup burn failed", error=exc)

        if cleanup_sweep_event:
            try:
                await _await_or_skip(
                    source_wallet.sweep_ecash_transfers(
                        relays=[transfer_relay],
                        event_id=cleanup_sweep_event,
                    ),
                    "source receive token round-trip cleanup sweep",
                    timeout,
                )
            except Exception as exc:
                live_progress(
                    "token round-trip cleanup sweep receive failed",
                    event=cleanup_sweep_event[:12],
                    error=exc,
                )

        remove_test_wallet_config(test_wallet_config)
