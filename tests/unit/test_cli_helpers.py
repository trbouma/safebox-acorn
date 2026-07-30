from __future__ import annotations

import importlib
import os
from pathlib import Path
import pytest
import yaml
from click.testing import CliRunner


def _load_cli(monkeypatch, tmp_path):
    default_oqs_path = Path.home() / "_oqs"
    if default_oqs_path.exists():
        monkeypatch.setenv("OQS_INSTALL_PATH", str(default_oqs_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    return importlib.import_module("acorn.cli_acorn")


def test_normalize_relay_adds_wss(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    assert cli._normalize_relay("relay.example.com") == "wss://relay.example.com"
    assert cli._normalize_relay("wss://relay.example.com") == "wss://relay.example.com"
    assert cli._normalize_relay("ws://localhost:7777") == "ws://localhost:7777"


def test_normalize_mint_adds_https(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    assert cli._normalize_mint("mint.example.com") == "https://mint.example.com"
    assert cli._normalize_mint("https://mint.example.com") == "https://mint.example.com"
    assert cli._normalize_mint("http://localhost:3338") == "http://localhost:3338"


def test_split_csv_trims_spaces(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    assert cli._split_csv("relay.one, relay.two,,relay.three") == [
        "relay.one",
        "relay.two",
        "relay.three",
    ]


def test_minimize_config_keeps_recovery_essentials(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    minimized = cli._minimize_config(
        {
            "nsec": "nsec1example",
            "home_relay": "wss://relay.example.com",
            "mints": ["https://mint.example.com"],
            "public_relays": ["wss://relay.damus.io"],
            "logging_level": 10,
        }
    )

    assert minimized == {
        "nsec": "nsec1example",
        "home_relay": "wss://relay.example.com",
    }


def test_minimize_config_defaults_home_relay(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    minimized = cli._minimize_config({"nsec": "nsec1example"})

    assert minimized == {
        "nsec": "nsec1example",
        "home_relay": cli.default_home_relay,
    }


def test_format_recovery_material(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    rendered = cli._format_recovery_material(
        {
            "home_relay": "wss://relay.example.com",
            "seed_phrase": "alpha beta gamma",
            "nsec": "nsec1example",
        }
    )

    assert rendered.splitlines() == [
        "home_relay: wss://relay.example.com",
        "seed_phrase: alpha beta gamma",
        "nsec: nsec1example",
    ]


def test_resolve_config_path_from_explicit_value(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    config_path = cli._resolve_config_path("./test-wallet.yml")

    assert config_path == os.path.abspath("./test-wallet.yml")


def test_extract_early_config_path_from_argv(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    assert cli._extract_early_config_path(["--config", "./wallet.yml", "balance"]) == "./wallet.yml"
    assert cli._extract_early_config_path(["--config=./wallet.yml", "balance"]) == "./wallet.yml"


def test_extract_early_config_path_from_env(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)
    monkeypatch.setenv("ACORN_CONFIG", "./env-wallet.yml")

    assert cli._extract_early_config_path(["balance"]) == "./env-wallet.yml"


def test_test_wallet_config_uses_test_relay_override(monkeypatch, tmp_path):
    from tests.helpers import require_test_wallet_config

    config_path = tmp_path / "test-wallet.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "nsec": "nsec1example",
                "home_relay": "wss://stored-relay.example.com",
            }
        )
    )
    monkeypatch.setenv("ACORN_TEST_WALLET_CONFIG", str(config_path))
    monkeypatch.setenv("ACORN_TEST_RELAY", "ws://beelink:7777")

    config = require_test_wallet_config()

    assert config["home_relay"] == "ws://beelink:7777"


def test_transfer_relay_prefers_explicit_transfer_relay(monkeypatch):
    from tests.helpers import get_test_transfer_relay

    monkeypatch.setenv("ACORN_TEST_RELAY", "ws://beelink:7777")
    monkeypatch.setenv("ACORN_TEST_TRANSFER_RELAY", "relay.example.com")

    assert get_test_transfer_relay("wss://wallet-relay.example.com") == "wss://relay.example.com"


def test_transfer_relay_uses_relay_scenario_when_no_explicit_override(monkeypatch):
    from tests.helpers import get_test_transfer_relay

    monkeypatch.setenv("ACORN_TEST_RELAY", "ws://beelink:7777")

    assert (
        get_test_transfer_relay(
            "wss://wallet-relay.example.com",
            relay="relay.thirdparty.example.com",
        )
        == "wss://relay.thirdparty.example.com"
    )


def test_configured_test_mints_prefers_explicit_override(monkeypatch):
    from tests.helpers import configured_test_mints

    monkeypatch.setenv("ACORN_TEST_MINT", "mint.endfiat.money")

    assert configured_test_mints(fallback_mints=["https://mint.getsafebox.app"]) == [
        "https://mint.endfiat.money"
    ]


def test_configured_test_mints_uses_fallback_when_no_override(monkeypatch):
    from tests.helpers import configured_test_mints

    monkeypatch.delenv("ACORN_TEST_MINT", raising=False)

    assert configured_test_mints(fallback_mints=["mint.endfiat.money"]) == [
        "https://mint.endfiat.money"
    ]


def test_get_receive_nsec_prefers_explicit_override(monkeypatch):
    from tests.helpers import get_receive_nsec

    monkeypatch.setenv("ACORN_RECEIVE_NSEC", "nsec1override")

    assert get_receive_nsec({"nsec": "nsec1source"}) == "nsec1override"


def test_get_receive_nsec_defaults_to_source_wallet(monkeypatch, capsys):
    from tests.helpers import get_receive_nsec

    monkeypatch.delenv("ACORN_RECEIVE_NSEC", raising=False)

    assert get_receive_nsec({"nsec": "nsec1source"}) == "nsec1source"
    assert "receive nsec inherited from source wallet" in capsys.readouterr().out


def test_proof_to_dict_omits_empty_witness_for_mint_api():
    from acorn.models import Proof

    proof = Proof(id="00abc", amount=1, secret="secret", C="02abc", Y="03abc")

    assert proof.to_dict() == {
        "id": "00abc",
        "amount": 1,
        "secret": "secret",
        "C": "02abc",
    }


def test_live_relay_scenarios_include_optional_third_party(monkeypatch):
    from tests.helpers import live_relay_scenarios

    monkeypatch.delenv("ACORN_RELAY_SCENARIO", raising=False)
    monkeypatch.setenv("ACORN_TEST_RELAY", "ws://beelink:7777")
    monkeypatch.setenv("ACORN_THIRD_PARTY_RELAY", "relay.thirdparty.example.com")

    scenarios = [param.values[0] for param in live_relay_scenarios()]

    assert scenarios == [
        {
            "name": "controlled",
            "relay": "ws://beelink:7777",
            "config_suffix": "",
        },
        {
            "name": "third-party",
            "relay": "wss://relay.thirdparty.example.com",
            "config_suffix": "-third-party",
        },
    ]


def test_live_relay_scenarios_can_select_third_party_only(monkeypatch):
    from tests.helpers import live_relay_scenarios

    monkeypatch.setenv("ACORN_TEST_RELAY", "ws://beelink:7777")
    monkeypatch.setenv("ACORN_THIRD_PARTY_RELAY", "relay.thirdparty.example.com")
    monkeypatch.setenv("ACORN_RELAY_SCENARIO", "third-party")

    scenarios = [param.values[0] for param in live_relay_scenarios()]

    assert scenarios == [
        {
            "name": "third-party",
            "relay": "wss://relay.thirdparty.example.com",
            "config_suffix": "-third-party",
        },
    ]


def test_live_relay_scenarios_can_select_controlled_only(monkeypatch):
    from tests.helpers import live_relay_scenarios

    monkeypatch.setenv("ACORN_TEST_RELAY", "ws://beelink:7777")
    monkeypatch.setenv("ACORN_THIRD_PARTY_RELAY", "relay.thirdparty.example.com")
    monkeypatch.setenv("ACORN_RELAY_SCENARIO", "controlled")

    scenarios = [param.values[0] for param in live_relay_scenarios()]

    assert scenarios == [
        {
            "name": "controlled",
            "relay": "ws://beelink:7777",
            "config_suffix": "",
        },
    ]


def test_skip_if_relay_unsuitable_short_circuits_later_scenarios(monkeypatch, capsys):
    from tests import helpers

    helpers.UNSUITABLE_RELAYS.clear()
    helpers.RELAY_SUITABILITY_RESULTS.clear()
    helpers.UNSUITABLE_RELAYS["wss://relay.unsuitable.example.com"] = (
        "wallet-bootstrap-readback: wallet bootstrap state was not readable after initialization"
    )

    with pytest.raises(pytest.skip.Exception) as exc:
        helpers.skip_if_relay_unsuitable("wss://relay.unsuitable.example.com")

    capsys.readouterr()
    assert "already marked unsuitable" in str(exc.value)
    helpers.UNSUITABLE_RELAYS.clear()
    helpers.RELAY_SUITABILITY_RESULTS.clear()


def test_format_tx_history_entry_credit(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    rendered = cli._format_tx_history_entry(
        {
            "create_time": "2026-07-29 12:12:22",
            "tx_type": "C",
            "amount": 3,
            "comment": "ecash transfer received",
            "tendered_amount": 3.0,
            "tendered_currency": "SAT",
            "fees": 0,
            "current_balance": 25,
        }
    )

    assert "Credit" in rendered
    assert "+3 sats" in rendered
    assert "balance: 25 sats" in rendered
    assert "ecash transfer received" in rendered


def test_format_tx_history_entry_debit(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    rendered = cli._format_tx_history_entry(
        {
            "create_time": "2026-07-29 12:04:07",
            "tx_type": "D",
            "amount": 1,
            "comment": "gift wrapped test",
            "tendered_amount": 1.0,
            "tendered_currency": "SAT",
            "fees": 0,
            "current_balance": 20,
        }
    )

    assert "Debit" in rendered
    assert "-1 sats" in rendered
    assert "gift wrapped test" in rendered


def test_format_tx_history_entry_handles_missing_optional_fields(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    rendered = cli._format_tx_history_entry(
        {
            "tx_type": "C",
            "amount": 2,
        }
    )

    assert "Credit" in rendered
    assert "+2 sats" in rendered


def test_balance_by_mint_groups_keysets(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    class Wallet:
        known_mints = {
            "keyset-a": "https://mint.one",
            "keyset-b": "https://mint.one",
            "keyset-c": "https://mint.two",
        }

        def _proofs_by_keyset(self):
            return (
                {
                    "keyset-a": [object(), object()],
                    "keyset-b": [object()],
                    "keyset-c": [object()],
                },
                {
                    "keyset-a": 3,
                    "keyset-b": 5,
                    "keyset-c": 2,
                },
            )

    rows = cli._balance_by_mint(Wallet())

    assert rows == [
        {
            "mint": "https://mint.one",
            "balance": 8,
            "unit": "sat",
            "proof_count": 3,
            "keysets": [
                {"keyset": "keyset-a", "balance": 3, "unit": "sat", "proof_count": 2},
                {"keyset": "keyset-b", "balance": 5, "unit": "sat", "proof_count": 1},
            ],
        },
        {
            "mint": "https://mint.two",
            "balance": 2,
            "unit": "sat",
            "proof_count": 1,
            "keysets": [
                {"keyset": "keyset-c", "balance": 2, "unit": "sat", "proof_count": 1},
            ],
        },
    ]


def test_format_balance_by_mint(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    rendered = cli._format_balance_by_mint(
        [
            {
                "mint": "https://mint.one",
                "balance": 8,
                "proof_count": 3,
                "keysets": [
                    {"keyset": "keyset-b", "balance": 5, "proof_count": 1},
                    {"keyset": "keyset-a", "balance": 3, "proof_count": 2},
                ],
            }
        ]
    )

    assert "Mint balances:" in rendered
    assert "https://mint.one: 8 sats in 3 proofs" in rendered
    assert "keyset keyset-a: 3 sats in 2 proofs" in rendered
    assert "keyset keyset-b: 5 sats in 1 proofs" in rendered


def test_burn_rejects_ecash_and_lightning_recipients(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    result = CliRunner().invoke(
        cli.burn,
        [
            "--send-to",
            "alice@example.com",
            "--pay-to",
            "alice@example.com",
            "--force",
        ],
    )

    assert result.exit_code != 0
    assert "Use only one of --send-to" in result.output


@pytest.mark.asyncio
async def test_burn_lightning_auto_amount_uses_fee_aware_quote():
    from acorn.acorn import Acorn

    wallet = object.__new__(Acorn)
    wallet.home_relay = "wss://relay.example.com"
    wallet.pubkey_hex = "00" * 32
    wallet.pubkey_bech32 = "npub1example"

    captured = {}

    wallet._normalize_relays = lambda relays: relays
    wallet.get_balance = lambda: 21

    async def max_payable_lightning_amount(lnaddress, balance, comment):
        captured["quote"] = {
            "lnaddress": lnaddress,
            "balance": balance,
            "comment": comment,
        }
        return {
            "amount": 20,
            "fee_reserve": 1,
            "total": 21,
            "mode": "lightning",
            "mint": "https://mint.example.com",
        }

    async def pay_multi(amount, lnaddress, comment):
        captured["payment"] = {
            "amount": amount,
            "lnaddress": lnaddress,
            "comment": comment,
        }
        return "Payment of 20 sats with fee 1 sats successful!", 1

    async def load_data():
        return None

    async def query_authored_events_for_burn(relays, kinds, limit):
        return []

    wallet._max_payable_lightning_amount = max_payable_lightning_amount
    wallet.pay_multi = pay_multi
    wallet.load_data = load_data
    wallet._query_authored_events_for_burn = query_authored_events_for_burn

    result = await wallet.burn_wallet(pay_to="alice@example.com")

    assert captured["quote"]["balance"] == 21
    assert captured["payment"]["amount"] == 20
    assert result["payment"]["auto_amount"] is True
    assert result["payment"]["amount"] == 20
    assert result["payment"]["fees"] == 1
    assert result["payment"]["estimated_total"] == 21
