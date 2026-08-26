"""Cashu NUT-18 payment-request encoding and validation."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import cbor2


PAYMENT_REQUEST_PREFIX = "creqA"
MAX_PAYMENT_REQUEST_BYTES = 16_384


class PaymentRequestError(ValueError):
    """The supplied NUT-18 request is malformed or unsupported."""


@dataclass(frozen=True)
class PaymentRequestTransport:
    transport_type: str
    target: str
    tags: tuple[tuple[str, ...], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"t": self.transport_type, "a": self.target}
        if self.tags:
            result["g"] = [list(tag) for tag in self.tags]
        return result


@dataclass(frozen=True)
class PaymentRequest:
    payment_id: str | None = None
    amount: int | None = None
    unit: str | None = None
    single_use: bool | None = None
    mints: tuple[str, ...] = ()
    mint_list_preferred: bool | None = None
    description: str | None = None
    transports: tuple[PaymentRequestTransport, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.payment_id is not None:
            result["i"] = self.payment_id
        if self.amount is not None:
            result["a"] = self.amount
        if self.unit is not None:
            result["u"] = self.unit
        if self.single_use is not None:
            result["s"] = self.single_use
        if self.mints:
            result["m"] = list(self.mints)
        if self.mint_list_preferred is not None:
            result["mp"] = self.mint_list_preferred
        if self.description is not None:
            result["d"] = self.description
        if self.transports:
            result["t"] = [transport.to_dict() for transport in self.transports]
        return result


def _short_text(value: Any, *, field: str, maximum: int) -> str:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > maximum:
        raise PaymentRequestError(f"NUT-18 {field} is missing or too long")
    return normalized


def _parse_tags(raw_tags: Any) -> tuple[tuple[str, ...], ...]:
    if raw_tags is None:
        return ()
    if not isinstance(raw_tags, list):
        raise PaymentRequestError("NUT-18 transport tags must be an array")
    tags: list[tuple[str, ...]] = []
    for raw_tag in raw_tags:
        if not isinstance(raw_tag, list) or len(raw_tag) < 2:
            raise PaymentRequestError("NUT-18 transport tags must contain a name and value")
        tag = tuple(_short_text(item, field="transport tag", maximum=256) for item in raw_tag)
        tags.append(tag)
    return tuple(tags)


def payment_request_from_dict(payload: dict[str, Any]) -> PaymentRequest:
    if not isinstance(payload, dict):
        raise PaymentRequestError("NUT-18 payment request must be a CBOR map")

    amount = payload.get("a")
    if amount is not None:
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise PaymentRequestError("NUT-18 amount must be a positive integer")

    unit = payload.get("u")
    if amount is not None and unit is None:
        raise PaymentRequestError("NUT-18 unit is required when amount is set")
    normalized_unit = (
        _short_text(unit, field="unit", maximum=128) if unit is not None else None
    )

    raw_mints = payload.get("m") or []
    if not isinstance(raw_mints, list):
        raise PaymentRequestError("NUT-18 mint list must be an array")
    mints = tuple(
        _short_text(mint, field="mint", maximum=2048).rstrip("/")
        for mint in raw_mints
    )

    raw_transports = payload.get("t") or []
    if not isinstance(raw_transports, list):
        raise PaymentRequestError("NUT-18 transports must be an array")
    transports: list[PaymentRequestTransport] = []
    for raw_transport in raw_transports:
        if not isinstance(raw_transport, dict):
            raise PaymentRequestError("NUT-18 transport must be a map")
        transports.append(
            PaymentRequestTransport(
                transport_type=_short_text(
                    raw_transport.get("t"), field="transport type", maximum=32
                ),
                target=_short_text(
                    raw_transport.get("a"), field="transport target", maximum=4096
                ),
                tags=_parse_tags(raw_transport.get("g")),
            )
        )

    payment_id = payload.get("i")
    description = payload.get("d")
    single_use = payload.get("s")
    mint_list_preferred = payload.get("mp")
    if single_use is not None and not isinstance(single_use, bool):
        raise PaymentRequestError("NUT-18 single-use flag must be boolean")
    if mint_list_preferred is not None and not isinstance(mint_list_preferred, bool):
        raise PaymentRequestError("NUT-18 mint preference flag must be boolean")

    return PaymentRequest(
        payment_id=(
            _short_text(payment_id, field="payment id", maximum=128)
            if payment_id is not None
            else None
        ),
        amount=amount,
        unit=normalized_unit,
        single_use=single_use,
        mints=mints,
        mint_list_preferred=mint_list_preferred,
        description=(
            _short_text(description, field="description", maximum=512)
            if description is not None
            else None
        ),
        transports=tuple(transports),
    )


def encode_payment_request(request: PaymentRequest) -> str:
    validated = payment_request_from_dict(request.to_dict())
    encoded = base64.urlsafe_b64encode(
        cbor2.dumps(validated.to_dict(), canonical=True)
    ).decode("ascii")
    return PAYMENT_REQUEST_PREFIX + encoded


def decode_payment_request(encoded: str) -> PaymentRequest:
    request = str(encoded or "").strip()
    if not request.startswith(PAYMENT_REQUEST_PREFIX):
        raise PaymentRequestError("NUT-18 payment request must begin with creqA")
    body = request[len(PAYMENT_REQUEST_PREFIX) :]
    if not body or len(body) > MAX_PAYMENT_REQUEST_BYTES:
        raise PaymentRequestError("NUT-18 payment request is empty or oversized")
    body += "=" * (-len(body) % 4)
    try:
        raw = base64.b64decode(body, altchars=b"-_", validate=True)
        payload = cbor2.loads(raw)
    except Exception as exc:
        raise PaymentRequestError("NUT-18 payment request is not valid CBOR") from exc
    return payment_request_from_dict(payload)


def nostr_nip17_transport(nprofile: str) -> PaymentRequestTransport:
    target = _short_text(nprofile, field="Nostr transport target", maximum=4096)
    if not target.startswith("nprofile1"):
        raise PaymentRequestError("NUT-18 Nostr transport target must be an nprofile")
    return PaymentRequestTransport("nostr", target, (("n", "17"),))
