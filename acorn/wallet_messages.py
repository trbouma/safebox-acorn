"""Wallet-only messages: no social NIP-05 resolution or automatic actions."""
import asyncio
import json
from stroma import BasicKeySigner, ClientPool, Event, GiftWrap, Keys
from acorn.safebox_discovery import resolve_safebox_address, normalize_safebox_address, WALLET_MESSAGE


async def resolve_wallet_message(address):
    destination = await resolve_safebox_address(address)
    if not destination.supports(WALLET_MESSAGE):
        raise ValueError('This address does not advertise wallet messaging')
    return {'pubkey': destination.pubkey, 'relays': list(destination.relays)}


def parse_wallet_message(content):
    result = {'content': content, 'claimed_sender': None, 'verification': None}
    try:
        value = json.loads(content)
    except (ValueError, TypeError):
        return result
    if not isinstance(value, dict):
        return result
    if {'mint', 'unit', 'proofs'}.issubset(value):
        return None
    if (value.get('type') == 'safebox.dm' and type(value.get('version')) is int
            and value['version'] == 1 and isinstance(value.get('message'), str)
            and (value.get('sender') is None or isinstance(value.get('sender'), str))):
        result.update(content=value['message'], claimed_sender=value.get('sender'),
                      verification='unverified' if value.get('sender') else None)
    return result


async def send_wallet_message(wallet, recipient, message, *, relays=None, sender=None):
    if not isinstance(message, str) or not message.strip() or len(message) > 4000:
        raise ValueError('Enter a message of 1 to 4000 characters')
    if sender is not None:
        sender = normalize_safebox_address(sender)
    if '@' in recipient:
        if relays is not None:
            raise ValueError('An address must use its wallet directory routes')
        destination = await resolve_wallet_message(recipient)
        pubkey, relays = destination['pubkey'], destination['relays']
    else:
        # Explicit keys are for trusted local wallet bindings, never address lookup.
        pubkey = Keys(pub_k=recipient).public_key_hex()
    routes = wallet._normalize_relays(relays or [])
    if not routes:
        raise ValueError('Wallet message relays are required')
    routes = await wallet._require_reachable_transfer_relays(routes)
    content = json.dumps({'type': 'safebox.dm', 'version': 1, 'sender': sender,
                          'message': message}, ensure_ascii=False)
    wrapper = GiftWrap(BasicKeySigner(wallet.k), jitter_seconds=0,
                       gift_wrap_kind=1059, preserve_rumour_kind=True)
    event = Event(kind=14, content=content, pub_key=wallet.pubkey_hex, tags=[['p', pubkey]])
    outer, _ = await wrapper.wrap(event, to_pub_k=pubkey)
    try:
        async with ClientPool(routes) as client:
            await client.publish(outer)
    except Exception:
        raise RuntimeError('Delivery could not be confirmed. The message may have reached a relay; do not automatically resend.') from None
    return {'event_id': outer.id, 'recipient': pubkey, 'status': 'published'}


async def get_wallet_messages(wallet, limit=50, *, resolver=None):
    rows = []
    for row in await wallet.get_private_messages(limit=limit):
        parsed = parse_wallet_message(row['content'])
        if parsed is not None:
            rows.append({**row, **parsed})
    claims = list(dict.fromkeys(row['claimed_sender'] for row in rows if row['claimed_sender']))[:10]
    async def lookup(address):
        try:
            address = normalize_safebox_address(address)
            async with asyncio.timeout(5):
                return await (resolver or resolve_wallet_message)(address)
        except Exception:
            return None
    destinations = dict(zip(claims, await asyncio.gather(*(lookup(a) for a in claims))))
    for row in rows:
        destination = destinations.get(row['claimed_sender'])
        if destination:
            row['verification'] = 'verified' if destination['pubkey'] == row['sender'].lower() else 'mismatch'
    return rows
