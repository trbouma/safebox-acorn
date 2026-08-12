from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from monstr.encrypt import Keys

from acorn import acorn as acorn_module
from acorn.acorn import Acorn
from acorn.models import NIP60Proofs, Proof


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
    wallet.proof_event_ids = []
    wallet.balance = 0
    wallet.events = 0
    wallet.logger = logging.getLogger("proof-state-safety-test")
    wallet.handle = "proof-test-wallet"
    wallet._lock_acquired_at = None
    wallet._lock_owner = None
    wallet._lock_token = None
    wallet._lock_depth = 0
    wallet._process_wallet_lock = None
    return wallet


@pytest.mark.asyncio
async def test_owned_wallet_lock_cannot_be_stolen_by_second_actor(monkeypatch):
    acorn_module._PROCESS_WALLET_LOCKS.clear()
    first = wallet_with_key()
    second = wallet_with_key()
    relay_state = {"lock": "FALSE"}

    async def get_wallet_info(label):
        return relay_state[label]

    async def set_wallet_info(label, label_info, **kwargs):
        relay_state[label] = label_info
        return {"status": "OK"}

    first.get_wallet_info = AsyncMock(side_effect=get_wallet_info)
    second.get_wallet_info = AsyncMock(side_effect=get_wallet_info)
    first.set_wallet_info = AsyncMock(side_effect=set_wallet_info)
    second.set_wallet_info = AsyncMock(side_effect=set_wallet_info)

    await first.acquire_lock(attempts=1)
    with pytest.raises(RuntimeError, match="Wallet is busy"):
        await second.acquire_lock(attempts=1)

    assert first._lock_token
    assert Acorn._parse_wallet_lock(relay_state["lock"])["active"] is True
    await first.release_lock()
    assert relay_state["lock"] == "FALSE"


@pytest.mark.asyncio
async def test_reconcile_spent_proofs_removes_only_mint_confirmed_spent(monkeypatch):
    wallet = wallet_with_key()
    keyset = "test-keyset"
    mint = "https://mint.example"
    spent = Proof(amount=2, id=keyset, secret="spent", C="spent-c", Y="spent-y")
    unspent = Proof(amount=4, id=keyset, secret="unspent", C="unspent-c", Y="unspent-y")
    wallet.proofs = [spent, unspent]
    wallet.balance = 6
    wallet.known_mints = {keyset: mint}
    wallet._load_proofs = AsyncMock()
    wallet.write_proofs = AsyncMock()
    wallet.check_proofs = AsyncMock(return_value={
        "status": "repair-recommended",
        "keysets": [{
            "keyset": keyset,
            "states": {"SPENT": {"proof_count": 1, "amount": 2}},
        }],
    })

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"states": [{"state": "SPENT"}, {"state": "UNSPENT"}]}

    class FakeHttpClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(acorn_module.httpx, "AsyncClient", FakeHttpClient)

    result = await wallet._reconcile_spent_proofs_locked()

    assert result == {"removed": 1, "amount": 2, "balance": 4}
    assert wallet.proofs == [unspent]
    wallet.write_proofs.assert_awaited_once()


@pytest.mark.asyncio
async def test_public_stale_reconciliation_uses_narrow_locked_operation():
    wallet = wallet_with_key()
    wallet.acquire_lock = AsyncMock()
    wallet.release_lock = AsyncMock()
    wallet._require_resolved_pending_melts = AsyncMock()
    wallet._reconcile_spent_proofs_locked = AsyncMock(
        return_value={"removed": 1, "amount": 2, "balance": 4}
    )

    result = await wallet.reconcile_stale_proofs()

    assert result == {
        "status": "OK",
        "operation": "reconcile-stale-proofs",
        "removed": 1,
        "amount": 2,
        "balance": 4,
    }
    wallet.acquire_lock.assert_awaited_once()
    wallet._require_resolved_pending_melts.assert_awaited_once()
    wallet._reconcile_spent_proofs_locked.assert_awaited_once()
    wallet.release_lock.assert_awaited_once()


@pytest.mark.asyncio
async def test_public_stale_reconciliation_releases_lock_when_state_is_inconclusive():
    wallet = wallet_with_key()
    wallet.acquire_lock = AsyncMock()
    wallet.release_lock = AsyncMock()
    wallet._require_resolved_pending_melts = AsyncMock()
    wallet._reconcile_spent_proofs_locked = AsyncMock(
        side_effect=RuntimeError("Mint proof state is inconclusive; no proofs were removed")
    )

    with pytest.raises(RuntimeError, match="inconclusive"):
        await wallet.reconcile_stale_proofs()

    wallet.release_lock.assert_awaited_once()


