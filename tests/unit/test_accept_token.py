from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from monstr.encrypt import Keys

from acorn import acorn as acorn_module
from acorn.acorn import Acorn, AmbiguousSwapError, RetryablePreSwapError
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
    wallet._require_resolved_pending_melts = AsyncMock()
    wallet._keyset_input_fee_ppk = AsyncMock(return_value=0)
    wallet.add_proofs_obj = AsyncMock(return_value={"verified": True})
    wallet.add_tx_history = AsyncMock()
    wallet._maybe_maintain_received_proofs = AsyncMock()
    return wallet


def test_relay_verify_timeout_default_and_validation():
    assert acorn_module.RELAY_VERIFY_TIMEOUT_SECONDS > 0
    assert acorn_module._positive_timeout("90", name="timeout") == 90.0
    with pytest.raises(ValueError, match="must be a positive number"):
        acorn_module._positive_timeout("0", name="timeout")
    with pytest.raises(ValueError, match="must be a positive number"):
        acorn_module._positive_timeout("invalid", name="timeout")


@pytest.mark.asyncio
async def test_keyset_fee_transport_failure_is_retryable_before_swap(monkeypatch):
    wallet = wallet_with_key()
    keyset = "00f300c64b950282"
    wallet.known_mints = {keyset: "https://mint.example"}

    class FailingHttpClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url, **kwargs):
            raise httpx.ConnectTimeout("mint unavailable")

    monkeypatch.setattr(acorn_module.httpx, "AsyncClient", FailingHttpClient)

    with pytest.raises(RetryablePreSwapError, match="before swap|keyset fees"):
        await Acorn._keyset_input_fee_ppk(wallet, keyset)

    wallet._preflight_proof_persistence = AsyncMock()
    proof = Proof(
        amount=2,
        id=keyset,
        secret="pre-swap-proof",
        C="02" + "31" * 32,
        Y="02" + "32" * 32,
    )
    with pytest.raises(RetryablePreSwapError, match="keyset lookup failed"):
        await wallet.swap_for_payment_multi(keyset, [proof], 1)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        RetryablePreSwapError("safe to retry"),
        AmbiguousSwapError("outcome unknown"),
    ],
)
async def test_issue_token_preserves_typed_swap_failures(failure):
    wallet = wallet_with_key()
    keyset = "00f300c64b950282"
    wallet.known_mints = {keyset: "https://mint.example"}
    wallet.proofs = [
        Proof(
            amount=2,
            id=keyset,
            secret="wallet-proof",
            C="02" + "11" * 32,
            Y="02" + "12" * 32,
        )
    ]
    wallet.balance = 2
    wallet.swap_for_payment_multi = AsyncMock(side_effect=failure)

    with pytest.raises(type(failure), match=str(failure)):
        await wallet.issue_token(1)


@pytest.mark.asyncio
async def test_swap_read_timeout_after_submission_is_ambiguous(monkeypatch):
    wallet = wallet_with_key()
    keyset = "00f300c64b950282"
    wallet.known_mints = {keyset: "https://mint.example"}
    wallet._preflight_proof_persistence = AsyncMock()
    proof = Proof(
        amount=2,
        id=keyset,
        secret="ambiguous-proof",
        C="02" + "41" * 32,
        Y="02" + "42" * 32,
    )

    class Response:
        def __init__(self, payload):
            self.payload = payload
            self.status_code = 200
            self.text = ""

        def json(self):
            return self.payload

        def raise_for_status(self):
            return None

    class AmbiguousHttpClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url, **kwargs):
            return Response(
                {
                    "keysets": [
                        {
                            "id": keyset,
                            "active": True,
                            "unit": "sat",
                            "input_fee_ppk": 0,
                        }
                    ]
                }
            )

        async def post(self, url, **kwargs):
            if url.endswith("/v1/checkstate"):
                return Response({"states": [{"state": "UNSPENT"}]})
            raise httpx.ReadTimeout("mint response lost")

    monkeypatch.setattr(acorn_module.httpx, "AsyncClient", AmbiguousHttpClient)

    with pytest.raises(AmbiguousSwapError, match="outcome is unknown"):
        await wallet.swap_for_payment_multi(keyset, [proof], 1)


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
    history = wallet.add_tx_history.await_args.kwargs
    assert history["amount"] == 3
    assert history["tendered_amount"] == 3
    assert history["fees"] == 0
    wallet._maybe_maintain_received_proofs.assert_not_awaited()


