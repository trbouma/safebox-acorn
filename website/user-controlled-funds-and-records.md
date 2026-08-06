---
title: User-Controlled Keys, Funds and Records
description: How Acorn uses one component model for transferable funds and private records with different control rules.
---

# User-controlled keys, funds and records

Acorn treats funds and private records as different forms of controlled
protocol state. Both are anchored by the cryptographic keys of an Acorn
wallet, protected from application lock-in, and recoverable through compatible
environments. They differ in what control means and who remains authoritative.

This gives Acorn a broader role than either a payment wallet or a document
store. It is a common component for objects that a user needs to hold, operate,
recover, and carry between applications.

## Keys supply continuity and authority

An Acorn wallet has its own user-controlled cryptographic keypair. The keys
provide continuity and authority; they are not the identity of the component or
the person operating it.

The wallet keypair provides:

- **continuity**, so compatible environments can recover and continue the same
  key authority and protocol state; and
- **authority**, so the component can sign, decrypt, update, present, transfer,
  or spend controlled objects according to their rules.

Another party may associate the public key with a person or organization
through NIP-05, a kind `0` profile, a Lightning address, credentials,
attestations, relationships, prior interactions, or legal claims. Those
associations are external interpretations and are not implied by possession of
the key alone.

A history of signed events can provide verifiable continuity and evidence of
key use. It cannot prove that the content is true or that a conscious actor
personally intended each action. Identity is interpreted from that continuity
and its surrounding context; trust is the further judgment that an intentional
actor governs the key and any delegated automation over time.

## The controllable-record model

A controllable record is a protocol object whose useful state includes not only
its contents, but also who can act on it and how that control can change.

```text
content     -> what the record says or contains
authority   -> who may act on it
control     -> what actions the current holder can perform
continuity  -> how the holder can recover and continue
validation  -> who determines whether the record remains valid
```

Acorn currently supports two principal classes:

| Record class | What user control means | External authority that remains |
| --- | --- | --- |
| Transferable funds | Hold, spend, transfer, receive, refresh, and recover ecash proofs. | The issuing mint validates whether proofs are spendable. |
| Private records | Encrypt, store, retrieve, present, replicate, migrate, and request deletion. | An issuer or legal framework determines whether a claim is authentic or meaningful. |

## Funds are transferable controlled records

Ecash is Acorn's concrete example of a transferable record. A mint issues
Cashu proofs. Control of valid proofs allows a wallet to spend or transfer the
represented value.

A private Acorn transfer follows a deliberate lifecycle:

```text
sender controls spendable proofs
        ↓
sender creates and privately delivers a transfer
        ↓
recipient decrypts and accepts it
        ↓
mint validates and refreshes the proofs
        ↓
recipient stores new spendable proof state
        ↓
both wallets retain transaction history
```

Transfer is therefore more than copying data. The recipient must establish
fresh spendable state through the mint. The mint provides anti-double-spend
validation, while Acorn provides private delivery, wallet control, durable
state, recovery, and application interoperability.

Changing the application does not require changing the wallet keys.
Changing mints is a different matter: proofs remain obligations of the mint
that issued them.

## Private records are holder-controlled objects

Private records may include notes, documents, credentials, healthcare records,
membership records, permissions, attestations, or application-defined data.
They are encrypted before being published to relay infrastructure.

The holder can:

- retrieve and decrypt the record;
- list it without exposing its plaintext label to ordinary relay queries;
- replicate its signed encrypted event to another suitable relay;
- recover it through another compatible Acorn environment; and
- present it in an application-defined workflow.

Presentation does not normally transfer the record in the way that spending
transfers ecash. An issuer may create or sign a record for a holder, and that
issuer remains responsible for the authenticity of its claims. Acorn protects
holder control and continuity; it does not manufacture truth or legal effect.

## One kernel, different rules

Funds and records share a common foundation:

```text
cryptographic keys and authority
encrypted relay-backed state
private delivery
signed events
recovery material
replication and migration
human and machine interfaces
```

Their control rules remain intentionally different. Funds need spend-state
validation and safe transfer. Issued records need provenance, privacy,
presentation, and domain-specific verification. Acorn supplies the reusable
mechanics without absorbing every payment, healthcare, credential, or document
schema into the component.

## What user-controlled does not mean

User control does not imply that:

- the wallet key proves the identity of a person;
- the holder can alter an issuer's claim without detection;
- the wallet can declare spent proofs valid;
- encrypted data is guaranteed to remain available;
- deletion requests erase every relay copy; or
- every application must interpret a record in the same way.

It means the user has a practical continuity and authority path that does not
depend exclusively on one application interface.

[Explore the user-controlled architecture](user-controlled-architecture.md){ .md-button .md-button--primary }
[See the policy vocabulary](better-policy-vocabulary.md){ .md-button }
[Return to How Acorn Works](how-acorn-works.md){ .md-button }

## Reference basis

- [Acorn Record Model](https://github.com/trbouma/safebox-acorn/blob/main/docs/ACORN-RECORD-MODEL.md)
- [Record Encryption Specification](https://github.com/trbouma/safebox-acorn/blob/main/docs/RECORD-ENCRYPTION-SPEC.md)
- [Ecash Transfer Design](https://github.com/trbouma/safebox-acorn/blob/main/docs/ECASH-TRANSFER-KIND-7378-DESIGN.md)
- [Mint Configuration Specification](https://github.com/trbouma/safebox-acorn/blob/main/docs/MINT-CONFIGURATION-SPEC.md)
