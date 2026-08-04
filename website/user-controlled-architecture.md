---
title: User-Controlled Architecture
description: How Acorn reverses the conventional relationship between users, applications, keys, funds, records, and infrastructure.
---

# User-controlled architecture

Most digital services place the application and its operator at the centre of
the model. The provider creates the account, stores the records, maintains the
balance, controls recovery, and decides which interfaces may access the system.
The user receives permission to use an account inside it.

Acorn starts from the opposite direction. A user-controlled component safeguards
cryptographic keys, funds, records, and recovery context. Applications and
providers can offer useful services around that component without becoming the
only place where its continuity can exist.

This produces an architectural inversion:

```text
conventional model: provider system -> account -> user access
Acorn model:        user-controlled component -> chosen services and infrastructure
```

The objective is not to remove service providers. It is to change the
relationship so that using a service does not automatically mean becoming
permanently dependent on it.

## The conventional centre of gravity

In a conventional application, account identifiers, data, permissions, and recovery are
usually records in the provider's database:

```text
provider account
├── login and account profile
├── application balance
├── private records
├── permissions
└── recovery process
```

This arrangement is efficient and familiar, but it concentrates continuity in
one administrative system. If the application closes, changes its terms,
loses data, disables an account, or stops supporting an export format, the
user's practical ability to continue may disappear with it.

Backups can protect the provider. Data exports can help the user. Neither, by
itself, makes another application capable of continuing the same key authority and
protocol state.

## Acorn moves continuity to the component

Acorn separates the responsibilities that are often bundled inside one
account:

```text
keys        -> Acorn keypair provides continuity and authority
funds       -> wallet controls proofs; mint validates spend state
records     -> encrypted protocol state; issuers remain authoritative for claims
application -> experience, workflows, policy, and support
operator    -> trusted execution environment for the running code
relay       -> availability for signed and encrypted events
recovery    -> key material plus the location of relay-backed state
```

The user does not have to operate every layer. A trusted provider can run the
code, a community can operate relays, and a mint can issue value. The inversion
comes from keeping those roles distinct and preserving a credible path to move
between compatible applications and operators.

## An Acorn wallet is a component with its own cryptographic keys

Conventional services normally assign an internal user identifier and decide
how the account is authenticated and recovered. Other applications cannot
continue that account unless the provider permits it.

An Acorn wallet instead has a user-controlled public/private keypair. The keys
provide protocol continuity and cryptographic authority over funds and records.
They are not the identity of the user or an identity contained by the
component.

Identity is formed outside Acorn. A person or organization may be associated
with the public key through a NIP-05 name, kind `0` profile, Lightning address,
credential, attestation, legal claim, social relationship, prior interaction,
or some combination of them. Ultimately, a counterparty decides what those
signals mean and whom it believes controls the key.

```text
private key -> signing, decryption, and authorization
public key  -> addressing, verification, and encryption to Acorn
seed phrase -> recovery material when Acorn generated or derived the wallet key
```

The keypair allows another compatible Acorn environment to continue the same
cryptographic authority and protocol state. Control of the private key authorizes signing, decryption,
record updates, and wallet actions, subject to the separate authority of mints,
record issuers, and applicable legal frameworks. The inversion is therefore
precise: the provider no longer has to be the sole source of continuity or
authority.

## Funds: from provider balance to controlled value

Many applications represent funds as a number in an application database. The
operator owns the ledger interface, determines account access, and provides the
only supported path for moving the value.

Acorn holds ecash proofs as controllable records. The wallet can receive,
store, transfer, recover, and present those proofs through compatible Acorn
environments. The application displaying the balance is not itself the wallet's
continuity boundary.

This does not eliminate the issuer. The mint remains authoritative about
whether its proofs are valid, pending, or spent. Existing proofs are liabilities
of their issuing mint and cannot simply be reassigned to another mint.

The inversion is not “trust nobody.” It is:

```text
the wallet controls how it holds and uses the proofs;
the mint controls the validity and spend state of what it issued;
the application provides an interface to both.
```