@pytest.mark.asyncio
async def test_write_proofs_rejects_same_balance_with_wrong_proof_identity():
    wallet = wallet_with_key()
    keyset = "test-keyset"
    expected = Proof(amount=4, id=keyset, secret="expected", C="expected-c", Y="expected-y")
    unexpected = Proof(amount=4, id=keyset, secret="unexpected", C="unexpected-c", Y="unexpected-y")
    wallet.proofs = [expected]
    wallet.balance = 4
    wallet.known_mints = {keyset: "https://mint.example"}
    wallet.add_proofs_obj = AsyncMock(return_value={"verified": True})
    wallet._async_delete_events_by_ids = AsyncMock()

    class MemoryPool:
        def __init__(self, relays):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def query(self, filters):
            return []

    async def load_unexpected():
        wallet.proofs = [unexpected]
        wallet.balance = 4

    wallet._load_proofs = AsyncMock(side_effect=load_unexpected)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(acorn_module, "ClientPool", MemoryPool)
        monkeypatch.setattr(acorn_module.asyncio, "sleep", AsyncMock())
        with pytest.raises(RuntimeError, match="unexpected relay proofs"):
            await wallet.write_proofs()

    assert wallet.proofs == [expected]
    assert wallet.balance == 4


@pytest.mark.asyncio
async def test_load_proofs_ignores_events_referenced_by_authored_deletions(monkeypatch):
    wallet = wallet_with_key()
    keyset = "test-keyset"
    mint = "https://mint.example"
    stale = Proof(amount=32768, id=keyset, secret="stale", C="stale-c", Y="stale-y")
    current = Proof(amount=5, id=keyset, secret="current", C="current-c", Y="current-y")

    stale_event = SimpleNamespace(
        id="stale-event",
        kind=7375,
        tags=[],
        content=NIP60Proofs(mint=mint, proofs=[stale]).model_dump_json(),
    )
    current_event = SimpleNamespace(
        id="current-event",
        kind=7375,
        tags=[],
        content=NIP60Proofs(mint=mint, proofs=[current]).model_dump_json(),
    )
    deletion_event = SimpleNamespace(
        id="delete-stale",
        kind=5,
        tags=[["e", "stale-event"], ["k", "7375"]],
        content="",
    )

    class PlaintextNip44:
        def __init__(self, keys):
            pass

        def decrypt(self, content, pubkey):
            return content

    class MemoryPool:
        def __init__(self, relays):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def query(self, filters):
            kinds = set(filters[0].get("kinds", []))
            if kinds == {5}:
                return [deletion_event]
            return [stale_event, current_event]

    monkeypatch.setattr(acorn_module, "NIP44Encrypt", PlaintextNip44)
    monkeypatch.setattr(acorn_module, "ClientPool", MemoryPool)

    await wallet._load_proofs()

    assert wallet.balance == 5
    assert [proof.secret for proof in wallet.proofs] == ["current"]
    assert wallet.proof_event_ids == ["current-event"]
    assert wallet.events == 1
    assert wallet.known_mints[keyset] == mint


@pytest.mark.asyncio
async def test_receive_maintenance_is_disabled_without_loading_or_swapping(monkeypatch):
    wallet = wallet_with_key()
    wallet._load_proofs = AsyncMock()
    wallet.swap_multi_each = AsyncMock()
    wallet.swap_multi_consolidate = AsyncMock()
    monkeypatch.setattr(acorn_module, "RECEIVE_PROOF_MAINTENANCE_ENABLED", False)

    await wallet._maybe_maintain_received_proofs("deposit", added_proof_count=3)

    wallet._load_proofs.assert_not_awaited()
    wallet.swap_multi_each.assert_not_awaited()
    wallet.swap_multi_consolidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_mint_proofs_updates_balance_after_verified_deposit(monkeypatch):
    wallet = wallet_with_key()
    wallet.home_mint = "https://mint.example"
    wallet.proofs = [
        Proof(
            amount=31,
            id="existing-keyset",
            secret="existing",
            C="existing-c",
            Y="existing-y",
        )
    ]
    wallet.balance = 31
    wallet.acquire_lock = AsyncMock()
    wallet.release_lock = AsyncMock()
    wallet.add_proofs_obj = AsyncMock(return_value={"verified": True})

    serialized_point = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
    dummy_point = SimpleNamespace(serialize=lambda: bytes.fromhex(serialized_point))
    monkeypatch.setattr(
        acorn_module,
        "step1_alice",
        lambda secret: (dummy_point, object(), dummy_point),
    )
    monkeypatch.setattr(acorn_module, "step3_alice", lambda *args: dummy_point)

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeHttpClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url, **kwargs):
            if url.endswith("/v1/keysets"):
                return Response(
                    {
                        "keysets": [
                            {"id": "deposit-keyset", "unit": "sat", "active": True}
                        ]
                    }
                )
            return Response(
                {
                    "keysets": [
                        {
                            "keys": {
                                "1": serialized_point,
                                "4": serialized_point,
                                "16": serialized_point,
                            }
                        }
                    ]
                }
            )

        async def post(self, url, **kwargs):
            return Response(
                {
                    "signatures": [
                        {"amount": 1, "C_": serialized_point},
                        {"amount": 4, "C_": serialized_point},
                        {"amount": 16, "C_": serialized_point},
                    ]
                }
            )

    monkeypatch.setattr(acorn_module.httpx, "AsyncClient", FakeHttpClient)

    result = await wallet._mint_proofs("paid-quote", 21)

    assert result is True
    assert wallet.balance == 52
    assert sum(proof.amount for proof in wallet.proofs) == 52
    assert len(wallet.proofs) == 4
    assert wallet.known_mints["deposit-keyset"] == "https://mint.example"
    wallet.add_proofs_obj.assert_awaited_once()
    persisted_proofs = wallet.add_proofs_obj.await_args.args[0]
    assert sum(proof.amount for proof in persisted_proofs) == 21
    assert wallet.add_proofs_obj.await_args.kwargs == {"verify": True}
    wallet.release_lock.assert_awaited_once()


