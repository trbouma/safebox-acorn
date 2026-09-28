from unittest.mock import AsyncMock

import pytest
from stroma import Keys, BasicKeySigner

from acorn import acorn as module
from acorn.acorn import TransferRelayUnavailable
from acorn.stroma_compat import KindOtherGiftWrap
from tests.unit.test_inbox_relay_routing import wallet


@pytest.mark.asyncio
@pytest.mark.parametrize("signed,nip05,explicit,expected", [
    (["wss://inbox.example"], ["wss://hint.example"], None, ["wss://inbox.example"]),
    ([], ["wss://hint.example"], None, ["wss://hint.example"]),
    (["wss://inbox.example"], [], ["ws://spurline:8080"], ["ws://spurline:8080"]),
])
async def test_dm_routing_precedence(signed, nip05, explicit, expected):
    acorn = wallet()
    acorn._resolve_pubkey_and_relays = lambda _: ("22" * 32, nip05)
    acorn.resolve_inbox_relays = AsyncMock(return_value={"relays": signed})
    acorn._require_reachable_transfer_relays = AsyncMock(side_effect=lambda routes: routes)
    acorn._async_secure_dm = AsyncMock()
    assert await acorn.secure_dm("alice@example.com", "private message", explicit) == "message sent"
    acorn._require_reachable_transfer_relays.assert_awaited_once_with(expected)
    acorn._async_secure_dm.assert_awaited_once_with(
        npub_hex="22" * 32, message="private message", dm_relays=expected)
    if explicit:
        acorn.resolve_inbox_relays.assert_not_awaited()


@pytest.mark.asyncio
async def test_dm_never_silently_uses_sender_home():
    acorn = wallet()
    acorn._resolve_pubkey_and_relays = lambda _: ("22" * 32, [])
    acorn.resolve_inbox_relays = AsyncMock(return_value={"relays": []})
    acorn._async_secure_dm = AsyncMock()
    with pytest.raises(ValueError, match="No recipient inbox relay"):
        await acorn.secure_dm("22" * 32, "private message")
    acorn._async_secure_dm.assert_not_awaited()


@pytest.mark.asyncio
async def test_dm_discovery_failure_uses_nip05_hint():
    acorn = wallet()
    acorn._resolve_pubkey_and_relays = lambda _: ("22" * 32, ["wss://hint.example"])
    acorn.resolve_inbox_relays = AsyncMock(side_effect=TimeoutError())
    acorn._require_reachable_transfer_relays = AsyncMock(side_effect=lambda routes: routes)
    acorn._async_secure_dm = AsyncMock()
    await acorn.secure_dm("alice@example.com", "private message")
    assert acorn._async_secure_dm.await_args.kwargs["dm_relays"] == ["wss://hint.example"]


@pytest.mark.asyncio
async def test_dm_unreachable_routes_do_not_publish():
    acorn = wallet()
    acorn._require_reachable_transfer_relays = AsyncMock(side_effect=TransferRelayUnavailable("offline"))
    acorn._async_secure_dm = AsyncMock()
    with pytest.raises(RuntimeError, match="No message was published"):
        await acorn.secure_dm("22" * 32, "private message", ["ws://spurline:8080"])
    acorn._async_secure_dm.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("message,relays", [("", None), ("hello", []), ("hello", [" "])])
async def test_dm_rejects_empty_inputs(message, relays):
    with pytest.raises(ValueError):
        await wallet().secure_dm("22" * 32, message, relays)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [False, True])
async def test_dm_real_encryption_and_acknowledgement(monkeypatch, caplog, failure):
    acorn = wallet()
    recipient = Keys(priv_k="22" * 32)
    published = []
    class Pool:
        def __init__(self, relays):
            assert relays == ["ws://spurline:8080"]
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def publish(self, event):
            published.append(event)
            if failure: raise RuntimeError("relay unavailable")
            return []
    monkeypatch.setattr(module, "ClientPool", Pool)
    acorn._require_reachable_transfer_relays = AsyncMock(side_effect=lambda routes: routes)
    call = acorn.secure_dm(recipient.public_key_hex(), "secret test message", ["ws://spurline:8080"])
    if failure:
        with pytest.raises(RuntimeError, match="may already have reached"):
            await call
    else:
        assert await call == "message sent"
    assert len(published) == 1
    outer = published[0]
    assert outer.kind == 1059
    assert outer.tags.get_tag_value_pos("p") == recipient.public_key_hex()
    assert "secret test message" not in outer.content
    inner = await KindOtherGiftWrap(BasicKeySigner(recipient), kind_gift_wrap=1059).unwrap(outer)
    assert inner.kind == 14
    assert inner.content == "secret test message"
    assert inner.pub_key == acorn.pubkey_hex
    assert "secret test message" not in caplog.text
