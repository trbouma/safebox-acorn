from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib
import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest
import yaml

from acorn import config as config_storage


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_missing_config_load_is_read_only(tmp_path):
    config_path = tmp_path / "missing" / "config.yml"

    assert config_storage.load_config(config_path) == {}
    assert not config_path.exists()
    assert not config_path.parent.exists()


def test_default_config_directory_and_file_are_private(tmp_path):
    config_path = tmp_path / ".acorn" / "config.yml"

    config_storage.write_config(
        config_path,
        {
            "nsec": "nsec1example",
            "home_relay": "wss://relay.example.com",
        },
        harden_directory=True,
    )

    assert _mode(config_path.parent) == 0o700
    assert _mode(config_path) == 0o600


def test_custom_config_file_is_private_without_changing_existing_directory(tmp_path):
    config_path = tmp_path / "wallet.yml"
    os.chmod(tmp_path, 0o755)

    config_storage.write_config(
        config_path,
        {
            "nsec": "nsec1example",
            "home_relay": "wss://relay.example.com",
        },
    )

    assert _mode(tmp_path) == 0o755
    assert _mode(config_path) == 0o600


def test_existing_config_permissions_can_be_upgraded_without_rewrite(tmp_path):
    config_path = tmp_path / ".acorn" / "config.yml"
    config_path.parent.mkdir()
    config_path.write_text(
        "nsec: nsec1legacy\nhome_relay: wss://relay.example.com\n"
    )
    original_content = config_path.read_bytes()
    os.chmod(config_path.parent, 0o755)
    os.chmod(config_path, 0o644)

    config_storage.harden_config_permissions(
        config_path,
        harden_directory=True,
    )

    assert config_path.read_bytes() == original_content
    assert _mode(config_path.parent) == 0o700
    assert _mode(config_path) == 0o600


def test_successful_rewrite_preserves_recovery_essentials(tmp_path):
    config_path = tmp_path / ".acorn" / "config.yml"
    original = {
        "nsec": "nsec1example",
        "home_relay": "wss://relay.one",
        "mints": ["https://mint.one"],
    }
    updated = {
        **original,
        "home_relay": "wss://relay.two",
    }

    config_storage.write_config(config_path, original, harden_directory=True)
    config_storage.write_config(config_path, updated, harden_directory=True)

    loaded = config_storage.load_config(config_path)
    assert loaded["nsec"] == original["nsec"]
    assert loaded["home_relay"] == "wss://relay.two"
    assert _mode(config_path) == 0o600


def test_serialization_failure_preserves_existing_config(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yml"
    original = {
        "nsec": "nsec1original",
        "home_relay": "wss://relay.original",
    }
    config_storage.write_config(config_path, original)

    def fail_serialization(*args, **kwargs):
        raise yaml.YAMLError("simulated serialization failure")

    monkeypatch.setattr(config_storage.yaml, "safe_dump", fail_serialization)

    with pytest.raises(config_storage.ConfigWriteError, match="serialize"):
        config_storage.write_config(config_path, {"nsec": "nsec1replacement"})

    assert config_storage.load_config(config_path) == original
    assert not list(tmp_path.glob(".config.yml.*.tmp"))


def test_atomic_replace_failure_preserves_existing_config(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yml"
    original = {
        "nsec": "nsec1original",
        "home_relay": "wss://relay.original",
    }
    config_storage.write_config(config_path, original)

    def fail_replace(source, target):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(config_storage.os, "replace", fail_replace)

    with pytest.raises(config_storage.ConfigWriteError, match="Unable to write"):
        config_storage.write_config(config_path, {"nsec": "nsec1replacement"})

    assert config_storage.load_config(config_path) == original
    assert not list(tmp_path.glob(".config.yml.*.tmp"))


@pytest.mark.parametrize(
    "contents",
    [
        "nsec: [unterminated",
        "- this\n- is\n- a\n- list\n",
    ],
)
def test_malformed_or_non_mapping_yaml_has_clear_error(tmp_path, contents):
    config_path = tmp_path / "config.yml"
    config_path.write_text(contents)

    with pytest.raises(config_storage.ConfigReadError, match="Acorn config"):
        config_storage.load_config(config_path)


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission behavior")
def test_permission_denied_config_has_clear_error(tmp_path):
    config_path = tmp_path / "config.yml"
    config_path.write_text("nsec: nsec1example\n")
    os.chmod(config_path, 0o000)

    try:
        with pytest.raises(config_storage.ConfigReadError, match="Unable to read"):
            config_storage.load_config(config_path)
    finally:
        os.chmod(config_path, 0o600)


def test_concurrent_writers_leave_one_complete_config(tmp_path):
    config_path = tmp_path / ".acorn" / "config.yml"
    candidates = [
        {
            "nsec": f"nsec1writer{index}",
            "home_relay": f"wss://relay-{index}.example.com",
            "writer": index,
        }
        for index in range(8)
    ]

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(
            executor.map(
                lambda candidate: config_storage.write_config(
                    config_path,
                    candidate,
                    harden_directory=True,
                ),
                candidates,
            )
        )

    loaded = config_storage.load_config(config_path)
    assert loaded in candidates
    assert _mode(config_path) == 0o600


def test_importing_cli_does_not_create_default_config(tmp_path):
    environment = os.environ.copy()
    environment["HOME"] = str(tmp_path)
    environment.pop("ACORN_CONFIG", None)
    command = [
        sys.executable,
        "-c",
        "import acorn.cli_acorn; print('imported')",
    ]

    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.stdout.strip() == "imported"
    assert not (tmp_path / ".acorn").exists()


def test_cli_help_does_not_create_config(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ACORN_CONFIG", raising=False)
    cli = importlib.reload(importlib.import_module("acorn.cli_acorn"))

    from click.testing import CliRunner

    result = CliRunner().invoke(cli.cli, ["--help"])

    assert result.exit_code == 0
    assert not (tmp_path / ".acorn").exists()


def test_cli_command_without_config_instructs_user_to_initialize(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ACORN_CONFIG", raising=False)
    cli = importlib.reload(importlib.import_module("acorn.cli_acorn"))

    from click.testing import CliRunner

    result = CliRunner().invoke(cli.cli, ["info"])

    assert result.exit_code != 0
    assert "No initialized Acorn config found" in result.output
    assert "init" in result.output
    assert not (tmp_path / ".acorn").exists()


def test_cli_set_can_intentionally_create_private_custom_config(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ACORN_CONFIG", raising=False)
    cli = importlib.reload(importlib.import_module("acorn.cli_acorn"))
    config_path = tmp_path / "profiles" / "wallet.yml"

    from click.testing import CliRunner

    result = CliRunner().invoke(
        cli.cli,
        [
            "--config",
            str(config_path),
            "set",
            "--nsec",
            "nsec1secret",
            "--home",
            "relay.example.com",
        ],
    )

    assert result.exit_code == 0
    assert "nsec1secret" not in result.output
    assert "<redacted" in result.output
    assert config_storage.load_config(config_path) == {
        "nsec": "nsec1secret",
        "home_relay": "wss://relay.example.com",
    }
    assert _mode(config_path.parent) == 0o700
    assert _mode(config_path) == 0o600
