---
title: Uniform Resource Model
description: A common model for transferable, non-transferable, fungible, and non-fungible records.
---

# Uniform Resource Model

The **Uniform Resource Model (URM)** is an emerging architecture for treating
funds, documents, credentials, credits, and other records as different profiles
of one common resource model.

URLs, URIs, and URNs help identify, name, or locate resources. URM adds another
layer:

```text
identity
authority
control
representations
policy
state
history
resolution
verification
```

The core idea is:

> A record is a resource with identity, authority, state, representations,
> policy, and history.

## Four resource classes

Transferability and fungibility are independent properties.

| | Non-transferable | Transferable |
| --- | --- | --- |
| **Non-fungible** | credential, personal record, signed receipt | title, ticket, negotiable document |
| **Fungible** | personal quota, account-bound allowance | cash proofs, Clear Mint Units, bearer credits |

The classification describes policy, not merely data structure. A resource may
change class or transfer rules over its lifecycle.

## Transfer means control changes

Copying bytes is not necessarily transfer.

```text
sharing     -> grants access
presentation -> supplies evidence for a purpose
copying     -> creates another representation
delivery    -> places transfer material in a recipient inbox
transfer    -> changes protocol-recognized operative control
acceptance  -> completes recipient validation and durable state
```

Keeping those operations distinct prevents a shared document from being
mistaken for transferred title and prevents an arrived bearer token from being
shown as finalized value.

## Fungibility is scoped

Fungibility never means “these labels look alike.”

A fungibility domain may depend on issuer, mint, unit, keyset, policy, expiry,
or restrictions. Two Clear balances are not interchangeable merely because
both display **credits** or **CMU**.

A Cashu proof also illustrates an important distinction: each proof is a unique
cryptographic record, while the quantity it represents may be fungible with
other valid proofs in the same mint and unit domain.

## One resource, several representations

A resource can have structured metadata, an encrypted Nostr event, an original
PDF, a content-addressed blob, a thumbnail, or a wallet view.

The resource is not identical to any one storage location or rendition:

```text
resource       -> conceptual controlled object
record         -> protocol state or evidence about it
representation -> bytes or data expressing it
```

This lets Grove preserve an opaque original, Spurline preserve signed events,
Acorn preserve control state, and Safebox Web present a useful human view
without making any one product the whole resource.

## Existing examples

### Private records

Credentials, health records, signed documents, and protected originals can be
held, recovered, and presented without being transferable.

### Transferable electronic records

Titles, negotiable documents, tickets, and controlled originals need an
observable chain showing who has operative control now. OpenETR explores this
non-fungible control model.

### Cash and Clear

Cashu ecash and Clear Mint Units represent fungible quantities through unique
bearer proofs. Acorn keeps cash and Clear in separate proof-state and history
profiles because their issuers, units, policies, and settlement models differ.

### Transferable gym guest passes

A gym can issue a member several guest-pass units. The member may transfer a
unit to any guest, who presents it for admission. The gym verifies the unit and
retires it when redeemed so it cannot be used again.

These passes are transferable, fungible entitlements within the gym's program:
each unit grants the same in-kind service, but it is not cash or a promise of
monetary redemption. The gym governs issuance and redemption while holders
control how valid units move between them.

### Entitlements

Personal quotas and non-transferable service allowances are fungible within a
program but cannot necessarily move to another holder.

## Product-family roles

| Product | Role |
| --- | --- |
| **Acorn** | keys, control state, encrypted records, transfer, and recovery |
| **Safebox Web** | human workflows, presentation, and confirmation |
| **Clear** | fungible organization-issued units |
| **OpenETR** | provenance and non-fungible control history |
| **Grove** | content-addressed representations |
| **Spurline** | signed event availability and synchronization |
| **Mainstay** | unified application across resource profiles |
| **Lockbox** | locally controlled execution and storage |

The common model creates interoperability without collapsing these product
boundaries.

## Current status

URM is a proposed architectural model, not a stable protocol standard. Existing
Acorn record, Cashu, Clear, Nostr, Blossom, and OpenETR formats retain their
current wire contracts.

The next work is to map those formats into explicit URM profiles, complete the
Clear acceptance lifecycle, and define the difference between copying a record
and transferring exclusive control.

[Read the full design note](https://github.com/trbouma/safebox-acorn/blob/main/docs/UNIFORM-RESOURCE-MODEL-DESIGN-NOTE.md){ .md-button .md-button--primary }
[User-controlled keys, funds and records](user-controlled-funds-and-records.md){ .md-button }
[How Acorn works](how-acorn-works.md){ .md-button }
