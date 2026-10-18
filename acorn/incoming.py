"""Prepared incoming-payment writes owned by Acorn.

Callers persist opaque signed events between prepare and delivery. Reusing those
objects preserves event IDs across crashes; signature/payload validation prevents
replaying a different wallet's or operation's event by mistake.
"""
import asyncio
import ipaddress
from urllib.parse import urlsplit
import aiohttp
from aiohttp.resolver import DefaultResolver
from stroma import Event, NIP44Encrypt, RelayClient
from .models import NIP60Proofs, Proof, TxHistory
from .stroma_compat import ExtendedNIP44Encrypt


def validate_event(wallet, raw, kind):
    event = Event.load(raw)
    if event.kind != kind or event.pub_key != wallet.pubkey_hex or not event.is_valid():
        raise ValueError('Prepared event does not belong to this Acorn operation')
    return event


def proofs_event(wallet, proofs):
    mint = wallet.known_mints[proofs[0].id]
    if any(wallet.known_mints[p.id] != mint for p in proofs):
        raise ValueError('A proof delivery must use one mint')
    payload = NIP60Proofs(mint=mint, proofs=proofs).model_dump_json()
    if len(payload) > wallet.max_proof_event_size:
        raise ValueError('Prepared proof batch exceeds event size limit')
    event = Event(kind=7375, pub_key=wallet.pubkey_hex,
                  content=ExtendedNIP44Encrypt(wallet.k).encrypt(payload, to_pub_k=wallet.pubkey_hex))
    event.sign(wallet.privkey_hex)
    return event.data()


def validate_proofs(wallet, events, proofs):
    actual = []
    for raw in events:
        event = validate_event(wallet, raw, 7375)
        payload = NIP60Proofs.model_validate_json(ExtendedNIP44Encrypt(wallet.k).decrypt(event.content, for_pub_k=wallet.pubkey_hex))
        if any(wallet.known_mints[p.id] != payload.mint for p in payload.proofs):
            raise ValueError('Prepared proofs have a different mint')
        actual.extend(p.model_dump_json() for p in payload.proofs)
    if sorted(actual) != sorted(p.model_dump_json() for p in proofs):
        raise ValueError('Prepared proof delivery does not match its proofs')


def history_event(wallet, payload):
    event = Event(kind=7377, pub_key=wallet.pubkey_hex, created_at=payload.create_time,
                  content=NIP44Encrypt(wallet.k).encrypt(payload.model_dump_json(), to_pub_k=wallet.pubkey_hex))
    event.sign(wallet.privkey_hex)
    return event.data()


def validate_history(wallet, raw, tx_type, amount, invoice):
    event = validate_event(wallet, raw, 7377)
    payload = TxHistory.model_validate_json(NIP44Encrypt(wallet.k).decrypt(event.content, wallet.pubkey_hex))
    if (payload.tx_type, payload.amount, payload.invoice) != (tx_type, amount, invoice):
        raise ValueError('Prepared history does not match its transaction')


def zap_event(wallet, raw, invoice, paid_at):
    request = Event.load(raw)
    if request.kind != 9734 or not request.is_valid():
        raise ValueError('Invalid signed zap request')
    tags = list(request.tags)
    recipients = [t for t in tags if t and t[0] == 'p']
    if len(recipients) != 1 or len(recipients[0]) < 2 or recipients[0][1] != wallet.pubkey_hex:
        raise ValueError('Zap recipient is not this Acorn')
    copied = [t for t in tags if t[0] in ('p', 'e', 'a', 'k')]
    copied += [['P', request.pub_key], ['bolt11', invoice], ['description', raw]]
    event = Event(kind=9735, pub_key=wallet.pubkey_hex, created_at=paid_at, content='', tags=copied)
    event.sign(wallet.privkey_hex)
    return event.data()

def secure_url(value, scheme):
    value = value.strip().rstrip('/')
    p = urlsplit(value)
    if (p.scheme != scheme or not p.hostname or p.username is not None or p.password is not None
            or p.query or p.fragment or p.port not in (None, 443)):
        raise ValueError(f'Expected a {scheme} URL without credentials, query or custom port')
    return value


class PublicResolver(DefaultResolver):
    async def resolve(self, host, port=0, family=0):
        addresses = await super().resolve(host, port, family)
        if not addresses or any((not ipaddress.ip_address(row['host']).is_global or ipaddress.ip_address(row['host']).is_multicast) for row in addresses):
            raise OSError('Metadata endpoint must be public')
        return addresses


def public_relay(value):
    value = secure_url(value, 'wss')
    host = urlsplit(value).hostname
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if '.' not in host or host.endswith(('.localhost', '.local')):
            raise ValueError('Relay must be public')
    else:
        if not address.is_global or address.is_multicast:
            raise ValueError('Relay must be public')
    return value


async def publish_event(wallet, relay, event, *, private=False):
    kind = event.get('kind')
    if kind not in ((7375, 7377) if private else (9735,)):
        raise ValueError('Incorrect private/public destination for payment event')
    validate_event(wallet, event, kind)
    if private and relay != wallet.home_relay:
        raise ValueError("Private payment events must use the Acorn home relay")
    """Check the signed event is readable, or receive an OK for public receipts.

    Home relays are operator-allowlisted. Payer-provided public destinations also
    enforce public DNS at connection time and reject HTTP redirects.
    """
    if not private:
        public_relay(relay)
    async def no_redirect(session, context, params):
        raise ValueError('Relay redirects are not supported')
    trace = aiohttp.TraceConfig()
    trace.on_request_redirect.append(no_redirect)
    def session_factory(**kwargs):
        connector = aiohttp.TCPConnector(resolver=PublicResolver()) if not private else aiohttp.TCPConnector()
        return aiohttp.ClientSession(connector=connector, trace_configs=[trace],
                                     trust_env=False, **kwargs)

    client = RelayClient(relay, timeout=8, session_factory=session_factory, max_msg_size=262144)
    signed = validate_event(wallet, event, kind)

    async def readable():
        events = await client.query({'ids': [signed.id], 'limit': 1})
        return any(item.id == signed.id and item.is_valid() for item in events)

    async with asyncio.timeout(8):
        # A previous attempt may have succeeded before its journal checkpoint.
        if private and await readable():
            return True
        result = await client.publish(signed)
        if private:
            return await readable()
        return result.accepted
