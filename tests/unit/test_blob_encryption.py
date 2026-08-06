from __future__ import annotations

import hashlib
import os

import pytest
from cryptography.exceptions import InvalidTag

from acorn.func_utils import (
    decrypt_and_verify_record_blob,
    encrypt_bytes,
)
from acorn.models import EncryptionParms


def encrypted_fixture() -> tuple[bytes, bytes, EncryptionParms, str, str]:
    plaintext = b"private Acorn blob contents"
    key = os.urandom(32)
    encrypted = encrypt_bytes(plaintext, key)
    parameters = EncryptionParms(
        alg=encrypted.alg,
        key=key.hex(),
        iv=encrypted.iv.hex(),
    )
    return (
        plaintext,
        encrypted.cipherbytes,
        parameters,
        hashlib.sha256(encrypted.cipherbytes).hexdigest(),
        hashlib.sha256(plaintext).hexdigest(),
    )


def test_private_record_blob_round_trip_verifies_both_hashes() -> None:
    plaintext, ciphertext, parameters, cipher_hash, plain_hash = encrypted_fixture()

    restored = decrypt_and_verify_record_blob(
        cipherbytes=ciphertext,
        encryptparms=parameters,
        blobsha256=cipher_hash,
        origsha256=plain_hash,
    )

    assert restored == plaintext


def test_private_record_blob_rejects_ciphertext_hash_mismatch() -> None:
    _, ciphertext, parameters, _, plain_hash = encrypted_fixture()

    with pytest.raises(ValueError, match="ciphertext hash mismatch"):
        decrypt_and_verify_record_blob(
            cipherbytes=ciphertext,
            encryptparms=parameters,
            blobsha256="00" * 32,
            origsha256=plain_hash,
        )


def test_private_record_blob_rejects_authenticated_ciphertext_tampering() -> None:
    _, ciphertext, parameters, _, plain_hash = encrypted_fixture()
    tampered = bytearray(ciphertext)
    tampered[-1] ^= 1
    tampered_bytes = bytes(tampered)

    with pytest.raises(InvalidTag):
        decrypt_and_verify_record_blob(
            cipherbytes=tampered_bytes,
            encryptparms=parameters,
            blobsha256=hashlib.sha256(tampered_bytes).hexdigest(),
            origsha256=plain_hash,
        )


def test_private_record_blob_rejects_plaintext_hash_mismatch() -> None:
    _, ciphertext, parameters, cipher_hash, _ = encrypted_fixture()

    with pytest.raises(ValueError, match="plaintext hash mismatch"):
        decrypt_and_verify_record_blob(
            cipherbytes=ciphertext,
            encryptparms=parameters,
            blobsha256=cipher_hash,
            origsha256="00" * 32,
        )


def test_private_record_blob_rejects_unknown_algorithm() -> None:
    _, ciphertext, parameters, cipher_hash, plain_hash = encrypted_fixture()
    unsupported = parameters.model_copy(update={"alg": "unknown"})

    with pytest.raises(ValueError, match="unsupported encrypted blob algorithm"):
        decrypt_and_verify_record_blob(
            cipherbytes=ciphertext,
            encryptparms=unsupported,
            blobsha256=cipher_hash,
            origsha256=plain_hash,
        )
