# Acorn Product North Star

## Summary

Acorn is a protocol-first sovereign data haven.

It is not merely a wallet library, a command-line tool, or the code extracted
from Safebox. Acorn is intended to be a sovereign protocol component that gives
applications user-controlled identity, encrypted records, relay-backed
resilience, Cashu value transfer, recovery, and reciprocal resilience across
replaceable infrastructure.

The north star is:

```text
Acorn lets a user carry cryptographic identity, private records, and value
across applications and infrastructure without being trapped by any single app,
relay, mint, or service provider.
```

Put another way:

```text
Acorn is a sovereign protocol component for building protocol-first sovereign
data havens.
```

The core value proposition can be summarized as:

```text
reciprocal resilience, protocol-first.
```

Acorn should make it simple for people and communities to help each other stay
recoverable without surrendering secrets to each other or to a central provider.

## Why Acorn exists

Most applications bind users to infrastructure controlled by the application
operator:

- user accounts live in app databases;
- private data lives in app storage;
- recovery depends on the operator;
- migration is difficult or impossible;
- infrastructure failure becomes user failure.

Acorn takes a different approach. It treats identity, private records, and
wallet state as user-controlled protocol state that applications can use but do
not own.

## Sovereign data haven

Acorn is inspired by the broader idea of a data haven: a place or system built
to keep important data available and protected when ordinary devices, accounts,
buildings, providers, or people are unavailable.

Acorn's version is a sovereign data haven: user-controlled identity, private
records, wallet state, and recovery context that can survive application,
provider, relay, mint, and device failure.

The design is protocol-first and hardware-enabled over time. Acorn should work
as open software before it requires any special appliance. But the same protocol
model should eventually be able to run inside stronger custody environments,
including HSM-like devices, secure elements, confidential-computing enclaves, or
dedicated personal appliances.

In that future, the `nsec` may never need to leave protected hardware. The
hardware can hold the key, perform signing and decryption operations, and expose
only constrained protocol actions to applications.

The result should feel like a protocol-native safe:

```text
encrypted enough for untrusted hosts;
portable enough to move;
recoverable enough to survive boring failures;
structured enough for applications to build on.
```

In this model, a relay operator can host encrypted Acorn data without becoming
the owner of that data. An application can use Acorn records without trapping
the user inside the application. A user can replicate their encrypted state
without turning every copy into a plaintext handoff.

Hardware can strengthen this model, but it should not define it. The protocol
comes first so that recovery, replication, and interoperability are not tied to
one box, vendor, or deployment path.

One Acorn node gives a user's data a home. A community of nodes creates
continuity. A home relay, a private relay, a friend's relay, a community relay,
and a future hardware appliance can all participate in the same encrypted
recovery fabric without becoming shared plaintext storage.

This is reciprocal resilience: people, families, teams, or communities can help
keep each other recoverable without taking custody of each other's plaintext
data.

In plain language:

```text
I can help keep you recoverable without holding your secrets.
You can help keep me recoverable without holding mine.
```

The model is closer to reciprocal safes than to a shared folder:

```text
I can host your encrypted Acorn tenant;
you can host mine;
neither of us receives the other's contents.
```

The useful object is the isolated encrypted tenant: the wallet identity, record
namespace, recovery context, and signed event set controlled by the user.

## Sovereign protocol component

A sovereign protocol component has several properties.

For Acorn, the term means a compartmentalized protocol boundary that gives
applications portable identity, encrypted user-controlled state, recovery, and
migration across replaceable infrastructure.

This is different from an ordinary library or backend module. A library provides
functions. A backend module usually serves one application. A sovereign protocol
component carries interoperable user state across applications, relays, mints,
devices, and providers.

The continuity boundary is the user and their cryptographic material, not the
application operator.

The compartmentalization matters. Acorn should separate:

```text
keys
  nsec, seed phrase, signing authority, future HSM-held secrets

code
  the Acorn implementation and application code that requests protocol actions

data
  encrypted records, proof events, wallet metadata, blobs, and signed events

configuration state
  home relay, public relays, home mint, recovery context, replication policy
```

These layers can move and harden independently. For example, data can be
replicated to a community relay, keys can eventually live in protected hardware,
and application code can be replaced without losing the user's protocol state.

### Becoming concrete

The sovereign protocol component idea becomes concrete when Acorn can operate
against infrastructure that the Safebox project does not control.

Recent live testing has shown that Acorn can use both a third-party Nostr relay
and a third-party Cashu mint while preserving the same user-controlled wallet
model:

- the user's `nsec` remains the continuity boundary;
- wallet state and private records remain relay-backed and encrypted;
- ecash proofs are accepted, refreshed, and stored back into Acorn state;
- transaction history remains visible to compatible application surfaces;
- relay and mint choice remain explicit infrastructure decisions rather than
  application lock-in.

This is the practical difference between an application feature and a sovereign
protocol component. A feature works inside one product boundary. A sovereign
protocol component keeps working when the surrounding relay, mint, app, or
deployment operator changes.

### It carries its own identity

Acorn identity is rooted in user key material:

```text
nsec
npub
seed phrase
```

Applications can use this identity, but they do not need to create it or own it.

### It stores data on replaceable infrastructure

Acorn stores encrypted records and wallet metadata as signed Nostr events.

Relays are important, but they are not permanent dependencies. A user should be
able to replicate, verify, and promote a new relay when the current relay
becomes unreliable or adversarial.

### It keeps private data encrypted

