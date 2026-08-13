# Proof State and Relay Consistency Design Note

## Summary

Acorn proof state lives at the intersection of two systems:

- Nostr relays store encrypted proof events.
- Cashu mints decide whether individual proofs are spendable.

Relays are storage and transport. They are not the source of truth for proof
spend status. The mint is the authority for whether a proof is unspent.

There are two separate questions:

1. Does the mint report a supplied proof identifier (`Y`) as unspent?
2. Is the proof cryptographically compatible with the mint's current Cashu
   verification rules?

NUT-07 `/checkstate` answers only the first question. It is not a redemption
preflight and cannot establish the second by itself.

Relay migration exposed two important design lessons: read-only commands must
not mutate wallet proof state, and mint-mutating operations must reconcile
known-spent relay proofs before selecting value. Whole-wallet refresh and
consolidation remain explicit maintenance operations.

## What happened in testing

A wallet was replicated from the normal home relay to a test relay:

```text
ws://beelink:8735
```

Records were successfully readable from the test relay.

Then proofs were spent while the wallet was pointed at the replicated relay.
That made the test relay the freshest source of proof events. The original home
relay still contained stale encrypted proof events from before the spend.

When switching back to the original relay, Acorn saw a higher apparent proof
balance because stale proof events were still present. When proof repair checked
those proofs with the mint, the mint reported some as already spent, and Acorn
dropped them.

## Core lesson

Relay-visible proof events are not enough to know wallet value.

The apparent relay balance is:

```text
sum(encrypted proof events visible on relay)
```

The real wallet balance is:

```text
sum(proofs that the mint reports as UNSPENT)
```

For operationally spendable value, Acorn must additionally establish that the
proof identifier follows the mandatory NUT-00 hash-to-curve construction.

These values can diverge during:

- relay migration;
- failed deletion propagation;
- interrupted proof rewrites;
- multi-relay replication;
- stale relay reads;
- adversarial relay behavior.

## Why deletion events matter

When proof state is rewritten, old proof events may be deleted using Nostr
deletion events.

If replication copies only proof events but not deletion events, the target
relay can retain stale proof history.

Therefore proof-state replication should include:

```text
5       deletion events
7375    proof events
```

For full wallet migration, Acorn's default replication includes both.

## Read-only commands must be read-only

Testing showed that `load_data()` could trigger automatic proof reduction when
the proof count exceeded a threshold. This meant a command like:

```sh
acorn balance
```

could start proof maintenance. That is wrong for operator safety.

The corrected rule is:

```text
balance/read commands may load and report state;
they must not swap, repair, consolidate, delete, or rewrite proofs.
```

Proof mutation should happen only through explicit user operations such as:

```sh
acorn repair-proofs
acorn swap
acorn swap --consolidate
acorn deposit
acorn pay
acorn issue_token
acorn receive-ecash
```

Receive-side proof maintenance is therefore disabled by default. Deposits and
token acceptance persist their newly issued proofs but do not automatically
swap or consolidate the rest of the wallet. Maintenance remains an explicit
operator action.

There is one narrow automatic safety action. Before payment, token issuance,
or token acceptance, Acorn reloads relay-backed proof state and asks the mint
about spend state. Proofs reported definitively as `SPENT` are removed before
the requested operation continues. This is reconciliation within an already
mutating operation, not background maintenance. Proofs reported as `PENDING`
or `UNKNOWN`, and proofs whose mint cannot be reached, are never discarded.

## August 2026 stale-balance incident

A Safebox Web deposit exposed a concrete stale-relay case. Before the deposit,
the web application displayed approximately 33,905 sats by summing every kind
`7375` proof event returned by the home relay. A 21-sat deposit added three
proofs and triggered the former automatic maintenance threshold.

The mint then reported 87 of 95 relay-visible proofs as already spent. Those
proofs totalled 33,874 sats, including one 32,768-sat proof. Maintenance
completed with eight proofs and 52 spendable sats:

```text
33,874 sats already spent
+   52 sats retained
=33,926 sats relay-visible after the deposit
```

The deposit did not destroy 33,874 sats; the relay had retained historical
proof events whose deletion requests were not reflected in the query result.
The incident demonstrated that an unqualified relay-derived balance is unsafe
and that a deposit must never unexpectedly initiate whole-wallet maintenance.

Acorn now:

- loads authored kind `5` deletion events and excludes referenced kind `7375`
  events from the current proof view;
