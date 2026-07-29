from __future__ import annotations

import asyncio
import contextlib
import os

import pytest
import pytest_asyncio

from acorn.acorn import Acorn

from tests.helpers import require_env


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
@pytest.mark.asyncio
async def test_live_gift_wrapped_ecash_transfer_round_trip():
    env = require_env(
        "ACORN_SENDER_NSEC",
        "ACORN_RECEIVE_NSEC",
        "ACORN_RECIPIENT_NIP05",
        "ACORN_TEST_RELAY",
    )
    amount = int(os.getenv("ACORN_TEST_AMOUNT", "1"))
    timeout = float(os.getenv("ACORN_TEST_TIMEOUT", "15"))

    sender = Acorn(
        nsec=env["ACORN_SENDER_NSEC"],
        home_relay=env["ACORN_TEST_RELAY"],
        relays=[env["ACORN_TEST_RELAY"]],
    )
    try:
        await _await_or_skip(sender.load_data(), "sender wallet load", timeout)
    except RuntimeError as exc:
        pytest.skip(
            "ACORN_SENDER_NSEC must be an initialized, funded Acorn wallet "
            f"on {env['ACORN_TEST_RELAY']}: {exc}"
        )
    before = sender.get_balance()
    if before < amount:
        pytest.skip(
            "ACORN_SENDER_NSEC must have enough spendable balance for the live "
            f"test: balance={before}, amount={amount}"
        )

    transfer = await _await_or_skip(
        sender.send_ecash_transfer(
            amount=amount,
            recipient=env["ACORN_RECIPIENT_NIP05"],
            relay=env["ACORN_TEST_RELAY"],
            comment="pytest live gift-wrapped transfer",
        ),
        "ecash transfer publish",
        timeout,
    )

    assert transfer["kind"] == 7378
    assert transfer["mode"] == "gift-wrapped"
    assert transfer["deletable_by_sender"] is False
    assert transfer["event_id"]

    receiver_wallet = Acorn(
        nsec=env["ACORN_SENDER_NSEC"],
        home_relay=env["ACORN_TEST_RELAY"],
        relays=[env["ACORN_TEST_RELAY"]],
    )
    await _await_or_skip(receiver_wallet.load_data(), "receiver wallet load", timeout)

    receive = await _await_or_skip(
        receiver_wallet.sweep_ecash_transfers(
            relays=[env["ACORN_TEST_RELAY"]],
            receive_nsec=env["ACORN_RECEIVE_NSEC"],
            event_id=transfer["event_id"],
        ),
        "ecash transfer receive",
        timeout,
    )

    assert receive["accepted_count"] == 1
    assert receive["accepted_amount"] == amount
    assert receive["accepted"][0]["mode"] == "gift-wrapped"

    await _await_or_skip(receiver_wallet.load_data(), "final wallet reload", timeout)
    assert receiver_wallet.get_balance() >= before
