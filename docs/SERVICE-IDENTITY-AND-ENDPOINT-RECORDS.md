# Service Identity and Endpoint Records

Status: Implemented schema foundation; Grove resource resolver integrated

## Purpose

Acorn owns durable service resolution state. Mainstay or another runtime context
may provide initial and ongoing endpoint hints, but a wallet must not depend on
that context for every operation and must not treat a supplied URL as an
identity.

The model separates three questions:

```text
Which service is authorized for this keyset?
How can that service normally be reached?
Which route applies inside the current runtime context?
```

The answers are stored in three encrypted, wallet-authored, relay-backed
records:

| Label | Record type | Purpose |
| --- | --- | --- |
| `service_bindings` | `acorn-service-bindings` | Clear keyset ID to mint-service `npub` |
| `service_endpoints` | `acorn-service-endpoints` | Service `npub` to capability-bearing endpoint candidates |
| `context_endpoints` | `acorn-context-endpoints` | Mainstay-qualified endpoint hints |

All three schemas are version 1. Acorn stores them as private kind `37375`
replaceable records using its existing hashed `d` tag and NIP-44 encryption.
The records are signed by the Acorn identity. The labels are reserved and do
not appear as ordinary user records.

The Acorn signature proves ownership and continuity of the wallet's stored
resolution state. It does not make a service binding or descriptor
authoritative. That authority must come from the evidence retained with the
entry and the verification policy applied to it.

## Stable Identities and Mutable Routes

For a Clear Mint Unit, the target resolution chain is:

```text
complete Cashu keyset ID
    -> authorized Clear mint-service npub
    -> service endpoint set
    -> endpoint selected for the active context
```

The keyset ID remains the issuance identity. A service `npub` identifies the
service responsible for that keyset. HTTP, WebSocket, and FIPS locators are
mutable routes.

A service-key rotation therefore changes the service `npub` only when Acorn has
acceptable succession or root-authority evidence. Moving an Acorn between
Mainstay installations changes its applicable context routes without changing
the Clear keyset identity.

## Service Bindings

The `service_bindings` record contains one entry per complete Clear keyset ID:

```json
{
  "type": "acorn-service-bindings",
  "version": 1,
  "bindings": [
    {
      "keyset_id": "01...",
      "unit": "cmu-0011223344556677",
      "service_npub": "npub1...",
      "state": "verified",
      "sequence": 4,
      "updated_at": 1788537600,
      "evidence": {
        "type": "clear-root-service-record",
        "event_id": "4ab3...",
        "issuer_npub": "npub1...",
        "verified_at": 1788537600
      }
    }
  ]
}
```

Binding states are:

- `provisional`: retained as a hint but not yet proven authoritative;
- `verified`: supported by retained evidence; and
- `revoked`: deliberately retained so stale discovery cannot silently restore
  it.

A verified binding requires evidence. Duplicate keyset IDs are rejected.
Clear keysets must use the complete 66-character, `01`-prefixed identifier
emitted by Clear; a shortened fingerprint or URL-resolved alias is not
accepted. Clear units must use their canonical `cmu-` form.

Mainstay can suggest a local keyset binding, but it does not become the Clear
currency root merely by supplying the hint. The future verification step must
check root or service-authority evidence before promotion to `verified`.

## Service Endpoints

The `service_endpoints` record groups endpoint candidates by service `npub`:

```json
{
  "type": "acorn-service-endpoints",
  "version": 1,
  "services": [
    {
      "service_npub": "npub1...",
      "service_type": "clear-mint",
      "capabilities": ["clear.mint", "cashu.swap"],
      "state": "verified",
      "sequence": 7,
      "issued_at": 1788537600,
      "expires_at": 1791129600,
      "endpoints": [
        {
          "endpoint_id": "clear-external",
          "scope": "external",
          "transport": "https",
          "locator": {"url": "https://clear.example"},
          "capabilities": ["clear.mint"],
          "priority": 30
        }
      ],
      "evidence": {
        "type": "service-descriptor",
        "event_id": "7def...",
        "issuer_npub": "npub1...",
        "verified_at": 1788537600
      }
    }
  ]
}
```

