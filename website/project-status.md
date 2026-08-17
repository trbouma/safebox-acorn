---
title: Project Status
description: What Acorn has demonstrated, what remains under development, and the gates before a public release.
---

# Project status

Acorn is developer-stage software being hardened as an independent component.
It has progressed beyond a design experiment, but it is not yet a stable wallet
release for meaningful balances or production-critical records.

The recommended current use is development, integration, relay and mint
interoperability testing, and small-value experimentation.

## What has been demonstrated

The project has working implementations of:

- independent installation as the `safebox-acorn` Python package;
- a Python component interface and command-line interface;
- cryptographic wallet initialization and recovery;
- encrypted private-record storage, retrieval, listing, and deletion;
- Cashu deposit, payment, transfer, receipt, proof inspection, repair, and
  wallet-burn flows;
- mint-authoritative removal of confirmed spent proofs before wallet mutations,
  while preserving pending or unknown proof state;
- process-local and owned relay-lease serialization for wallet mutations;
- NIP-59 gift-wrapped private ecash delivery;
- separate receive, validation, checkpoint, and pending storage for NIP-59
  kind `7379` Clear CMU transfers;
- grouped multi-mint Clear balance and keyset representation;
- encrypted kind `7380` Clear proof-state and kind `7381` append-only history
  foundations;
- durable pending Clear transfer deletion with rescan tombstones;
- Safebox Web interoperability for Clear discovery, display aliases, relay
  checks, and deletion;
- transaction history shared between the CLI and Safebox web application;
- relay replication, readback verification, and migration workflows;
- operation against controlled and independently operated relays and mints;
- deterministic unit tests and opt-in live integration tests;
- installation and operation inside a FreeBSD jail; and
- an optional boundary for experimental post-quantum dependencies.

This evidence makes Acorn a credible hardened-alpha foundation. It does not
remove the need for release discipline around failure recovery and value safety.

## August 2026 fund-safety milestone

Pre-release testing uncovered that historical Acorn clients used a
non-standard Cashu hash-to-curve construction. A mint could report the
canonical proof identifier as unspent even though the historical proof was not
redeemable under mandatory NUT-00 rules. Current Acorn now uses the standard
construction and reference vectors, identifies incompatible historical
proofs, refuses destructive operations against them, and distinguishes raw
mint state from cryptographically compatible spendable value.

The same hardening pass added exact event-ID readback for proof and transaction
history persistence, read-only pending-funds preview, and safer narrow proof
reconciliation. Fresh compatible funds subsequently completed a Lightning
payment to an independently operated Swiss Bitcoin Pay application. This is
strong interoperability evidence, while the remaining crash-window and
failure-injection work stays explicitly on the release roadmap.

