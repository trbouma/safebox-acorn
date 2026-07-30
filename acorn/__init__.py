"""Public API for the standalone Acorn component."""

__all__ = ["Acorn"]


def __getattr__(name):
    if name == "Acorn":
        from acorn.acorn import Acorn

        return Acorn
    raise AttributeError(f"module 'acorn' has no attribute {name!r}")
