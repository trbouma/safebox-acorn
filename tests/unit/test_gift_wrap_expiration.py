from __future__ import annotations

import asyncio

import pytest
from monstr.encrypt import Keys
from monstr.event.event import Event
from monstr.signing.signing import BasicKeySigner

from acorn.monstrmore import KindOtherGiftWrap


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