@pytest.mark.asyncio
async def test_swap_each_persists_first_replacement_before_later_failure(monkeypatch):
    wallet = wallet_with_key()
    keyset = "test-keyset"
    mint = "https://mint.example"
    wallet.proofs = [
        Proof(amount=1, id=keyset, secret="one", C="one-c", Y="one-y"),
        Proof(amount=1, id=keyset, secret="two", C="two-c", Y="two-y"),
    ]
    wallet.known_mints = {keyset: mint}
    wallet.proof_event_ids = ["source-event"]
    wallet.acquire_lock = AsyncMock()
    wallet.release_lock = AsyncMock()
    wallet._require_resolved_pending_melts = AsyncMock()
    wallet.proof_safety_audit = AsyncMock(
        return_value={"safe_to_swap": True, "reason": "ok"}
    )
    wallet.add_proofs_obj = AsyncMock(return_value={"verified": True})
    wallet._async_delete_events_by_ids = AsyncMock()

    async def load_existing_proofs():
        wallet.proofs = [
            Proof(amount=1, id=keyset, secret="one", C="one-c", Y="one-y"),
            Proof(amount=1, id=keyset, secret="two", C="two-c", Y="two-y"),
        ]
        wallet.known_mints = {keyset: mint}
        wallet.proof_event_ids = ["source-event"]

    wallet._load_proofs = AsyncMock(side_effect=load_existing_proofs)

    serialized_point = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
    dummy_point = SimpleNamespace(serialize=lambda: bytes.fromhex(serialized_point))
    monkeypatch.setattr(
        acorn_module,
        "step1_alice",
        lambda secret: (dummy_point, object(), dummy_point),
    )
    monkeypatch.setattr(acorn_module, "step3_alice", lambda *args: dummy_point)

    class Response:
        def __init__(self, payload=None, status_code=200, text=""):
            self._payload = payload or {}
            self.status_code = status_code
            self.text = text
            self.is_error = status_code >= 400

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.is_error:
                raise RuntimeError(f"HTTP {self.status_code}")

    class FakeHttpClient:
        swap_calls = 0

        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url, **kwargs):
            return Response({"keysets": [{"keys": {"1": serialized_point}}]})

        async def post(self, url, **kwargs):
            if url.endswith("/v1/checkstate"):
                return Response(
                    {"states": [{"state": "UNSPENT"}, {"state": "UNSPENT"}]}
                )
            self.__class__.swap_calls += 1
            if self.__class__.swap_calls == 1:
                return Response(
                    {"signatures": [{"amount": 1, "C_": serialized_point}]}
                )
            return Response({"detail": "later swap failed"}, 500, "later swap failed")

    monkeypatch.setattr(acorn_module.httpx, "AsyncClient", FakeHttpClient)

    with pytest.raises(RuntimeError, match="later swap failed"):
        await wallet.swap_multi_each()

    wallet.add_proofs_obj.assert_awaited_once()
    persisted_args, persisted_kwargs = wallet.add_proofs_obj.await_args
    assert persisted_kwargs == {"verify": True}
    assert sum(proof.amount for proof in persisted_args[0]) == 1
    wallet._async_delete_events_by_ids.assert_not_awaited()
    wallet.release_lock.assert_awaited_once()
