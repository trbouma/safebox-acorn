# Acorn Product North Star

## Summary

Acorn is a protocol-first component for user-controlled identity, funds and records.

It is not merely a wallet library, a command-line tool, or the code extracted
from Safebox. Acorn is intended to be a user-controlled protocol component that
gives applications portable identity, encrypted records, relay-backed
availability, value transfer, recovery, and reciprocal resilience across
replaceable infrastructure.

The north star is:

```text
Acorn lets a user carry cryptographic identity, private records, and value
across applications and infrastructure without being trapped by any single app,
service provider, or infrastructure operator.
```

Put another way:

```text
Acorn gives applications a protocol-first way to build user-controlled havens
for identity, funds, records, and recovery.
```

The core value proposition can be summarized as:

```text
reciprocal resilience, protocol-first.
```

Acorn should make it simple for people and communities to help each other stay
recoverable without surrendering secrets to each other or to a central provider.

## Product rationale

People increasingly depend on platforms, services, devices, and applications
to hold the things that matter to them. That convenience often comes with a
hidden cost: protocol identity, records, value, and recovery become
inseparable from a particular provider or product.

The user need is not to reject useful services or become an infrastructure
operator. It is to remain able to change them. A platform may change its terms
or disappear. A service may become unavailable or unaffordable. A device may be
lost, damaged, or replaced. An application may be abandoned, redesigned, or
discontinued. In each case, the user should be able to carry the Acorn
protocol identity, private records, funds, and recovery path to another
compatible environment.

Acorn exists to make that continuity practical. It gives applications a
user-controlled protocol component instead of making the application the sole
owner of the user's system of record. The application can provide the
experience, workflow, support, and service surface; Acorn preserves the
portable protocol state underneath.

This creates a more useful relationship between users and providers:

- users can choose services without being permanently trapped by them;
- trusted operators can provide execution, availability, and support without
  owning the user's keys or plaintext records;
- communities can help maintain continuity across replaceable relays,
  devices, and operators;
- applications can compete on experience while remaining interoperable at the
  protocol layer.

The goal is practical independence, not isolation. Acorn should make it easier
to use dependable services while preserving a credible path to recovery,
migration, and replacement when those services no longer meet the user's
needs.

## What identity means in Acorn

In Acorn, identity does not mean the person. It does not attempt to represent
a person's civil, legal, social, or organizational identity. It means the
protocol identity of an Acorn component or wallet lineage.

That identity is specifically a cryptographic public/private keypair:

```text
private key (`nsec`) -> signing, decryption, and authorization
public key (`npub`)  -> addressing, verification, and encryption to Acorn
seed phrase          -> recovery material from which the keypair can be restored
```

The seed phrase is recovery material, not a separate identity. A running Acorn
instance can be replaced while the same keypair continues the same protocol
identity.

The keypair provides two properties:

- **continuity** — the same Acorn identity can locate, verify, decrypt, and
  continue its protocol state across compatible apps, devices, operators, and
  infrastructure;
- **authority** — control of the private key authorizes signing, decryption,
  record updates, and wallet actions over the controlled objects associated
  with that identity.

This is component-level protocol authority. It does not replace the authority
of a mint to determine Cashu spend state, an issuer to make or revoke a claim,
or a legal framework to determine rights. Acorn controls how its keypair acts
on an object; the object's issuing and validation rules still apply.

Those controlled objects are principally funds and records. The keypair does
not, by itself, prove a person's legal identity, establish real-world title,
or make every claim signed by the key true. Human names, NIP-05 identifiers,
credentials, roles, and legal assertions may be associated with an Acorn
identity through records or external trust frameworks, but they are separate
claims.

A person may control more than one Acorn identity. Several Acorn runtimes may
also operate the same identity when deliberately configured with the same key,
subject to the concurrency and trust boundaries documented elsewhere. The
important continuity is the keypair and its protocol state, not a particular
process, device, application, or provider.

