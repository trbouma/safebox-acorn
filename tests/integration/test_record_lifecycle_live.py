from __future__ import annotations

import asyncio
import contextlib
import os
from uuid import uuid4

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
    env = require_env("ACORN_SENDER_NSEC", "ACORN_TEST_RELAY")
    timeout = float(os.getenv("ACORN_TEST_TIMEOUT", "15"))
    label = f"pytest-record-{uuid4().hex[:12]}"
    payload = f"hello from pytest {uuid4().hex}"

    acorn = Acorn(
        nsec=env["ACORN_SENDER_NSEC"],
        home_relay=env["ACORN_TEST_RELAY"],
        relays=[env["ACORN_TEST_RELAY"]],
    )
    try:
        await _await_or_skip(acorn.load_data(), "wallet load", timeout)
    except RuntimeError as exc:
        pytest.skip(
            "ACORN_SENDER_NSEC must be an initialized Acorn wallet "
            f"on {env['ACORN_TEST_RELAY']}: {exc}"
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
            lambda: acorn.get_user_record_labels(relays=[env["ACORN_TEST_RELAY"]]),
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