- labels ordinary balance output as relay-visible;
- provides `acorn balance --verify` for a read-only mint-confirmed balance;
- leaves receive-side maintenance disabled unless explicitly enabled; and
- does not invoke maintenance from deposits or token acceptance.

## August 2026 hash-to-curve compatibility incident

A newly created wallet reported 3,925 sats in 34 proofs as `UNSPENT` through
NUT-07, yet a 21-sat Lightning payment failed at `/v1/swap` with Cashu error
`11001`. Reconciliation removed nothing because the identifiers queried by the
client were not in the mint's spent set.

The underlying issue was that historical Acorn releases used an experimental
hash-to-curve loop without the mandatory NUT-00 domain separator and
little-endian counter. A blind mint can sign a point constructed by that older
client, but a current mint later derives the standard NUT-00 point from the
revealed secret during redemption. The resulting proof is incompatible even
though a NUT-07 query for the standard identifier can return `UNSPENT`.

Acorn now uses the NUT-00 algorithm and tests it against published reference
vectors. The proof audit also compares a proof's cached identifier with both
the NUT-00 and historical Acorn derivations. A historical match is reported as
`incompatible`, never as mint-confirmed spendable, and all destructive proof
operations are refused.

Existing incompatible proofs must be preserved exactly as stored. They cannot
be safely repaired by swapping, refreshing, pruning, or rewriting relay state.
Recovery requires cooperation from the issuing mint operator, which may be
able to validate the historical construction and migrate the value under a
controlled compatibility procedure.

For development wallets where preservation of the incompatible value is not a
requirement, `discard-incompatible-proofs --confirm-amount <sats>` provides a
narrow reset. It removes only non-NUT-00 proof state and retains the component
key, configuration, records, history, and any already-compatible proofs. This
is an intentional loss operation rather than cryptographic migration; the
wallet becomes usable again only after receiving freshly issued NUT-00 proofs.

## Received ecash proof state

Incoming ecash transfers are delivery events, not durable proof state.

The default receive path is:

```text
kind 1059 gift wrap
  -> unwrap inner kind 7378 Acorn transfer
  -> extract Cashu token
  -> accept token through the mint
  -> refresh/swap proofs as needed
  -> persist spendable proofs as kind 7375 proof state
  -> write transaction history as kind 7377
```

The relay-visible transfer event is therefore not the balance. It is an inbox
delivery mechanism. The wallet balance comes from the refreshed proofs that are
accepted by the mint and then persisted into the normal kind `7375` proof
state.

This is why `receive-ecash` is explicit and mutating. It turns received transfer
material into current wallet proof state. In contrast, `balance` must remain a
read-only inspection command.

If the issuing mint conclusively rejects a pending receipt token with Cashu
error `11001` (`Token already spent`), Acorn cannot credit that value and must
not retry it indefinitely. Reconciliation writes an idempotent transaction
history entry with type `X`, amount and event reference, marks the encrypted
receipt `terminal-error`, removes its bearer token, and continues with later
receipts. The entry is an error record, not a credit, and the wallet balance is
unchanged. Timeouts, unavailable mints, pending states, and other ambiguous
failures remain pending rather than being discarded.

Structurally malformed incoming transfer events are terminal for cursor
processing. This category is intentionally narrow: payloads that cannot be
decrypted or parsed, invalid Cashu tokens, and proof/amount mismatches. Acorn
writes an idempotent type `X` transaction-history entry containing the event
reference and a bounded error description, advances the receive cursor, and
continues with later messages. A malformed event therefore cannot indefinitely
block valid payments behind it.

Operational failures are different. If Acorn cannot write the error entry,
persist the provisional receipt, or update relay-backed state, it does not
advance past the affected event. This preserves retryability and prevents a
temporary infrastructure problem from silently discarding valid funds.

Incoming delivery now uses a versioned `(created_at, event_id)` checkpoint and
overlapping paginated relay reads. See
[Incoming Funds Reliability and Scaling](INCOMING-FUNDS-RELIABILITY-AND-SCALING.md)
for the cursor invariants, pagination safety behavior, and remaining limits.

## Inspection, automatic reconciliation, and explicit repair

Before repair, the operator can perform a read-only mint-state check:

```sh
acorn check-proofs
```

This asks each mapped mint for the current state of the wallet-visible proofs
and reports `UNSPENT`, `SPENT`, `PENDING`, and `UNKNOWN` totals. It also reports
local structural problems such as duplicates and unknown keyset mappings.
Duplicate proof copies are counted once in the mint-confirmed total.

