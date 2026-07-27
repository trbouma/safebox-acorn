"""Public API for the standalone Acorn component."""

import contextlib
import io
import os
import warnings

__all__ = ["Acorn"]


def __getattr__(name):
    if name == "Acorn":
        warnings.filterwarnings(
            "ignore",
            message=r"liboqs version .* differs from liboqs-python version .*",
            category=UserWarning,
            module=r"oqs.*",
        )
        if os.getenv("ACORN_SHOW_IMPORT_WARNINGS"):
            from acorn.acorn import Acorn

            return Acorn

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            from acorn.acorn import Acorn

        return Acorn
    raise AttributeError(f"module 'acorn' has no attribute {name!r}")
