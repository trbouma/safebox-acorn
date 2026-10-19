import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from stroma import Keys, BasicKeySigner, GiftWrap
from acorn import wallet_messages as module
from acorn.safebox_discovery import SafeboxNotFound, WALLET_MESSAGE
from tests.unit.test_inbox_relay_routing import wallet


@pytest.mark.asyncio
async def test_wallet_send_uses_directory_and_zero_jitter_stroma(monkeypatch):
    sender = wallet()
    recipient = Keys()
    directory = SimpleNamespace(pubkey=recipient.public_key_hex(), relays=['wss://wallet.example'],
                                supports=lambda cap: cap == WALLET_MESSAGE)
    lookup = AsyncMock(return_value=directory)
    monkeypatch.setattr(module, 'resolve_safebox_address', lookup)
    sender._resolve_pubkey_and_relays = lambda _: pytest.fail('No social resolver')
    sender._require_reachable_transfer_relays = AsyncMock(side_effect=lambda r:r)
    events = []
    class Pool:
        def __init__(self, routes): assert routes == directory.relays
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def publish(self, event): events.append(event)
    monkeypatch.setattr(module, 'ClientPool', Pool)
    before = int(time.time())
    result = await sender.send_wallet_message('alice@example.com', 'private hello', sender='bob@example.com')
    assert result['recipient'] == recipient.public_key_hex()
    lookup.assert_awaited_once_with('alice@example.com')
    assert len(events) == 1 and before <= events[0].data()['created_at'] <= int(time.time())
    assert 'private hello' not in events[0].content
    wrapper = GiftWrap(BasicKeySigner(recipient), jitter_seconds=0)
    inner = await wrapper.unwrap(events[0])
    assert inner.kind == 14 and inner.pub_key == sender.pubkey_hex
    assert json.loads(inner.content) == {'type':'safebox.dm','version':1,'sender':'bob@example.com','message':'private hello'}
    # The existing Safebox Web reader can authenticate the new Stroma envelope.
    from acorn.stroma_compat import KindOtherGiftWrap
    old_inner = await KindOtherGiftWrap(BasicKeySigner(recipient), kind_gift_wrap=1059).unwrap(events[0])
    assert old_inner.content == inner.content


@pytest.mark.asyncio
async def test_missing_wallet_never_calls_social_or_publishes(monkeypatch):
    sender = wallet()
    monkeypatch.setattr(module, 'resolve_safebox_address', AsyncMock(side_effect=SafeboxNotFound('missing')))
    sender._resolve_pubkey_and_relays = lambda _: pytest.fail('No social fallback')
    sender._require_reachable_transfer_relays = AsyncMock()
    with pytest.raises(SafeboxNotFound):
        await sender.send_wallet_message('alice@example.com', 'hello')
    sender._require_reachable_transfer_relays.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_capability_fails(monkeypatch):
    monkeypatch.setattr(module, 'resolve_safebox_address', AsyncMock(return_value=SimpleNamespace(supports=lambda c:False)))
    with pytest.raises(ValueError, match='does not advertise'):
        await wallet().send_wallet_message('alice@example.com', 'hello')


@pytest.mark.asyncio
async def test_wallet_inbox_keeps_authenticated_key_and_filters_payments():
    sender = wallet()
    def row(content): return {'id':'id','sender':'11'*32,'created_at':1,'content':content}
    envelope = json.dumps({'type':'safebox.dm','version':1,'sender':'alice@example.com','message':'hello'})
    sender.get_private_messages = AsyncMock(return_value=[row(envelope),row('{"mint":"m","unit":"sat","proofs":[]}'),row('plain text')])
    resolver = AsyncMock(return_value={'pubkey':'22'*32})
    rows = await sender.get_wallet_messages(resolver=resolver)
    assert len(rows) == 2 and rows[0]['verification'] == 'mismatch'
    assert rows[0]['sender'] == '11'*32 and rows[0]['content'] == 'hello'
    resolver.side_effect = TimeoutError()
    assert (await sender.get_wallet_messages(resolver=resolver))[0]['verification'] == 'unverified'


@pytest.mark.asyncio
async def test_publication_failure_is_not_retried(monkeypatch):
    sender = wallet()
    sender._require_reachable_transfer_relays = AsyncMock(side_effect=lambda r:r)
    publish = AsyncMock(side_effect=RuntimeError('private relay error'))
    class Pool:
        def __init__(self,r): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*a): pass
    Pool.publish = publish
    monkeypatch.setattr(module,'ClientPool',Pool)
    with pytest.raises(RuntimeError,match='do not automatically resend'):
        await sender.send_wallet_message(Keys().public_key_hex(),'hello',relays=['wss://relay.example'])
    assert publish.await_count == 1
