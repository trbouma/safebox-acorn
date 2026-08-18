---
title: How Acorn Works
description: A plain-language guide to Acorn keys, controlled funds and records, infrastructure, and recovery.
---

# How Acorn works

Acorn separates a user's portable protocol state from the application used to
access it. The component provides cryptographic key authority, wallet functions,
private records, and recovery mechanics that compatible applications can build
on.

The result is a different relationship between the user and the application:
the application provides the experience, while Acorn provides continuity.

## Acorn is a component

Acorn is not a website, account provider, relay, or mint. It is an installable
software component with a Python interface and command-line interface.

Applications such as Safebox can use Acorn to provide onboarding, workflows,
support, and a polished web experience. A command-line tool, future mobile app,
trusted hosted service, or dedicated appliance can use the same component model.

This matters because the application does not have to become the only place
where the user's state can be understood or recovered.

The same component boundary supports
[Deep Verification](deep-verification.md): Acorn preserves exact Original
Record bytes and digests, while applications and external control layers add
representations, signed evidence, recognition, and verifier policy.

## Keys provide continuity and authority

Acorn safeguards and exercises the cryptographic keys of the component or
wallet lineage.

```text
private key (nsec) -> signing, decryption, and authorization
public key (npub)  -> addressing, verification, and encryption to Acorn
seed phrase        -> recovery material when Acorn generated or derived the wallet key
```

The public/private keypair provides two important properties:

- **Continuity:** another compatible Acorn environment can restore and continue
  the same key authority and protocol state.
- **Authority:** control of the private key authorizes Acorn to sign, decrypt,
  update records, and perform wallet actions.

The keypair is not identity and does not prove someone's civil, legal, social,
or organizational identity. Identity is interpreted outside Acorn. Another
party may associate the public key with a NIP-05 name, kind `0` profile,
Lightning address, credentials, relationships, prior interactions, and its own
understanding of the controller.

Signed events make the key's use verifiable over time, but a signature remains
evidence of authorization—not proof of truth, consciousness, or intent.
Identity is another party's contextual interpretation of the actor behind that
continuity. Trust is its judgment that an intentional actor continues to govern
the key, including any delegated automation, and accepts accountability for its
use.

## Funds and records are controlled objects

Keys supply cryptographic continuity and authority. Funds and records are the
principal objects controlled through them.

<div class="acorn-grid acorn-grid--two" markdown>

<article class="acorn-card" markdown>

### Funds

Acorn can hold Cashu proofs, receive and transfer ecash, interact with Lightning
payments, maintain transaction history, and preserve wallet state on relays.

The mint remains authoritative about whether the ecash it issued is valid,
pending, or spent. Acorn gives the user control of the wallet and its recovery
path; it does not replace the mint's validation rules.

Organization-issued Clear transfers use a separate wallet path. Acorn groups
them by exact mint and CMU, keeps them out of the Cash Balance, and preserves
pending receipts until the user accepts or deletes them.

</article>

<article class="acorn-card" markdown>

### Records

Acorn encrypts private records before publishing them to relays. The user can
write, retrieve, list, replicate, migrate, and request deletion of those
records through compatible Acorn environments.

An issuer may make claims in a record, but control of the Acorn keypair does not
automatically make those claims true or legally binding.

</article>

</div>

## The architecture is separated

Conventional applications often bind keys, code, data, and service operation
into one provider account. Acorn keeps those responsibilities distinct:

```text
keys  -> continuity and authority
code  -> execution environment and trusted operator
data  -> encrypted state stored on relays
mint  -> value issuance and spend-state authority
app   -> experience and workflows
```

These layers cooperate, but they do not all need to be operated by the same
party.

For example, a trusted provider may run Acorn and offer a web interface without
becoming the owner of the user's plaintext records. A community relay may host
encrypted state without receiving the key needed to decrypt it. The key may
eventually live in protected hardware while applications request only
constrained signing or decryption operations.

## Relays provide availability

Acorn stores signed and encrypted protocol state on Nostr relays. A home relay
is the primary location used by a wallet, but it should not become an
irreplaceable dependency.

A user can:

- replicate signed events to another suitable relay;
- verify that the target relay can return the required state;
- promote another relay to become the new home;
- use private or firewalled relays for especially sensitive deployments.

Encryption protects record contents, but it does not make every relay equally
reliable. Acorn tests relay capabilities because retention, indexing, deletion,
availability, and protocol support differ between operators.

