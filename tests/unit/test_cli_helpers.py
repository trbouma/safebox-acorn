from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml
import click
from click.testing import CliRunner
from mnemonic import Mnemonic
from monstr.encrypt import Keys


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
    assert cli._normalize_mint("https://mint.example.com/") == "https://mint.example.com"
    assert cli._normalize_mint("testnut.cashu.space///") == "https://testnut.cashu.space"


def test_split_csv_trims_spaces(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    assert cli._split_csv("relay.one, relay.two,,relay.three") == [
        "relay.one",
        "relay.two",
        "relay.three",
    ]


def test_normalize_relay_csv_preserves_local_websocket_relays(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    assert cli._normalize_relay_csv(
        "ws://beelink:8735, relay.example.com"
    ) == [
        "ws://beelink:8735",
        "wss://relay.example.com",
    ]


def test_forced_proof_refresh_requires_explicit_acknowledgement(
    monkeypatch,
    tmp_path,
):
    cli = _load_cli(monkeypatch, tmp_path)

    def fail_if_constructed(*args, **kwargs):
        raise AssertionError("wallet must not load before refresh acknowledgement")

    monkeypatch.setattr(cli, "Acorn", fail_if_constructed)
    result = CliRunner().invoke(cli.repair_proofs, ["--refresh"])

    assert result.exit_code == 1
    assert "--refresh performs irreversible mint swaps" in result.output
    assert "--refresh --confirm-refresh" in result.output


def test_delete_record_requires_confirmation_before_loading_wallet(
    monkeypatch,
    tmp_path,
):
    cli = _load_cli(monkeypatch, tmp_path)

    def fail_if_constructed(*args, **kwargs):
        raise AssertionError("wallet must not load when deletion is declined")

    monkeypatch.setattr(cli, "Acorn", fail_if_constructed)

    result = CliRunner().invoke(
        cli.delete_record,
        ["Field Notes"],
        input="n\n",
    )

    assert result.exit_code == 1
    assert "Request deletion of record 'Field Notes' (kind 37375)?" in result.output
    assert "Aborted!" in result.output


def test_delete_record_yes_bypasses_confirmation(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)
    delete = AsyncMock(
        return_value={
            "status": "DELETE_REQUESTED",
            "message": "Deletion requested.",
            "advisory": "Relay deletion is advisory.",
            "hidden_on": [],
        }
    )

    class FakeAcorn:
        def __init__(self, **kwargs):
            pass

        async def load_data(self):
            return None

        delete_record = delete

    monkeypatch.setattr(cli, "Acorn", FakeAcorn)

    result = CliRunner().invoke(
        cli.delete_record,
        ["Field Notes", "--yes"],
    )

    assert result.exit_code == 0
    assert "Deletion requested." in result.output
    assert "Request deletion" not in result.output
    delete.assert_awaited_once()


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


def test_config_for_display_redacts_nsec(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    displayed = cli._config_for_display(
        {
            "nsec": "nsec1secret",
            "home_relay": "wss://relay.example.com",
        }
    )

    assert displayed == {
        "nsec": "<redacted; use 'acorn set --show-recovery'>",
        "home_relay": "wss://relay.example.com",
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


def test_format_recovery_material_marks_imported_seed_unavailable(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    rendered = cli._format_recovery_material(
        {
            "home_relay": "wss://relay.example.com",
            "seed_phrase": None,
            "nsec": "nsec1example",
        }
    )

    assert "seed_phrase: unavailable (back up the nsec)" in rendered


def test_init_help_does_not_offer_broken_longseed_option(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    result = CliRunner().invoke(cli.init, ["--help"])

    assert result.exit_code == 0
    assert "--longseed" not in result.output
    assert "--entropy" in result.output
    assert "--words 12|24" in result.output


def test_receive_ecash_preview_is_read_only(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)
    sweep = AsyncMock(
        return_value={
            "queried": 1,
            "page_count": 1,
            "previewed_count": 1,
            "previewed_amount": 25,
        }
    )

    class FakeAcorn:
        def __init__(self, **kwargs):
            pass

        async def load_data(self):
            return None

        sweep_ecash_transfers = sweep

    monkeypatch.setattr(cli, "Acorn", FakeAcorn)

    result = CliRunner().invoke(cli.receive_ecash, ["--preview"])

    assert result.exit_code == 0
    assert "Pending incoming funds: 25 sats in 1 transfer event(s)." in result.output
    assert "wallet proofs, history, and receive cursor were unchanged" in result.output
    sweep.assert_awaited_once()
    assert sweep.await_args.kwargs["preview_only"] is True
    assert sweep.await_args.kwargs["advance_cursor"] is False


@pytest.mark.parametrize(("words", "word_count"), [("12", 12), ("24", 24)])
def test_init_can_generate_selected_mnemonic_length(
    monkeypatch, tmp_path, words, word_count
):
    cli = _load_cli(monkeypatch, tmp_path)
    observed = {}

    class FakeAcorn:
        def __init__(self, **kwargs):
            self.seed_phrase = None
            self.privkey_bech32 = kwargs["nsec"]
            keys = Keys(priv_k=kwargs["nsec"])
            self.pubkey_bech32 = keys.public_key_bech32()
            self.pubkey_hex = keys.public_key_hex()

        async def create_instance(self, keepkey=False, seed_phrase=None):
            observed["keepkey"] = keepkey
            observed["seed_phrase"] = seed_phrase
            self.seed_phrase = seed_phrase
            return self.privkey_bech32

        async def load_data(self):
            return None

    monkeypatch.setattr(cli, "Acorn", FakeAcorn)
    monkeypatch.setattr(cli, "write_config", lambda: None)
    cli.config_obj.clear()
    cli.CONFIG_FILE_EXISTED = False
    cli.NSEC = None

    result = CliRunner().invoke(
        cli.init,
        ["--words", words, "--force", "--json"],
    )

    assert result.exit_code == 0
    assert len(observed["seed_phrase"].split()) == word_count
    assert Mnemonic("english").check(observed["seed_phrase"])
    assert observed["keepkey"] is False
    assert json.loads(result.stdout)["key_source"] == "acorn_generated"


def test_init_rejects_words_with_external_key_sources(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    result = CliRunner().invoke(
        cli.init,
        ["--words", "24", "--entropy", "--force"],
    )

    assert result.exit_code != 0
    assert "--words applies only to Acorn-generated keys" in result.output


def test_init_rejects_entropy_with_import_nsec(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    result = CliRunner().invoke(
        cli.init,
        ["--entropy", "--import-nsec", "--force"],
    )

    assert result.exit_code != 0
    assert "--entropy cannot be combined with --import-nsec or --nsec-file" in result.output


def test_init_rejects_entropy_with_keepkey(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    result = CliRunner().invoke(cli.init, ["--entropy", "--keepkey", "--force"])

    assert result.exit_code != 0
    assert "--entropy and --keepkey are mutually exclusive" in result.output


def test_init_external_entropy_is_hidden_recoverable_and_redacted(
    monkeypatch, tmp_path
):
    cli = _load_cli(monkeypatch, tmp_path)
    entropy_hex = "02" * 32
    seed_phrase, secret_nsec = cli.seed_phrase_and_nsec_from_entropy(entropy_hex)
    observed = {}

    class FakeAcorn:
        def __init__(self, **kwargs):
            observed["constructor_nsec"] = kwargs["nsec"]
            self.seed_phrase = None
            self.privkey_bech32 = kwargs["nsec"]
            keys = Keys(priv_k=kwargs["nsec"])
            self.pubkey_bech32 = keys.public_key_bech32()
            self.pubkey_hex = keys.public_key_hex()

        async def create_instance(self, keepkey=False, seed_phrase=None):
            observed["keepkey"] = keepkey
            observed["seed_phrase"] = seed_phrase
            self.seed_phrase = seed_phrase
            return self.privkey_bech32

        async def load_data(self):
            return None

    monkeypatch.setattr(cli, "Acorn", FakeAcorn)
    monkeypatch.setattr(cli, "write_config", lambda: None)
    cli.config_obj.clear()
    cli.CONFIG_FILE_EXISTED = False
    cli.NSEC = None

    result = CliRunner().invoke(
        cli.init,
        ["--entropy", "--force", "--json"],
        input=f"{entropy_hex}\n{entropy_hex}\n",
    )

    assert result.exit_code == 0
    assert entropy_hex not in result.output
    assert seed_phrase not in result.output
    assert secret_nsec not in result.output
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["key_source"] == "external_entropy"
    assert payload["recovery_included"] is False
    assert observed == {
        "constructor_nsec": secret_nsec,
        "keepkey": False,
        "seed_phrase": seed_phrase,
    }


def _prepare_successful_init(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)
    secret_nsec = "nsec1generatedsecret"
    secret_phrase = "alpha beta gamma secret recovery phrase"

    class FakeAcorn:
        def __init__(self, **kwargs):
            self.seed_phrase = secret_phrase
            self.privkey_bech32 = secret_nsec
            self.pubkey_bech32 = "npub1generatedpublic"
            self.pubkey_hex = "11" * 32

        async def create_instance(self, keepkey=False):
            return secret_nsec

        async def load_data(self):
            return None

    monkeypatch.setattr(cli, "Acorn", FakeAcorn)
    monkeypatch.setattr(cli, "write_config", lambda: None)
    cli.config_obj.clear()
    cli.CONFIG_FILE_EXISTED = False
    cli.NSEC = None
    return cli, secret_nsec, secret_phrase


def test_init_json_redacts_recovery_by_default(monkeypatch, tmp_path):
    cli, secret_nsec, secret_phrase = _prepare_successful_init(monkeypatch, tmp_path)

    result = CliRunner().invoke(cli.init, ["--force", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["recovery_included"] is False
    assert "recovery" not in payload
    assert secret_nsec not in result.output
    assert secret_phrase not in result.output


def test_init_json_includes_recovery_only_when_explicit(monkeypatch, tmp_path):
    cli, secret_nsec, secret_phrase = _prepare_successful_init(monkeypatch, tmp_path)

    result = CliRunner().invoke(
        cli.init,
        ["--force", "--json", "--include-recovery"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["recovery_included"] is True
    assert payload["recovery"]["nsec"] == secret_nsec
    assert payload["recovery"]["seed_phrase"] == secret_phrase


def test_init_force_does_not_print_recovery(monkeypatch, tmp_path):
    cli, secret_nsec, secret_phrase = _prepare_successful_init(monkeypatch, tmp_path)

    result = CliRunner().invoke(cli.init, ["--force"])

    assert result.exit_code == 0
    assert secret_nsec not in result.output
    assert secret_phrase not in result.output
    assert "Recovery material was not displayed" in result.output


def test_init_import_nsec_uses_one_hidden_entry(monkeypatch, tmp_path):
    cli, _, _ = _prepare_successful_init(monkeypatch, tmp_path)
    imported_nsec = Keys().private_key_bech32()

    result = CliRunner().invoke(
        cli.init,
        ["--import-nsec", "--force", "--json"],
        input=f"{imported_nsec}\n",
    )

    assert result.exit_code == 0
    assert imported_nsec not in result.output
    assert "Repeat nsec private key" not in result.output


def test_recover_reports_only_public_identity(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)
    secret_nsec = "nsec1recoveredsecret"

    class FakeAcorn:
        def __init__(self, **kwargs):
            self.pubkey_bech32 = "npub1recoveredpublic"

        async def load_data(self):
            return None

    monkeypatch.setattr(cli, "recover_nsec_from_seed", lambda **kwargs: secret_nsec)
    monkeypatch.setattr(cli, "Acorn", FakeAcorn)
    monkeypatch.setattr(cli, "write_config", lambda: None)
    cli.config_obj.clear()

    result = CliRunner().invoke(
        cli.recover,
        ["--homerelay", "relay.example.com"],
        input="alpha beta gamma\ny\n",
    )

    assert result.exit_code == 0
    assert secret_nsec not in result.output
    assert "npub1recoveredpublic" in result.output
    assert "Acorn wallet recovered." in result.output


def test_recover_missing_wallet_suggests_correct_home_relay_without_writing_config(
    monkeypatch, tmp_path
):
    cli = _load_cli(monkeypatch, tmp_path)
    original_config = {
        "nsec": "nsec1existingsecret",
        "home_relay": "wss://existing.example.com",
    }
    writes = []

    class FakeAcorn:
        def __init__(self, **kwargs):
            pass

        async def load_data(self):
            raise RuntimeError("No wallet data found on wss://missing.example.com")

    monkeypatch.setattr(
        cli,
        "recover_nsec_from_seed",
        lambda **kwargs: "nsec1candidate",
    )
    monkeypatch.setattr(cli, "Acorn", FakeAcorn)
    monkeypatch.setattr(cli, "write_config", lambda: writes.append(dict(cli.config_obj)))
    cli.config_obj.clear()
    cli.config_obj.update(original_config)

    result = CliRunner().invoke(
        cli.recover,
        ["--homerelay", "missing.example.com"],
        input="alpha beta gamma\ny\n",
    )

    assert result.exit_code != 0
    assert "No wallet data found on wss://missing.example.com" in result.output
    assert "Try again with --homerelay" in result.output
    assert cli.config_obj == original_config
    assert writes == []


def test_recovery_secrets_are_not_accepted_as_command_arguments(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    init_help = CliRunner().invoke(cli.init, ["--help"])
    set_help = CliRunner().invoke(cli.set, ["--help"])
    recover_help = CliRunner().invoke(cli.recover, ["--help"])
    receive_help = CliRunner().invoke(cli.receive_ecash, ["--help"])

    assert "--nsec TEXT" not in init_help.output
    assert "--nsec TEXT" not in set_help.output
    assert "SEEDPHRASE" not in recover_help.output
    assert "--receive-nsec TEXT" not in receive_help.output
    assert "--import-nsec" in init_help.output
    assert "--seed-file PATH" in recover_help.output
    assert "--receive-key" in receive_help.output


def test_secret_file_rejects_group_or_world_permissions(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)
    secret_file = tmp_path / "recovery.txt"
    secret_file.write_text("alpha beta gamma", encoding="utf-8")
    secret_file.chmod(0o644)

    with pytest.raises(click.ClickException, match="chmod 600"):
        cli._read_secret_file(str(secret_file), "seed phrase")


def test_secret_file_accepts_owner_only_permissions(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)
    secret_file = tmp_path / "recovery.txt"
    secret_file.write_text("  alpha beta gamma\n", encoding="utf-8")
    secret_file.chmod(0o600)

    assert cli._read_secret_file(str(secret_file), "seed phrase") == "alpha beta gamma"


def test_init_uses_code_defaults_not_existing_config_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    config_path = tmp_path / ".acorn" / "config.yml"
    config_path.parent.mkdir()
    config_path.write_text(
        yaml.safe_dump(
            {
                "nsec": Keys().private_key_bech32(),
                "home_relay": "wss://old-relay.example",
                "mints": ["https://testnut.cashu.space"],
            }
        ),
        encoding="utf-8",
    )
    config_path.chmod(0o600)
    cli = importlib.reload(importlib.import_module("acorn.cli_acorn"))

    class FakeAcorn:
        def __init__(self, nsec=None, relays=None, mints=None, home_relay=None, **kwargs):
            self.privkey_bech32 = nsec or Keys().private_key_bech32()
            self.pubkey_bech32 = "npub1fake"
            self.pubkey_hex = "f" * 64
            self.seed_phrase = None
            self.home_relay = home_relay
            self.mints = mints

        async def get_wallet_config(self):
            return {}

        async def create_instance(self, **kwargs):
            return self.privkey_bech32

        async def load_data(self):
            return None

    monkeypatch.setattr(cli, "Acorn", FakeAcorn)

    result = CliRunner().invoke(cli.init, ["--force", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["home_relay"] == cli.default_home_relay
    assert payload["home_mint"] == cli.default_mints[0]


def test_recover_hidden_prompt_does_not_echo_seed_phrase(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)
    secret_phrase = "alpha beta gamma"

    monkeypatch.setattr(
        cli,
        "recover_nsec_from_seed",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("test stop")),
    )
    result = CliRunner().invoke(
        cli.recover,
        input=f"{secret_phrase}\n",
    )

    assert result.exit_code != 0
    assert secret_phrase not in result.output
    assert "Invalid recovery phrase" in result.output


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


def test_source_wallet_ignores_legacy_secret_environment_overrides(monkeypatch, tmp_path):
    from tests.helpers import require_source_config

    source_path = tmp_path / "source.yml"
    source_path.write_text(
        yaml.safe_dump(
            {
                "nsec": "nsec1fromprotectedconfig",
                "home_relay": "wss://relay.from-config.example",
            }
        ),
        encoding="utf-8",
    )
    source_path.chmod(0o600)
    monkeypatch.setenv("ACORN_SOURCE_CONFIG", str(source_path))
    monkeypatch.setenv("ACORN_SOURCE_NSEC", "nsec1legacyenvironment")
    monkeypatch.setenv("ACORN_SOURCE_RELAY", "wss://legacy-environment.example")

    source = require_source_config()

    assert source["nsec"] == "nsec1fromprotectedconfig"
    assert source["home_relay"] == "wss://relay.from-config.example"
    assert source["_path"] == str(source_path)


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
    assert "funds transfer received" in rendered


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


def test_lightning_capacity_uses_largest_mapped_keyset(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    class Wallet:
        known_mints = {
            "keyset-a": "https://mint.one",
            "keyset-b": "https://mint.two",
        }

        def _proofs_by_keyset(self):
            return (
                {
                    "keyset-a": [object(), object()],
                    "keyset-b": [object()],
                    "unknown-keyset": [object()],
                },
                {
                    "keyset-a": 131,
                    "keyset-b": 1,
                    "unknown-keyset": 500,
                },
            )

    capacity = cli._lightning_capacity(Wallet())

    assert capacity == {
        "amount": 131,
        "unit": "sat",
        "mint": "https://mint.one",
        "keyset": "keyset-a",
        "proof_count": 2,
        "constraint": "single_keyset",
        "fee_reserve_included": False,
    }

    rendered = cli._format_lightning_capacity(capacity)
    assert "up to 131 sats before mint fees" in rendered
    assert "Mint: https://mint.one" in rendered
    assert "Keyset: keyset-a" in rendered
    assert "one keyset per Lightning payment" in rendered


def test_lightning_capacity_reports_no_mapped_keyset(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    class Wallet:
        known_mints = {}

        def _proofs_by_keyset(self):
            return ({"unknown": [object()]}, {"unknown": 10})

    capacity = cli._lightning_capacity(Wallet())

    assert capacity["amount"] == 0
    assert capacity["mint"] is None
    assert "no mint-mapped spendable keyset" in cli._format_lightning_capacity(capacity)


def test_balance_command_includes_lightning_capacity_in_text_and_json(
    monkeypatch,
    tmp_path,
):
    cli = _load_cli(monkeypatch, tmp_path)

    class FakeAcorn:
        def __init__(self, **kwargs):
            self.proofs = [object(), object()]
            self.known_mints = {
                "keyset-large": "https://mint.one",
                "keyset-small": "https://mint.two",
            }

        async def load_data(self):
            return None

        async def check_proofs(self):
            return {
                "status": "repair-recommended",
                "recommendation": "Review stale proofs.",
                "mint_confirmed_unspent": {"amount": 52, "proof_count": 8},
            }

        async def get_clear_receipts(self):
            return [
                {
                    "event_id": "clear-1",
                    "status": "pending",
                    "amount": 25,
                    "unit": "cmu-test",
                    "mint": "http://clear.example",
                    "keyset_ids": ["keyset-clear"],
                }
            ]

        def get_balance(self):
            return 132

        def _proofs_by_keyset(self):
            return (
                {
                    "keyset-large": [self.proofs[0]],
                    "keyset-small": [self.proofs[1]],
                },
                {"keyset-large": 131, "keyset-small": 1},
            )

    monkeypatch.setattr(cli, "Acorn", FakeAcorn)

    text_result = CliRunner().invoke(cli.balance)
    assert text_result.exit_code == 0
    assert "Relay-visible balance: 132 sats in 2 proofs" in text_result.output
    assert "Mint state not checked" in text_result.output
    assert "up to 131 sats before mint fees" in text_result.output
    assert "one keyset per Lightning payment" in text_result.output
    assert "Pending Clear transactions: 25 unit(s) in 1 receipt(s)" in text_result.output
    assert "- cmu-test: 25 unit(s) in 1 receipt(s)" in text_result.output

    json_result = CliRunner().invoke(cli.balance, ["--json"])
    assert json_result.exit_code == 0
    payload = json.loads(json_result.output)
    assert payload["balance"] == 132
    assert payload["balance_basis"] == "relay-visible"
    assert payload["relay_visible_balance"] == 132
    assert payload["lightning_capacity"] == {
        "amount": 131,
        "unit": "sat",
        "mint": "https://mint.one",
        "keyset": "keyset-large",
        "proof_count": 1,
        "constraint": "single_keyset",
        "fee_reserve_included": False,
    }
    assert payload["pending_clear"] == {
        "pending": True,
        "count": 1,
        "amount": 25,
        "units": [
            {
                "unit": "cmu-test",
                "amount": 25,
                "count": 1,
                "mints": ["http://clear.example"],
                "keyset_ids": ["keyset-clear"],
            }
        ],
    }

    verified_result = CliRunner().invoke(cli.balance, ["--verify"])
    assert verified_result.exit_code == 0
    assert "Mint-confirmed spendable balance: 52 sats in 8 proofs" in verified_result.output
    assert "Proof verification status: repair-recommended" in verified_result.output

    verified_json_result = CliRunner().invoke(cli.balance, ["--verify", "--json"])
    assert verified_json_result.exit_code == 0
    verified_payload = json.loads(verified_json_result.output)
    assert verified_payload["relay_visible_balance"] == 132
    assert verified_payload["mint_confirmed_balance"] == 52
    assert verified_payload["mint_verification"]["status"] == "repair-recommended"


def test_receive_clear_command_stores_pending_receipts(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    class FakeAcorn:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def load_data(self):
            return None

        async def sweep_clear_transfers(self, **kwargs):
            assert kwargs["preview_only"] is False
            assert kwargs["advance_cursor"] is True
            return {
                "status": "OK",
                "queried": 1,
                "query_pages": [{"limit": 1024}],
                "event_id": None,
                "stored_count": 1,
                "stored_amount": 25,
                "previewed_count": 0,
                "previewed_amount": 0,
                "failed": [],
            }

        async def get_clear_receipts(self):
            return [
                {
                    "event_id": "clear-1",
                    "status": "pending",
                    "amount": 25,
                    "unit": "cmu-test",
                    "mint": "http://clear.example",
                    "keyset_ids": ["keyset-clear"],
                }
            ]

    monkeypatch.setattr(cli, "Acorn", FakeAcorn)

    result = CliRunner().invoke(cli.receive_clear)

    assert result.exit_code == 0
    assert "Stored 25 Clear unit(s) from 1 pending transfer receipt(s)" in result.output
    assert "Pending Clear transactions: 25 unit(s) in 1 receipt(s)" in result.output


def test_clear_balances_command_reports_each_mint_and_unit(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    class FakeAcorn:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def load_data(self):
            return None

        async def get_clear_balances(self):
            return [
                {
                    "mint": "https://clear.one",
                    "unit": "cmu-one",
                    "amount": 25,
                    "proof_count": 3,
                    "event_ids": ["a" * 64],
                    "keysets": [
                        {"keyset": "keyset-one", "amount": 25, "proof_count": 3}
                    ],
                },
                {
                    "mint": "https://clear.two",
                    "unit": "cmu-two",
                    "amount": 8,
                    "proof_count": 1,
                    "event_ids": ["b" * 64],
                    "keysets": [
                        {"keyset": "keyset-two", "amount": 8, "proof_count": 1}
                    ],
                },
            ]

    monkeypatch.setattr(cli, "Acorn", FakeAcorn)

    text_result = CliRunner().invoke(cli.clear_wallet, ["balances"])
    json_result = CliRunner().invoke(cli.clear_wallet, ["balances", "--json"])

    assert text_result.exit_code == 0
    assert "Clear balances:" in text_result.output
    assert "25 cmu-one from https://clear.one in 3 proof(s)" in text_result.output
    assert "8 cmu-two from https://clear.two in 1 proof(s)" in text_result.output
    assert "keyset keyset-one: 25 in 3 proof(s)" in text_result.output
    assert json_result.exit_code == 0
    payload = json.loads(json_result.output)
    assert payload["status"] == "OK"
    assert len(payload["balances"]) == 2
    assert payload["balances"][0]["unit"] == "cmu-one"


def test_clear_history_command_filters_and_formats_journal(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)
    calls = []

    class FakeAcorn:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def load_data(self):
            return None

        async def get_clear_transaction_history(self, **kwargs):
            calls.append(kwargs)
            return [
                {
                    "event_id": "c" * 64,
                    "direction": "out",
                    "operation": "send",
                    "amount": 5,
                    "mint": "https://clear.one",
                    "unit": "cmu-one",
                    "timestamp": 100,
                    "memo": "community supplies",
                }
            ]

    monkeypatch.setattr(cli, "Acorn", FakeAcorn)

    result = CliRunner().invoke(
        cli.clear_wallet,
        [
            "history",
            "--mint",
            "https://clear.one",
            "--unit",
            "cmu-one",
            "--direction",
            "out",
            "--operation",
            "send",
        ],
    )

    assert result.exit_code == 0
    assert "Clear transaction history:" in result.output
    assert "-5 cmu-one send" in result.output
    assert "Mint: https://clear.one" in result.output
    assert "Memo: community supplies" in result.output
    assert calls == [
        {
            "mint": "https://clear.one",
            "unit": "cmu-one",
            "direction": "out",
            "operation": "send",
        }
    ]


def test_format_proof_check_emphasizes_read_only_result(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    rendered = cli._format_proof_check(
        {
            "status": "repair-recommended",
            "wallet": {"amount": 8, "proof_count": 3},
            "mint_confirmed_unspent": {"amount": 6, "proof_count": 2},
            "states": {
                "UNSPENT": {"amount": 6, "proof_count": 2},
                "SPENT": {"amount": 2, "proof_count": 1},
                "PENDING": {"amount": 0, "proof_count": 0},
                "UNKNOWN": {"amount": 0, "proof_count": 0},
            },
            "structural": {
                "duplicate_proofs": 0,
                "invalid_proofs": 0,
                "unknown_keysets": [],
            },
            "errors": [],
            "recommendation": "Review, then repair.",
        }
    )

    assert "Proof check (read-only)" in rendered
    assert "Status: repair-recommended" in rendered
    assert "Mint-confirmed unspent: 6 sats in 2 proofs" in rendered
    assert "SPENT: 2 sats in 1 proofs" in rendered
    assert "Recommendation: Review, then repair." in rendered
    assert rendered.endswith("No wallet state was changed.")


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
