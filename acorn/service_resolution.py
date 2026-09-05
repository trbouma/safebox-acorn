"""Versioned records for identity-based service endpoint resolution."""

from __future__ import annotations

from typing import Any, Literal
from urllib.parse import urlsplit

from monstr.encrypt import Keys
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SERVICE_BINDINGS_LABEL = "service_bindings"
SERVICE_ENDPOINTS_LABEL = "service_endpoints"
CONTEXT_ENDPOINTS_LABEL = "context_endpoints"
SERVICE_RESOLUTION_RECORD_KIND = 37375


def _validated_npub(value: str) -> str:
    normalized = str(value).strip()
    if not normalized.startswith("npub1"):
        raise ValueError("service identities must use npub encoding")
    try:
        return Keys(pub_k=normalized).public_key_bech32()
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid npub service identity") from exc


def _validated_keyset_id(value: str) -> str:
    normalized = str(value).strip()
    if (
        len(normalized) != 66
        or not normalized.startswith("01")
        or any(character not in "0123456789abcdef" for character in normalized)
    ):
        raise ValueError("Clear keysets require a complete 01-prefixed identifier")
    return normalized


class ResolutionRecordModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResolutionEvidence(ResolutionRecordModel):
    type: str = Field(min_length=1, max_length=120)
    event_id: str | None = Field(default=None, min_length=1, max_length=128)
    issuer_npub: str | None = None
    event: dict[str, Any] | None = None
    verified_at: int | None = Field(default=None, ge=0)

    @field_validator("issuer_npub")
    @classmethod
    def validate_issuer_npub(cls, value: str | None) -> str | None:
        return _validated_npub(value) if value is not None else None

    @model_validator(mode="after")
    def require_event_reference(self) -> ResolutionEvidence:
        if self.event_id is None and self.event is None:
            raise ValueError("resolution evidence requires an event ID or event")
        return self


class ServiceBinding(ResolutionRecordModel):
    keyset_id: str
    unit: str = Field(min_length=5, max_length=260)
    service_npub: str
    state: Literal["provisional", "verified", "revoked"] = "provisional"
    sequence: int = Field(default=0, ge=0)
    updated_at: int = Field(ge=0)
    evidence: ResolutionEvidence | None = None

    @field_validator("keyset_id")
    @classmethod
    def validate_keyset_id(cls, value: str) -> str:
        return _validated_keyset_id(value)

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized.startswith("cmu-"):
            raise ValueError("Clear bindings require a canonical cmu- unit")
        return normalized

    @field_validator("service_npub")
    @classmethod
    def validate_service_npub(cls, value: str) -> str:
        return _validated_npub(value)

    @model_validator(mode="after")
    def require_verified_evidence(self) -> ServiceBinding:
        if self.state == "verified" and self.evidence is None:
            raise ValueError("verified service bindings require evidence")
        return self


class ServiceBindingsRecord(ResolutionRecordModel):
    type: Literal["acorn-service-bindings"] = "acorn-service-bindings"
    version: Literal[1] = 1
    bindings: list[ServiceBinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_duplicate_keysets(self) -> ServiceBindingsRecord:
        keysets = [binding.keyset_id for binding in self.bindings]
        if len(keysets) != len(set(keysets)):
            raise ValueError("service bindings contain a duplicate keyset identifier")
        return self


class ServiceLocator(ResolutionRecordModel):
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    node_npub: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)

    @field_validator("node_npub")
    @classmethod
    def validate_node_npub(cls, value: str | None) -> str | None:
        return _validated_npub(value) if value is not None else None


