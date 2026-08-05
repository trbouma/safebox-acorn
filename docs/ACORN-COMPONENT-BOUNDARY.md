# Acorn Component Boundary Specification

## Summary

Acorn is a protocol-first component for safeguarding user-controlled keys,
funds and records, extracted from Safebox as a standalone component. It should
remain small, installable, and product-neutral. Safebox and other applications
may depend on Acorn, but Acorn should not depend on Safebox application concepts.

This specification defines what belongs in Acorn, what does not, and how future
features should be evaluated before they are added.

## Goals

- Keep Acorn installable as an independent Python package.
- Provide a stable Python API and CLI for key, wallet, record, relay, and
  payment operations.
- Avoid leaking Safebox web-app concerns into the component.
- Make Acorn reusable by future applications, including Safebox-next.
- Keep experimental side projects out of the core component until they become
  broadly reusable primitives.

## Acorn owns

Acorn is responsible for the generic capabilities needed by user-controlled
applications built on Nostr, Cashu, and encrypted records.

## Compartmentalization model

Acorn is not only reusable code. It is a protocol boundary that separates keys,
code, data, and configuration state.

```text
keys
  nsec, seed phrase, signing authority, future HSM-held secrets

code
  Acorn implementation code and application code that calls it

data
  encrypted records, proof events, wallet metadata, blobs, signed events

configuration state
  home relay, public relays, home mint, recovery context, replication policy
```

In deployment terms:

```text
keys  -> continuity and authority
code  -> execution environment and trusted operator
data  -> encrypted tenant on relays
mint  -> value and spend-state authority
app   -> user experience and workflows
```

This separation is central to the component boundary:

- applications can be replaced without losing user state;
- relays can be replaced without changing the Acorn keypair or authority;
- sensitive keys can eventually move into stronger custody environments;
- configuration can move from plaintext local files into encrypted reserved
  records where appropriate;
- data can be replicated without handing hosts plaintext access.

This follows the architectural inversion described in
[Acorn Product North Star](./ACORN-PRODUCT-NORTH-STAR.md): applications should
be replaceable interfaces over user-controlled protocol state, not the only
system of record for the user's keys, funds, records, or recovery path.

### Keys, identifiers, and identity

Acorn holds and uses a Nostr public/private keypair. The public key provides a
stable protocol identifier and address; control of the private key provides
signing, decryption, and authorization over associated funds and records. The
keypair is therefore a continuity and authority mechanism, not identity itself.

Identity is interpreted outside Acorn. A counterparty may associate the public
key with a NIP-05 name, kind `0` profile, Lightning address, credential,
relationship, legal record, or prior interaction. Identity may be an amalgam of
several such claims and of what the counterparty recognizes about the
controller. Acorn can sign, store, retrieve, or resolve some of that material;
it does not turn the key or any single claim into the identity of a person.

The keypair and its authority can continue across replacement processes,
devices, applications, and operators. A seed phrase is recovery material for
the keypair. NIP-05 names, profiles, credentials, and real-world identity
assertions remain separate records, claims, and external interpretations.

Acorn owns:

- Nostr private/public key handling.
- `nsec`-based wallet initialization.
- seed phrase recovery support.
- deterministic wallet handles and access-key derivation where needed by core
  wallet behavior.

### Relay-backed wallet data

Acorn owns:

- the home relay concept;
- encrypted wallet metadata;
- encrypted private records;
- reserved encrypted records used by the component itself;
- relay query/publish helpers needed by the component.

### Encrypted records

Acorn owns:

- private record writes;
- private record reads;
- deterministic private lookup tags;
- label-only listing;
- JSON and human output for records;
- optional encrypted blob metadata and transfer support.

The record encryption model is specified separately in
[Record Encryption Specification](./RECORD-ENCRYPTION-SPEC.md).

### Cashu and Lightning wallet flows

Acorn owns:

- proof loading and storage;
- balance reporting;
- deposit invoice creation and confirmation;
- token issuance and acceptance;
- paying Lightning invoices through Cashu melt;
- proof repair and consolidation primitives.

### Generic Nostr interactions

Acorn may own generic Nostr primitives when they are not product-specific:

- profile publish/read helpers;
- text notes;
- replies and reactions;
- follows;
- direct messages;
- zaps and zap discovery.

## Acorn does not own

Acorn should not contain application-specific, product-specific, or experimental
side-project logic.

### Safebox web application

The following belong in the Safebox application, not Acorn:

- FastAPI routers;
- templates and static assets;
- sessions and cookies;
- database models and migrations;
- user onboarding flows;
- branding;
- appliance, jail, or deployment orchestration;
- web-specific admin or support workflows.

Safebox Web currently applies this separation through a server-rendered
hypermedia interface. The browser follows links and submits forms; FastAPI owns
HTTP validation, sessions, CSRF, and representations; Acorn owns key, fund,
record, mint, and relay behavior. This is an application of the component
boundary, not a requirement that every Acorn client use FastAPI or HTML. See
[Safebox App Boundary](SAFEBOX-APP-BOUNDARY.md) for the fuller allocation of
browser, application, component, and infrastructure responsibilities.

### MS02 / market / digital trade side project

The MS02 market and digital trade experiment is intentionally outside Acorn.
Acorn must not expose market-specific APIs such as:

- market order creation;
- MS02 ask parsing;
- entitlement encryption/decryption;
- wrapper-secret delivery;
- token-secret commitment verification;
- market follow-list discovery.

Those belong in a separate application or package if they are continued.

### Product-specific record schemas

Acorn may store generic private records, but it should not own specific product
schemas such as healthcare, identity, trade, or credential workflows unless they
are expressed as generic record primitives.

Applications can define their own record conventions on top of Acorn.

## Public API expectations

The preferred downstream use is:

```python
from acorn import Acorn
```

Applications may also import documented support modules:

```python
from acorn.models import SafeboxRecord
from acorn.func_utils import get_profile_for_pub_hex
from acorn.monstrmore import ExtendedNIP44Encrypt
```

Over time, these imports should be documented and narrowed so applications rely
on a deliberate contract rather than implementation details.

## CLI expectations

The `acorn` CLI is part of the component boundary. It should remain useful for:

- standalone wallet operation;
- smoke testing installs;
- development and diagnostics;
- simple scripting via JSON output.

The CLI should not become the Safebox application UI.

## Integration guidance for Safebox-next

A future Safebox application should consume Acorn as a dependency rather than
copying its source into the Safebox tree.

Recommended architecture:

```text
safebox-acorn
  installable component

safebox-next
  FastAPI/web application depending on safebox-acorn

safebox-2
  legacy/reference implementation
```

Safebox-next should call Acorn through stable methods rather than reaching into
private state where possible.

## Feature admission test

Before adding a feature to Acorn, ask:

1. Is this useful outside the Safebox web app?
2. Is this a generic wallet, relay, record, payment, or Nostr primitive?
3. Can another application use it without importing Safebox concepts?
4. Does it avoid hard-coding a product workflow?
5. Can it be documented as part of the component contract?

If the answer is no, the feature probably belongs in an application layer.
