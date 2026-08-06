---
title: Security
description: Acorn's current safeguards, trust boundaries, security status, and residual risks.
---

# Security

Acorn handles Nostr private keys, recovery phrases, encrypted records, Cashu
bearer proofs, and Lightning payment state. A defect can expose private data,
interrupt recovery, misreport a payment, or cause loss of funds. Security is
therefore treated as an explicit product and protocol responsibility.

!!! warning "Current status: developer preview"

    Acorn has not received a comprehensive independent security audit. Its
    interfaces and storage behavior may still change before a stable release.
    Use only small test balances and non-critical records.

## What Acorn protects

Acorn is designed to protect:

- the component's private key and recovery phrase;
- spendable ecash proofs and payment capabilities;
- private record labels, contents, attachments, and encryption material;
- wallet configuration and transaction history; and
- continuity of access to relay-backed state.

The keypair provides the Acorn component's cryptographic continuity and
authority. It is not, by itself, the civil, legal, or social identity of a
person. Identity claims and interpretations remain outside the keypair.

## Safeguards implemented today

Current safeguards include:

- hidden secret entry instead of recovery material in command arguments;
- independent RPK generation or domain-separated derivation from external
  256-bit entropy, with an exact 24-word checksummed recovery encoding;
- owner-only configuration and secret-file permissions;
- atomic, locked configuration updates;
- NIP-44 encryption for private record metadata;
- AES-256-GCM encryption for private blob content;
- NIP-59 gift wrapping for private ecash delivery by default;
- explicit recovery verification before replacing local configuration;
- proof inspection separated from mutating repair operations;
- pending-payment reconciliation intended to avoid blindly repeating an
  ambiguous Lightning payment;
- relay readback, replication, migration, and suitability testing; and
- logging rules and regression tests intended to keep keys, proofs, invoices,
  messages, and decrypted records out of diagnostic output.

These controls reduce specific risks. They do not amount to a general proof of
security.

## Trust remains explicit

Acorn separates key, code, and data, but every deployment still has trust
boundaries:

| Dependency | What it controls |
| --- | --- |
| Key holder | Signing, decryption, spending, and recovery authority |
| Execution environment | The running code and plaintext processed in memory |
| Relay | Availability, retention, indexing, query behavior, and visible metadata |
| Mint | Cashu issuance, redemption, and authoritative proof spend state |
| Lightning infrastructure | Invoice resolution, routing, and settlement reporting |
| Blob server | Availability and retention of encrypted attachments |

Encryption can prevent infrastructure operators from directly reading record
content. It cannot force a relay to retain, return, or erase an event. A mint
remains authoritative for whether its proofs are spendable. An operator that
controls the execution environment may be able to observe keys and plaintext
while Acorn is running.

## Important residual risks

The current risks include:

- the code has not been independently audited;
- the local config contains the `nsec` in permission-protected but unencrypted
  form;
- Python process memory is not a hardware-backed or reliably zeroized secret
  boundary;
- relay metadata, access patterns, censorship, partial views, and advisory
  deletion remain concerns;
- Cashu proofs are bearer assets and mint operation remains an external trust
  dependency;
- crash-safe outgoing ecash transfer and complete distributed multi-writer
  consistency remain release gates;
- third-party dependencies and native cryptographic libraries create supply-
  chain and compatibility risk;
- Acorn does not itself provide Tor, traffic padding, or protection from
  endpoint correlation; and
- ordinary Acorn operations use classical cryptography and must not currently
  be described as quantum-safe.

The RPK and its recovery encoding are foundations for a proposed
protected-record profile. No current record is encrypted with the RPK. Safebox
Web implements an initial phrase display, backup-confirmation, authenticated
redisplay, and reconnect ceremony, but that workflow and the future encryption
profile have not received independent review.

The complete residual-risk register, deployment guidance, disclosure process,
and security non-claims are maintained in the repository.

[Read the full SECURITY.md](https://github.com/trbouma/safebox-acorn/blob/main/SECURITY.md){ .md-button .md-button--primary }
[Read Mitigating AI and Quantum Attacks](mitigating-ai-and-quantum-attacks.md){ .md-button }
[View the release roadmap](https://github.com/trbouma/safebox-acorn/blob/main/docs/ROADMAP-TO-RELEASABILITY.md){ .md-button }

## Reporting a vulnerability

Do not place private keys, seed phrases, Cashu proofs, tokens, invoices,
preimages, private records, or unpatched exploit details in a public issue.

Use GitHub's private vulnerability-reporting feature under **Security → Report
a vulnerability** when it is available. If it is unavailable, open a public
issue containing no sensitive details and ask the maintainer to establish a
private communication channel.

[Return to the Acorn home page](index.md){ .md-button }
