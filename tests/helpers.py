from __future__ import annotations

import os

import pytest


def require_env(*names: str) -> dict[str, str]:
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        pytest.skip(f"missing env vars: {', '.join(missing)}")
    return {name: os.environ[name] for name in names}

