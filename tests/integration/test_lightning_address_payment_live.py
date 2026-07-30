from __future__ import annotations

import asyncio
import contextlib
import os

import pytest
import pytest_asyncio

from acorn.acorn import Acorn

from tests.helpers import (
    live_progress,
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
        live_progress("SKIPPED lightning payment test step timed out", step=label, timeout=f"{timeout:g}s")
        pytest.skip(f"{label} timed out after {timeout:g}s")


@pytest_asyncio.fixture(autouse=True)
async def cleanup_monstr_clients():
    yield
    await _drain_monstr_tasks()


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_lightning_address_payment_from_source_wallet():
    lnaddress = os.getenv("ACORN_LIGHTNING_ADDRESS")
    if not lnaddress:
        pytest.skip("ACORN_LIGHTNING_ADDRESS is required for the lightning-address payment live test")

    source_config = require_source_config()
    source_nsec = source_config["nsec"]
    source_relay = source_config["home_relay"]
    amount = int(os.getenv("ACORN_LIGHTNING_TEST_AMOUNT", os.getenv("ACORN_TEST_AMOUNT", "1")))
    timeout = float(os.getenv("ACORN_TEST_TIMEOUT", "15"))
    comment = os.getenv("ACORN_LIGHTNING_TEST_COMMENT", "pytest lightning address payment")

    wallet = Acorn(
        nsec=source_nsec,
        home_relay=source_relay,
        relays=[source_relay],
    )
    await _await_or_skip(wallet.load_data(), "source wallet load", timeout)
    before = wallet.get_balance()
    live_progress("lightning payment test: source balance loaded", balance=f"{before} sats")
    if before < amount:
        pytest.skip(
            "source wallet must have enough spendable balance for the lightning payment live "
            f"test: balance={before}, amount={amount}"
        )

    live_progress("lightning payment test: paying lightning address", amount=f"{amount} sat", lnaddress=lnaddress)
    msg_out, fees = await _await_or_skip(
        wallet.pay_multi(amount=amount, lnaddress=lnaddress, comment=comment),
        "lightning address payment",
        timeout,
    )

    assert "successful" in msg_out.lower()
    assert fees >= 0
    tx_history = await _await_or_skip(
        wait_for_tx_history_entry(
            wallet,
            lambda entry: entry.get("tx_type") == "D"
            and entry.get("amount") == amount
            and comment in entry.get("comment", ""),
            timeout,
            "source debit for lightning address payment",
        ),
        "source lightning debit transaction history readback",
        timeout + 2,
    )
    assert any(
        entry.get("tx_type") == "D"
        and entry.get("amount") == amount
        and comment in entry.get("comment", "")
        for entry in tx_history
    )
