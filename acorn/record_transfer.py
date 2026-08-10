"""Short-lived, bearer-capability transfer envelopes for Acorn records."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import os
import time
from typing import Any
from urllib.parse import urlsplit

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


RECORD_TRANSFER_PREFIX = "acorn:record-transfer:"
_ENVELOPE_MAGIC = b"ACRN-RECORD-XFER-1\x00"
_ENVELOPE_AAD = b"acorn/record-transfer/envelope/v1"
_KEY_INFO = b"acorn/record-transfer/encryption-key/v1"
_AUTHORITY_INFO = b"acorn/record-transfer/blossom-authority/v1"
_SECP256K1_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


class RecordTransferError(ValueError):
    """A record-transfer descriptor or envelope is invalid."""


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str, *, field: str) -> bytes:
    try:
        encoded = str(value).encode("ascii")
        return base64.b64decode(
            encoded + b"=" * (-len(encoded) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (UnicodeError, ValueError) as exc:
        raise RecordTransferError(f"Record transfer {field} is not valid Base64URL") from exc


def _derive(secret: bytes, info: bytes) -> bytes:
    if len(secret) != 32:
        raise RecordTransferError("Record transfer secret must be 32 bytes")
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=info,
    ).derive(secret)


def derive_record_transfer_authority_hex(secret: bytes) -> str:
    """Derive the transfer-scoped Blossom signing key from a bearer secret."""

    candidate = _derive(secret, _AUTHORITY_INFO)
    for counter in range(256):
        scalar = int.from_bytes(candidate, "big")
        if 0 < scalar < _SECP256K1_ORDER:
            return candidate.hex()
        candidate = hashlib.sha256(candidate + bytes([counter])).digest()
    raise RecordTransferError("Unable to derive a valid transfer authority")


@dataclass(frozen=True)
class RecordTransferDescriptor:
    blob_url: str
    ciphertext_sha256: str
    secret: bytes
    expires_at: int
    version: int = 1

    @property
    def server(self) -> str:
        parsed = urlsplit(self.blob_url)
        return f"{parsed.scheme}://{parsed.netloc}"


@dataclass(frozen=True)
class RecordTransferEnvelope:
    label: str
    record_type: str
    payload: Any
    blob_data: bytes | None = None
    blob_type: str | None = None
    version: int = 1


def encode_record_transfer_descriptor(descriptor: RecordTransferDescriptor) -> str:
    parsed = urlsplit(descriptor.blob_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RecordTransferError("Record transfer blob URL must use HTTP or HTTPS")
    if parsed.username or parsed.password or parsed.fragment:
        raise RecordTransferError("Record transfer blob URL contains unsupported authority data")
    if not isinstance(descriptor.expires_at, int) or descriptor.expires_at <= 0:
        raise RecordTransferError("Record transfer expiry is invalid")
    try:
        digest = bytes.fromhex(descriptor.ciphertext_sha256)
    except ValueError as exc:
        raise RecordTransferError("Record transfer ciphertext hash is invalid") from exc
    if len(digest) != 32:
        raise RecordTransferError("Record transfer ciphertext hash must be 32 bytes")
    if len(descriptor.secret) != 32:
        raise RecordTransferError("Record transfer secret must be 32 bytes")
    payload = json.dumps(
        {
            "e": descriptor.expires_at,
            "h": _b64url_encode(digest),
            "s": _b64url_encode(descriptor.secret),
            "u": descriptor.blob_url,
            "v": descriptor.version,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return RECORD_TRANSFER_PREFIX + _b64url_encode(payload)


def decode_record_transfer_descriptor(
    value: str,
    *,
    now: int | None = None,
    require_unexpired: bool = True,
) -> RecordTransferDescriptor:
    normalized = str(value or "").strip()
    if not normalized.lower().startswith(RECORD_TRANSFER_PREFIX):
        raise RecordTransferError("QR code is not an Acorn record transfer")
    encoded = normalized[len(RECORD_TRANSFER_PREFIX) :]
    try:
        data = json.loads(_b64url_decode(encoded, field="descriptor"))
        descriptor = RecordTransferDescriptor(
            blob_url=str(data["u"]),
            ciphertext_sha256=_b64url_decode(data["h"], field="hash").hex(),
            secret=_b64url_decode(data["s"], field="secret"),
            expires_at=int(data["e"]),
            version=int(data["v"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RecordTransferError("Record transfer descriptor is malformed") from exc
    if descriptor.version != 1:
        raise RecordTransferError("Record transfer version is not supported")
    # Reuse the strict structural validation without changing the supplied form.
    encode_record_transfer_descriptor(descriptor)
    if require_unexpired and descriptor.expires_at < int(time.time() if now is None else now):
        raise RecordTransferError("Record transfer has expired")
    return descriptor


def encrypt_record_transfer_envelope(
    envelope: RecordTransferEnvelope,
    *,
    secret: bytes | None = None,
) -> tuple[bytes, bytes]:
    transfer_secret = secret or os.urandom(32)
    key = _derive(transfer_secret, _KEY_INFO)
    nonce = os.urandom(12)
    payload: dict[str, Any] = {
        "l": envelope.label,
        "p": envelope.payload,
        "t": envelope.record_type,
        "v": envelope.version,
    }
    if envelope.blob_data is not None:
        payload["b"] = {
            "d": envelope.blob_data,
            "h": hashlib.sha256(envelope.blob_data).hexdigest(),
            "m": envelope.blob_type or "application/octet-stream",
        }
    try:
        plaintext = cbor2.dumps(payload, canonical=True)
    except (TypeError, ValueError) as exc:
        raise RecordTransferError("Record transfer payload cannot be encoded") from exc
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, _ENVELOPE_AAD)
    return _ENVELOPE_MAGIC + nonce + ciphertext, transfer_secret


def decrypt_record_transfer_envelope(
    ciphertext: bytes,
    *,
    secret: bytes,
) -> RecordTransferEnvelope:
    if not ciphertext.startswith(_ENVELOPE_MAGIC):
        raise RecordTransferError("Record transfer envelope has an invalid header")
    sealed = ciphertext[len(_ENVELOPE_MAGIC) :]
    if len(sealed) <= 28:
        raise RecordTransferError("Record transfer envelope is truncated")
    nonce, encrypted = sealed[:12], sealed[12:]
    try:
        plaintext = AESGCM(_derive(secret, _KEY_INFO)).decrypt(
            nonce,
            encrypted,
            _ENVELOPE_AAD,
        )
        data = cbor2.loads(plaintext)
        if int(data["v"]) != 1:
            raise RecordTransferError("Record transfer envelope version is not supported")
        blob = data.get("b")
        blob_data = None
        blob_type = None
        if blob is not None:
            blob_data = bytes(blob["d"])
            if hashlib.sha256(blob_data).hexdigest() != str(blob["h"]):
                raise RecordTransferError("Record transfer Original Record hash does not match")
            blob_type = str(blob["m"])
        label = str(data["l"]).strip()
        record_type = str(data["t"]).strip()
        if not label or len(label) > 200 or not record_type:
            raise RecordTransferError("Record transfer metadata is invalid")
        return RecordTransferEnvelope(
            label=label,
            record_type=record_type,
            payload=data["p"],
            blob_data=blob_data,
            blob_type=blob_type,
        )
    except RecordTransferError:
        raise
    except Exception as exc:
        raise RecordTransferError("Record transfer could not be decrypted or validated") from exc


def verify_record_transfer_ciphertext(
    ciphertext: bytes,
    descriptor: RecordTransferDescriptor,
) -> None:
    if hashlib.sha256(ciphertext).hexdigest() != descriptor.ciphertext_sha256:
        raise RecordTransferError("Record transfer ciphertext hash does not match")
