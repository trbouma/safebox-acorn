"""Public API for the standalone Acorn component."""

__all__ = [
    "Acorn",
    "BitcoinCapabilityError",
    "OptionalDependencyError",
    "broadcast_silent_payment_sweep",
    "create_silent_payment_sweep_preview",
    "derive_nostr_silent_payment_address",
    "detect_silent_payment_receipts",
    "generate_record_protection_key",
    "record_protection_key_from_entropy",
    "record_protection_key_from_recovery_phrase",
    "record_protection_recovery_phrase",
    "validate_record_protection_key",
]


class OptionalDependencyError(RuntimeError):
    """An explicitly requested Acorn capability is not installed."""


def __getattr__(name):
    if name == "Acorn":
        from acorn.acorn import Acorn

        return Acorn
    if name in {
        "BitcoinCapabilityError",
        "broadcast_silent_payment_sweep",
        "create_silent_payment_sweep_preview",
        "derive_nostr_silent_payment_address",
        "detect_silent_payment_receipts",
    }:
        try:
            from acorn import silent_payments
        except ModuleNotFoundError as exc:
            if exc.name and exc.name.startswith("btclib"):
                raise OptionalDependencyError(
                    "Acorn's Bitcoin capability is not installed. Install "
                    "safebox-acorn[bitcoin] or run poetry install -E bitcoin."
                ) from exc
            raise

        return getattr(silent_payments, name)
    if name in {
        "generate_record_protection_key",
        "record_protection_key_from_entropy",
        "record_protection_key_from_recovery_phrase",
        "record_protection_recovery_phrase",
        "validate_record_protection_key",
    }:
        from acorn import record_protection

        return getattr(record_protection, name)
    raise AttributeError(f"module 'acorn' has no attribute {name!r}")
