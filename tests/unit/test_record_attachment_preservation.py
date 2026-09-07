from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from monstr.encrypt import Keys

from acorn import acorn as acorn_module
from acorn.acorn import Acorn
from acorn.models import EncryptionParms


PKPASS_MIME = "application/vnd.apple.pkpass"
PKPASS_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "Example.pkpass"
GROVE_NPUB = Keys(priv_k="22" * 32).public_key_bech32()


def wallet_with_existing_attachment() -> Acorn:
    wallet = object.__new__(Acorn)
    wallet.k = Keys(priv_k="11" * 32)
    wallet.pubkey_hex = wallet.k.public_key_hex()
    wallet.privkey_bech32 = wallet.k.private_key_bech32()
    wallet.home_relay = "ws://home:7777"
    wallet.relays = [wallet.home_relay]
    wallet.blossom_home_server = "https://blossom.example"
    wallet.blossom_servers = [wallet.blossom_home_server]
    wallet.acorn_tags = []
    wallet.logger = logging.getLogger("record-attachment-preservation-test")
    wallet.get_record_safebox = AsyncMock(
        return_value=SimpleNamespace(
            blobref="https://blossom.example/encrypted",
            blobtype="application/pdf",
            blobsha256="cipher-sha",
            blob_service_npubs=[GROVE_NPUB],
            origsha256="plain-sha",
            encryptparms=EncryptionParms(
                alg="AES-256-GCM",
                key="11" * 32,
                iv="22" * 12,
            ),
        )
    )
    wallet.set_wallet_info = AsyncMock(
        return_value={
            "event_id": "event-1",
            "relays": [wallet.home_relay],
            "verified": True,
            "verification": {},
        }
    )
    wallet.update_tags = AsyncMock()
    wallet.set_wallet_config = AsyncMock()
    wallet.discover_blossom_service_identity = AsyncMock(return_value=GROVE_NPUB)
    wallet.resolve_blob_servers = AsyncMock(
        return_value=[wallet.blossom_home_server]
    )
    return wallet


@pytest.mark.asyncio
async def test_put_record_preserves_existing_encrypted_attachment_metadata():
    wallet = wallet_with_existing_attachment()

    result = await wallet.put_record(
        "Field Notes",
        "updated text",
        preserve_existing_blob=True,
        return_result=True,
    )

    stored = json.loads(wallet.set_wallet_info.await_args.args[1])
    assert stored["payload"] == "updated text"
    assert "blobref" not in stored
    assert stored["blobtype"] == "application/pdf"
    assert stored["blobsha256"] == "cipher-sha"
    assert stored["blob_service_npubs"] == [GROVE_NPUB]
    assert stored["origsha256"] == "plain-sha"
    assert stored["encryptparms"]["alg"] == "AES-256-GCM"
    assert result["blobref"] is None
    assert result["blobsha256"] == "cipher-sha"
    wallet.update_tags.assert_not_awaited()
    wallet.set_wallet_config.assert_not_awaited()


@pytest.mark.asyncio
async def test_put_record_replaces_attachment_after_verified_record_publish(monkeypatch):
    wallet = wallet_with_existing_attachment()
    deleted = []

    class FakeBlossomClient:
        def __init__(self, **kwargs):
            pass

        def upload_blob(self, server, data, mime_type=None, description=None):
            assert mime_type == "application/octet-stream"
            return {
                "sha256": "new-cipher-sha",
                "url": f"{server}/new-cipher-sha",
            }

        def delete_blob(self, server, sha256):
            deleted.append((server, sha256))

    monkeypatch.setattr(acorn_module, "BlossomClient", FakeBlossomClient)

    result = await wallet.put_record(
        "Field Notes",
        "updated text",
        blob_data=b"replacement attachment",
        preserve_existing_blob=True,
        return_result=True,
    )

    stored = json.loads(wallet.set_wallet_info.await_args.args[1])
    assert "blobref" not in stored
    assert stored["blobsha256"] == "new-cipher-sha"
    assert stored["blob_service_npubs"] == [GROVE_NPUB]
    assert stored["origsha256"] != "plain-sha"
    assert deleted == [("https://blossom.example", "cipher-sha")]
    assert result["replaced_blob_cleanup"]["deleted"] is True


@pytest.mark.asyncio
async def test_put_record_preserves_declared_pkpass_effective_mime(monkeypatch):
    wallet = wallet_with_existing_attachment()
    wallet.get_record_safebox = AsyncMock(side_effect=ValueError("No event found"))
    wallet.blossom_home_server = "https://blossom.example"
    wallet.blossom_servers = [wallet.blossom_home_server]

    uploaded: dict[str, bytes] = {}

    class FakeBlossomClient:
        def __init__(self, **kwargs):
            pass

        def upload_blob(self, server, data, mime_type=None, description=None):
            assert mime_type == "application/octet-stream"
            uploaded["data"] = data
            return {
                "sha256": "cipher-sha",
                "url": f"{server}/cipher-sha",
            }

    monkeypatch.setattr(acorn_module, "BlossomClient", FakeBlossomClient)

    result = await wallet.put_record(
        "Boarding Pass",
        {"filename": "Example.pkpass"},
        blob_data=PKPASS_FIXTURE.read_bytes(),
        blob_type=PKPASS_MIME,
        return_result=True,
    )

    stored = json.loads(wallet.set_wallet_info.await_args.args[1])
    assert stored["blobtype"] == PKPASS_MIME
    assert stored["effective_mime"] == PKPASS_MIME
    assert stored["effective_mime_source"] == "declared"
    assert stored["detected_mime"] == "application/zip"
    assert stored["blob_service_npubs"] == [GROVE_NPUB]
    assert "blobref" not in stored
    assert result["effective_mime"] == PKPASS_MIME
    assert uploaded["data"] != PKPASS_FIXTURE.read_bytes()


@pytest.mark.asyncio
async def test_put_record_retains_blobref_for_unidentified_blossom(monkeypatch):
    wallet = wallet_with_existing_attachment()
    wallet.get_record_safebox = AsyncMock(side_effect=ValueError("No event found"))
    wallet.discover_blossom_service_identity = AsyncMock(return_value=None)

    class FakeBlossomClient:
        def __init__(self, **kwargs):
            pass

        def upload_blob(self, server, data, mime_type=None, description=None):
            return {
                "sha256": "legacy-cipher-sha",
                "url": f"{server}/legacy-cipher-sha",
            }

    monkeypatch.setattr(acorn_module, "BlossomClient", FakeBlossomClient)

    result = await wallet.put_record(
        "Legacy Attachment",
        "content",
        blob_data=b"attachment",
        return_result=True,
    )

    stored = json.loads(wallet.set_wallet_info.await_args.args[1])
    assert stored["blob_service_npubs"] == []
    assert stored["blobref"] == (
        "https://blossom.example/legacy-cipher-sha"
    )
    assert result["blobref"] == stored["blobref"]