## Mints validate value

Cashu proofs are issued by a mint. Acorn can store and operate those proofs, but
the issuing mint determines whether they are valid and spendable.

This creates an explicit trust boundary:

- the Acorn keypair controls access to the wallet's protocol state;
- the user chooses which mint to use;
- proofs remain associated with their issuing mint;
- Acorn checks proof state and provides repair and recovery tools;
- changing applications does not require changing the Acorn keys.

Mint choice is therefore important. Replaceable application infrastructure does
not mean that existing proofs can simply be treated as liabilities of another
mint.

## Applications are replaceable interfaces

The same Acorn keys and compatible state can be operated through
different surfaces:

```text
Safebox web application
Acorn command-line interface
trusted hosted service
future mobile or desktop application
FreeBSD jail or dedicated appliance
```

Each surface may provide a different experience. The continuity boundary is the
keypair and recoverable protocol state, not a particular interface.

## Recovery restores continuity

Practical recovery requires two things:

```text
key material + location of relay-backed state
```

The private key—or the original seed phrase when Acorn generated or derived the
wallet key—restores the Acorn keypair and protocol authority. This includes the 24-word
phrase created from external entropy. An imported `nsec` has no Acorn-generated
seed phrase and must be backed up directly. The home relay tells
the recovered component where to locate its encrypted wallet events. From
there, Acorn can reconstruct the wallet state available on that relay.

Recovery material must be protected carefully. Anyone with the private key or
seed phrase may be able to control the associated wallet and records.

## Reciprocal resilience

Acorn's encrypted state can be hosted by infrastructure chosen by the user,
including infrastructure provided by trusted people, communities, or service
operators.

```text
I can host your encrypted Acorn state.
You can host mine.
Neither of us needs access to the other's contents.
```

This is reciprocal resilience: participants improve each other's continuity
without pooling keys, plaintext data, or custody of the underlying funds and
records.

## What Acorn does not claim

Acorn does not claim that:

- a public key proves who a person is;
- encryption makes every relay trustworthy or available;
- a wallet key replaces a mint's spend-state authority;
- every issued record is valid merely because it is signed;
- infrastructure failure can be eliminated;
- the current developer-stage software is ready for large balances.

Acorn instead provides explicit control, portability, verification, migration,
and recovery paths so that failure of one application or provider does not have
to become permanent loss of continuity.

## Where Acorn stands today

Acorn has demonstrated encrypted private records, Cashu and Lightning flows,
gift-wrapped ecash delivery, wallet recovery, relay replication, and operation
against independently run relays and mints.

It has also demonstrated private kind `7379` Clear transfer receipt from a
public Clear mint, multi-mint Clear balance identity, Safebox Web display, and
durable pending-transfer deletion. Finalization into spendable Clear state and
onward Clear spending remain under development.

Current work is focused on interrupted-transfer recovery, incoming-transfer
idempotency, failure injection, clean async lifecycle handling, package
validation, FreeBSD deployment, and release automation. Acorn should currently
be treated as developer-stage software and used only with small test balances.

[Explore user-controlled keys, funds and records](user-controlled-funds-and-records.md){ .md-button .md-button--primary }
[Explore the user-controlled architecture](user-controlled-architecture.md){ .md-button }
[Return to the Acorn home page](index.md){ .md-button }
[View the source repository](https://github.com/trbouma/safebox-acorn){ .md-button }

## Reference basis

This public explanation is derived from the project's detailed reference
documents. Those documents remain separate from the website content:

- [Acorn Product North Star](https://github.com/trbouma/safebox-acorn/blob/main/docs/ACORN-PRODUCT-NORTH-STAR.md)
- [Acorn Component Boundary](https://github.com/trbouma/safebox-acorn/blob/main/docs/ACORN-COMPONENT-BOUNDARY.md)
- [Acorn Record Model](https://github.com/trbouma/safebox-acorn/blob/main/docs/ACORN-RECORD-MODEL.md)
- [Record Encryption Specification](https://github.com/trbouma/safebox-acorn/blob/main/docs/RECORD-ENCRYPTION-SPEC.md)
- [Recovery Specification](https://github.com/trbouma/safebox-acorn/blob/main/docs/RECOVERY-SPEC.md)
- [Relay Resilience and Replication Design](https://github.com/trbouma/safebox-acorn/blob/main/docs/RELAY-RESILIENCE-AND-REPLICATION-DESIGN.md)