class ServiceEndpoint(ResolutionRecordModel):
    endpoint_id: str = Field(min_length=1, max_length=120)
    scope: Literal["internal", "local", "external"]
    transport: Literal["http", "https", "websocket", "fips-native"]
    locator: ServiceLocator
    capabilities: list[str] = Field(default_factory=list)
    priority: int = Field(default=100, ge=0, le=65535)

    @field_validator("capabilities")
    @classmethod
    def normalize_capabilities(cls, values: list[str]) -> list[str]:
        normalized = [str(value).strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("endpoint capabilities must not be empty")
        if len(normalized) != len(set(normalized)):
            raise ValueError("endpoint capabilities must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_locator_for_transport(self) -> ServiceEndpoint:
        if self.transport == "fips-native":
            if self.locator.node_npub is None or self.locator.port is None:
                raise ValueError("FIPS endpoints require node_npub and port")
            if self.locator.url is not None:
                raise ValueError("FIPS endpoints must not contain a URL locator")
            return self

        if self.locator.url is None:
            raise ValueError(f"{self.transport} endpoints require a URL locator")
        if self.locator.node_npub is not None or self.locator.port is not None:
            raise ValueError("URL endpoints must not contain FIPS locator fields")
        parsed = urlsplit(self.locator.url)
        expected_schemes = {
            "http": {"http"},
            "https": {"https"},
            "websocket": {"ws", "wss"},
        }[self.transport]
        if parsed.scheme.lower() not in expected_schemes or not parsed.hostname:
            raise ValueError(
                f"{self.transport} endpoint has an incompatible URL locator"
            )
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(
                "endpoint URLs must not contain credentials, queries, or fragments"
            )
        self.locator.url = self.locator.url.rstrip("/")
        return self


class ServiceEndpointSet(ResolutionRecordModel):
    service_npub: str
    service_type: str = Field(min_length=1, max_length=120)
    capabilities: list[str] = Field(default_factory=list)
    state: Literal["provisional", "verified", "revoked"] = "provisional"
    sequence: int = Field(default=0, ge=0)
    issued_at: int = Field(ge=0)
    expires_at: int | None = Field(default=None, ge=0)
    endpoints: list[ServiceEndpoint] = Field(default_factory=list)
    evidence: ResolutionEvidence | None = None

    @field_validator("service_npub")
    @classmethod
    def validate_service_npub(cls, value: str) -> str:
        return _validated_npub(value)

    @field_validator("capabilities")
    @classmethod
    def normalize_capabilities(cls, values: list[str]) -> list[str]:
        normalized = [str(value).strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("service capabilities must not be empty")
        if len(normalized) != len(set(normalized)):
            raise ValueError("service capabilities must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_endpoint_set(self) -> ServiceEndpointSet:
        endpoint_ids = [endpoint.endpoint_id for endpoint in self.endpoints]
        if len(endpoint_ids) != len(set(endpoint_ids)):
            raise ValueError("service endpoint identifiers must be unique")
        if self.expires_at is not None and self.expires_at <= self.issued_at:
            raise ValueError("service endpoint expiry must follow its issue time")
        if self.state == "verified" and self.evidence is None:
            raise ValueError("verified service endpoints require evidence")
        return self


class ServiceEndpointsRecord(ResolutionRecordModel):
    type: Literal["acorn-service-endpoints"] = "acorn-service-endpoints"
    version: Literal[1] = 1
    services: list[ServiceEndpointSet] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_duplicate_services(self) -> ServiceEndpointsRecord:
        identities = [service.service_npub for service in self.services]
        if len(identities) != len(set(identities)):
            raise ValueError("service endpoints contain a duplicate service identity")
        return self


class ContextEndpointHint(ResolutionRecordModel):
    context_npub: str
    service_npub: str
    endpoint: ServiceEndpoint
    source: Literal["mainstay", "operator", "service", "migration"]
    source_npub: str | None = None
    state: Literal["candidate", "verified", "rejected"] = "candidate"
    sequence: int = Field(default=0, ge=0)
    updated_at: int = Field(ge=0)
    expires_at: int | None = Field(default=None, ge=0)
    evidence: ResolutionEvidence | None = None

    @field_validator("context_npub", "service_npub")
    @classmethod
    def validate_identity_npub(cls, value: str) -> str:
        return _validated_npub(value)

    @field_validator("source_npub")
    @classmethod
    def validate_source_npub(cls, value: str | None) -> str | None:
        return _validated_npub(value) if value is not None else None

    @model_validator(mode="after")
    def validate_hint(self) -> ContextEndpointHint:
        if self.expires_at is not None and self.expires_at <= self.updated_at:
            raise ValueError("context endpoint expiry must follow its update time")
        if self.state == "verified" and self.evidence is None:
            raise ValueError("verified context endpoints require evidence")
        return self


class ContextEndpointsRecord(ResolutionRecordModel):
    type: Literal["acorn-context-endpoints"] = "acorn-context-endpoints"
    version: Literal[1] = 1
    hints: list[ContextEndpointHint] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_duplicate_hints(self) -> ContextEndpointsRecord:
        identities = [
            (
                hint.context_npub,
                hint.service_npub,
                hint.endpoint.endpoint_id,
            )
            for hint in self.hints
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("context endpoints contain a duplicate endpoint hint")
        return self
