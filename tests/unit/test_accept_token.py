from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from monstr.encrypt import Keys

from acorn import acorn as acorn_module
from acorn.acorn import Acorn
from acorn.models import Proof


def wallet_with_key() -> Acorn:
    wallet = object.__new__(Acorn)
    wallet.k = Keys(priv_k="11" * 32)
    wallet.pubkey_hex = wallet.k.public_key_hex()
    wallet.privkey_hex = wallet.k.private_key_hex()
    wallet.privkey_bech32 = wallet.k.private_key_bech32()
    wallet.home_relay = "ws://home:7777"
    wallet.relays = [wallet.home_relay]
    wallet.known_mints = {}
    wallet.proofs = []
    wallet.balance = 0
    wallet.logger = logging.getLogger("accept-token-test")
    wallet.acquire_lock = AsyncMock()
    wallet.release_lock = AsyncMock()
    wallet._reconcile_spent_proofs_locked = AsyncMock(
        return_value={"removed": 0, "amount": 0, "balance": 0}
    )
    wallet.add_proofs_obj = AsyncMock(return_value={"verified": True})
    wallet.add_tx_history = AsyncMock()
    wallet._maybe_maintain_received_proofs = AsyncMock()
    return wallet


@pytest.mark.asyncio
async def test_accept_token_registers_rotated_keyset_and_updates_balance(monkeypatch):
    wallet = wallet_with_key()
    mint = "https://new-mint.example"
    incoming = Proof(amount=1, id="old-keyset", secret="incoming", C="02" + "11" * 32)
    incoming_second = Proof(
        amount=2,
        id="older-keyset",
        secret="incoming-second",
        C="02" + "33" * 32,
    )
    refreshed = Proof(amount=3, id="new-keyset", secret="refreshed", C="02" + "22" * 32)

    token_obj = SimpleNamespace(mint=mint, proofs=[incoming, incoming_second])

    monkeypatch.setattr(
        acorn_module.TokenV4,
        "deserialize",
        classmethod(lambda cls, token: token_obj),
    )
    wallet.swap_proofs = AsyncMock(return_value=[refreshed])

    message, amount = await wallet.accept_token("cashuB-test")

    assert message == "Successfully accepted 3 sats!"
    assert amount == 3
    assert wallet.known_mints["old-keyset"] == mint
    assert wallet.known_mints["older-keyset"] == mint
    assert wallet.known_mints["new-keyset"] == mint
    assert wallet.proofs == [refreshed]
    assert wallet.balance == 3
    wallet.add_proofs_obj.assert_awaited_once_with([refreshed], verify=True)
    wallet.add_tx_history.assert_awaited_once()
    wallet._maybe_maintain_received_proofs.assert_not_awaited()


@pytest.mark.asyncio
async def test_accept_token_does_not_report_success_when_proofs_are_not_verified(monkeypatch):
    wallet = wallet_with_key()
    mint = "https://new-mint.example"
    incoming = Proof(amount=1, id="old-keyset", secret="incoming", C="02" + "11" * 32)
    refreshed = Proof(amount=1, id="new-keyset", secret="refreshed", C="02" + "22" * 32)

    token_obj = SimpleNamespace(mint=mint, proofs=[incoming])

    monkeypatch.setattr(
        acorn_module.TokenV4,
        "deserialize",
        classmethod(lambda cls, token: token_obj),
    )
    wallet.swap_proofs = AsyncMock(return_value=[refreshed])
    wallet.add_proofs_obj = AsyncMock(
        side_effect=RuntimeError("Proof publish could not be verified")
    )

    with pytest.raises(RuntimeError, match="Proof publish could not be verified"):
        await wallet.accept_token("cashuB-test")

    assert wallet.proofs == []
    assert wallet.balance == 0
    wallet.release_lock.assert_awaited_once()
    wallet.add_tx_history.assert_not_awaited()
    wallet._maybe_maintain_received_proofs.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_proofs_obj_verifies_relay_readback(monkeypatch):
    wallet = wallet_with_key()
    wallet.add_proofs_obj = Acorn.add_proofs_obj.__get__(wallet, Acorn)
    wallet.max_proof_event_size = 16384
    wallet.known_mints = {"new-keyset": "https://new-mint.example"}
    proof = Proof(
        amount=1,
        id="new-keyset",
        secret="refreshed",
        C="02" + "22" * 32,
    )
    stored = {wallet.home_relay: []}

    class PlaintextNip44:
        def __init__(self, keys):
            pass

        def encrypt(self, content, to_pub_k):
            return content

    class MemoryPool:
        def __init__(self, relays):
            self.relays = relays if isinstance(relays, list) else [relays]

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        def publish(self, event):
            for relay in self.relays:
                if all(str(existing.id) != str(event.id) for existing in stored[relay]):
                    stored[relay].append(event)

        async def query(self, filters):
            event_ids = set(filters[0].get("ids", []))
            return [
                event
                for relay in self.relays
                for event in stored[relay]
                if not event_ids or str(event.id) in event_ids
            ]

    monkeypatch.setattr(acorn_module, "ExtendedNIP44Encrypt", PlaintextNip44)
    monkeypatch.setattr(acorn_module, "ClientPool", MemoryPool)
    monkeypatch.setattr(acorn_module.asyncio, "sleep", AsyncMock())

    result = await wallet.add_proofs_obj([proof], verify=True)

    assert result["verified"] is True
    assert len(result["event_ids"]) == 1
    assert result["verification"][wallet.home_relay]["readable"] is True


@pytest.mark.asyncio
async def test_issue_token_does_not_double_decrement_empty_wallet_balance():
    wallet = wallet_with_key()
    keyset = "00f300c64b950282"
    wallet.proof_events = SimpleNamespace(proof_events=[])
    wallet.proof_event_ids = []
    wallet.events = 1
    wallet.known_mints = {keyset: "https://mint.example"}
    wallet.proofs = [
        Proof(
            amount=1,
            id=keyset,
            secret="wallet-proof",
            C="02" + "11" * 32,
            Y="02" + "12" * 32,
        )
    ]
    wallet.balance = 1
    issued_proof = Proof(
        amount=1,
        id=keyset,
        secret="issued-proof",
        C="02" + "22" * 32,
        Y="02" + "23" * 32,
    )
    wallet._require_resolved_pending_melts = AsyncMock()
    wallet.swap_for_payment_multi = AsyncMock(return_value=[issued_proof])

    async def write_and_reload_empty_proof_set():
        wallet.balance = sum(proof.amount for proof in wallet.proofs)

    wallet.write_proofs = AsyncMock(side_effect=write_and_reload_empty_proof_set)

    token = await wallet.issue_token(1, comment="pytest issue token")

    assert token.startswith("cashuB")
    assert wallet.proofs == []
    assert wallet.balance == 0
    wallet.add_tx_history.assert_awaited_once()
