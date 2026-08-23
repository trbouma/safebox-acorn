# Acorn Load Boundaries and Relay-Backed Read Models

## Status

This note records an architectural evolution prompted by live use of Acorn
through Safebox Web. It defines the intended direction; some boundaries already
exist, while the remaining separation should be introduced incrementally and
without changing Acorn's relay-backed source-of-truth model.

## Summary

Acorn originally exposed `load_data()` as a convenient way to reconstruct a
wallet. As the component matured, that operation accumulated several distinct
responsibilities: loading wallet configuration, discovering proof events,
reconstructing balances, preparing transaction state, and supporting stronger
relay and mint safety checks.

That complete reconstruction remains appropriate before a funds mutation. It
is unnecessarily expensive for a page or caller that needs only a component
key, recovery state, wallet configuration, a balance snapshot, a record
catalog, or one private record.

The governing rule is:

> Correctness checks belong at the mutation or explicit verification boundary,
> not automatically on every read or representation.

Acorn should therefore expose purpose-specific load and read boundaries while
retaining `load_data()` as the compatibility path for a complete wallet load.

## What prompted the re-architecture

The performance problem did not arise from one isolated regression. It became
visible as several necessary reliability improvements accumulated:

- proof publication and wallet-record writes gained canonical relay-readback
  verification;
- stale, spent, pending, unknown, and structurally incompatible proofs gained
  explicit classification and safer repair behavior;
- fee-bearing mints required exact input-fee accounting and additional mint
  interactions;
- incoming gift-wrapped funds became a staged process of relay discovery,
  provisional receipt, mint finalization, proof persistence, transaction
  history, and checkpoint advancement;
- Clear receipts, balances, proofs, and history expanded the state that a
  complete wallet reconstruction could encounter;
- wallet-scoped locks and background jobs made concurrent mutation safer but
  made an accidental full load more visible when it occupied a worker; and
- larger proof histories, multiple mints, slower third-party relays, and real
  network timeouts replaced the low-latency assumptions of early development.

These safeguards improved correctness. The architectural mistake was allowing
their cost to flow into unrelated reads. In Safebox Web, ordinary page routes
sometimes requested a fully loaded Acorn merely to display records, recovery
material, or a previously confirmed balance. A particularly clear incident was
the recovery page: the mnemonic already existed in the encrypted browser
session, yet displaying it waited for full proof retrieval. Under relay delay or
another active operation, the reverse proxy could time out before the recovery
material appeared.

The incident demonstrated both a performance and a continuity principle:
recovery material already held by the user-facing session must not become
unavailable merely because a relay, mint, or funds reconstruction is slow.

## State domains

The Acorn object presents one component, but its state falls into distinct
operational domains:

| Domain | Examples | Normal authority |
| --- | --- | --- |
| Local key context | `nsec`, `npub`, derived handle | Caller-supplied key material |
| Wallet metadata | home relay, home mint, name, currency, recovery markers | Encrypted relay-backed system records |
| Presentation snapshots | previously confirmed Cash and Clear totals | Encrypted relay-backed snapshot records |
| Record navigation | record catalog, labels and modification times | Encrypted relay-backed catalog |
| Authoritative records | one requested private record and attachment metadata | Encrypted signed record events |
| Funds state | Cashu proofs, Clear proofs, receipts and transaction journals | Relay-backed wallet events plus issuing mint state |
| Verification state | unspent, spent, pending, unknown, canonical publication | Mint and relay observations made on demand |
| Mutation state | locks, swaps, replacement proofs, journal and cursor updates | Acorn protocol operations across relay and mint boundaries |

Reading one domain must not implicitly read every other domain.

## Intended API boundaries

Names below describe capabilities rather than freezing exact method signatures.

### Constructed Acorn

Constructing `Acorn` from an `nsec` and bootstrap relay establishes the local
key context. It should not perform network I/O. It is suitable for public-key
display, local derivation, and operations that perform an exact relay lookup.

### Wallet metadata load

A metadata-only operation should retrieve and validate wallet configuration
without loading proof events. It supports configuration display, recovery
cleanup, and other system-record workflows. This remains a bounded relay
operation; it is not a funds verification.

### Snapshot reads

Balance snapshots provide a lightweight, previously confirmed presentation.
They are useful for wallet landing pages and status summaries. A snapshot:

- is portable relay-backed state, not a process-local cache;
- does not prove current spendability;
- must not silently trigger mint verification when absent; and
- is refreshed after successful authoritative mutations on a best-effort basis.

### Record-catalog and exact-record reads

The record catalog supports bounded navigation without decrypting the complete
record history. Opening a record uses a direct authoritative lookup for that
label. Neither operation requires proof loading.

An absent catalog should produce an explicit refresh action rather than an
unbounded automatic scan during ordinary page rendering.

