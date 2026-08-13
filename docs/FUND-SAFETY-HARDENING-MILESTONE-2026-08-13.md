# Fund-Safety Hardening and Interoperability Milestone — 2026-08-13

## Summary

Testing on August 13, 2026 uncovered a critical compatibility defect before a
public release: historical Acorn clients did not use the mandatory Cashu
NUT-00 hash-to-curve construction. A wallet could therefore appear clean under
NUT-07 proof-state inspection while its proofs could not be redeemed by a
current mint.

The work that followed corrected the cryptographic construction, made proof
compatibility an explicit safety check, hardened relay persistence and
transaction-history verification, separated payment arrival from mint
finality, and demonstrated a fresh outgoing Lightning payment to an
independently operated Swiss Bitcoin Pay application.

This was a valuable pre-release discovery. It invalidated an unsafe assumption
and converted it into testable release behavior rather than allowing the
defect to become part of Acorn's future proof history.

## Incident and root cause

A newly created development wallet reported 3,925 sats in 34 proofs. NUT-07
reported all 34 proofs as `UNSPENT`, and ordinary reconciliation found nothing
to remove. A subsequent mint swap was nevertheless rejected with Cashu error
`11001`.

The mint was not simply old or unavailable. Historical Acorn code had derived
the proof point using an experimental hash-to-curve loop that omitted the
NUT-00 domain separator and little-endian counter. A blind mint could sign that
client-supplied point during issuance. At redemption, however, a current mint
derived the standard point from the revealed secret and rejected the
incompatible proof.

This exposed a subtle but critical distinction:

```text
mint reports canonical Y as UNSPENT
    does not imply
the stored proof is cryptographically redeemable as canonical NUT-00
```

NUT-07 answers whether the queried identifier is in a particular spend state.
It is not a complete redemption preflight. Proof compatibility must be checked
independently.

## Corrective controls in Acorn

Acorn now:

- derives proof points using the mandatory NUT-00 domain-separated algorithm;
- tests the implementation against published reference vectors;
- derives canonical `Y` from the proof secret instead of trusting a cached
  relay field;
- classifies cached identifiers as current, historical, missing, or
  inconsistent;
- distinguishes raw `mint_reported_unspent` value from the narrower
  `mint_confirmed_unspent` value;
- refuses payment, issuance, swapping, refreshing, repair, or pruning when
  incompatible proofs are present; and
- preserves incompatible proofs for mint-operator recovery rather than
  pretending an ordinary repair can migrate their signatures.

For explicitly disposable development balances, the destructive
`discard-incompatible-proofs --confirm-amount <sats>` command provides a
narrow reset. It requires an exact amount acknowledgement, preserves
compatible wallet and record state, verifies the relay rewrite, and records
the discard. It is not a recovery mechanism.

## Relay persistence and audit history

The same testing also reinforced that a successful mint mutation and an
eventually consistent relay write cannot be made atomic. Acorn deliberately
does not introduce an application-local proof journal; encrypted component
state remains relay-backed.

The hardened mutation sequence is:

```text
verify home-relay write/read behavior
  -> perform the irreversible mint operation
  -> sign one exact replacement event
  -> publish and idempotently retry that same event
  -> require exact event-ID readback
  -> report success
```

Relay acknowledgement may precede query visibility, so exact-ID verification
uses a configurable wait window. A timeout is an indeterminate persistence
result, not proof that the mint operation failed. The caller must not repeat a
payment blindly.

Kind `7377` transaction history now follows the same exact signed-event
readback rule. History remains an audit view rather than a balance source, but
silently losing a payment or deposit entry would make the wallet misleading.

## Narrow reconciliation instead of destructive repair

The preferred operational sequence is now:

```sh
acorn check-proofs
acorn reconcile-proofs
acorn balance --verify
```

`check-proofs` is read-only. `reconcile-proofs` removes only inputs that the
mint conclusively reports as spent and refuses to proceed through pending,
unknown, malformed, unreachable, or incompatible state. Whole-wallet refresh
remains an explicit, separately confirmed maintenance operation.

The distinction matters: stale relay history, incompatible cryptography, an
ambiguous Lightning result, and delayed relay readback are different failure
classes and must not share a single indiscriminate repair path.

## Incoming funds and application integration

Incoming gift-wrapped transfers are now treated as an inbox followed by a
separate settlement step:

```text
relay-visible transfer
  -> read-only pending preview
  -> provisional continuity receipt
  -> mint acceptance and proof refresh
  -> verified kind 7375 proof state
  -> verified kind 7377 transaction history
```

The read-only preview reports pending amount and event count without accepting
proofs, advancing the incoming cursor, or writing history. Safebox Web uses
this to reassure the user immediately that funds have arrived while continuing
to label them as non-spendable. Finalization runs asynchronously under a
public-key-scoped lease; the recipient key remains in web-process memory and is
not written to the application database.

Stable `(created_at, event_id)` checkpoints, paginated relay reads, duplicate
handling, provisional receipts, and terminal handling for conclusively spent
or malformed transfers prevent one bad or delayed event from indefinitely
blocking later valid funds.

## Live interoperability evidence

After the NUT-00 correction and reset of disposable incompatible development
proofs, fresh funds could be deposited and spent again. On August 13, 2026, a
connected Acorn completed an outgoing Lightning payment to an independently
operated Swiss Bitcoin Pay application.

This is meaningful interoperability evidence because the recipient was not a
Safebox-controlled address or application. It demonstrates the fresh
Acorn-to-mint-to-Lightning path against external infrastructure. It does not
certify the mint or recipient, prove every timeout-recovery path, or justify
meaningful production balances.

## Release implications

This milestone improves the hardened-alpha foundation but does not close the
fund-safety release gate. Before a pilot, the project still needs:

- deterministic failure injection around mint success and relay failure;
- an acknowledged, idempotent outgoing-transfer outbox;
- broader wallet-scoped serialization across application operations;
- replicated-relay recovery exercises;
- artifact-level tests from built wheels; and
- independent review of proof derivation, persistence ordering, and recovery.

The lasting lesson is that protocol conformance, mint spend state, relay
durability, and application presentation are separate layers. Acorn must prove
and communicate each layer rather than collapsing them into a single balance
or success message.

## Related documents

- [Proof State and Relay Consistency](PROOF-STATE-RELAY-CONSISTENCY.md)
- [Incoming Funds Reliability and Scaling](INCOMING-FUNDS-RELIABILITY-AND-SCALING.md)
- [Lightning Melt Recovery](LIGHTNING-MELT-RECOVERY.md)
- [CLI Contract](CLI-CONTRACT.md)
- [Roadmap to Releasability](ROADMAP-TO-RELEASABILITY.md)
- [Security Policy and Residual Risks](../SECURITY.md)
