from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock

import pytest
from monstr.encrypt import Keys
from pydantic import ValidationError

from acorn.acorn import Acorn
from acorn.service_resolution import (
    CONTEXT_ENDPOINTS_LABEL,
    SERVICE_BINDINGS_LABEL,
    SERVICE_ENDPOINTS_LABEL,
    SERVICE_RESOLUTION_RECORD_KIND,
    ContextEndpointHint,
    ContextEndpointsRecord,
    ResolutionEvidence,
    ServiceBinding,
    ServiceBindingsRecord,
    ServiceEndpoint,
    ServiceEndpointSet,
    ServiceEndpointsRecord,
    ServiceLocator,
)


def npub(secret: str) -> str:
    return Keys(priv_k=secret * 32).public_key_bech32()


SERVICE_NPUB = npub("11")
CONTEXT_NPUB = npub("22")
ROOT_NPUB = npub("33")
# Deterministic root keyset produced by Clear's test mint from its root master
# secret and max_order=10 configuration.
CLEAR_ROOT_KEYSET_ID = (
    "0198628b42ed48c81da014c79f23a9e4e0fcf78cb081d84ba2f1cde4fbef7b0425"
)
CLEAR_ROOT_UNIT = "cmu-00270f745c490cf8"


def evidence() -> ResolutionEvidence:
    return ResolutionEvidence(
        type="clear-root-service-record",
        event_id="a" * 64,
        issuer_npub=ROOT_NPUB,
        verified_at=1_788_537_600,
    )


def internal_endpoint() -> ServiceEndpoint:
    return ServiceEndpoint(
        endpoint_id="clear-internal",
        scope="internal",
        transport="http",
        locator=ServiceLocator(url="http://clear:3339/"),
        capabilities=["clear.mint"],
        priority=10,
    )


def wallet() -> Acorn:
    result = object.__new__(Acorn)
    result.logger = logging.getLogger("service-resolution-test")
    result.known_mints = {"cash-keyset": "https://mint.example"}
    return result


def test_service_resolution_schemas_round_trip_all_three_records() -> None:
    binding_record = ServiceBindingsRecord(
        bindings=[
            ServiceBinding(
                keyset_id=CLEAR_ROOT_KEYSET_ID,
                unit=CLEAR_ROOT_UNIT,
                service_npub=SERVICE_NPUB,
                state="verified",
                sequence=4,
                updated_at=1_788_537_600,
                evidence=evidence(),
            )
        ]
    )
    endpoint_record = ServiceEndpointsRecord(
        services=[
            ServiceEndpointSet(
                service_npub=SERVICE_NPUB,
                service_type="clear-mint",
                capabilities=["clear.mint", "cashu.swap"],
                state="verified",
                sequence=7,
                issued_at=1_788_537_600,
                expires_at=1_791_129_600,
                endpoints=[internal_endpoint()],
                evidence=evidence(),
            )
        ]
    )
    context_record = ContextEndpointsRecord(
        hints=[
            ContextEndpointHint(
                context_npub=CONTEXT_NPUB,
                service_npub=SERVICE_NPUB,
                endpoint=internal_endpoint(),
                source="mainstay",
                source_npub=CONTEXT_NPUB,
                state="candidate",
                sequence=2,
                updated_at=1_788_537_600,
            )
        ]
    )

    assert ServiceBindingsRecord.model_validate_json(
        binding_record.model_dump_json()
    ) == binding_record
    assert ServiceEndpointsRecord.model_validate_json(
        endpoint_record.model_dump_json()
    ) == endpoint_record
    assert ContextEndpointsRecord.model_validate_json(
        context_record.model_dump_json()
    ) == context_record
    assert endpoint_record.services[0].endpoints[0].locator.url == (
        "http://clear:3339"
    )


def test_verified_records_require_evidence() -> None:
    with pytest.raises(ValidationError, match="event ID or event"):
        ResolutionEvidence(type="empty-evidence")

    with pytest.raises(ValidationError, match="require evidence"):
        ServiceBinding(
            keyset_id=CLEAR_ROOT_KEYSET_ID,
            unit=CLEAR_ROOT_UNIT,
            service_npub=SERVICE_NPUB,
            state="verified",
            updated_at=1,
        )

    with pytest.raises(ValidationError, match="require evidence"):
        ServiceEndpointSet(
            service_npub=SERVICE_NPUB,
            service_type="clear-mint",
            state="verified",
            issued_at=1,
            endpoints=[internal_endpoint()],
        )

    with pytest.raises(ValidationError, match="require evidence"):
        ContextEndpointHint(
            context_npub=CONTEXT_NPUB,
            service_npub=SERVICE_NPUB,
            endpoint=internal_endpoint(),
            source="mainstay",
            state="verified",
            updated_at=1,
        )


def test_records_reject_duplicate_stable_identities() -> None:
    binding = ServiceBinding(
        keyset_id=CLEAR_ROOT_KEYSET_ID,
        unit=CLEAR_ROOT_UNIT,
        service_npub=SERVICE_NPUB,
        updated_at=1,
    )
    with pytest.raises(ValidationError, match="duplicate keyset"):
        ServiceBindingsRecord(bindings=[binding, binding])

    service = ServiceEndpointSet(
        service_npub=SERVICE_NPUB,
        service_type="clear-mint",
        issued_at=1,
        endpoints=[internal_endpoint()],
    )
    with pytest.raises(ValidationError, match="duplicate service identity"):
        ServiceEndpointsRecord(services=[service, service])


