from __future__ import annotations

import asyncio
from datetime import datetime

import pytest
from stroma import Keys, Event, BasicKeySigner

from acorn.stroma_compat import KindOtherGiftWrap


def test_gift_wrap_uses_current_timestamp_without_jitter(monkeypatch) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(500, tz=tz)

    monkeypatch.setattr("acorn.stroma_compat.datetime", FixedDateTime)
    sender = Keys()
    recipient = Keys()
    wrapper = KindOtherGiftWrap(
        BasicKeySigner(sender),
        kind_gift_wrap=1059,
        preserve_rumour_kind=True,
    )
    inner = Event(kind=7378, content="{}", pub_key=sender.public_key_hex())

    wrapped, transient_key = asyncio.run(
        wrapper.wrap(inner, to_pub_k=recipient.public_key_hex())
    )
    seal_json = asyncio.run(
        BasicKeySigner(recipient).nip44_decrypt(
            wrapped.content,
            transient_key.public_key_hex(),
        )
    )
    seal = Event.load(seal_json)

    assert wrapped.created_at == 500
    assert seal is not None
    assert seal.created_at == 500


def test_gift_wrap_adds_signed_nip40_expiration_tag() -> None:
    sender = Keys()
    recipient = Keys()
    wrapper = KindOtherGiftWrap(
        BasicKeySigner(sender),
        kind_gift_wrap=1059,
        preserve_rumour_kind=True,
    )
    inner = Event(
        kind=7378,
        content='{"type":"cashu-token"}',
        pub_key=sender.public_key_hex(),
        tags=[["p", recipient.public_key_hex()]],
    )

    wrapped, _transient_key = asyncio.run(
        wrapper.wrap(
            inner,
            to_pub_k=recipient.public_key_hex(),
            expiration=2_000_000_000,
        )
    )

    assert ["p", recipient.public_key_hex()] in wrapped.data()["tags"]
    assert ["expiration", "2000000000"] in wrapped.data()["tags"]
    assert wrapped.sig


def test_gift_wrap_rejects_non_positive_expiration() -> None:
    sender = Keys()
    recipient = Keys()
    wrapper = KindOtherGiftWrap(BasicKeySigner(sender), kind_gift_wrap=1059)
    inner = Event(kind=7378, content="{}", pub_key=sender.public_key_hex(), tags=[])

    with pytest.raises(ValueError, match="positive Unix timestamp"):
        asyncio.run(
            wrapper.wrap(
                inner,
                to_pub_k=recipient.public_key_hex(),
                expiration=0,
            )
        )
