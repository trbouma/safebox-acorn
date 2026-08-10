import hashlib
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from acorn.record_transfer import (
    RECORD_TRANSFER_PREFIX,
    RecordTransferDescriptor,
    RecordTransferEnvelope,
    RecordTransferError,
    decode_record_transfer_descriptor,
    decrypt_record_transfer_envelope,
    derive_record_transfer_authority_hex,
    encode_record_transfer_descriptor,
    encrypt_record_transfer_envelope,
    verify_record_transfer_ciphertext,
)
from acorn import acorn as acorn_module
from acorn.acorn import Acorn


def test_record_transfer_descriptor_round_trip_uses_base64url() -> None:
    secret = bytes(range(32))
    descriptor = RecordTransferDescriptor(
        blob_url="https://blossom.example/" + "ab" * 32,
        ciphertext_sha256="cd" * 32,
        secret=secret,
        expires_at=2_000_000_000,
    )

    encoded = encode_record_transfer_descriptor(descriptor)
    decoded = decode_record_transfer_descriptor(encoded, now=1_900_000_000)

    assert encoded.startswith(RECORD_TRANSFER_PREFIX)
    assert "+" not in encoded and "/" not in encoded and "=" not in encoded
    assert decoded == descriptor
    assert len(encoded) < 500


def test_record_transfer_envelope_round_trip_with_original_record() -> None:
    envelope = RecordTransferEnvelope(
        label="Field Notes",
        record_type="generic",
        payload={"note": "leave before noon"},
        blob_data=b"original record bytes",
        blob_type="application/pdf",
    )

    ciphertext, secret = encrypt_record_transfer_envelope(
        envelope,
        secret=b"s" * 32,
    )
    descriptor = RecordTransferDescriptor(
        blob_url="https://blossom.example/" + hashlib.sha256(ciphertext).hexdigest(),
        ciphertext_sha256=hashlib.sha256(ciphertext).hexdigest(),
        secret=secret,
        expires_at=2_000_000_000,
    )

    verify_record_transfer_ciphertext(ciphertext, descriptor)
    assert decrypt_record_transfer_envelope(ciphertext, secret=secret) == envelope


def test_record_transfer_rejects_expired_and_tampered_values() -> None:
    ciphertext, secret = encrypt_record_transfer_envelope(
        RecordTransferEnvelope(label="A", record_type="generic", payload="B"),
        secret=b"t" * 32,
    )
    descriptor = RecordTransferDescriptor(
        blob_url="https://blossom.example/" + hashlib.sha256(ciphertext).hexdigest(),
        ciphertext_sha256=hashlib.sha256(ciphertext).hexdigest(),
        secret=secret,
        expires_at=100,
    )
    encoded = encode_record_transfer_descriptor(descriptor)

    with pytest.raises(RecordTransferError, match="expired"):
        decode_record_transfer_descriptor(encoded, now=101)
    with pytest.raises(RecordTransferError, match="hash does not match"):
        verify_record_transfer_ciphertext(ciphertext + b"x", descriptor)
    with pytest.raises(RecordTransferError):
        decrypt_record_transfer_envelope(ciphertext[:-1] + b"x", secret=secret)


def test_transfer_authority_is_stable_and_scoped() -> None:
    first = derive_record_transfer_authority_hex(b"a" * 32)
    second = derive_record_transfer_authority_hex(b"a" * 32)

    assert first == second
    assert len(first) == 64
    assert first != (b"a" * 32).hex()


@pytest.mark.asyncio
async def test_component_transfer_stores_before_deleting_temporary_blob(monkeypatch) -> None:
    stored_blobs: dict[str, bytes] = {}
    deleted: list[tuple[str, str]] = []

    class FakeBlob:
        def __init__(self, data: bytes) -> None:
            self._data = data

        def get_bytes(self) -> bytes:
            return self._data

    class FakeBlossomClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def upload_blob(self, server, data, description):
            digest = hashlib.sha256(data).hexdigest()
            stored_blobs[digest] = data
            return {"sha256": digest, "url": f"{server}/{digest}"}

        def get_blob(self, server, sha256):
            return FakeBlob(stored_blobs[sha256])

        def delete_blob(self, server, sha256):
            deleted.append((server, sha256))
            stored_blobs.pop(sha256)
            return True

    monkeypatch.setattr(acorn_module, "BlossomClient", FakeBlossomClient)

    sender = object.__new__(Acorn)
    sender.blossom_xfer_server = "https://blossom.example"
    sender.logger = logging.getLogger("record-transfer-sender-test")
    sender.get_record_safebox = AsyncMock(
        return_value=SimpleNamespace(
            type="generic",
            payload={"note": "portable"},
            blobref=None,
            blobtype=None,
        )
    )
    transfer = await sender.create_record_transfer("Field Notes", expires_in=3600)

    receiver = object.__new__(Acorn)
    receiver.logger = logging.getLogger("record-transfer-receiver-test")
    receiver.put_record = AsyncMock()
    result = await receiver.accept_record_transfer(
        transfer["descriptor"],
        record_name="Imported Notes",
        allowed_servers=["https://blossom.example"],
    )

    receiver.put_record.assert_awaited_once_with(
        "Imported Notes",
        {"note": "portable"},
        record_type="generic",
        blob_data=None,
    )
    assert result["transfer_deleted"] is True
    assert deleted == [
        ("https://blossom.example", transfer["ciphertext_sha256"])
    ]
    assert stored_blobs == {}
