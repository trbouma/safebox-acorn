import pytest

from acorn.record_protection import (
    generate_record_protection_key,
    record_protection_key_from_entropy,
    validate_record_protection_key,
)


def test_generated_record_protection_keys_are_independent_256_bit_values():
    first = generate_record_protection_key()
    second = generate_record_protection_key()

    assert len(bytes.fromhex(first)) == 32
    assert len(bytes.fromhex(second)) == 32
    assert first != second
    assert first == first.lower()


def test_external_entropy_derivation_is_deterministic_and_domain_separated():
    entropy = "A5" * 32

    first = record_protection_key_from_entropy(entropy)
    second = record_protection_key_from_entropy(entropy.lower())

    assert first == second
    assert first != entropy.lower()
    assert validate_record_protection_key(first) == first


@pytest.mark.parametrize(
    "entropy, message",
    [
        ("", "exactly 64"),
        ("00" * 31, "exactly 64"),
        ("00" * 33, "exactly 64"),
        ("gg" * 32, "only hexadecimal"),
    ],
)
def test_external_record_protection_entropy_is_strictly_validated(entropy, message):
    with pytest.raises(ValueError, match=message):
        record_protection_key_from_entropy(entropy)


def test_record_protection_key_validation_canonicalizes_hex():
    assert validate_record_protection_key("AB" * 32) == "ab" * 32


@pytest.mark.parametrize("value", ["", "00" * 31, "00" * 33, "zz" * 32])
def test_invalid_record_protection_keys_are_rejected(value):
    with pytest.raises(ValueError):
        validate_record_protection_key(value)