The output distinguishes `mint_reported_unspent` from
`mint_confirmed_unspent`. The former is the raw NUT-07 state response. The
latter excludes proofs whose cached identifier shows historical or inconsistent
hash-to-curve behavior.

The check deliberately performs no lock acquisition, proof refresh, event
deletion, proof rewrite, or transaction-history update. `PENDING`, `UNKNOWN`,
and network-error results are inconclusive; the operator should recheck or
investigate rather than assume that repair is safe.

For an operator-initiated audit or whole-wallet refresh, `repair-proofs` is the
appropriate tool. Acorn also performs a narrower reconciliation automatically
at the start of mint-mutating payment, issuance, and acceptance operations.
That automatic path removes only proofs the mint definitively reports as
`SPENT`; it stops without removing value if any relevant result is pending,
unknown, malformed, or unreachable.

Applications that need this narrow recovery explicitly can call
`await acorn.reconcile_stale_proofs()`. The method acquires the wallet lock,
requires any pending Lightning melt journal to reach a terminal state, reloads
the relay-backed proofs, verifies them with their mapped mints, and rewrites
the wallet only when mint-confirmed `SPENT` proofs must be removed. It does not
swap or refresh `UNSPENT` proofs. This makes it suitable for retrying receipt
finalization without invoking the much heavier whole-wallet `repair-proofs`
workflow.

The same narrow operation is available to CLI operators:

```sh
acorn reconcile-proofs
acorn balance --verify
```

This is preferred over a forced whole-wallet refresh when the immediate
problem is a mint error `11001` (`Token already spent`). Older proof events may
omit or contain an incorrect cached `Y`; Acorn never trusts that field for
spend-state decisions and instead derives canonical `Y` from the proof secret
for reconciliation, inspection, pending-payment state, and the final pre-swap
check. Incomplete mint check-state responses fail closed before a swap is
submitted.

It should:

1. load visible proof events;
2. group and deduplicate proofs;
3. ask the mint for proof states;
4. drop proofs that are already spent;
5. keep or refresh usable proofs;
6. rewrite clean proof state to the current home relay.

Warnings such as:

```text
reason=already_spent
```

are expected when stale relay events are being cleaned.

## Migration consistency pattern

Automatic removal of mint-confirmed spent proofs is necessary but not
sufficient for relay migration. It removes stale inputs visible on the
destination, but it cannot recover replacement proof secrets that exist only
on another relay. The mint knows whether presented proofs are spent; it does
not act as a backup of the wallet's replacement proofs.

Migration is therefore a controlled single-writer operation. All Acorn and web
instances using the wallet must stop mutating it while the freshest source is
replicated, verified, and promoted. Relay-backed leases on two different home
relays do not coordinate with one another and cannot prevent split-brain
wallet mutation.

If spending occurs while pointed at a replicated relay, the safest convergence
pattern is:

```text
stop all wallet writers
  -> identify the freshest relay
fresh relay proof state
  -> replicate kinds 5,7375
  -> verify destination event and proof visibility
  -> switch home relay
  -> check-proofs
  -> repair-proofs when a whole-wallet refresh is needed
  -> balance --verify
  -> resume one writer
```

Example:

```sh
acorn replicate \
  --source ws://beelink:8735 \
  --target relay.getsafebox.app \
  --kinds 5,7375

acorn set --home wss://relay.getsafebox.app
acorn check-proofs
acorn repair-proofs
acorn balance --verify
```

## Design implications

### Relays are eventually consistent storage

Acorn should assume that relays can be:

- stale;
- incomplete;
- unavailable;
- duplicated;
- adversarial;
- inconsistent with other relays.

### The mint is the spend-state authority

For Cashu value, the mint's `checkstate` and swap responses are decisive.
When the mint reports `SPENT`, Acorn removes that proof from its current wallet
view automatically before another mint mutation. Relay presence cannot restore
spendability. By contrast, absence of a decisive mint response is not evidence
that a proof is spent, so Acorn preserves uncertain proofs and stops the
operation.
Lightning melt quotes are also authoritative when a payment response is lost.
Acorn persists post-swap proofs and a pending-melt journal before submission,
then uses quote lookup rather than repeating an ambiguous melt request. See
[Lightning Melt Recovery](LIGHTNING-MELT-RECOVERY.md).

### Proof writes need verification

After rewriting proof events, Acorn should verify that the expected proof state
can be loaded back from the relay. Verification compares exact proof identities
(keyset and secret), not only total balance or proof count. A same-value proof
set containing an unexpected historical proof is a failed verification.