[Read the complete milestone](https://github.com/trbouma/safebox-acorn/blob/main/docs/FUND-SAFETY-HARDENING-MILESTONE-2026-08-13.md){ .md-button .md-button--primary }

## August 2026 Clear transfer milestone

Acorn now receives organization-issued CMUs through a protocol path that is
cryptographically and operationally separate from cash. A public Clear mint
sent an exact amount to a NIP-05 address; Acorn recovered the inner kind `7379`
transfer from its relay-backed inbox; and Safebox Web displayed the pending
transfer under the correct mint and CMU aliases.

The milestone includes durable deletion: removing a pending transfer erases
its bearer token while retaining a tombstone that prevents relay rescans from
restoring it.

[Read the Clear transfer wallet milestone](https://github.com/trbouma/safebox-acorn/blob/main/docs/CLEAR-TRANSFER-WALLET-MILESTONE-2026-08-17.md){ .md-button .md-button--primary }

The practical product scope is the safekeeping of user-controlled keys, funds,
and records. Keys provide cryptographic authority and continuity; identity
claims and their interpretation remain outside the component.

## Current hardening priorities

The most important work is not adding more commands. It is making interrupted
and repeated operations predictable:

1. **Configuration safety** — private permissions, atomic writes, and
   non-destructive failure behavior.
2. **Wallet-state isolation** — independent Acorn instances without shared
   mutable state.
3. **Outgoing transfer recovery** — durable retry without issuing value twice.
4. **Incoming idempotency** — safe handling of duplicate, delayed, or
   same-timestamp transfers.
5. **Proof failure testing** — explicit recovery from mint and relay failures.
6. **Async lifecycle discipline** — clean event-loop and relay-client shutdown.
7. **Stable public contracts** — predictable Python methods, CLI output, JSON
   errors, and compatibility rules.
8. **Artifact validation** — testing the actual wheel in core and optional
   dependency environments.
9. **Clean deployment validation** — repeatable macOS, Linux, and FreeBSD
   installation.
10. **External pilot evidence** — real use through applications and replaceable
    infrastructure.

## Release progression

| Level | Intended audience | Required confidence |
| --- | --- | --- |
| Developer preview | Collaborators who expect APIs and storage behavior to change | Clean installation, deterministic tests, preserved recovery material, and explicit limitations |
| Pilot release | Bounded application deployments with operational support | Reliable transfer recovery, protected configuration, repeatable deployment, and stable core contracts |
| Stable release | Applications and operators expecting compatibility | Reproducible publication, concurrency safety, upgrade rules, supported recovery, and resolved pilot findings |

Releasability is not the same as feature completeness. Because Acorn handles
private keys, encrypted records, and spendable ecash, loss prevention and
recovery matter more than the number of features.

## Testing approach

Acorn uses two complementary test layers:

- **Deterministic tests** run without spending sats or depending on live
  infrastructure. They cover component behavior, validation, formatting, and
  failure paths.
- **Opt-in live tests** exercise real relays, mints, private records, ecash
  delivery, wallet cleanup, Lightning interoperability, and recovery behavior.

Disposable wallets absorb most test churn. A configured source wallet funds
small live transfers and receives cleanup sweeps. Tests can run against
controlled infrastructure or an explicitly selected third-party relay.

Passing against third-party infrastructure is important evidence of protocol
interoperability. It does not certify an operator, promise future availability,
or make large balances safe.

## Known boundaries

Current users should assume that:

- interfaces and stored payloads may still evolve;
- pending Clear CMU transfers are visible and deletable but not yet finalized
  into spendable Clear proof state;
- interrupted value transfers need further hardening;
- relays vary substantially in compatibility and retention;
- mint reliability and liability remain outside Acorn's control;
- local key storage does not yet provide hardware-grade isolation;
- experimental post-quantum support is optional and not a production security
  claim; and
- only small test balances should be used.

## Follow the work

Detailed specifications, test runbooks, the relay suitability ledger, and the
release roadmap remain in the source repository. Public pages provide the
reader-facing model; the repository documents provide implementation and
operational detail.

[View the release roadmap](https://github.com/trbouma/safebox-acorn/blob/main/docs/ROADMAP-TO-RELEASABILITY.md){ .md-button .md-button--primary }
[Read the security statement](security.md){ .md-button }
[View the source repository](https://github.com/trbouma/safebox-acorn){ .md-button }
[Return to the Acorn home page](index.md){ .md-button }

## Reference basis

- [Roadmap to Releasability](https://github.com/trbouma/safebox-acorn/blob/main/docs/ROADMAP-TO-RELEASABILITY.md)
- [Security Policy and Residual Risks](https://github.com/trbouma/safebox-acorn/blob/main/SECURITY.md)
- [Testing Guide](https://github.com/trbouma/safebox-acorn/blob/main/docs/TESTING.md)
- [Relay Suitability Ledger](https://github.com/trbouma/safebox-acorn/blob/main/docs/RELAY-SUITABILITY-LEDGER.md)
- [CLI and Safebox Interoperability](https://github.com/trbouma/safebox-acorn/blob/main/docs/ACORN-WEBAPP-INTEROPERABILITY.md)
- [August 13 Fund-Safety Hardening Milestone](https://github.com/trbouma/safebox-acorn/blob/main/docs/FUND-SAFETY-HARDENING-MILESTONE-2026-08-13.md)
- [August 17 Clear Transfer Wallet Milestone](https://github.com/trbouma/safebox-acorn/blob/main/docs/CLEAR-TRANSFER-WALLET-MILESTONE-2026-08-17.md)
