from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock

import pytest
from monstr.encrypt import Keys

from acorn.acorn import Acorn, BALANCE_SNAPSHOT_LABEL
from acorn.models import Proof


def snapshot_wallet() -> Acorn:
    wallet = object.__new__(Acorn)
    wallet.k = Keys(priv_k="11" * 32)
    wallet.pubkey_hex = wallet.k.public_key_hex()
    wallet.privkey_hex = wallet.k.private_key_hex()
    wallet.home_relay = "wss://relay.example"
    wallet.logger = logging.getLogger("balance-snapshot-test")
    wallet.proofs = [
        Proof(amount=8, id="cash-keyset", secret="one", C="cash-one"),
        Proof(amount=2, id="cash-keyset", secret="two", C="cash-two"),
    ]
    wallet.proof_event_ids = ["a" * 64]
    return wallet


@pytest.mark.asyncio
async def test_publish_and_read_balance_snapshot() -> None:
    wallet = snapshot_wallet()
    stored: dict[str, str] = {}

    async def set_wallet_info(label, label_info, **kwargs):
        stored[label] = label_info
        assert kwargs["record_kind"] == 37376
        assert kwargs["verify"] is False
        return {"event_id": "f" * 64}

    async def get_wallet_info(label, **kwargs):
        assert label == BALANCE_SNAPSHOT_LABEL
        assert kwargs["record_kind"] == 37376
        return stored.get(label)

    wallet.set_wallet_info = AsyncMock(side_effect=set_wallet_info)
    wallet.get_wallet_info = AsyncMock(side_effect=get_wallet_info)

    published = await wallet.publish_balance_snapshot(
        clear_balances=[
            {
                "mint": "https://clear.example/",
                "unit": "cmu-example",
                "amount": 25,
                "proof_count": 3,
                "event_ids": ["b" * 64],
            }
        ]
    )
    loaded = await wallet.get_balance_snapshot()

    assert published["cash"] == {
        "amount": 10,
        "proof_count": 2,
        "event_ids": ["a" * 64],
    }
    assert published["clear"] == [
        {
            "mint": "https://clear.example",
            "unit": "cmu-example",
            "amount": 25,
            "proof_count": 3,
            "event_ids": ["b" * 64],
        }
    ]
    assert published["relay_event_id"] == "f" * 64
    assert loaded == {
        key: value
        for key, value in published.items()
        if key not in {"relay_event_id", "verified"}
    }


@pytest.mark.asyncio
async def test_missing_balance_snapshot_returns_none() -> None:
    wallet = snapshot_wallet()
    wallet.get_wallet_info = AsyncMock(return_value=None)

    assert await wallet.get_balance_snapshot() is None


@pytest.mark.asyncio
async def test_cash_snapshot_refresh_preserves_existing_clear_balances() -> None:
    wallet = snapshot_wallet()
    existing_clear = [
        {
            "mint": "https://clear.example",
            "unit": "cmu-existing",
            "amount": 40,
            "proof_count": 2,
            "event_ids": ["c" * 64],
        }
    ]
    wallet.get_balance_snapshot = AsyncMock(
        return_value={"clear": existing_clear}
    )
    wallet.get_clear_balances = AsyncMock(
        side_effect=AssertionError("Cash refresh must not scan Clear proof state")
    )
    wallet.set_wallet_info = AsyncMock(return_value={"event_id": "d" * 64})

    result = await wallet.publish_balance_snapshot()

    assert result["clear"] == existing_clear
    wallet.get_clear_balances.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_balance_snapshot_is_rejected() -> None:
    wallet = snapshot_wallet()
    wallet.get_wallet_info = AsyncMock(
        return_value=json.dumps(
            {
                "type": "acorn-balance-snapshot",
                "version": 1,
                "observed_at": 1,
                "cash": {"amount": -1, "proof_count": 1},
                "clear": [],
            }
        )
    )

    with pytest.raises(RuntimeError, match="balance snapshot is invalid"):
        await wallet.get_balance_snapshot()


@pytest.mark.asyncio
async def test_best_effort_snapshot_failure_does_not_escape() -> None:
    wallet = snapshot_wallet()
    wallet.publish_balance_snapshot = AsyncMock(side_effect=RuntimeError("relay down"))

    await wallet._publish_balance_snapshot_best_effort()

    wallet.publish_balance_snapshot.assert_awaited_once_with(
        refresh_clear=False,
        verify=False,
    )