Human-readable record labels and payloads are encrypted before publication.
Relays see metadata, but not record contents.

The record model is specified in
[Record Encryption Specification](./RECORD-ENCRYPTION-SPEC.md).

### It should have a quantum-safe migration path

Acorn should be designed with long-lived records in mind. Private records,
recovery context, and institutional documents may need to remain confidential
for years or decades.

The near-term design should remain conservative and interoperable, using widely
implemented classical cryptography where required by Nostr, Cashu, and existing
wallet tooling. At the same time, Acorn should preserve room for hybrid and
post-quantum cryptography where it can add protection without breaking the
protocol.

The right posture is:

```text
classical compatibility now;
hybrid protection where practical;
post-quantum agility over premature claims.
```

This means Acorn should treat quantum-safe cryptography as a migration and
agility requirement, not as a slogan. Any PQC feature should be versioned,
documented, testable, and optional until there is a stable compatibility story.

### It supports value transfer

Acorn integrates Cashu proofs and Lightning flows so applications can use value
transfer without turning themselves into custodial account systems.

Mints are also replaceable infrastructure. The mint is authoritative for proof
spend state, but it should not become an application lock-in point.

### It can recover from minimal material

Recovery should be understandable and portable:

```text
home_relay
seed_phrase
nsec
```

The recovery model is specified in
[Recovery Specification](./RECOVERY-SPEC.md).

### It can move

Acorn should be able to move between relays in the same spirit that robust
storage systems replicate and promote datasets.

The long-term relay resilience model is specified in
[Relay Resilience and Replication Design](./RELAY-RESILIENCE-AND-REPLICATION-DESIGN.md).

## What Acorn should feel like

Acorn should feel:

- portable;
- boringly reliable;
- inspectable;
- recoverable;
- scriptable;
- product-neutral;
- small enough to understand;
- strong enough to build on.

The CLI should be calm and explicit. It should avoid spooky side effects, ask
before displaying secrets, and support JSON output where programs need it.

The CLI contract is specified in
[CLI Contract](./CLI-CONTRACT.md).

## What Acorn is not

Acorn is not the Safebox web application.

It should not own:

- FastAPI routes;
- templates;
- sessions;
- database migrations;
- product onboarding flows;
- branding;
- appliance deployment;
- MS02 or market-specific trade experiments.

Those belong in applications built on top of Acorn.

The component boundary is specified in
[Acorn Component Boundary Specification](./ACORN-COMPONENT-BOUNDARY.md).

## Applications built on Acorn

Acorn should be useful to multiple application families:

- Safebox-style personal data wallets;
- healthcare record pilots;
- digital trade documentation;
- sovereign infrastructure appliances;
- agent wallets;
- Nostr-native private record systems;
- Cashu-enabled applications.

Each application can define its own workflows and product experience while
delegating core identity, record, relay, and value primitives to Acorn.

## Design commitments

### Keep Acorn product-neutral

Acorn should expose primitives, not product-specific workflows.

### Prefer open protocols

Acorn should build on open, inspectable protocols:

- Nostr;
- Cashu;
- Lightning;
- BIP39;
- NIP-44;
- simple JSON records.

Where quantum-safe cryptography is introduced, Acorn should prefer standardized
or widely reviewed primitives and hybrid designs that preserve compatibility
with existing protocol ecosystems.

### Make infrastructure replaceable

Relays, mints, and application services should be replaceable. A user should not
lose continuity because one provider fails.

### Let users choose their security boundary

Acorn should support practical deployment choices for different sensitivity
levels. For ordinary records, public or hosted relays may be acceptable because
record contents are encrypted. For highly sensitive records, users should be
able to keep relays on infrastructure they control:

- behind firewalls;
- on private networks;
- inside a home or office appliance;
- inside a FreeBSD jail;
- reachable only over VPN, Tor, WireGuard, or Tailscale;
- mirrored across trusted physical locations.

The key idea is user-controlled security. Acorn should not require trust in a
corporate SaaS boundary as the root of safety. Corporate-controlled security can
be useful as a service layer, but it should not be the user's only recovery or
custody path.

### Preserve cryptographic continuity

The user's keys and signed events are the continuity layer. Replication should
preserve event IDs and signatures where possible.

### Make dangerous operations explicit

Commands that display secrets, repair proofs, migrate relays, or change
infrastructure should be obvious and confirmed.

### Let experience shape the protocol

Acorn should harden from real operating experience. Specs should capture lessons
learned from actual failures, migrations, and edge cases.

## Strategic direction

The near-term goal is to harden the Python Acorn component until it is stable
enough to support Safebox-next as a clean dependency.

The medium-term goal is to make Acorn a reusable sovereign protocol component
with:

- stable Python API;
- stable CLI contract;
- documented record format;
- documented recovery model;
- relay migration and replication;
- proof consistency safeguards;
- tests and conformance vectors.

The long-term goal is interoperability: other applications and eventually other
implementations should be able to read, recover, and operate Acorn-compatible
wallets and records.

The hardware-enabled goal is confidential operation: keys can be held in
HSM-like devices or secure execution environments, while Acorn applications
request constrained protocol actions such as signing, decrypting, recovery
export, relay replication, or payment authorization.

## North-star test

When deciding whether a change belongs in Acorn, ask:

```text
Does this make user-controlled identity, records, value, recovery, or relay
resilience more portable across applications and infrastructure?
```

If yes, it may belong in Acorn.

If it only serves one product workflow, it probably belongs in an application
layer.