A brand-new wallet legitimately has no catalog before its first record. The UI
should present that as an empty initial state, not corruption. After the first
authoritative record write succeeds, Acorn may attempt a tightly bounded
best-effort catalog build. Failure of that derived-index update must not turn a
successfully verified record write into a failed write; the user can explicitly
refresh the catalog later.

### Full funds load

The full funds boundary retrieves relay-backed proofs and the wallet state
needed for funds operations. It is appropriate before issuing, accepting,
swapping, repairing, consolidating, depositing, melting, or otherwise mutating
bearer value.

`load_data()` should remain available as this complete compatibility operation
until callers have migrated to narrower interfaces.

### Explicit verification

Mint proof checks and canonical relay verification should remain explicit.
Presentation reads may report their observation time and limitations, but must
not imply that a snapshot or relay-visible proof is mint-confirmed merely
because it was displayed successfully.

### Mutation boundaries

Mutations retain the strongest checks: current state, wallet locking, mint
submission classification, replacement-proof persistence, canonical readback,
transaction journalling, and safe lock release. Performance improvements must
not bypass those invariants.

## Caller selection matrix

| Caller need | Narrowest suitable boundary |
| --- | --- |
| Show component public key | Constructed Acorn |
| Display a mnemonic already in an encrypted user session | Session data plus constructed Acorn; no relay or mint dependency |
| Inspect or complete relay-backed recovery state | Exact recovery/system-record lookup; metadata load only for configuration mutation |
| Render wallet landing totals | Balance snapshot |
| Browse record labels | Record catalog |
| Open one record | Exact record lookup |
| Show stored transaction history | Focused history read |
| Check current proof spendability | Full funds load plus explicit mint verification |
| Finalize incoming funds | Full funds mutation boundary |
| Pay, issue, swap, repair, or consolidate | Full funds mutation boundary |

## Failure isolation and latency

Each read boundary should have its own timeout and error language. A slow mint
must not prevent record navigation. A large proof history must not prevent
recovery display. A missing record catalog must not cause an implicit complete
record scan. A failed presentation snapshot must not be reported as a zero
balance.

Callers should log the selected scope and elapsed duration without logging
keys, proofs, tokens, decrypted records, or recovery material. Useful scopes
include `metadata`, `snapshot`, `record-catalog`, `record`, `funds`,
`verification`, and `mutation`.

Long-running mutations may be moved outside an HTTP request, but doing so does
not move wallet authority into an application database. Background coordination
rows may contain non-secret status and leases; relay-backed events and mint
state remain authoritative.

## Caching policy

This design does not introduce a local wallet journal. Acorn's durable state
continues to live on relays and at issuing mints.

Permitted performance aids are derived, replaceable read models:

- encrypted relay-backed balance snapshots;
- encrypted relay-backed record catalogs;
- short-lived in-process caches for public or non-authoritative metadata where
  explicitly documented; and
- application coordination rows that contain no wallet secrets or bearer
  value and cannot reconstruct wallet state.

No snapshot, catalog, or coordination row becomes the source of truth for
spending, recovery authority, or record content.

## Incremental migration plan

1. Inventory every `load_data()` caller and classify it by required state
   domain.
2. Keep full loading for funds mutations and explicit verification.
3. Move recovery, configuration, snapshot, catalog, history, and exact-record
   reads to narrow interfaces.
4. Add duration logging by scope and tests that fail if a narrow route loads
   proofs or contacts a mint.
5. Preserve `load_data()` as a documented complete-load wrapper during the
   migration.
6. Add live latency tests against controlled and third-party relays with large
   proof and record histories.
7. Review concurrency so a slow funds mutation cannot starve unrelated
   metadata and record reads in the host application.

## Acceptance criteria

The separation is effective when:

- recovery material held in the encrypted session renders without relay or
  mint access;
- wallet landing, record listing, and exact-record pages do not load proofs;
- snapshot and catalog failure cannot be mistaken for authoritative empty
  state;
- funds mutations still enforce locking, mint outcome classification, and
  canonical relay persistence;
- application databases contain coordination and presentation metadata only;
  and
- tests can assert which network boundaries each operation is permitted to
  cross.

## Related documents

- [Acorn Component Boundary](ACORN-COMPONENT-BOUNDARY.md)
- [Safebox App Boundary](SAFEBOX-APP-BOUNDARY.md)
- [Proof-State and Relay Consistency](PROOF-STATE-RELAY-CONSISTENCY.md)
- [Incoming Funds Reliability and Scaling](INCOMING-FUNDS-RELIABILITY-AND-SCALING.md)
- [Fund Safety Hardening Milestone](FUND-SAFETY-HARDENING-MILESTONE-2026-08-13.md)
