"""Paced first-user journey; no automatic retries or destructive cleanup."""
from __future__ import annotations

import asyncio
import math

from tests.helpers import confirmed_transfer_amount, live_progress


def positive_seconds(value: str, minimum: float) -> float:
    seconds = float(value)
    if not math.isfinite(seconds) or seconds < minimum:
        raise ValueError(f"Timing must be finite and at least {minimum:g} seconds")
    return seconds


async def run_user_journey(
    source, wallet, *, relay, recipient, source_recipient, label,
    amount=32, send_amount=8, action_pause=30, read_pause=5, timeout=120,
    sleep=asyncio.sleep, on_step=None,
):
    """Exercise real APIs, accepting mint fees without equating tender and credit.

    The caller saves the disposable identity before entering this function.
    A timeout may leave a submitted operation unresolved: never retry it here.
    """
    async def step(label, operation, *, observation=False):
        if on_step is not None:
            on_step(label)
        delay = read_pause if observation else action_pause
        live_progress("user journey: waiting", next_step=label, seconds=delay)
        await sleep(delay)
        live_progress("user journey: running", step=label)
        return await asyncio.wait_for(operation(), timeout=timeout)

    await step("create wallet", lambda: wallet.create_instance(keepkey=True))
    await step("wallet bootstrap readback", wallet.load_data, observation=True)
    assert wallet.get_balance() == 0

    incoming = await step("send funding payment", lambda: source.send_ecash_transfer(
        amount=amount, recipient=recipient, relay=relay,
        comment=f"user journey funding {label}",
    ))
    assert incoming["event_id"]
    live_progress("user journey: funding event", event=incoming["event_id"])
    received = await step("receive payment", lambda: wallet.sweep_ecash_transfers(
        relays=[relay], event_id=incoming["event_id"],
    ))
    net_received = confirmed_transfer_amount(received, amount)
    await step("read received balance", wallet.load_data, observation=True)
    assert wallet.get_balance() == net_received
    assert net_received > send_amount, "Insufficient received funds for send amount plus mint fees"

    await step("read funding wallet balance", source.load_data, observation=True)
    source_before = source.get_balance()
    outgoing = await step("send payment back", lambda: wallet.send_ecash_transfer(
        amount=send_amount, recipient=source_recipient, relay=relay,
        comment=f"user journey return {label}",
    ))
    assert outgoing["event_id"]
    live_progress("user journey: return event", event=outgoing["event_id"])
    returned = await step("recipient accepts payment", lambda: source.sweep_ecash_transfers(
        relays=[relay], event_id=outgoing["event_id"],
    ))
    net_returned = confirmed_transfer_amount(returned, send_amount)
    await step("read recipient balance", source.load_data, observation=True)
    assert source.get_balance() == source_before + net_returned
    await step("read sending balance", wallet.load_data, observation=True)
    assert 0 <= wallet.get_balance() <= net_received - send_amount

    for action, payload in (("create record", "My first private note"),
                            ("edit record", "My edited private note")):
        stored = await step(action, lambda: wallet.put_record(label, payload))
        assert stored == label
        record = await step("read record", lambda: wallet.get_record_safebox(label), observation=True)
        assert record.tag == [label]
        assert record.payload == payload

    deleted = await step("delete record", lambda: wallet.delete_record(label))
    assert deleted["status"] == "DELETE_REQUESTED"
    assert deleted["delete_event_id"]
    labels = await step("verify record removed", lambda: wallet.get_user_record_labels(relays=[relay]), observation=True)
    assert label not in labels
    return {"received": net_received, "returned": net_returned, "remaining": wallet.get_balance()}