Service endpoint states are `provisional`, `verified`, and `revoked`. Verified
sets require evidence. Sequences and validity times allow a later resolver to
reject rollback and expired descriptors. Duplicate service identities and
duplicate endpoint IDs within one service are rejected.

Supported scopes are `internal`, `local`, and `external`. Supported transports
are:

- `http`, requiring an `http://` URL;
- `https`, requiring an `https://` URL;
- `websocket`, requiring a `ws://` or `wss://` URL; and
- `fips-native`, requiring a FIPS node `npub` and port instead of a URL.

URL locators cannot contain credentials, query strings, or fragments. This is
schema validation, not proof that the endpoint is safe or authoritative.

## Context Endpoint Hints

An internal route such as `http://clear:3339` is meaningful only inside a
particular Mainstay installation. The `context_endpoints` record therefore
qualifies every hint by both context and service identity:

```json
{
  "type": "acorn-context-endpoints",
  "version": 1,
  "hints": [
    {
      "context_npub": "npub1mainstay...",
      "service_npub": "npub1clear...",
      "endpoint": {
        "endpoint_id": "clear-internal",
        "scope": "internal",
        "transport": "http",
        "locator": {"url": "http://clear:3339"},
        "capabilities": ["clear.mint"],
        "priority": 10
      },
      "source": "mainstay",
      "source_npub": "npub1mainstay...",
      "state": "candidate",
      "sequence": 2,
      "updated_at": 1788537600
    }
  ]
}
```

Hint states are:

- `candidate`: supplied but not yet promoted;
- `verified`: tested against the expected service identity, keyset, and
  capability; and
- `rejected`: retained to prevent repeated unsafe promotion.

Verified hints require evidence. Duplicate combinations of context `npub`,
service `npub`, and endpoint ID are rejected.

When an Acorn moves context, the later resolver must ignore internal and local
hints belonging to another context. External service descriptors can remain
usable when their validity and evidence still hold.

## Evidence

All three records use the same evidence envelope:

```json
{
  "type": "clear-root-service-record",
  "event_id": "...",
  "issuer_npub": "npub1...",
  "event": {},
  "verified_at": 1788537600
}
```

The complete signed event may be retained in `event` when offline
reverification is required. An evidence entry must contain either `event_id`
or `event`; `event_id` alone is a reference, not proof.
Evidence must never contain an `nsec`, keyset secret, bearer proof, operator
token, or other private service credential.

## Acorn API

Acorn exposes typed read and validated replace operations:

```python
bindings = await acorn.get_service_bindings()
await acorn.publish_service_bindings(bindings)

endpoints = await acorn.get_service_endpoints()
await acorn.publish_service_endpoints(endpoints)

contexts = await acorn.get_context_endpoints()
await acorn.publish_context_endpoints(contexts)
```

Missing records return empty typed version 1 documents. Invalid records fail
closed. Publications request canonical relay readback by default and return the
new relay event ID.

## Update and Resolution Boundary

The Grove resource resolver now selects capability-bearing external HTTPS
routes and active-context HTTP or HTTPS routes for attachment reads and
deletes. Clear mint routing remains outside this generic resolver. The broader
implementation does not yet:

- compare a proposed sequence with the currently stored sequence;
- verify a signed service descriptor or root binding;
- probe a candidate endpoint;
- promote a candidate to verified;
- request a fresh hint from Mainstay; or
- change any payment, Clear receipt, or `known_mints` behavior.

The next resolver implementation should follow this order:

```text
load binding by keyset ID
    -> require acceptable binding state and evidence
    -> load service endpoint set
    -> overlay hints for the active Mainstay context
    -> select by capability, scope, validity, and priority
    -> verify the candidate endpoint
    -> return a short-lived resolved endpoint
```

If no usable route remains, Acorn may ask its current context for a fresh hint.
The hint enters as `candidate`; it must not overwrite a verified route merely
because it is newer or locally convenient.

During migration, `known_mints` can remain a derived compatibility cache from
the resolver. Tokens and proof events must eventually stop writing advertised
URLs directly into it. A token-carried mint URL is provenance and a possible
discovery hint, not authorization for an outbound request.
