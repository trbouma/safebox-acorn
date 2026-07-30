"""Private, atomic storage for Acorn's local bootstrap configuration."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from filelock import FileLock, Timeout as FileLockTimeout
import yaml


CONFIG_DIRECTORY_MODE = 0o700
CONFIG_FILE_MODE = 0o600
CONFIG_LOCK_TIMEOUT = 10.0


class ConfigError(RuntimeError):
    """Base class for local Acorn configuration failures."""


class ConfigReadError(ConfigError):
    """Raised when an existing configuration cannot be read safely."""


class ConfigWriteError(ConfigError):
    """Raised when a configuration cannot be persisted atomically."""


def load_config(config_path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load an existing config without creating or rewriting anything."""

    path = Path(config_path)
    if not path.exists():
        return {}
    if not path.is_file():
        raise ConfigReadError(f"Acorn config is not a regular file: {path}")

    try:
        with path.open("r", encoding="utf-8") as config_file:
            loaded = yaml.safe_load(config_file)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigReadError(f"Unable to read Acorn config {path}: {exc}") from exc

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ConfigReadError(f"Acorn config must contain a YAML mapping: {path}")
    return loaded


def _prepare_directory(directory: Path, harden_existing: bool) -> None:
    existed = directory.exists()
    try:
        directory.mkdir(mode=CONFIG_DIRECTORY_MODE, parents=True, exist_ok=True)
        if not existed or harden_existing:
            os.chmod(directory, CONFIG_DIRECTORY_MODE)
    except OSError as exc:
        raise ConfigWriteError(
            f"Unable to prepare Acorn config directory {directory}: {exc}"
        ) from exc


def harden_config_permissions(
    config_path: str | os.PathLike[str],
    *,
    harden_directory: bool = False,
) -> None:
    """Upgrade permissions on an existing config without rewriting its content."""

    path = Path(config_path)
    if not path.exists():
        return
    try:
        if harden_directory:
            os.chmod(path.parent, CONFIG_DIRECTORY_MODE)
        os.chmod(path, CONFIG_FILE_MODE)
    except OSError as exc:
        raise ConfigWriteError(
            f"Unable to protect Acorn config permissions for {path}: {exc}"
        ) from exc


def write_config(
    config_path: str | os.PathLike[str],
    config: Mapping[str, Any],
    *,
    harden_directory: bool = False,
    lock_timeout: float = CONFIG_LOCK_TIMEOUT,
) -> None:
    """Atomically write a complete config while preserving the previous file."""

    path = Path(config_path)
    directory = path.parent
    _prepare_directory(directory, harden_existing=harden_directory)

    try:
        serialized = yaml.safe_dump(
            dict(config),
            default_flow_style=False,
            sort_keys=False,
        )
    except (TypeError, ValueError, yaml.YAMLError) as exc:
        raise ConfigWriteError(f"Unable to serialize Acorn config: {exc}") from exc

    lock_path = path.with_name(f"{path.name}.lock")
    lock = FileLock(
        str(lock_path),
        timeout=lock_timeout,
        mode=CONFIG_FILE_MODE,
    )
    temporary_path: Path | None = None

    try:
        with lock:
            descriptor, temporary_name = tempfile.mkstemp(
                dir=directory,
                prefix=f".{path.name}.",
                suffix=".tmp",
                text=True,
            )
            temporary_path = Path(temporary_name)
            os.chmod(temporary_path, CONFIG_FILE_MODE)

            with os.fdopen(descriptor, "w", encoding="utf-8") as config_file:
                config_file.write(serialized)
                config_file.flush()
                os.fsync(config_file.fileno())

            os.replace(temporary_path, path)
            temporary_path = None
            os.chmod(path, CONFIG_FILE_MODE)

            try:
                directory_descriptor = os.open(directory, os.O_RDONLY)
            except OSError:
                directory_descriptor = None
            if directory_descriptor is not None:
                try:
                    os.fsync(directory_descriptor)
                finally:
                    os.close(directory_descriptor)
    except FileLockTimeout as exc:
        raise ConfigWriteError(f"Timed out waiting to write Acorn config {path}") from exc
    except OSError as exc:
        raise ConfigWriteError(f"Unable to write Acorn config {path}: {exc}") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
        try:
            os.chmod(lock_path, CONFIG_FILE_MODE)
        except FileNotFoundError:
            pass
