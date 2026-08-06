---
title: A Better Vocabulary for Digital Policy
description: Why keys, funds and records provide a clearer policy starting point than identity, credentials and wallets alone.
---

# A better vocabulary for digital policy

Digital policy is increasingly organized around three familiar ideas:
**digital identity**, **digital credentials**, and **digital wallets**. Each
describes important work. Together, however, they do not describe the full set
of resources that people and applications need to safeguard and control.

Acorn starts with a more direct vocabulary:

```text
keys, funds and records
```

This is not a proposal to discard identity systems, credential standards, or
wallet applications. It is a way to put each in its proper place—and to make
the missing questions visible.

## The vocabulary problem

The word **wallet** is commonly used for both a container and everything the
container manages. That makes it difficult to distinguish the application from
the resources that must survive when the application, device, or provider is
replaced.

The word **credential** is sometimes extended to cover nearly every important
digital object. Credentials are valuable, but they are a specialized kind of
record: typically a set of claims made by an issuer and presented by a holder
to a verifier. Private notes, configuration, transaction histories, files,
mutable state, and transferable instruments do not all fit that lifecycle.

The phrase **digital identity** can similarly become overloaded. A
cryptographic key or identifier may anchor an identity claim, but neither is a
person. Identity is interpreted from evidence and context that can include
names, profiles, credentials, legal records, relationships, and prior
interactions.

Finally, **digital payments** describe transactions and payment rails, but not
necessarily the funds being held. Safeguarding value also requires balance
integrity, spend authority, settlement, fees, reconciliation, recovery, and a
credible way to change providers.

## Three distinctions that matter

<div class="acorn-grid" markdown>

<article class="acorn-card" markdown>

### Keys are not identity

Keys provide cryptographic continuity and authority. They can sign, decrypt,
address, and authorize operations. They can contribute evidence to an identity
judgment, but they do not define the person, organization, or role behind that
judgment.

</article>

<article class="acorn-card" markdown>

### Credentials are records

A credential is a typed record with particular rules for issuance,
presentation, verification, privacy, and status. Treating it as a record
profile preserves those rules without forcing every digital object into a
credential-shaped model.

</article>

<article class="acorn-card" markdown>

### Wallets are implementations

A wallet may be software, a hosted service, a device, or hardware. It is an
execution and safekeeping environment—not the conceptual owner of the keys,
funds, and records it operates upon.

</article>

</div>

## From keys to identity and trust

A clearer chain is:

```text
keys          -> cryptographic authority
signed events -> verifiable continuity and evidence over time
identity      -> an interpretation of the actor behind that continuity
trust         -> reliance on intentional control and accountability over time
```

A signature proves that a key authorized exact event bytes. It does not prove
that the event is true or that a conscious actor personally intended it. A
history of signed events can strengthen continuity and provide evidence of
prior conduct, but it remains evidence of key use.

Trust arises when another party believes that the key remains governed by an
intentional actor—a person, or people acting through an organization—and that
the actor can be relied upon or held accountable. Software and AI agents may
exercise delegated authority, but their signatures do not prove consciousness.
Trust in their actions depends on who authorized, constrained, supervised, and
accepted responsibility for them.

This is why key compromise, coercion, or uncontrolled automation can produce a
valid signature without producing a trustworthy action. It is also why recovery
and rotation need recognized continuity evidence rather than merely a new key.

Trust in an actor is distinct from operational reliance on infrastructure. A
relay, mint, application, or hosted operator may need to behave correctly, but
that dependency does not make it the actor represented by a key. Good policy
asks both who intentionally controls the authority and which systems must work
for that authority to remain useful.

## Start with the resources

| Resource | What it represents | Questions policy should ask |
| --- | --- | --- |
| **Keys** | Cryptographic continuity and authority | How are they generated, protected, delegated, rotated, recovered, and replaced? |
| **Funds** | Controlled units or claims of value | Who can spend them? Who validates them? How are balances, settlement, fees, failures, and recovery handled? |
| **Records** | Information, evidence, configuration, history, and instruments | Who can create, read, update, present, transfer, verify, retain, or delete them? |

Identity, credentials, wallets, and payments still have important roles:

```text
identity     -> an interpretation and recognition question
credential   -> a specialized record profile
wallet       -> an implementation that acts on resources
payment      -> an operation that moves or settles funds
```

This framing separates the resources that require continuity from the products
and services used to access them.

## Why the distinction matters

When a wallet is treated as the system of record, changing the wallet can mean
starting over. When a key is treated as identity, cryptographic control can be
mistaken for proof of who a person is. When every record is treated as a
credential, useful information is forced into an issuer-holder-verifier model
whether it belongs there or not. When policy addresses payments but not funds,
it leaves custody, reconciliation, and recovery under-specified.

A resource-oriented approach instead asks whether authorized users or
components can continue to locate, decrypt, verify, present, transfer, and
recover what matters through another compatible environment.

This is practical independence, not isolation. People should be able to use
trusted providers for execution, availability, and support. The important
question is whether that provider remains replaceable without destroying the
user's practical control.

## A simple policy test

Before approving a digital wallet, identity, credential, or payment
initiative, ask:

1. What keys, funds, and records does the system safeguard or act upon?
2. Who controls each resource, and what actions does that control permit?
3. Which issuer, institution, protocol, or legal framework gives it validity
   or recognition?
4. What evidence supports identity, intent, control, and transaction history?
   Who is the intentional actor, and is any signing authority delegated to
   software or an AI agent?
5. Can the resources be recovered and used through another application,
   device, provider, or infrastructure operator?
6. What happens when one of those systems becomes unavailable?

These questions do not prescribe a particular architecture. They expose where
an implementation has silently become a permanent dependency.

## Acorn as practical evidence

Acorn makes this resource boundary concrete:

- its keypair provides continuity and cryptographic authority without being
  described as the user's identity;
- its ecash proofs represent funds, while Lightning provides payment
  interoperability;
- its encrypted relay-backed records cover private data, configuration,
  transaction history, and application-defined record types; and
- applications can provide interfaces and services without becoming the only
  system of record.

Acorn is one implementation of the model, not a prescribed policy
architecture. Nostr, Cashu, and Acorn are not the only possible technologies.
Their value here is demonstrating that keys, funds, records, and application
containers can be separated in working software.

[Explore keys, funds and records](user-controlled-funds-and-records.md){ .md-button .md-button--primary }
[Read the full policy brief](https://github.com/trbouma/safebox-acorn/blob/main/docs/POLICY-BRIEF-KEYS-FUNDS-RECORDS.md){ .md-button }

## Further reading

- Timothy Bouma, [*The Niels Bohr Moment for Digital Architecture*](https://trbouma.substack.com/p/the-niels-bohr-moment-for-digital)
- [Full policy brief: Beyond Digital Identity, Credentials and Wallets](https://github.com/trbouma/safebox-acorn/blob/main/docs/POLICY-BRIEF-KEYS-FUNDS-RECORDS.md)
- [W3C Verifiable Credentials Data Model](https://www.w3.org/TR/vc-data-model/all/)
- [European Digital Identity Framework](https://eur-lex.europa.eu/eli/reg/2024/1183/oj?locale=en)
