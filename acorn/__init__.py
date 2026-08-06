"""Public API for the standalone Acorn component."""

__all__ = [
    "Acorn",
    "generate_record_protection_key",
    "record_protection_key_from_entropy",
    "validate_record_protection_key",
]


def __getattr__(name):
    if name == "Acorn":
        from acorn.acorn import Acorn

        return Acorn
    if name in {
        "generate_record_protection_key",
        "record_protection_key_from_entropy",
        "validate_record_protection_key",
    }:
        from acorn import record_protection

        return getattr(record_protection, name)
    raise AttributeError(f"module 'acorn' has no attribute {name!r}")
