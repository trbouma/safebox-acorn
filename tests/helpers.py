from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml


def normalize_relay(relay: str) -> str:
    relay = str(relay).strip()
    if relay.startswith(("wss://", "ws://")):
        return relay
    return f"wss://{relay}"


def normalize_mint(mint: str) -> str:
    mint = str(mint).strip()
    if mint.startswith(("https://", "http://")):
        return mint
    return f"https://{mint}"


def truthy_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def require_env(*names: str) -> dict[str, str]:
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        pytest.skip(f"missing env vars: {', '.join(missing)}")
    return {name: os.environ[name] for name in names}


def require_env_value(name: str, *fallback_names: str) -> str:
    for candidate in (name, *fallback_names):
        value = os.getenv(candidate)
        if value:
            return value

    expected = ", ".join((name, *fallback_names))
    pytest.skip(f"missing env var: one of {expected}")


def require_config(path: str | Path, label: str) -> dict:
    config_path = Path(path).expanduser()
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    if not config_path.exists():
        pytest.skip(f"{label} config file does not exist: {config_path}")

    with config_path.open("r") as file:
        config = yaml.safe_load(file) or {}

    if not config.get("nsec"):
        pytest.skip(f"{label} config is missing nsec: {config_path}")
    if not config.get("home_relay"):
        pytest.skip(f"{label} config is missing home_relay: {config_path}")

    config["_path"] = str(config_path)
    return config


def require_source_config() -> dict:
    if os.getenv("ACORN_SOURCE_NSEC") and os.getenv("ACORN_SOURCE_RELAY"):
        return {
            "nsec": os.environ["ACORN_SOURCE_NSEC"],
            "home_relay": os.environ["ACORN_SOURCE_RELAY"],
            "_path": "(ACORN_SOURCE_NSEC/ACORN_SOURCE_RELAY)",
        }

    source_path = os.getenv("ACORN_SOURCE_CONFIG", "~/.acorn/config.yml")
    return require_config(source_path, "source wallet")


def require_test_wallet_config() -> dict:
    test_path = os.getenv("ACORN_TEST_WALLET_CONFIG", "./.acorn-test/test-wallet.yml")
    config = require_config(test_path, "test wallet")
    if os.getenv("ACORN_TEST_RELAY"):
        config["home_relay"] = normalize_relay(os.environ["ACORN_TEST_RELAY"])
    return config


def get_test_transfer_relay(default_relay: str) -> str:
    return normalize_relay(os.getenv("ACORN_TEST_TRANSFER_RELAY") or os.getenv("ACORN_TEST_RELAY") or default_relay)


def get_test_wallet_config_path() -> Path:
    config_path = Path(os.getenv("ACORN_TEST_WALLET_CONFIG", "./.acorn-test/test-wallet.yml")).expanduser()
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    return config_path


def write_test_wallet_config(nsec: str, home_relay: str) -> dict:
    config_path = get_test_wallet_config_path()
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        pytest.skip(f"could not create test wallet config directory {config_path.parent}: {exc}")
    config = {
        "nsec": nsec,
        "home_relay": normalize_relay(home_relay),
        "mints": [normalize_mint(os.getenv("ACORN_TEST_MINT", "https://mint.getsafebox.app"))],
        "test_wallet": True,
    }
    try:
        with config_path.open("w") as file:
            yaml.safe_dump(config, file)
    except OSError as exc:
        pytest.skip(f"could not write test wallet config {config_path}: {exc}")
    config["_path"] = str(config_path)
    return config


async def ensure_test_wallet_config() -> dict:
    config_path = get_test_wallet_config_path()
    if config_path.exists():
        config = require_test_wallet_config()
        config.setdefault("test_wallet", True)
        if os.getenv("ACORN_TEST_RELAY"):
            config["home_relay"] = normalize_relay(os.environ["ACORN_TEST_RELAY"])
        if truthy_env("ACORN_TEST_CREATE_WALLET", "true"):
            config["test_wallet"] = True
            try:
                with config_path.open("w") as file:
                    yaml.safe_dump({k: v for k, v in config.items() if not k.startswith("_")}, file)
            except OSError as exc:
                pytest.skip(f"could not update disposable test wallet config {config_path}: {exc}")
            await initialize_test_wallet_config(config)
        return config

    if not truthy_env("ACORN_TEST_CREATE_WALLET", "true"):
        pytest.skip(f"test wallet config file does not exist: {config_path}")

    from monstr.encrypt import Keys

    test_relay = normalize_relay(os.getenv("ACORN_TEST_RELAY", "ws://beelink:7777"))
    config = write_test_wallet_config(Keys().private_key_bech32(), test_relay)
    await initialize_test_wallet_config(config)
    return config


async def initialize_test_wallet_config(config: dict) -> None:
    from acorn.acorn import Acorn

    acorn = Acorn(
        nsec=config["nsec"],
        home_relay=config["home_relay"],
        relays=[config["home_relay"]],
        mints=config.get("mints"),
    )
    try:
        await acorn.load_data()
        return
    except Exception:
        pass

    try:
        await acorn.create_instance(keepkey=True)
        await acorn.load_data()
    except Exception as exc:
        pytest.skip(f"could not initialize disposable test wallet on {config['home_relay']}: {exc}")


def should_burn_test_wallet(config: dict) -> bool:
    if not truthy_env("ACORN_TEST_BURN_AFTER", "true"):
        return False
    return bool(config.get("test_wallet")) or truthy_env("ACORN_TEST_BURN_EXISTING", "false")


def remove_test_wallet_config(config: dict) -> None:
    path_value = config.get("_path")
    if not path_value:
        return
    path = Path(path_value)
    if path.exists():
        path.unlink()
