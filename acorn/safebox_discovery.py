"""Additive Safebox v1 directory contract. Never substitutes social NIP-05 keys.

No wallet keys, signatures, mint operations or publications are performed here.
Existing Acorn address/transfer APIs retain their original semantics.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import ipaddress
import json
import re
import socket
from urllib.parse import urlsplit

import httpx
from stroma import Keys

CASH = 'acorn-ecash-transfer'
CLEAR = 'clear-token-transfer'
WALLET_MESSAGE = 'safebox-wallet-message'
_PROTOCOLS = {CASH: ('nip59', 7378), CLEAR: ('nip59', 7379), WALLET_MESSAGE: ('nip17', 14)}
MAX_BYTES = 65536


class SafeboxDiscoveryError(ValueError):
    """Malformed, unsafe or unavailable discovery; never downgrade to NIP-05."""


class SafeboxNotFound(SafeboxDiscoveryError):
    """HTTP 404 only: absent endpoint and absent handle are indistinguishable."""


class SafeboxHTTPError(SafeboxDiscoveryError):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f'Safebox directory returned HTTP {status_code}')


def normalize_safebox_name(name: str) -> str:
    if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9_.-]{1,64}', name.lower()):
        raise SafeboxDiscoveryError('Invalid Safebox name')
    return name.lower()


def normalize_safebox_address(address: str) -> str:
    if not isinstance(address, str) or address.count('@') != 1:
        raise SafeboxDiscoveryError('Invalid Safebox address')
    name, domain = address.strip().split('@')
    name = normalize_safebox_name(name)
    try:
        domain = domain.encode('idna').decode('ascii').lower()
    except UnicodeError:
        raise SafeboxDiscoveryError('Invalid Safebox domain') from None
    if (len(domain) > 253 or '.' not in domain or any(not re.fullmatch(
            r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in domain.split('.'))):
        raise SafeboxDiscoveryError('Invalid Safebox domain')
    return f'{name}@{domain}'


def _public_host(host: str) -> None:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        try:
            host = host.encode('idna').decode('ascii').lower()
        except UnicodeError:
            raise SafeboxDiscoveryError('Invalid public hostname') from None
        if (len(host) > 253 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in host.split('.'))
                or '.' not in host or host.endswith(('.localhost', '.local', '.lan', '.internal', '.home.arpa'))
                or host.endswith('.')):
            raise SafeboxDiscoveryError('Public host required')
    else:
        if not address.is_global or address.is_multicast:
            raise SafeboxDiscoveryError('Public host required')


def _relay(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2048 or any(c.isspace() or ord(c) < 32 for c in value):
        raise SafeboxDiscoveryError('Invalid wallet relay')
    try:
        p = urlsplit(value)
        if (p.scheme != 'wss' or not p.hostname or p.username is not None or p.password is not None
                or p.fragment or '\\' in value or (p.port is not None and not 1 <= p.port <= 65535)):
            raise ValueError()
        _public_host(p.hostname)
    except ValueError:
        raise SafeboxDiscoveryError('Invalid wallet relay') from None
    return value


@dataclass(frozen=True)
class SafeboxDestination:
    address: str
    pubkey: str
    relays: tuple[str, ...]
    # Canonical JSON avoids mutable nested structures inside this result.
    _capabilities_json: str
    source: str = 'safebox-v1'

    @property
    def capabilities(self) -> dict:
        return json.loads(self._capabilities_json)

    def supports(self, capability: str, unit: str | None = None) -> bool:
        if capability not in _PROTOCOLS:
            return False
        descriptor = self.capabilities.get(capability)
        if descriptor is None:
            return False
        return unit is None or 'units' not in descriptor or unit in descriptor['units']

    def to_dict(self) -> dict:
        return {'version': 1, 'address': self.address, 'pubkey': self.pubkey,
                'relays': list(self.relays), 'capabilities': self.capabilities}


def parse_safebox_document(payload: dict, address: str) -> SafeboxDestination:
    expected = normalize_safebox_address(address)
    if not isinstance(payload, dict) or type(payload.get('version')) is not int or payload['version'] != 1:
        raise SafeboxDiscoveryError('Unsupported Safebox document version')
    if payload.get('address') != expected:
        raise SafeboxDiscoveryError('Safebox address mismatch')
    pubkey = payload.get('pubkey')
    if not isinstance(pubkey, str) or not re.fullmatch(r'[0-9a-f]{64}', pubkey):
        raise SafeboxDiscoveryError('Invalid wallet public key')
    try:
        Keys(pub_k=pubkey)
    except Exception:
        raise SafeboxDiscoveryError('Invalid wallet public key') from None
    relays = payload.get('relays')
    if not isinstance(relays, list) or not 1 <= len(relays) <= 8:
        raise SafeboxDiscoveryError('Expected 1–8 wallet relays')
    relays = tuple(_relay(value) for value in relays)
    if len(set(relays)) != len(relays):
        raise SafeboxDiscoveryError('Duplicate wallet relay')
    capabilities = payload.get('capabilities')
    if not isinstance(capabilities, dict) or not capabilities:
        raise SafeboxDiscoveryError('Missing wallet capabilities')
    known = {}
    for name, (transport, kind) in _PROTOCOLS.items():
        if name not in capabilities:
            continue
        descriptor = capabilities[name]
        if not isinstance(descriptor, dict):
            raise SafeboxDiscoveryError('Invalid capability')
        transports, kinds = descriptor.get('transports'), descriptor.get('kinds')
        if (not isinstance(transports, list) or any(not isinstance(t, str) for t in transports)
                or transport not in transports or not isinstance(kinds, list)
                or any(type(k) is not int for k in kinds) or kind not in kinds):
            raise SafeboxDiscoveryError('Invalid capability transport or kind')
        units = descriptor.get('units')
        if 'units' in descriptor and (not isinstance(units, list) or not units
                or any(not isinstance(u, str) or not u or len(u) > 128 for u in units)):
            raise SafeboxDiscoveryError('Invalid capability units')
        if name == CASH and (not units or 'sat' not in units):
            raise SafeboxDiscoveryError('Cash capability must include sat')
        # Never propagate issuer restrictions or unrecognized fields as policy.
        known[name] = {'transports': list(transports), 'kinds': list(kinds)}
        if units is not None:
            known[name]['units'] = list(units)
    return SafeboxDestination(expected, pubkey, relays, json.dumps(known, separators=(',', ':')))


def build_safebox_document(address: str, pubkey: str, relays, *, cash: bool = True,
                            clear: bool = False, clear_units=()) -> dict:
    capabilities = {}
    if cash:
        capabilities[CASH] = {'transports': ['nip59'], 'kinds': [7378], 'units': ['sat']}
    if clear:
        capabilities[CLEAR] = {'transports': ['nip59'], 'kinds': [7379]}
        if clear_units:
            capabilities[CLEAR]['units'] = list(clear_units)
    address = normalize_safebox_address(address)
    return parse_safebox_document({'version': 1, 'address': address, 'pubkey': pubkey,
        'relays': list(relays), 'capabilities': capabilities}, address).to_dict()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SafeboxDiscoveryError('Duplicate JSON key')
        result[key] = value
    return result


async def resolve_safebox_address(address: str, *, timeout: float = 5.0) -> SafeboxDestination:
    """Public-only, bounded HTTPS lookup. No cache, redirects or NIP-05 fallback.

    SafeboxNotFound is raised only for 404. Other HTTP/network/document errors
    must not be interpreted as consent to send to a social NIP-05 key.
    """
    address = normalize_safebox_address(address)
    name, domain = address.split('@')
    if not 0 < timeout <= 30:
        raise SafeboxDiscoveryError('Discovery timeout must be 0–30 seconds')
    _public_host(domain)
    try:
        async with asyncio.timeout(timeout):
            answers = await asyncio.get_running_loop().getaddrinfo(domain, 443, type=socket.SOCK_STREAM)
            ips = list(dict.fromkeys(answer[4][0] for answer in answers))
            if not ips:
                raise SafeboxDiscoveryError('No public address')
            for ip in ips:
                _public_host(str(ipaddress.ip_address(ip)))
            url = httpx.URL(f'https://{domain}/.well-known/safebox.json').copy_with(host=ips[0])
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
                async with client.stream('GET', url, params={'name': name}, headers={'Host': domain, 'Accept': 'application/json'},
                                         extensions={'sni_hostname': domain}) as response:
                    if response.status_code == 404:
                        raise SafeboxNotFound('Safebox address not found')
                    if response.status_code != 200:
                        raise SafeboxHTTPError(response.status_code)
                    if response.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
                        raise SafeboxDiscoveryError('Expected JSON content type')
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_BYTES:
                            raise SafeboxDiscoveryError('Safebox response too large')
                    payload = json.loads(body, object_pairs_hook=_unique_object)
                    return parse_safebox_document(payload, address)
    except SafeboxDiscoveryError:
        raise
    except (ValueError, UnicodeError, httpx.HTTPError, OSError, TimeoutError):
        raise SafeboxDiscoveryError('Safebox discovery unavailable or invalid') from None
