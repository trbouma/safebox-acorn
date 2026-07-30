from __future__ import annotations

import asyncio
import contextlib
import os
from uuid import uuid4

import pytest
import pytest_asyncio

from acorn.acorn import Acorn

from tests.helpers import (
    ensure_test_wallet_config,
    live_progress,
    live_relay_scenarios,
    relay_suitable,
    remove_test_wallet_config,
    should_burn_test_wallet,
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
        live_progress("SKIPPED record lifecycle test step timed out", step=label, timeout=f"{timeout:g}s")
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
            live_progress("FAILED record lifecycle eventual check", step=label, timeout=f"{timeout:g}s")
            pytest.fail(f"{label} did not become available after {timeout:g}s")
        await asyncio.sleep(interval)


@pytest_asyncio.fixture(autouse=True)
async def cleanup_monstr_clients():
    yield
    await _drain_monstr_tasks()


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("relay_scenario", live_relay_scenarios())
async def test_live_record_lifecycle_round_trip(relay_scenario):
    timeout = float(os.getenv("ACORN_TEST_TIMEOUT", "15"))
    live_progress(
        "record lifecycle test: ensuring disposable wallet",
        scenario=relay_scenario["name"],
        relay=relay_scenario["relay"],
        timeout=f"{timeout:g}s",
    )
    test_wallet_config = await _await_or_skip(
        ensure_test_wallet_config(
            relay=relay_scenario["relay"],
            config_suffix=relay_scenario["config_suffix"],
        ),
        "test wallet init",
        timeout,
    )
    test_nsec = test_wallet_config["nsec"]
    test_relay = test_wallet_config["home_relay"]
    label = f"pytest-record-{uuid4().hex[:12]}"
    payload = f"hello from pytest {uuid4().hex}"

    live_progress("record lifecycle test: loading wallet", relay=test_relay)
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

    deleted = False
    try:
        live_progress("record lifecycle test: putting record", label=label)
        stored_label = await _await_or_skip(
            acorn.put_record(label, payload),
            "record publish",
            timeout,
        )
        assert stored_label == label

        live_progress("record lifecycle test: reading record back", label=label)
        record = await _eventually(
            lambda: acorn.get_record_safebox(label),
            "record readback",
            timeout,
        )
        assert record.tag == [label]
        assert record.type == "generic"
        assert record.payload == payload

        live_progress("record lifecycle test: listing labels")
        labels = await _eventually(
            lambda: acorn.get_user_record_labels(relays=[test_relay]),
            "record label listing",
            timeout,
            predicate=lambda labels: label in labels,
        )
        assert label in labels

        live_progress("record lifecycle test: deleting record", label=label)
        delete_result = await _await_or_skip(
            acorn.delete_record(label),
            "record delete",
            timeout,
        )
        assert delete_result["status"] == "DELETE_REQUESTED"
        assert delete_result["label"] == label
        assert delete_result["kind"] == 37375
        assert delete_result["delete_event_id"]
        deleted = True

        live_progress("record lifecycle test: verifying label removal")
        labels_after_delete = await _eventually(
            lambda: acorn.get_user_record_labels(relays=[test_relay]),
            "record label removal",
            timeout,
            predicate=lambda labels: label not in labels,
        )
        assert label not in labels_after_delete
        relay_suitable(
            relay_scenario,
            "private-record-put-get-list-delete",
            label=label,
        )

    finally:
        if not deleted:
            live_progress("record lifecycle test: cleanup delete", label=label)
            with contextlib.suppress(Exception):
                await _await_or_skip(
                    acorn.delete_record(label),
                    "record cleanup delete",
                    timeout,
                )
        if should_burn_test_wallet(test_wallet_config):
            live_progress("record lifecycle test: cleanup burn disposable wallet")
            with contextlib.suppress(Exception):
                await _await_or_skip(
                    acorn.burn_wallet(allow_funded=True),
                    "test wallet burn cleanup",
                    timeout,
                )
            remove_test_wallet_config(test_wallet_config)