Every successful swap consumes bearer inputs immediately at the mint. Acorn
must therefore publish and verify each replacement batch before attempting the
next independent input or keyset. Only after every replacement is durable may
it publish a deletion request for the source proof events. If a later swap
fails, already-created replacements remain recoverable from the relay and the
old historical events remain available for diagnosis.

Because a mint swap is irreversible, Acorn performs a relay write/read
preflight before consuming proofs and then publishes each exact signed
replacement event immediately:

```text
verify home-relay write/read behavior
  -> perform irreversible mint operation
  -> create and sign the replacement kind 7375 event
  -> publish the exact event
  -> retry the same signed event in memory
  -> require readback of the exact event ID
```

Acorn deliberately does not persist a local proof journal. Wallet state,
pending-payment state, continuity receipts, and recovery coordination belong
in encrypted relay records rather than application-local files or databases.
The exact signed event is retried idempotently only while the operation remains
alive.

Relay acknowledgement and relay query visibility are not always simultaneous.
Acorn therefore waits up to 60 seconds by default for exact-ID readback and
republishes the same signed event during that interval. Operators may tune this
without changing wallet semantics:

```sh
ACORN_RELAY_VERIFY_TIMEOUT_SECONDS=90
```

The value must be a positive number of seconds. A timeout is an indeterminate
storage result, not proof that publication failed. If it occurs after a mint
operation, do not repeat the payment or swap blindly. Wait for the relay to
settle, run `acorn check-proofs`, and use `acorn reconcile-proofs` only if the
mint conclusively reports an obsolete input as spent. The error includes the
replacement event IDs so an operator can investigate the relay directly.

This boundary has an unavoidable consequence: no client can make an
irreversible mint swap and an eventually consistent relay write atomic. If the
mint succeeds and every configured relay remains unavailable until the process
terminates, a replacement proof held only in memory may be lost. The mitigations
are preflight verification, reliable home relays, optional relay replication,
small independently persisted batches, exact-ID readback, and keeping the
process alive while a post-swap publication failure is investigated. Acorn
must not imply that application-local storage closes this protocol gap.

Whole-wallet refresh is intentionally guarded because even a clean-looking
wallet is rewritten through irreversible mint swaps:

```sh
acorn check-proofs
acorn repair-proofs --refresh --confirm-refresh
```

An inability to verify the remote release of a wallet lease is reported as a
degraded cleanup condition. The local mutex is still released and the owned
remote lease expires naturally. Most importantly, that cleanup condition no
longer replaces the primary mint or proof-persistence error.

### Wallet mutations need owned serialization

Mint swaps, melts, issuance, and acceptance must not operate concurrently on
the same wallet snapshot. Acorn uses two complementary controls:

- a process-local mutex keyed by wallet public key serializes concurrent web,
  service-worker, and component calls within one process; and
- an encrypted relay-backed owned lease coordinates independent Acorn
  instances using the same wallet.

The lease contains a random ownership token and an expiry. A caller releases
only the lease it owns. Another operation must not clear a live lease merely
because a mint or relay call takes longer than expected. Legacy boolean locks,
which had neither ownership nor expiry, are migrated into this owned-lease
model.

The relay lease reduces accidental concurrent mutation but does not turn an
eventually consistent relay into a transactional database. Multi-device and
partitioned-relay behavior therefore remains a release-hardening concern.

### Replication needs verification

Replication should eventually support a verify step that confirms target relay
visibility after publish.

## Possible future improvements

### Proof state epochs

Acorn could publish an encrypted proof-state epoch marker. A relay reader could
prefer the latest epoch and ignore older proof events.

### Latest proof-state pointer

Acorn could maintain a small encrypted reserved record pointing to the latest
valid proof event IDs.

### Relay comparison command

A future command could compare source and target relay event sets:

```sh
acorn relay-diff --source relay-a --target relay-b
```

### Dry-run repair

`repair-proofs` could support:

```sh
acorn repair-proofs --dry-run
```

to report what would be dropped without rewriting state.

### Guided migration command

A future wizard could combine:

1. replicate;
2. verify target;
3. switch home relay;
4. verify balance;
5. optionally replicate proof updates back.

## Operational rule of thumb

When in doubt:

```text
replicate events;
trust the mint for spend state;
allow mutating operations to remove mint-confirmed spent proofs;
use repair-proofs for an explicit whole-wallet refresh;
verify balance before spending again.
```
