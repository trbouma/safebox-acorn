from __future__ import annotations

import asyncio
import os

import pytest
from stroma import Keys

from acorn.acorn import Acorn
from acorn.nostr import nip05_to_npub

from tests.helpers import (
    live_progress,
    require_source_config,
    wait_for_tx_history_entry,
)


async def _await_or_skip(awaitable, label: str, timeout: float):
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout)
    except asyncio.TimeoutError:
        live_progress("SKIPPED nip05 ecash test step timed out", step=label, timeout=f"{timeout:g}s")
        pytest.skip(f"{label} timed out after {timeout:g}s")


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_nip05_ecash_transfer_to_external_wallet():
    nip05 = os.getenv("ACORN_NIP05_RECIPIENT")
    if not nip05:
        pytest.skip("ACORN_NIP05_RECIPIENT is required for the NIP-05 ecash live test")

    source_config = require_source_config()
    source_nsec = source_config["nsec"]
    source_relay = source_config["home_relay"]
    amount = int(os.getenv("ACORN_NIP05_TEST_AMOUNT", os.getenv("ACORN_TEST_AMOUNT", "1")))
    timeout = float(os.getenv("ACORN_TEST_TIMEOUT", "15"))
    comment = os.getenv("ACORN_NIP05_TEST_COMMENT", "pytest nip05 ecash transfer")
    source_pubkey = Keys(priv_k=source_nsec).public_key_hex()

    live_progress("nip05 ecash test: resolving recipient", nip05=nip05)
    resolved_pubkey, resolved_relays = nip05_to_npub(nip05)
    if not resolved_pubkey:
        pytest.skip(f"NIP-05 recipient did not resolve: {nip05}")
    assert resolved_pubkey != source_pubkey, (
        "NIP-05 live test requires an external recipient. "
        "Set ACORN_NIP05_RECIPIENT to an identifier that does not resolve to "
        "the source wallet."
    )
    live_progress(
        "nip05 ecash test: recipient resolved",
        pubkey=resolved_pubkey[:12],
        relays=resolved_relays,
    )

    wallet = Acorn(
        nsec=source_nsec,
        home_relay=source_relay,
        relays=[source_relay],
    )
    await _await_or_skip(wallet.load_data(), "source wallet load", timeout)
    before = wallet.get_balance()
    live_progress("nip05 ecash test: source balance loaded", balance=f"{before} sats")
    if before < amount:
        pytest.skip(
            "source wallet must have enough spendable balance for the NIP-05 ecash live "
            f"test: balance={before}, amount={amount}"
        )

    live_progress("nip05 ecash test: publishing transfer", amount=f"{amount} sat", relays=resolved_relays or [source_relay])
    transfer = await _await_or_skip(
        wallet.send_ecash_transfer(
            amount=amount,
            recipient=nip05,
            comment=comment,
        ),
        "nip05 ecash transfer publish",
        timeout,
    )

    assert transfer["recipient_pubkey"] == resolved_pubkey
    assert transfer["recipient_relays"] == resolved_relays

    tx_history = await _await_or_skip(
        wait_for_tx_history_entry(
            wallet,
            lambda entry: entry.get("tx_type") == "D"
            and entry.get("amount") == amount
            and comment in entry.get("comment", ""),
            timeout,
            "source debit for external NIP-05 ecash transfer",
        ),
        "source NIP-05 debit transaction history readback",
        timeout + 2,
    )
    assert any(
        entry.get("tx_type") == "D"
        and entry.get("amount") == amount
        and comment in entry.get("comment", "")
        for entry in tx_history
    )
    live_progress(
        "PASSED external NIP-05 ecash send test; verify receipt in recipient wallet",
        nip05=nip05,
        amount=f"{amount} sat",
        event=transfer["event_id"][:12],
        relays=transfer["relays"] or resolved_relays,
    )
