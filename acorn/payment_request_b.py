"""Bounded NUT-26 Bech32m/TLV decoder into the NUT-18 data model."""
from stroma import Entities

from .payment_request import MAX_PAYMENT_REQUEST_BYTES, PaymentRequestError

CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _decode_bech32m(value: str) -> bytes:
    if len(value) > MAX_PAYMENT_REQUEST_BYTES * 2:
        raise PaymentRequestError("NUT-26 request is oversized")
    if value != value.lower() and value != value.upper():
        raise PaymentRequestError("NUT-26 request must not mix upper and lower case")
    value = value.lower()
    if not value.startswith("creqb1") or len(value) < 12:
        raise PaymentRequestError("Invalid NUT-26 prefix or checksum")
    try:
        words = [CHARSET.index(c) for c in value[6:]]
    except ValueError as exc:
        raise PaymentRequestError("Invalid NUT-26 alphabet") from exc
    hrp = "creqb"
    checksum = 1
    generators = (0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3)
    for word in [*(ord(c) >> 5 for c in hrp), 0, *(ord(c) & 31 for c in hrp), *words]:
        top = checksum >> 25
        checksum = ((checksum & 0x1ffffff) << 5) ^ word
        for bit, generator in enumerate(generators):
            if (top >> bit) & 1:
                checksum ^= generator
    if checksum != 0x2bc830a3:
        raise PaymentRequestError("Invalid NUT-26 Bech32m checksum")
    result = bytearray()
    accumulator = bits = 0
    for word in words[:-6]:
        accumulator = ((accumulator << 5) | word) & 0xffff
        bits += 5
        if bits >= 8:
            bits -= 8
            result.append((accumulator >> bits) & 255)
    if bits >= 5 or (accumulator << (8 - bits)) & 255:
        raise PaymentRequestError("Invalid NUT-26 padding")
    if len(result) > MAX_PAYMENT_REQUEST_BYTES:
        raise PaymentRequestError("NUT-26 request is oversized")
    return bytes(result)


def _tlv(data: bytes):
    offset = 0
    while offset < len(data):
        if len(data) - offset < 3:
            raise PaymentRequestError("Truncated NUT-26 TLV header")
        tag = data[offset]
        size = int.from_bytes(data[offset + 1:offset + 3], "big")
        offset += 3
        if size > len(data) - offset:
            raise PaymentRequestError("Truncated NUT-26 TLV value")
        yield tag, data[offset:offset + size]
        offset += size


def _text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PaymentRequestError("Invalid NUT-26 UTF-8") from exc


def _tuple(data: bytes) -> list[str]:
    result = []
    offset = 0
    while offset < len(data):
        size = data[offset]
        offset += 1
        if size > len(data) - offset:
            raise PaymentRequestError("Truncated NUT-26 tag tuple")
        result.append(_text(data[offset:offset + size]))
        offset += size
    if len(result) < 2 or any(not item for item in result):
        raise PaymentRequestError("Invalid NUT-26 tag tuple")
    return result


def _transport(data: bytes) -> dict:
    fields = {}
    tags = []
    for tag, value in _tlv(data):
        if tag == 3:
            tags.append(_tuple(value))
        elif tag in (1, 2):
            if tag in fields:
                raise PaymentRequestError("Duplicate NUT-26 transport field")
            fields[tag] = value
    kind, target = fields.get(1), fields.get(2)
    if kind == b"\x00" and target is not None and len(target) == 32:
        relays = [value for tag in tags if tag[0] == "r" for value in tag[1:]]
        target_text = (Entities.encode("nprofile", {"pubkey": target.hex(), "relay": relays})
                       if relays else Entities.encode("npub", target.hex()))
        return {"t": "nostr", "a": target_text, "g": tags}
    if kind == b"\x01" and target is not None:
        return {"t": "post", "a": _text(target), "g": tags}
    raise PaymentRequestError("Unsupported or malformed NUT-26 transport")


def decode_nut26(value: str) -> dict:
    payload = {}
    seen = set()
    text_fields = {1: "i", 5: "m", 6: "d"}
    for tag, data in _tlv(_decode_bech32m(value)):
        if tag in (1, 2, 3, 4, 6, 8):
            if tag in seen:
                raise PaymentRequestError("Duplicate NUT-26 request field")
            seen.add(tag)
        if tag in text_fields:
            field = text_fields[tag]
            if tag == 5:
                payload.setdefault(field, []).append(_text(data))
            else:
                payload[field] = _text(data)
        elif tag == 2:
            if len(data) != 8:
                raise PaymentRequestError("NUT-26 amount must be a u64")
            payload["a"] = int.from_bytes(data, "big")
        elif tag == 3:
            payload["u"] = "sat" if data == b"\x00" else _text(data)
        elif tag == 4:
            if data not in (b"\x00", b"\x01"):
                raise PaymentRequestError("Invalid NUT-26 single-use flag")
            payload["s"] = data == b"\x01"
        elif tag == 7:
            payload.setdefault("t", []).append(_transport(data))
        elif tag == 8:
            raise PaymentRequestError("NUT-10 spending conditions are not supported for payment requests")
        # Unknown tags are intentionally ignored for forward compatibility.
    return payload