@pytest.mark.asyncio
async def test_accept_token_records_net_amount_after_mint_input_fee(monkeypatch):
    wallet = wallet_with_key()
    mint = "https://fee-mint.example"
    incoming = Proof(
        amount=77,
        id="fee-keyset",
        secret="incoming",
        C="02" + "11" * 32,
    )
    refreshed = [
        Proof(amount=64, id="new-keyset", secret="new-64", C="02" + "22" * 32),
        Proof(amount=8, id="new-keyset", secret="new-8", C="02" + "33" * 32),
        Proof(amount=4, id="new-keyset", secret="new-4", C="02" + "44" * 32),
    ]
    token_obj = SimpleNamespace(mint=mint, unit="sat", proofs=[incoming])
    monkeypatch.setattr(
        acorn_module.TokenV4,
        "deserialize",
        classmethod(lambda cls, token: token_obj),
    )
    wallet.swap_proofs = AsyncMock(return_value=refreshed)

    message, amount = await wallet.accept_token("cashuB-test")

    assert message == "Successfully accepted 76 sats!"
    assert amount == 76
    history = wallet.add_tx_history.await_args.kwargs
    assert history["amount"] == 76
    assert history["tendered_amount"] == 77
    assert history["tendered_currency"] == "SAT"
    assert history["fees"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("input_fee_ppk", "expected_amount"),
    [(0, 77), (1000, 76)],
)
async def test_swap_proofs_accounts_for_input_fee(
    monkeypatch,
    input_fee_ppk,
    expected_amount,
):
    wallet = wallet_with_key()
    wallet._preflight_proof_persistence = AsyncMock()
    mint = "https://fee-mint.example"
    input_keyset = "fee-keyset"
    output_keyset = "active-keyset"
    wallet.known_mints[input_keyset] = mint
    incoming = Proof(
        amount=77,
        id=input_keyset,
        secret="incoming",
        C="02" + "11" * 32,
    )
    captured = {}
    serialized_point = (
        "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
    )
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
            self.status_code = 200
            self.text = ""

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
                            {
                                "id": input_keyset,
                                "active": False,
                                "unit": "sat",
                                "input_fee_ppk": input_fee_ppk,
                            },
                            {
                                "id": output_keyset,
                                "active": True,
                                "unit": "sat",
                                "input_fee_ppk": 0,
                            },
                        ]
                    }
                )
            return Response(
                {
                    "keysets": [
                        {
                            "id": output_keyset,
                            "keys": {
                                str(amount): serialized_point
                                for amount in (1, 2, 4, 8, 16, 32, 64)
                            },
                        }
                    ]
                }
            )

        async def post(self, url, **kwargs):
            captured["swap"] = kwargs["json"]
            return Response(
                {
                    "signatures": [
                        {
                            "id": output_keyset,
                            "amount": output["amount"],
                            "C_": serialized_point,
                        }
                        for output in kwargs["json"]["outputs"]
                    ]
                }
            )

    monkeypatch.setattr(acorn_module.httpx, "AsyncClient", FakeHttpClient)

    refreshed = await wallet.swap_proofs(
        [incoming],
        mint_base=mint,
        unit="sat",
    )

    assert sum(output["amount"] for output in captured["swap"]["outputs"]) == expected_amount
    assert sum(proof.amount for proof in refreshed) == expected_amount


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
    assert wallet.add_tx_history.await_args.kwargs["fees"] == 0


@pytest.mark.asyncio
async def test_issue_token_selects_enough_inputs_to_cover_mint_fee():
    wallet = wallet_with_key()
    keyset = "00f300c64b950282"
    wallet.proof_events = SimpleNamespace(proof_events=[])
    wallet.proof_event_ids = []
    wallet.events = 1
    wallet.known_mints = {keyset: "https://fee-mint.example"}
    wallet.proofs = [
        Proof(
            amount=amount,
            id=keyset,
            secret=f"wallet-proof-{amount}",
            C="02" + f"{amount:02x}" * 32,
            Y="02" + f"{amount + 1:02x}" * 32,
        )
        for amount in (64, 32, 8, 2, 1)
    ]
    wallet.balance = 107
    wallet._keyset_input_fee_ppk = AsyncMock(return_value=1000)

    replacement_proofs = [
        Proof(amount=64, id=keyset, secret="issued-64", C="02" + "21" * 32),
        Proof(amount=32, id=keyset, secret="issued-32", C="02" + "22" * 32),
        Proof(amount=2, id=keyset, secret="issued-2", C="02" + "23" * 32),
        Proof(amount=1, id=keyset, secret="issued-1", C="02" + "24" * 32),
        Proof(amount=2, id=keyset, secret="change-2", C="02" + "25" * 32),
    ]
    wallet.swap_for_payment_multi = AsyncMock(return_value=replacement_proofs)

    async def write_and_reload_proof_set():
        wallet.balance = sum(proof.amount for proof in wallet.proofs)

    wallet.write_proofs = AsyncMock(side_effect=write_and_reload_proof_set)

    token = await wallet.issue_token(99, comment="fee-aware transfer")

    assert token.startswith("cashuB")
    selected = wallet.swap_for_payment_multi.await_args.args[1]
    assert [proof.amount for proof in selected] == [64, 32, 8]
    assert sum(proof.amount for proof in selected) == 104
    assert sum(proof.amount for proof in wallet.proofs) == 5
    history = wallet.add_tx_history.await_args.kwargs
    assert history["amount"] == 99
    assert history["tendered_amount"] == 99
    assert history["fees"] == 3
