import asyncio
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from acorn.safebox_discovery import (
    CASH, CLEAR, SafeboxDiscoveryError, SafeboxNotFound, SafeboxHTTPError,
    build_safebox_document, parse_safebox_document, normalize_safebox_address,
    resolve_safebox_address,
)

FIXTURE = json.loads((Path(__file__).parents[1] / 'fixtures/safebox_discovery_v1.json').read_text())


def test_roundtrip_and_capabilities():
    result = parse_safebox_document(FIXTURE, ' Alice@EXAMPLE.com ')
    assert result.address == 'alice@example.com' and result.source == 'safebox-v1'
    assert result.supports(CASH, 'sat') and result.supports(CLEAR, 'anything')
    assert not result.supports('unknown')
    assert result.to_dict() == FIXTURE
    result.capabilities[CASH]['units'].clear()
    assert result.supports(CASH, 'sat')
    assert build_safebox_document('Alice@EXAMPLE.com', result.pubkey, result.relays, clear=True) == FIXTURE


@pytest.mark.parametrize('address', ['alice', 'a@@example.com', 'a@example.com:443', 'a@example.com/x',
    'a@example.com#x', 'a@localhost', 'a@foo..com', 'a+b@example.com', 'a@-foo.com', 'a@example.com.', 'a b@example.com'])
def test_bad_addresses(address):
    with pytest.raises(SafeboxDiscoveryError):
        normalize_safebox_address(address)


def test_idna_and_normalization():
    assert normalize_safebox_address('ALICE@bücher.de') == 'alice@xn--bcher-kva.de'


@pytest.mark.parametrize(('field', 'value'), [
    ('version', True), ('version', 2), ('address', 'bob@example.com'),
    ('pubkey', 'ff'*32), ('pubkey', 'AB'*32), ('relays', []),
    ('relays', ['wss://127.0.0.1']), ('relays', ['wss://relay..example.com']),
    ('relays', ['wss://relay%2eexample.com']), ('relays', ['ws://relay.example.com']),
    ('relays', ['wss://user@relay.example.com']), ('relays', ['wss://relay.example.com#x']),
    ('relays', ['wss://relay.example.com']*2), ('capabilities', {}),
    ('capabilities', {CASH: {'transports':['nip59'], 'kinds':[True], 'units':['sat']}}),
    ('capabilities', {CASH: {'transports':['nip59'], 'kinds':[7378]}}),
    ('capabilities', {CLEAR: {'transports':['nip59'], 'kinds':[7379], 'units':[]}}),
])
def test_invalid_documents(field, value):
    payload = deepcopy(FIXTURE); payload[field] = value
    with pytest.raises(SafeboxDiscoveryError):
        parse_safebox_document(payload, 'alice@example.com')


def test_additive_fields_and_unit_policy():
    payload = deepcopy(FIXTURE)
    payload['future'] = True
    payload['capabilities']['future'] = {'anything': True}
    payload['capabilities'][CLEAR]['mints'] = ['https://not-an-allowlist.example']
    payload['capabilities'][CLEAR]['units'] = ['CAD']
    result = parse_safebox_document(payload, 'alice@example.com')
    assert result.supports(CLEAR, 'CAD') and not result.supports(CLEAR, 'USD')
    assert 'mints' not in result.capabilities[CLEAR]
    payload['capabilities'] = {'future': {}}
    assert not parse_safebox_document(payload, 'alice@example.com').supports(CASH)


def install_transport(monkeypatch, handler, ips=('93.184.216.34',)):
    monkeypatch.setattr(asyncio.get_running_loop(), 'getaddrinfo', AsyncMock(
        return_value=[(2, 1, 6, '', (ip, 443)) for ip in ips]))
    original = httpx.AsyncClient
    def factory(**kwargs):
        assert kwargs['follow_redirects'] is False and kwargs['trust_env'] is False
        return original(**kwargs, transport=httpx.MockTransport(handler))
    monkeypatch.setattr('acorn.safebox_discovery.httpx.AsyncClient', factory)


def test_secure_fetch_and_no_social_lookup(monkeypatch):
    async def run():
        seen = []
        def respond(request):
            seen.append(request)
            assert request.url.host == '93.184.216.34'
            assert request.url.path == '/.well-known/safebox.json'
            assert request.url.params['name'] == 'alice'
            assert request.headers['Host'] == 'example.com'
            assert request.extensions['sni_hostname'] == 'example.com'
            return httpx.Response(200, json=FIXTURE)
        install_transport(monkeypatch, respond)
        result = await resolve_safebox_address('alice@example.com')
        assert result.pubkey == FIXTURE['pubkey'] and len(seen) == 1
    asyncio.run(run())


@pytest.mark.parametrize('status', [301, 302, 404, 410, 429, 500, 503])
def test_http_status_never_downgrades_to_nip05(monkeypatch, status):
    async def run():
        calls = []
        def respond(request):
            calls.append(request)
            return httpx.Response(status, headers={'Location':'https://other.example/nostr.json'})
        install_transport(monkeypatch, respond)
        with pytest.raises(SafeboxNotFound if status == 404 else SafeboxHTTPError):
            await resolve_safebox_address('alice@example.com')
        assert len(calls) == 1
    asyncio.run(run())


@pytest.mark.parametrize('ips', [('127.0.0.1',), ('93.184.216.34','10.0.0.1'), ('::1',), ('224.0.0.1',), ()])
def test_private_dns_never_connects(monkeypatch, ips):
    async def run():
        def respond(request):
            pytest.fail('unsafe request')
        install_transport(monkeypatch, respond, ips)
        with pytest.raises(SafeboxDiscoveryError):
            await resolve_safebox_address('alice@example.com')
    asyncio.run(run())


@pytest.mark.parametrize('body', [b'{"version":1,"version":1}', b' '*65537, b'not-json', b'[]'])
def test_bad_json_and_size(monkeypatch, body):
    async def run():
        install_transport(monkeypatch, lambda request: httpx.Response(200, content=body,
            headers={'Content-Type':'application/json'}))
        with pytest.raises(SafeboxDiscoveryError):
            await resolve_safebox_address('alice@example.com')
    asyncio.run(run())


def test_timeout_is_bounded(monkeypatch):
    async def run():
        async def respond(request):
            await asyncio.sleep(1)
            return httpx.Response(200, json=FIXTURE)
        install_transport(monkeypatch, respond)
        with pytest.raises(SafeboxDiscoveryError):
            await resolve_safebox_address('alice@example.com', timeout=0.01)
    asyncio.run(run())


def test_non_json_content_type_rejected(monkeypatch):
    async def run():
        install_transport(monkeypatch, lambda request: httpx.Response(200, content=json.dumps(FIXTURE),
            headers={'Content-Type':'text/html'}))
        with pytest.raises(SafeboxDiscoveryError, match='content type'):
            await resolve_safebox_address('alice@example.com')
    asyncio.run(run())


def test_public_exports_are_additive():
    from acorn import resolve_safebox_address as exported, build_safebox_document as builder
    assert exported is resolve_safebox_address and builder is build_safebox_document
