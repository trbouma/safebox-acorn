from __future__ import annotations

import asyncio
import contextlib
import hashlib
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


DEFAULT_TEST_BLOSSOM = "https://grove.safebox.dev"


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
        live_progress("SKIPPED Grove blob test step timed out", step=label, timeout=f"{timeout:g}s")
        pytest.skip(f"{label} timed out after {timeout:g}s")


@pytest_asyncio.fixture(autouse=True)
async def cleanup_monstr_clients():
    yield
    await _drain_monstr_tasks()


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("relay_scenario", live_relay_scenarios())
async def test_live_grove_blob_record_round_trip(relay_scenario):
    timeout = float(os.getenv("ACORN_TEST_TIMEOUT", "15"))
    blossom_server = os.getenv("ACORN_TEST_BLOSSOM", DEFAULT_TEST_BLOSSOM).rstrip("/")
    live_progress(
        "Grove blob test: ensuring disposable wallet",
        scenario=relay_scenario["name"],
        relay=relay_scenario["relay"],
        blossom=blossom_server,
        timeout=f"{timeout:g}s",
    )
    test_wallet_config = await _await_or_skip(
        ensure_test_wallet_config(
            relay=relay_scenario["relay"],
            config_suffix=relay_scenario["config_suffix"],
        ),
        "Grove blob test wallet init",
        timeout,
    )
    test_nsec = test_wallet_config["nsec"]
    test_relay = test_wallet_config["home_relay"]
    label = f"pytest-grove-blob-{uuid4().hex[:12]}"
    payload = f"blob metadata from pytest {uuid4().hex}"
    blob_data = (
        b"%PDF-1.4\n"
        b"% Acorn Grove live blob round trip\n"
        + uuid4().hex.encode("ascii")
        + b"\n%%EOF\n"
    )

    acorn = Acorn(
        nsec=test_nsec,
        home_relay=test_relay,
        relays=[test_relay],
        blossom_home_server=blossom_server,
        blossom_servers=[blossom_server],
    )
    try:
        await _await_or_skip(acorn.load_data(), "Grove blob wallet load", timeout)
    except RuntimeError as exc:
        pytest.skip(
            "test wallet config must point to an initialized Acorn wallet "
            f"on {test_relay}: {exc}"
        )

    deleted = False
    try:
        live_progress("Grove blob test: putting blob-backed record", label=label)
        result = await _await_or_skip(
            acorn.put_record(
                label,
                payload,
                record_type="blob-test",
                blob_data=blob_data,
                relays=[test_relay],
                return_result=True,
            ),
            "Grove blob record publish",
            timeout,
        )
        assert result["status"] == "OK"
        assert result["blobref"].startswith(blossom_server)
        assert result["blobsha256"]

        live_progress("Grove blob test: reading record metadata", label=label)
        record = await _await_or_skip(
            acorn.get_record_safebox(label, relays=[test_relay]),
            "Grove blob record metadata readback",
            timeout,
        )
        assert record.payload == payload
        assert record.blobsha256 == result["blobsha256"]
        assert record.origsha256 == hashlib.sha256(blob_data).hexdigest()
        assert record.encryptparms is not None

        live_progress("Grove blob test: retrieving and decrypting blob", sha256=result["blobsha256"][:12])
        blob_type, restored = await _await_or_skip(
            acorn.get_record_blobdata(label, relays=[test_relay]),
            "Grove blob retrieval",
            timeout,
        )
        assert restored == blob_data
        assert blob_type == "application/pdf"

        relay_suitable(
            relay_scenario,
            "grove-blob-put-get",
            blossom=blossom_server,
            bytes=len(blob_data),
        )

        live_progress("Grove blob test: deleting record and blob", label=label)
        delete_result = await _await_or_skip(
            acorn.delete_record(label, relays=[test_relay], delete_blob=True),
            "Grove blob record delete",
            timeout,
        )
        assert delete_result["status"] == "DELETE_REQUESTED"
        deleted = True
    except Exception as exc:
        if "Blob" in str(exc) or "upload" in str(exc).lower() or "blossom" in str(exc).lower():
            pytest.skip(f"Grove blob dependency unavailable or incompatible: {exc}")
        raise
    finally:
        if not deleted:
            live_progress("Grove blob test: cleanup delete", label=label)
            with contextlib.suppress(Exception):
                await _await_or_skip(
                    acorn.delete_record(label, relays=[test_relay], delete_blob=True),
                    "Grove blob cleanup delete",
                    timeout,
                )
        if should_burn_test_wallet(test_wallet_config):
            live_progress("Grove blob test: cleanup burn disposable wallet")
            with contextlib.suppress(Exception):
                await _await_or_skip(
                    acorn.burn_wallet(allow_funded=True, relays=[test_relay]),
                    "Grove blob cleanup burn",
                    timeout,
                )
        remove_test_wallet_config(test_wallet_config)
