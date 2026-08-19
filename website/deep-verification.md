---
title: Deep Verification
description: Acorn's role in layered verification for exact records, digests, and control evidence.
---

# Deep Verification

Deep verification is a layered way to verify digital records.

Acorn's role is to preserve the user's keys, encrypted records, exact Original
Record bytes, and plaintext digests. Other layers can then add control
evidence, recognition, and verifier policy without forcing Acorn to become the
schema owner for every kind of record.

```text
Original Record bytes
    -> Acorn digest
    -> external control evidence
    -> recognition
    -> verifier policy
```

## Exact bytes first

An Original Record may be a PDF, image, Wallet pass, credential, ticket, bill of
lading, or another artifact. Acorn should preserve the exact bytes and record a
plaintext digest before encryption.

That digest is the Original Record's **Uniform Digest Anchor (UDA)**. It
answers:

```text
Are these the exact bytes the evidence refers to?
```

It does not answer every trust question. A matching digest proves byte equality,
not truth, legal effect, issuer identity, or current validity.

The term is uniform because the same exact-byte anchoring mechanism works for
every artifact format. Native verification, third-party attestations,
notarization, provenance, and control history can all refer to the anchor while
remaining independent evidence layers.

## Effective MIME is a rendering hint

Effective MIME tells an application how it may represent an artifact.

For example, a `.pkpass` file is ZIP-shaped at the byte level but should be
handled as:

```text
application/vnd.apple.pkpass
```

That lets an application render a Wallet-pass preview while verification still
binds to the digest of the exact package bytes. MIME helps choose a viewer. The
digest identifies the artifact.

## Control evidence belongs above storage

OpenETR-style evidence can bind origin, control, transfer, presentation, or
termination events to the Original Record digest.

Acorn does not need to implement that control graph directly. Its job is to
make sure applications can reliably retrieve, authenticate, decrypt, hash, and
classify the original artifact. The control layer can then reason about that
artifact without depending on Blossom storage internals or application database
rows.

## Why the layers matter

Deep verification keeps concerns from collapsing into each other:

| Layer | Responsibility |
| --- | --- |
| Acorn | keys, encrypted records, exact bytes, plaintext digest, effective MIME |
| Blossom | opaque encrypted blob availability |
| Application | user workflow and bounded previews |
| Control layer | signed origin and lifecycle evidence |
| Recognition layer | whether keys and organizations are known to a verifier |
| Policy layer | the final conclusion for a context |

This is defense in depth for records. Each layer can be checked, replaced, or
improved without pretending it answers every question alone.
