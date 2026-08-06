---
title: Nostr-Native Approach
description: Why Acorn uses Nostr, what the protocol makes possible, and why Nostr-native does not mean Nostr-only.
---

# Nostr-native approach

Acorn uses Nostr as its current protocol foundation because Nostr provides a
small, practical set of building blocks for user-controlled keys and state:
cryptographic keypairs, signed events, extensible event kinds, and a choice of
relays that can store and forward those events.

This is a **Nostr-native** approach, not a claim that Nostr is the only possible
implementation. Nostr is valuable both as working infrastructure and as the
starting point for a broader idea: a digital wallet can be a user-controlled
protocol component rather than an account confined to one application.

## Why Nostr fits Acorn

The basic Nostr protocol is intentionally compact. Its primary object is an
event containing a public key, timestamp, kind, tags, content, identifier, and
signature. Clients publish events to relays and query them using filters.

That model gives Acorn several useful properties:

- **Cryptographic authority travels with the component.** The Acorn keypair,
  rather than an account assigned by a service, signs and decrypts its protocol
  state.
- **Events can be verified independently.** A valid signature remains
  verifiable regardless of which relay returned the event.
- **Events can evidence continuity over time.** A history of events signed by
  the same key can show prior key use, relationships, and protocol actions even
  when storage providers change.
- **Storage is separable from authority.** A relay can store encrypted,
  signed state without possessing the private key that controls it.
- **The same event can have more than one home.** Signed events can be copied to
  other suitable relays without changing their event IDs or authorship.
- **Event meanings can evolve.** Kinds and tags provide an extensible envelope
  for wallet state, private records, delivery messages, and future controlled
  objects.
- **Replaceable and addressable events support current state.** The protocol
  defines event ranges whose newer versions supersede earlier versions, which
  is useful when state must change over time.

