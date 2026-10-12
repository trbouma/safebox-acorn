from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from acorn.acorn import Acorn
from tests.helpers import cleanup_empty_test_wallet


def burn_wallet(balance=9, fee_ppk=100):
    wallet = object.__new__(Acorn)
    wallet.home_relay = "wss://relay.example"
    wallet.pubkey_hex = "00" * 32
    wallet.pubkey_bech32 = "npub-test"
    wallet.balance = balance
    wallet.get_balance = lambda: wallet.balance
    wallet._proofs_by_keyset = lambda: ({"keyset": [SimpleNamespace(amount=balance)]}, {})
    wallet._keyset_input_fee_ppk = AsyncMock(return_value=fee_ppk)
    wallet.send_ecash_transfer = AsyncMock(return_value={"amount": balance - (1 if fee_ppk else 0), "event_id": "test"})
    async def reload(): wallet.balance = 0
    wallet.load_data = AsyncMock(side_effect=reload)
    wallet._query_authored_events_for_burn = AsyncMock(return_value=[])
    wallet.publish_deletion_request = AsyncMock()
    return wallet


@pytest.mark.asyncio
@pytest.mark.parametrize("fee_ppk,expected", [(0, 9), (100, 8), (1000, 8)])
async def test_burn_sweep_reserves_input_fee(fee_ppk, expected):
    wallet = burn_wallet(fee_ppk=fee_ppk)
    result = await wallet.burn_wallet(send_to="recipient")
    assert wallet.send_ecash_transfer.call_args.kwargs["amount"] == expected
    assert result["balance_after"] == 0
    assert result["sweep"]["estimated_mint_input_fee"] == 9 - expected


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["dust", "multiple_keysets", "mismatch", "fee_lookup", "send", "readback", "remainder"])
async def test_uncertain_burn_does_not_delete(failure):
    wallet = burn_wallet()
    if failure == "dust": wallet._keyset_input_fee_ppk = AsyncMock(return_value=9000)
    if failure == "multiple_keysets": wallet._proofs_by_keyset = lambda: ({"a": [], "b": []}, {})
    if failure == "mismatch": wallet.balance = 10
    if failure == "fee_lookup": wallet._keyset_input_fee_ppk = AsyncMock(side_effect=RuntimeError("offline"))
    if failure == "send": wallet.send_ecash_transfer.side_effect = RuntimeError("unconfirmed")
    if failure == "readback": wallet.load_data.side_effect = RuntimeError("offline")
    if failure == "remainder": wallet.load_data = AsyncMock()
    with pytest.raises((ValueError, RuntimeError)):
        await wallet.burn_wallet(send_to="recipient")
    wallet._query_authored_events_for_burn.assert_not_awaited()
    wallet.publish_deletion_request.assert_not_awaited()
    if failure in {"dust", "multiple_keysets", "mismatch", "fee_lookup"}:
        wallet.send_ecash_transfer.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["empty", "funded", "pending", "unreadable", "burn_failed"])
async def test_cleanup_preserves_uncertain_wallet(tmp_path, state):
    path = tmp_path / "test-wallet.yml"
    path.touch()
    wallet = SimpleNamespace(
        load_data=AsyncMock(), get_balance=lambda: 9 if state == "funded" else 0,
        get_continuity_receipts=AsyncMock(return_value=[{}] if state == "pending" else []),
        burn_wallet=AsyncMock(),
    )
    if state == "unreadable": wallet.load_data.side_effect = RuntimeError("offline")
    if state == "burn_failed": wallet.burn_wallet.side_effect = RuntimeError("offline")
    result = await cleanup_empty_test_wallet(wallet, {"_path": str(path)}, ["wss://relay.example"], 1)
    assert result is (state == "empty")
    assert path.exists() is (state != "empty")
    if state in {"funded", "pending", "unreadable"}: wallet.burn_wallet.assert_not_awaited()
    else: assert "allow_funded" not in wallet.burn_wallet.call_args.kwargs
