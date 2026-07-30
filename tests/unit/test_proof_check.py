from __future__ import annotations

import pytest

from acorn.acorn import Acorn
from acorn.models import Proof


class FakeResponse:
    def __init__(self, states):
        self._states = states

    def raise_for_status(self):
        return None

    def json(self):
        return {"states": self._states}


class FakeAsyncClient:
    states_by_url = {}
    posts = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, json, headers):
        self.posts.append({"url": url, "json": json, "headers": headers})
        return FakeResponse(self.states_by_url[url])


def make_wallet(proofs, known_mints):
    wallet = object.__new__(Acorn)
    wallet.proofs = proofs
    wallet.known_mints = known_mints
    wallet.balance = sum(proof.amount for proof in proofs)
    return wallet


@pytest.mark.asyncio
async def test_check_proofs_reports_states_without_mutating_wallet(monkeypatch):
    from acorn import acorn as acorn_module

    proofs = [
        Proof(id="keyset-a", amount=1, secret="one", C="02a", Y="03a"),
        Proof(id="keyset-a", amount=1, secret="one", C="02a", Y="03a"),
        Proof(id="keyset-a", amount=2, secret="two", C="02b", Y="03b"),
        Proof(id="keyset-a", amount=4, secret="four", C="02c", Y="03c"),
    ]
    wallet = make_wallet(proofs, {"keyset-a": "https://mint.example.com/"})
    before_proofs = [proof.model_dump() for proof in wallet.proofs]
    before_mints = dict(wallet.known_mints)
    before_balance = wallet.balance

    FakeAsyncClient.posts = []
    FakeAsyncClient.states_by_url = {
        "https://mint.example.com/v1/checkstate": [
            {"state": "UNSPENT"},
            {"state": "SPENT"},
            {"state": "PENDING"},
        ]
    }
    monkeypatch.setattr(acorn_module.httpx, "AsyncClient", FakeAsyncClient)

    report = await wallet.check_proofs()

    assert report["read_only"] is True
    assert report["status"] == "inconclusive"
    assert report["requires_repair"] is True
    assert report["wallet"] == {"proof_count": 4, "amount": 8}
    assert report["checked"] == {"proof_count": 3, "amount": 7}
    assert report["mint_confirmed_unspent"] == {"proof_count": 1, "amount": 1}
    assert report["states"]["SPENT"] == {"proof_count": 1, "amount": 2}
    assert report["states"]["PENDING"] == {"proof_count": 1, "amount": 4}
    assert report["structural"]["duplicate_proofs"] == 1
    assert FakeAsyncClient.posts[0]["json"] == {"Ys": ["03a", "03b", "03c"]}

    assert [proof.model_dump() for proof in wallet.proofs] == before_proofs
    assert wallet.known_mints == before_mints
    assert wallet.balance == before_balance


@pytest.mark.asyncio
async def test_check_proofs_reports_unknown_keyset_without_network_call(monkeypatch):
    from acorn import acorn as acorn_module

    wallet = make_wallet(
        [Proof(id="missing", amount=8, secret="secret", C="02a", Y="03a")],
        {},
    )
    FakeAsyncClient.posts = []
    FakeAsyncClient.states_by_url = {}
    monkeypatch.setattr(acorn_module.httpx, "AsyncClient", FakeAsyncClient)

    report = await wallet.check_proofs()

    assert report["status"] == "inconclusive"
    assert report["requires_repair"] is True
    assert report["states"]["UNKNOWN"] == {"proof_count": 1, "amount": 8}
    assert report["errors"] == ["No mint mapping for keyset missing"]
    assert FakeAsyncClient.posts == []


@pytest.mark.asyncio
async def test_check_proofs_treats_response_length_mismatch_as_inconclusive(monkeypatch):
    from acorn import acorn as acorn_module

    wallet = make_wallet(
        [Proof(id="keyset-a", amount=2, secret="two", C="02b", Y="03b")],
        {"keyset-a": "https://mint.example.com"},
    )
    FakeAsyncClient.posts = []
    FakeAsyncClient.states_by_url = {
        "https://mint.example.com/v1/checkstate": [],
    }
    monkeypatch.setattr(acorn_module.httpx, "AsyncClient", FakeAsyncClient)

    report = await wallet.check_proofs()

    assert report["status"] == "inconclusive"
    assert report["requires_repair"] is False
    assert report["states"]["UNKNOWN"] == {"proof_count": 1, "amount": 2}
    assert "returned 0 states for 1 proofs" in report["errors"][0]


@pytest.mark.asyncio
async def test_check_proofs_clean_wallet_needs_no_repair(monkeypatch):
    from acorn import acorn as acorn_module

    wallet = make_wallet(
        [Proof(id="keyset-a", amount=2, secret="two", C="02b", Y="03b")],
        {"keyset-a": "https://mint.example.com"},
    )
    FakeAsyncClient.posts = []
    FakeAsyncClient.states_by_url = {
        "https://mint.example.com/v1/checkstate": [{"state": "UNSPENT"}],
    }
    monkeypatch.setattr(acorn_module.httpx, "AsyncClient", FakeAsyncClient)

    report = await wallet.check_proofs()

    assert report["status"] == "clean"
    assert report["requires_repair"] is False
    assert report["mint_confirmed_unspent"] == {"proof_count": 1, "amount": 2}
    assert report["recommendation"] == "No repair indicated."

