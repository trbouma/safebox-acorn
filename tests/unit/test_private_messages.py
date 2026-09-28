from unittest.mock import AsyncMock

import pytest
from stroma import BasicKeySigner, Event, Keys

from acorn import acorn as module
from acorn.stroma_compat import KindOtherGiftWrap
from tests.unit.test_inbox_relay_routing import wallet


@pytest.mark.asyncio
async def test_private_inbox_authenticated_deduplicated_and_read_only(monkeypatch):
    receiver = wallet()
    sender = Keys()
    wrapper = KindOtherGiftWrap(BasicKeySigner(sender), kind_gift_wrap=1059)
    inner = Event(kind=14, pub_key=sender.public_key_hex(), content="private text", tags=[["p", receiver.pubkey_hex]])
    good, _ = await wrapper.wrap(inner, receiver.pubkey_hex)
    bad = Event.load(good.data())
    bad.content = "invalid"
    receiver._resolve_receive_relay_pool = AsyncMock(return_value=(["ws://internal"], {}))
    receiver._require_reachable_transfer_relays = AsyncMock(side_effect=lambda routes: routes)
    receiver.secure_dm = AsyncMock()
    class Pool:
        def __init__(self, relays): assert relays == ["ws://internal"]
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def query(self, filters):
            assert filters["#p"] == [receiver.pubkey_hex]
            return [bad, good, good]
    monkeypatch.setattr(module, "ClientPool", Pool)
    result = await receiver.get_private_messages()
    assert len(result) == 1
    assert result[0]["sender"] == sender.public_key_hex()
    assert result[0]["content"] == "private text"
    receiver.secure_dm.assert_not_awaited()


@pytest.mark.asyncio
async def test_private_inbox_rejects_forged_rumour_author(monkeypatch):
    import json
    receiver = wallet()
    sender = Keys()
    wrapper = KindOtherGiftWrap(BasicKeySigner(sender), kind_gift_wrap=1059)
    rumour = Event(kind=14, pub_key=Keys().public_key_hex(), content="forged", tags=[["p", receiver.pubkey_hex]])
    seal = await wrapper._make_seal(rumour, receiver.pubkey_hex)
    transient = BasicKeySigner(Keys())
    outer = Event(kind=1059, pub_key=await transient.get_public_key(), tags=[["p", receiver.pubkey_hex]],
                  content=await transient.nip44_encrypt(json.dumps(seal.data()), receiver.pubkey_hex))
    await transient.sign_event(outer)
    receiver._resolve_receive_relay_pool = AsyncMock(return_value=(["ws://internal"], {}))
    receiver._require_reachable_transfer_relays = AsyncMock(side_effect=lambda routes: routes)
    class Pool:
        def __init__(self, relays): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def query(self, filters): return [outer]
    monkeypatch.setattr(module, "ClientPool", Pool)
    assert await receiver.get_private_messages() == []