These capabilities are part of the
[Nostr base protocol, NIP-01](https://github.com/nostr-protocol/nips/blob/master/01.md).
Acorn combines them into a component model for keys, funds, records,
recovery, replication, and migration.

## What it changes

Acorn is not simply replacing a conventional API with WebSockets. It changes
where continuity and authority reside.

| Conventional account-centric service | Acorn's Nostr-native model |
| --- | --- |
| The provider assigns and administers the account. | The Acorn keypair supplies a protocol identifier and cryptographic authority. |
| The provider's database is the primary source of state. | Signed events remain attributable and verifiable outside one database. |
| The service endpoint and storage layer are usually fixed together. | Clients can use, test, replicate to, and migrate among suitable relays. |
| Export and migration are application features. | Portability and relay choice are architectural concerns. |
| The provider normally sees and structures stored data. | Sensitive content can be encrypted before it reaches relay storage. |
| A wallet is often treated as a product or account. | A wallet can be an installable component used by several products and environments. |

This does not make every dependency disappear. Relays still have different
retention, indexing, deletion, access, and availability policies. Mints remain
authoritative about the validity and spend state of the ecash they issue. An
application or trusted provider still operates the code and supplies the user
experience.

The difference is that these responsibilities are explicit and separable.

## Private records and private delivery

Nostr events are public structures unless an application encrypts their
contents. Acorn encrypts private record content before publishing it, using
Nostr-compatible cryptographic conventions.

[NIP-44](https://github.com/nostr-protocol/nips/blob/master/44.md) defines a
versioned encrypted-payload scheme. For private delivery, including ecash
transfers, Acorn uses the
[NIP-59](https://github.com/nostr-protocol/nips/blob/master/59.md) gift-wrap
pattern. Gift wrapping encrypts the intended event through nested layers and
publishes the outer event under a temporary key, reducing the sender and
recipient metadata exposed by the delivery event.

Encryption is an important boundary, not a complete privacy claim. Relay
operators and network observers may still learn timing, connection, volume,
and other metadata. Especially sensitive deployments may use private or
firewalled relays in addition to application-layer encryption.

## From social protocol to component protocol

Nostr is widely encountered through social applications, but its underlying
model is more general: keys create authority, signed events carry assertions,
and relays provide replaceable transport and storage.

Working with those primitives gave genesis to a broader Acorn model. What is
normally called a *digital wallet* can be understood as a user-controlled
component that carries:

```text
keys               -> continuity and authority
funds              -> controllable value issued by mints
records            -> encrypted or issued controlled objects
recovery context   -> the material and locations needed to continue
```

In this model, a wallet is not limited to a payment interface on one device. It
can operate inside a web application, command-line tool, trusted hosted
service, FreeBSD jail, dedicated appliance, or future hardware-backed system.
The surrounding experience can change while the component keys and
recoverable state continue.

## Signatures are evidence, not intent

Nostr makes key authority and signed history unusually visible, but it does not
collapse identity or trust into cryptography. A valid event signature proves
that a key authorized the event bytes. It does not prove that the event content
is true, that its declared timestamp is independently established, or that a
conscious actor personally intended the action.

Identity is interpreted when a counterparty associates a key and its signed
history with a person, organization, role, or component in context. Trust is the
further decision to rely on the belief that an intentional actor continues to
govern that key and accepts accountability for its use. Automated clients and
AI agents can use delegated keys, but the trust question remains who authorized,
bounded, supervised, and can revoke that delegation.

This distinction is essential to Acorn's protocol-first model: Nostr preserves
portable evidence, while people, communities, institutions, and legal systems
decide what that evidence means.

## Nostr-native does not mean Nostr-only

Acorn should not become dependent on protocol branding for its architectural
integrity. Another implementation could express the same component model if it
preserved the properties Acorn depends on:

- user-controlled cryptographic keys;
- independently verifiable signed state;
- encryption before untrusted storage;
- more than one compatible storage or transport operator;
- recoverable and portable protocol state;
- stable semantics for funds, records, and their control; and
- practical ways to replicate, migrate, and verify that state.

A signed replicated log, content-addressed system, or purpose-built protocol
might meet those requirements. Nostr is Acorn's present implementation and
interoperability foundation because it already joins these properties in a
simple, open event-and-relay model.

The enduring idea is not that every system must use Nostr. It is that users
should be able to retain continuity and authority while applications,
operators, devices, and infrastructure change.

## Boundaries that remain

A Nostr-native design does not mean that:

- a public key proves the civil or legal identity of a person;
- a signature proves that every claim in a record is true;
- a signature proves consciousness, contemporaneous intent, or uncompromised
  key custody;
- encryption eliminates metadata exposure;
- every relay is suitable for wallet state;
- a relay validates whether ecash is spendable;
- replication replaces careful key backup and recovery; or
- protocol portability removes the need to trust running code.

Acorn treats these limits as design boundaries. It tests relay capabilities,
keeps mint authority distinct from wallet control, separates cryptographic keys
from external identity claims, and makes recovery part of the protocol model
rather than an afterthought.

[Continue to recovery and continuity](recovery-and-continuity.md){ .md-button .md-button--primary }
[Explore the user-controlled architecture](user-controlled-architecture.md){ .md-button }
[Return to How Acorn Works](how-acorn-works.md){ .md-button }
[View the source repository](https://github.com/trbouma/safebox-acorn){ .md-button }

## Reference basis

- [NIP-01: Basic protocol flow](https://github.com/nostr-protocol/nips/blob/master/01.md)
- [NIP-44: Versioned encryption](https://github.com/nostr-protocol/nips/blob/master/44.md)
- [NIP-59: Gift wrap](https://github.com/nostr-protocol/nips/blob/master/59.md)
- [Acorn Product North Star](https://github.com/trbouma/safebox-acorn/blob/main/docs/ACORN-PRODUCT-NORTH-STAR.md)
- [Acorn Component Boundary](https://github.com/trbouma/safebox-acorn/blob/main/docs/ACORN-COMPONENT-BOUNDARY.md)
- [Acorn Record Model](https://github.com/trbouma/safebox-acorn/blob/main/docs/ACORN-RECORD-MODEL.md)
- [Relay Resilience and Replication Design](https://github.com/trbouma/safebox-acorn/blob/main/docs/RELAY-RESILIENCE-AND-REPLICATION-DESIGN.md)