def test_clear_binding_rejects_a_truncated_root_keyset_id() -> None:
    with pytest.raises(ValidationError, match="complete 01-prefixed identifier"):
        ServiceBinding(
            keyset_id=CLEAR_ROOT_KEYSET_ID[:16],
            unit=CLEAR_ROOT_UNIT,
            service_npub=SERVICE_NPUB,
            updated_at=1,
        )


def test_clear_root_keyset_starts_as_a_provisional_service_binding() -> None:
    binding = ServiceBinding(
        keyset_id=CLEAR_ROOT_KEYSET_ID,
        unit=CLEAR_ROOT_UNIT,
        service_npub=SERVICE_NPUB,
        updated_at=1,
    )

    assert binding.keyset_id == CLEAR_ROOT_KEYSET_ID
    assert binding.unit == CLEAR_ROOT_UNIT
    assert binding.state == "provisional"
    assert binding.evidence is None


def test_endpoint_locators_are_transport_specific_and_do_not_allow_credentials() -> None:
    with pytest.raises(ValidationError, match="incompatible URL"):
        ServiceEndpoint(
            endpoint_id="wrong-scheme",
            scope="external",
            transport="https",
            locator=ServiceLocator(url="http://clear.example"),
        )
    with pytest.raises(ValidationError, match="credentials"):
        ServiceEndpoint(
            endpoint_id="credentials",
            scope="external",
            transport="https",
            locator=ServiceLocator(url="https://user:secret@clear.example"),
        )
    fips = ServiceEndpoint(
        endpoint_id="clear-fips",
        scope="external",
        transport="fips-native",
        locator=ServiceLocator(node_npub=SERVICE_NPUB, port=3339),
        capabilities=["clear.mint"],
    )

    assert fips.locator.url is None
    assert fips.locator.node_npub == SERVICE_NPUB


@pytest.mark.asyncio
async def test_service_resolution_records_use_private_relay_storage() -> None:
    acorn = wallet()
    stored: dict[str, str] = {}

    async def set_wallet_info(label, label_info, **kwargs):
        stored[label] = label_info
        assert kwargs["record_kind"] == SERVICE_RESOLUTION_RECORD_KIND
        assert kwargs["verify"] is True
        return {"event_id": "f" * 64}

    async def get_wallet_info(label, **kwargs):
        assert kwargs["record_kind"] == SERVICE_RESOLUTION_RECORD_KIND
        return stored.get(label)

    acorn.set_wallet_info = AsyncMock(side_effect=set_wallet_info)
    acorn.get_wallet_info = AsyncMock(side_effect=get_wallet_info)
    records = [
        (
            acorn.publish_service_bindings,
            acorn.get_service_bindings,
            SERVICE_BINDINGS_LABEL,
            ServiceBindingsRecord(
                bindings=[
                    ServiceBinding(
                        keyset_id=CLEAR_ROOT_KEYSET_ID,
                        unit=CLEAR_ROOT_UNIT,
                        service_npub=SERVICE_NPUB,
                        updated_at=1,
                    )
                ]
            ),
        ),
        (
            acorn.publish_service_endpoints,
            acorn.get_service_endpoints,
            SERVICE_ENDPOINTS_LABEL,
            ServiceEndpointsRecord(
                services=[
                    ServiceEndpointSet(
                        service_npub=SERVICE_NPUB,
                        service_type="clear-mint",
                        issued_at=1,
                        endpoints=[internal_endpoint()],
                    )
                ]
            ),
        ),
        (
            acorn.publish_context_endpoints,
            acorn.get_context_endpoints,
            CONTEXT_ENDPOINTS_LABEL,
            ContextEndpointsRecord(
                hints=[
                    ContextEndpointHint(
                        context_npub=CONTEXT_NPUB,
                        service_npub=SERVICE_NPUB,
                        endpoint=internal_endpoint(),
                        source="mainstay",
                        state="candidate",
                        updated_at=1,
                    )
                ]
            ),
        ),
    ]

    for publish, load, label, record in records:
        published = await publish(record)
        loaded = await load()
        assert loaded == record
        assert json.loads(stored[label]) == record.model_dump(
            mode="json", exclude_none=True
        )
        assert published["relay_event_id"] == "f" * 64
        assert published["verified_write"] is True

    assert acorn.known_mints == {"cash-keyset": "https://mint.example"}


@pytest.mark.asyncio
async def test_missing_resolution_records_return_typed_empty_documents() -> None:
    acorn = wallet()
    acorn.get_wallet_info = AsyncMock(return_value=None)

    assert await acorn.get_service_bindings() == ServiceBindingsRecord()
    assert await acorn.get_service_endpoints() == ServiceEndpointsRecord()
    assert await acorn.get_context_endpoints() == ContextEndpointsRecord()


@pytest.mark.asyncio
async def test_invalid_relay_resolution_record_fails_closed() -> None:
    acorn = wallet()
    acorn.get_wallet_info = AsyncMock(return_value='{"type":"unknown"}')

    with pytest.raises(RuntimeError, match="service_bindings record is invalid"):
        await acorn.get_service_bindings()
