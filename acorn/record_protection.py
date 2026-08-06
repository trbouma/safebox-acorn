"""Record-protection key generation and validation.

This module intentionally provides only key-material primitives. Protected
record encryption and recovery ceremonies remain separate, explicit features.
"""

from __future__ import annotations

import re
import secrets

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from mnemonic import Mnemonic


RECORD_PROTECTION_KEY_BYTES = 32
RECORD_PROTECTION_KEY_HEX_LENGTH = RECORD_PROTECTION_KEY_BYTES * 2
_RPK_DERIVATION_INFO = b"safebox-acorn/record-protection-key/v1"
_HEX_256 = re.compile(r"[0-9a-fA-F]{64}\Z")


def _derive_record_protection_key(entropy: bytes) -> str:
    """Derive a domain-separated 256-bit RPK from high-quality entropy."""

    return HKDF(
        algorithm=hashes.SHA256(),
        length=RECORD_PROTECTION_KEY_BYTES,
        salt=None,
        info=_RPK_DERIVATION_INFO,
    ).derive(entropy).hex()


def _decode_external_entropy(entropy_hex: str) -> bytes:
    normalized = str(entropy_hex).strip()
    if len(normalized) != RECORD_PROTECTION_KEY_HEX_LENGTH:
        raise ValueError(
            "record-protection entropy must contain exactly 64 hexadecimal "
            "characters (32 bytes)"
        )
    if not _HEX_256.fullmatch(normalized):
        raise ValueError(
            "record-protection entropy must contain only hexadecimal characters"
        )
    return bytes.fromhex(normalized)


def generate_record_protection_key() -> str:
    """Generate a fresh RPK from the operating system cryptographic RNG.

    The returned value is canonical lowercase hexadecimal representing 32
    bytes. It is secret key material and must not be logged or displayed by
    default.
    """

    entropy = secrets.token_bytes(RECORD_PROTECTION_KEY_BYTES)
    return _derive_record_protection_key(entropy)


def record_protection_key_from_entropy(entropy_hex: str) -> str:
    """Deterministically derive an RPK from external 256-bit entropy.

    The entropy is used as HKDF input keying material with an Acorn-specific
    context label. It is not reused as the RPK directly.
    """

    return _derive_record_protection_key(_decode_external_entropy(entropy_hex))


def validate_record_protection_key(value: str) -> str:
    """Validate and return the canonical lowercase representation of an RPK."""

    normalized = str(value).strip()
    if len(normalized) != RECORD_PROTECTION_KEY_HEX_LENGTH:
        raise ValueError(
            "record protection key must contain exactly 64 hexadecimal "
            "characters (32 bytes)"
        )
    if not _HEX_256.fullmatch(normalized):
        raise ValueError("record protection key must contain only hexadecimal characters")
    return normalized.lower()


def record_protection_recovery_phrase(record_protection_key: str) -> str:
    """Encode an RPK directly as a checksummed 24-word recovery phrase.

    This is a reversible encoding of the exact 32-byte RPK. It does not use the
    wallet's BIP39-to-SLIP-10 private-key derivation path.
    """

    canonical_key = validate_record_protection_key(record_protection_key)
    return Mnemonic("english").to_mnemonic(bytes.fromhex(canonical_key))


def record_protection_key_from_recovery_phrase(recovery_phrase: str) -> str:
    """Recover the exact RPK encoded by a protected-record recovery phrase."""

    phrase = " ".join(str(recovery_phrase).strip().split())
    if len(phrase.split()) != 24:
        raise ValueError("Protected record mnemonic must contain exactly 24 words")
    mnemonic = Mnemonic("english")
    if not mnemonic.check(phrase):
        raise ValueError("Protected record mnemonic is not valid")
    key_bytes = mnemonic.to_entropy(phrase)
    if len(key_bytes) != RECORD_PROTECTION_KEY_BYTES:
        raise ValueError("Protected record mnemonic must encode 32 bytes")
    return validate_record_protection_key(key_bytes.hex())