## Language and roots

Acorn's language has become calmer over time. Earlier descriptions leaned more
heavily on terms like radical independence, data havens, and infrastructure
independence. Those ideas helped shape the architecture, but they can also
sound ideological or unnecessarily alarming to people who simply need
dependable tools for identity, funds and records.

The current language is intentionally plainer:

```text
user-controlled identity, funds and records
```

This does not dilute the principles. It makes them easier to evaluate. Acorn is
still rooted in user control, cryptographic continuity, encrypted records,
replaceable infrastructure, reciprocal resilience, and recoverability across
applications. The shift is from provocative language to operational language:
less rhetoric, more dependable component.

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

## Architectural inversion

Acorn inverts the usual architecture for safekeeping user-controlled resources.

In a conventional application model:

```text
application/provider owns the system of record
user accesses an account inside that system
security, recovery, and availability are provider responsibilities
```

In the Acorn model:

```text
user-controlled identity is the continuity and authority layer
funds and records are controllable protocol objects
applications are replaceable interfaces
relays and mints are replaceable infrastructure
communities can support availability without taking custody
trusted operators can provide execution environments and service surfaces
```

The system of record is no longer primarily an application database. It is the
user's signed and encrypted protocol state, anchored by keys and recoverable
through chosen infrastructure.

That inversion explains why Acorn should remain a component rather than a
single product surface. Applications can provide excellent user experience,
workflow, compliance, support, and polish, but they should not become the only
place where the user's identity, funds, records, or recovery path can exist.

This does not require every user to run Acorn personally. A trusted operator is
whoever provides the execution environment or running code for an Acorn
instance. That operator may be the user, a family member, a community, an
employer, a service provider, an appliance, or a product such as Safebox. The
operator may provide web presence, service endpoints, Lightning address
support, hosted relay defaults, monitoring, and support. That is a valid
deployment model when the trust boundary is explicit.

The important distinction is between service operation and architectural
lock-in. An operator-run Acorn instance can make the system easier to use, but
it should still preserve the user's ability to export recovery material,
replicate relay-backed state, change operators, recover through another
compatible surface, or move toward stronger custody such as local hardware or
an HSM-like device.

## Havens for identity, funds and records

Acorn is inspired by the broader idea of a haven: a place or system built to
keep important things available and protected when ordinary devices, accounts,
buildings, providers, or people are unavailable.

Acorn's concrete focus is narrower and more practical: user-controlled
identity, funds and records. It gives applications a way to create havens for
identity, private records, wallet state, and recovery context that can survive
application, provider, relay, mint, and device failure.

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
recoverable enough for ordinary failures;
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

The pattern is closer to older forms of mutual assurance than to centralized
insurance or custodial service provision: participants improve each other's
continuity without pooling control of the underlying assets or records.

This also points to a middle path between cloud/SaaS dependency and
all-or-nothing self-hosting. Acorn should not require every user to become a
full-time infrastructure operator. Instead, it should make community-supported
continuity practical: families, teams, local organizations, professional
communities, or trusted operators can help provide availability while control
remains with the user.

This becomes especially relevant when local infrastructure is disrupted.
Wildfires, floods, earthquakes, storms, power outages, or regional network
disruptions can make a single home, office, provider, or device unavailable.
Acorn's model is intended to keep encrypted state recoverable from
independently operated relays, replicas, and recovery material.

In plain language:

```text
I can help keep you recoverable without holding your secrets.
You can help keep me recoverable without holding mine.
```

The model is reciprocal safes, not a shared folder:

```text
I can host your encrypted Acorn tenant;
you can host mine;
neither of us receives the other's contents.
```

The useful object is the isolated encrypted tenant: the wallet identity, record
namespace, recovery context, and signed event set controlled by the user.

## User-controlled protocol component

A user-controlled protocol component has several properties.

