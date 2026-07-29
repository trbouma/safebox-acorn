from __future__ import annotations

import asyncio
import contextlib
import os
from uuid import uuid4

import pytest
import pytest_asyncio

from acorn.acorn import Acorn

from tests.helpers import ensure_test_wallet_config, remove_test_wallet_config, should_burn_test_wallet


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


async def _eventually(
    awaitable_factory,
    label: str,
    timeout: float,
    interval: float = 1.0,
    predicate=bool,
):
    deadline = asyncio.get_running_loop().time() + timeout
    last_result = None
    while True:
        last_result = await awaitable_factory()
        if predicate(last_result):
            return last_result
        if asyncio.get_running_loop().time() >= deadline:
            pytest.fail(f"{label} did not become available after {timeout:g}s")
        await asyncio.sleep(interval)


@pytest_asyncio.fixture(autouse=True)
async def cleanup_monstr_clients():
    yield
    await _drain_monstr_tasks()


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_record_lifecycle_round_trip():
    timeout = float(os.getenv("ACORN_TEST_TIMEOUT", "15"))
    test_wallet_config = await _await_or_skip(
        ensure_test_wallet_config(),
        "test wallet init",
        timeout,
    )
    test_nsec = test_wallet_config["nsec"]
    test_relay = test_wallet_config["home_relay"]
    label = f"pytest-record-{uuid4().hex[:12]}"
    payload = f"hello from pytest {uuid4().hex}"

    acorn = Acorn(
        nsec=test_nsec,
        home_relay=test_relay,
        relays=[test_relay],
    )
    try:
        await _await_or_skip(acorn.load_data(), "wallet load", timeout)
    except RuntimeError as exc:
        pytest.skip(
            "test wallet config must point to an initialized Acorn wallet "
            f"on {test_relay}: {exc}"
        )

    try:
        stored_label = await _await_or_skip(
            acorn.put_record(label, payload),
            "record publish",
            timeout,
        )
        assert stored_label == label

        record = await _eventually(
            lambda: acorn.get_record_safebox(label),
            "record readback",
            timeout,
        )
        assert record.tag == [label]
        assert record.type == "generic"
        assert record.payload == payload

        labels = await _eventually(
            lambda: acorn.get_user_record_labels(relays=[test_relay]),
            "record label listing",
            timeout,
            predicate=lambda labels: label in labels,
        )
        assert label in labels

    finally:
        with contextlib.suppress(Exception):
            await _await_or_skip(
                acorn.delete_record(label),
                "record cleanup delete",
                timeout,
            )
        if should_burn_test_wallet(test_wallet_config):
            with contextlib.suppress(Exception):
                await _await_or_skip(
                    acorn.burn_wallet(allow_funded=True),
                    "test wallet burn cleanup",
                    timeout,
                )
            remove_test_wallet_config(test_wallet_config)