## Records: from database custody to encrypted protocol state

In the conventional model, private records are usually readable database rows
inside the application provider's infrastructure. Access control protects those
rows, but the provider remains the central custodian and often the only party
able to interpret, export, or restore them.

Acorn encrypts private record content before publishing it to relay
infrastructure. The Acorn tenant retains the key needed to decrypt its records,
while a relay can provide availability without receiving plaintext access.
Signed events can be replicated to another suitable relay without changing
their authorship.

An issuer may still be authoritative for a record's claims. Holding or
decrypting a healthcare record, credential, or trade document does not make its
contents true. Acorn separates holder control from issuer authenticity and from
the legal meaning assigned by an external framework.

## A reversal of roles

| Conventional service model | Acorn component model |
| --- | --- |
| The application account is the continuity boundary. | The keypair and recoverable protocol state are the continuity boundary. |
| The provider's database is the primary system of record. | Signed and encrypted protocol events carry portable state. |
| The provider normally holds readable records. | Records can be encrypted before relay storage. |
| Recovery restores access to the provider account. | Recovery can restore the component in another compatible environment. |
| Infrastructure migration is an operator concern. | Relay replication and migration are also user-continuity concerns. |
| Applications compete by retaining accounts and data. | Applications can compete on experience over interoperable state. |
| Community hosting implies shared custody or shared files. | Communities can host isolated encrypted tenants for one another. |

The result is closer to reciprocal safes than a shared folder. Participants can
help keep one another's encrypted state available without pooling keys,
plaintext records, or control of funds.

## Services remain valuable

Architectural inversion is not an argument that everyone should self-host.
Most people will reasonably prefer a trusted provider to run software, monitor
infrastructure, offer support, provide a web presence, and integrate payment or
identity services.

A Safebox provider, for example, can operate Acorn as a private component on
the user's behalf. The provider supplies the execution environment and user
experience. The design remains user-controlled when recovery material,
portable state, and compatible alternatives provide a practical way to leave
or recover if that provider is no longer available.

This creates a middle path between complete SaaS dependence and demanding that
every person become an infrastructure specialist:

```text
dependable services when they work;
portable continuity when they do not.
```

## What the inversion enables

When the model works as intended, a user can:

- replace an application without creating new keys or abandoning existing protocol state;
- recover through another compatible environment after losing a device;
- replicate encrypted state before a relay becomes unavailable;
- change the trusted operator that runs the component;
- use public, community, private, or firewalled relay infrastructure;
- retain private records without making every storage host a plaintext
  custodian; and
- receive services without making one provider the permanent owner of
  continuity.

These are not automatic guarantees. They require careful key handling,
compatible implementations, suitable relays, sound recovery procedures, and
clear mint and issuer boundaries. Acorn's purpose is to make those paths part
of the architecture rather than emergency features added after lock-in has
already occurred.

[Explore the Nostr-native approach](nostr-native-approach.md){ .md-button .md-button--primary }
[Explore user-controlled keys, funds and records](user-controlled-funds-and-records.md){ .md-button }
[Return to How Acorn Works](how-acorn-works.md){ .md-button }
[View the source repository](https://github.com/trbouma/safebox-acorn){ .md-button }

## Reference basis

- [Acorn Product North Star](https://github.com/trbouma/safebox-acorn/blob/main/docs/ACORN-PRODUCT-NORTH-STAR.md)
- [Acorn Component Boundary](https://github.com/trbouma/safebox-acorn/blob/main/docs/ACORN-COMPONENT-BOUNDARY.md)
- [Acorn Record Model](https://github.com/trbouma/safebox-acorn/blob/main/docs/ACORN-RECORD-MODEL.md)
- [Recovery Specification](https://github.com/trbouma/safebox-acorn/blob/main/docs/RECOVERY-SPEC.md)
- [Relay Resilience and Replication Design](https://github.com/trbouma/safebox-acorn/blob/main/docs/RELAY-RESILIENCE-AND-REPLICATION-DESIGN.md)
