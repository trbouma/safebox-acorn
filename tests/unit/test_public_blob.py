import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
import stroma
from stroma import NIP44Encrypt, Keys
from acorn.acorn import Acorn
from test_blob_encryption import encrypted_fixture


def test_public_blob_uses_stroma_and_decrypts_inside_acorn(monkeypatch):
    async def run():
        plaintext,ciphertext,parameters,cipher_hash,plain_hash=encrypted_fixture()
        wallet=Acorn(nsec=Keys().private_key_bech32(), home_relay='wss://relay.example')
        payload={'tag':['Note'],'type':'record','payload':'Note','blobsha256':cipher_hash,
                 'origsha256':plain_hash,'blobtype':'text/plain','encryptparms':parameters.model_dump()}
        wallet._async_get_wallet_info=AsyncMock(return_value=SimpleNamespace(
            content=NIP44Encrypt(wallet.k).encrypt(json.dumps(payload),to_pub_k=wallet.pubkey_hex)))
        wallet.resolve_blob_servers=AsyncMock(return_value=['https://blob.example'])
        pool=SimpleNamespace(retrieve=AsyncMock(return_value=SimpleNamespace(content=ciphertext)))
        def factory(servers, **kwargs):
            assert servers==['https://blob.example']
            assert kwargs['max_bytes']==25*1024*1024 and kwargs['operation_timeout']==30
            assert not kwargs.get('allow_private')
            return pool
        monkeypatch.setattr(stroma,'BlossomPool',factory)
        kind,data=await wallet.get_record_blobdata('Note',public_only=True)
        assert data==plaintext
        pool.retrieve.assert_awaited_once_with(cipher_hash)
        pool.retrieve.return_value.content=b'corrupted'
        with pytest.raises(RuntimeError,match='integrity'):
            await wallet.get_record_blobdata('Note',public_only=True)
    asyncio.run(run())
