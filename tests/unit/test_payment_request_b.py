import pytest
from stroma import Entities
from acorn.payment_request import decode_payment_request, PaymentRequestError

EXAMPLE = "CREQB1QYQQWER9D4HNZV3NQGQQSQQQQQQQQQQRAQPSQQGQQSQQZQG9QQVXSAR5WPEN5TE0D45KUAPWV4UXZMTSD3JJUCM0D5RQQRJRDANXVET9YPCXZ7TDV4H8GXHR3TQ"


def tlv(tag, value):
    return bytes([tag]) + len(value).to_bytes(2, "big") + value


def encode(data, constant=0x2bc830a3):
    # Test-only Bech32m encoder; production generation stays creqA.
    alphabet = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    bits = ''.join(f'{byte:08b}' for byte in data)
    bits += '0' * (-len(bits) % 5)
    words = [int(bits[i:i+5], 2) for i in range(0, len(bits), 5)]
    hrp = 'creqb'
    chk = 1
    for value in [*(ord(c) >> 5 for c in hrp), 0, *(ord(c) & 31 for c in hrp), *words, 0, 0, 0, 0, 0, 0]:
        top = chk >> 25
        chk = (chk & 0x1ffffff) << 5 ^ value
        for i, g in enumerate([0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]):
            if top >> i & 1: chk ^= g
    chk ^= constant
    return hrp + '1' + ''.join(alphabet[v] for v in words + [(chk >> (5 * i)) & 31 for i in range(5, -1, -1)])


@pytest.mark.parametrize('value', [EXAMPLE, EXAMPLE.lower(), 'bitcoin:?creq=' + EXAMPLE])
def test_official_vector(value):
    request = decode_payment_request(value)
    assert (request.payment_id, request.amount, request.unit, request.description) == ('demo123', 1000, 'sat', 'Coffee payment')
    assert request.single_use is True


@pytest.mark.parametrize('relay', [None, 'ws://spurline:8080'])
def test_clear_transport_and_multi_value_tags(relay):
    tags = tlv(3, b'\x01n\x0217\x0259')
    if relay:
        tags += tlv(3, b'\x01r' + bytes([len(relay)]) + relay.encode())
    transport = tlv(1, b'\x00') + tlv(2, bytes.fromhex('11' * 32)) + tags
    request = decode_payment_request(encode(tlv(2, (25).to_bytes(8, 'big')) + tlv(3, b'cmu-test') + tlv(7, transport) + tlv(99, b'ignored')))
    assert request.unit == 'cmu-test'
    assert request.transports[0].tags[0] == ('n', '17', '59')
    target = Entities.decode(request.transports[0].target)
    assert (target['pubkey'] if relay else target) == '11' * 32
    if relay: assert target['relay'] == relay
    from tests.unit.test_payment_request_routing import wallet
    assert wallet()._nut18_nostr_destination(request) == ('11' * 32, [relay] if relay else [])


@pytest.mark.parametrize('data', [b'\x01', b'\x01\x00\x05x', tlv(2,b'\x01'), tlv(4,b'\x02'), tlv(1,b'\xff'), tlv(1,b'a')+tlv(1,b'b'), tlv(8,b''), tlv(7,tlv(1,b'\x00')+tlv(2,b'bad'))])
def test_rejects_malformed_or_unsupported(data):
    with pytest.raises(PaymentRequestError): decode_payment_request(encode(data))


@pytest.mark.parametrize('value', [EXAMPLE[:-1]+'P', 'c'+EXAMPLE[1:], encode(tlv(1,b'a'), constant=1), 'bitcoin:?creq='+EXAMPLE+'&creq='+EXAMPLE])
def test_rejects_checksum_case_and_ambiguity(value):
    with pytest.raises(PaymentRequestError): decode_payment_request(value)


@pytest.mark.asyncio
async def test_npub_uses_inbox_discovery_and_never_sender_home():
    from unittest.mock import AsyncMock
    from tests.unit.test_payment_request_routing import wallet
    acorn = wallet()
    transport = tlv(1, b'\x00') + tlv(2, bytes.fromhex('11' * 32)) + tlv(3, b'\x01n\x0217')
    request = encode(tlv(2, (25).to_bytes(8, 'big')) + tlv(3, b'cmu-test') + tlv(7, transport))
    acorn._resolve_transfer_destination = AsyncMock(return_value={
        'relay_source': 'sender-home-fallback', 'relays': ['ws://spurline:8080']})
    acorn.get_clear_balances = AsyncMock(return_value=[])
    with pytest.raises(ValueError, match='no discoverable inbox'):
        await acorn.inspect_payment_request(request)
    acorn.get_clear_balances.assert_not_awaited()
    acorn._resolve_transfer_destination.return_value = {
        'relay_source': 'nip17-inbox', 'relays': ['wss://recipient.example']}
    with pytest.raises(ValueError, match='no matching Clear balance'):
        await acorn.inspect_payment_request(request)
    acorn.get_clear_balances.assert_awaited_once()