For Acorn, the term means a compartmentalized protocol boundary that gives
applications portable identity, encrypted user-controlled state, recovery, and
migration across replaceable infrastructure.

This is different from an ordinary library or backend module. A library provides
functions. A backend module usually serves one application. A user-controlled
protocol component carries interoperable user state across applications,
relays, mints, devices, and providers.

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

The operational frame is:

```text
keys  -> continuity and authority
code  -> execution environment and trusted operator
data  -> encrypted tenant on relays
mint  -> value and spend-state authority
app   -> user experience and workflows
```

These layers can move and harden independently. For example, data can be
replicated to a community relay, keys can eventually live in protected hardware,
and application code can be replaced without losing the user's protocol state.

### Becoming concrete

The user-controlled protocol component idea becomes concrete when Acorn can
operate against infrastructure that the Safebox project does not control.

Recent live testing has shown that Acorn can use both a third-party Nostr relay
and a third-party Cashu mint while preserving the same user-controlled wallet
model:

- the user's `nsec` remains the continuity boundary;
- wallet state and private records remain relay-backed and encrypted;
- ecash proofs are accepted, refreshed, and stored back into Acorn state;
- transaction history remains visible to compatible application surfaces;
- relay and mint choice remain explicit infrastructure decisions rather than
  application lock-in.

This is the practical difference between an application feature and a
user-controlled protocol component. A feature works inside one product
boundary. A user-controlled protocol component keeps working when the
surrounding relay, mint, app, or deployment operator changes.

### It carries its own identity

Acorn carries a component identity rooted in a cryptographic keypair:

```text
nsec -> private key
npub -> public key
```

The seed phrase can restore the keypair but is not an additional identity.
Applications can use the Acorn identity without creating it, owning it, or
mistaking it for the person operating Acorn. This lets the component retain
continuity and authority when the surrounding application or execution
environment changes.

### It stores data on replaceable infrastructure

Acorn stores encrypted records and wallet metadata as signed Nostr events.

Relays are important, but they are not permanent dependencies. A user should be
able to replicate, verify, and promote a new relay when the current relay
becomes unreliable or adversarial.

### It keeps private data encrypted

Human-readable record labels and payloads are encrypted before publication.
Relays see metadata, but not record contents.

The broader controllable-record model is specified in
[Acorn Record Model](./ACORN-RECORD-MODEL.md). The encryption details are
specified in [Record Encryption Specification](./RECORD-ENCRYPTION-SPEC.md).

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
- reliable in ordinary operation;
- inspectable;
- recoverable;
- scriptable;
- product-neutral;
- small enough to understand;
- strong enough to build on.

The CLI should be calm and explicit. It should avoid surprising side effects,
ask before displaying secrets, and support JSON output where programs need it.

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
- user-controlled infrastructure appliances;
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

Replaceable infrastructure is the design principle. Redundant architecture is
one way to implement it.

In practice, this can mean:

- more than one relay can hold the user's encrypted signed state;
- wallet state can be replicated before a home relay becomes unreliable;
- a new relay can be promoted without changing the user's identity;
- compatible applications can recover from the same user-controlled material;
- alternate deployment paths, including hosted relays, private relays, FreeBSD
  jails, and future appliances, can coexist.

The goal is not redundancy for its own sake. The goal is user continuity. If one
operator, relay, mint, application, or device fails, the user should still have
a practical path to recover, replicate, and keep operating.

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

### Make sensitive operations explicit

Commands that display secrets, repair proofs, migrate relays, or change
infrastructure should be obvious and confirmed.

### Let experience shape the protocol

Acorn should harden from real operating experience. Specs should capture lessons
learned from actual failures, migrations, and edge cases.

## Strategic direction

The near-term goal is to harden the Python Acorn component until it is stable
enough to support Safebox-next as a clean dependency.

The medium-term goal is to make Acorn a reusable user-controlled protocol
component with:

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
