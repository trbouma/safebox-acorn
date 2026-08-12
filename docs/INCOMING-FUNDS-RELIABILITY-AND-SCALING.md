# Incoming Funds Reliability and Scaling

## Summary

Acorn treats relay delivery, receipt persistence, mint finalization, proof
storage, transaction history, and cursor advancement as separate operations.
The receive path is designed to continue past conclusively malformed or spent
messages without allowing temporary infrastructure failures to silently lose
valid funds.

The principal ordering mechanism is a versioned `(created_at, event_id)`
checkpoint combined with paginated, overlapping relay queries.

## Processing invariants

The incoming-funds path follows these rules:

1. Relay events are deduplicated by event ID.
2. Events are ordered by `(created_at, event_id)`.
3. A valid bearer token is stored in the encrypted continuity-receipt journal
   before its event is eligible for checkpoint advancement.
4. Mint finalization happens after provisional receipt storage.
5. A malformed event advances the checkpoint only after an idempotent type `X`
   transaction-history entry has been written.
6. A token conclusively reported already spent becomes a terminal receipt error
   and is not retried indefinitely.
7. Ambiguous mint, relay, lock, or persistence failures remain retryable.
8. Preview mode and explicit event-ID lookup do not alter the receive checkpoint.

The wallet balance changes only after the mint accepts and refreshes the
received proofs. Relay visibility alone is never treated as spendable balance.

## Checkpoint representation

The reserved kind `37376` record labelled `ecash_transfer_latest` contains:

```json
{
  "version": 2,
  "created_at": 1780000000,
  "event_id": "0123456789abcdef..."
}
```

The event ID resolves ties between events created during the same second.
Earlier integer-only cursor values remain readable. A legacy value represents
the entire recorded second as processed, matching the behavior of earlier
releases that resumed at `timestamp + 1`.

Transient receive keys use a separate label suffixed by their public key, so
their checkpoints do not overwrite the wallet's normal receive position.

## Pagination

Acorn takes a snapshot timestamp when a receive operation begins and queries
backwards using Nostr `until`. Each subsequent page includes the oldest second
from the previous page. This overlap is intentional: it prevents events at a
page boundary from being discarded merely because several events share that
timestamp. Duplicate event IDs are removed before processing.

After collection, events newer than the stored checkpoint are processed from
oldest to newest. This lets Acorn persist the greatest contiguous safe
checkpoint even if a later event encounters an operational failure.

`limit` controls the relay page size. `max_pages` bounds the amount of work in
one receive call. Reaching `max_pages` is a safe failure: no newly collected
events are processed and the stored checkpoint is unchanged.

## Same-second saturation

NIP-01 filters do not provide an event-ID range cursor. If a relay repeatedly
returns a full page consisting of the same timestamp, Acorn cannot prove that
it has observed every event from that second. It therefore stops with a
`saturated same-second page` error and does not advance the checkpoint.

Operators can respond by increasing the page `limit`, querying another relay,
or investigating targeted message spam. This condition should be monitored; it
may indicate either unusually high legitimate volume or denial-of-service
traffic directed at the recipient public key.

## Failure classification

### Terminal event failures

Invalid encryption, invalid JSON, malformed Cashu tokens, missing tokens, and
proof/amount mismatches are structurally terminal. Acorn writes an idempotent
error transaction, credits no balance, and continues.

### Terminal mint failures

A conclusive Cashu `11001` response means the token is already spent. Acorn
records an error, removes the bearer token from the pending receipt, and moves
on. The error may mean a replay, a duplicate delivery, or funds accepted through
another wallet instance.

### Retryable operational failures

Timeouts, unreachable relays or mints, unknown keysets, pending mint states,
lock failures, and failed journal writes remain retryable. Acorn does not move
the checkpoint past an event whose safe disposition could not be persisted.

## Scaling limits and follow-up work

The checkpoint and pagination changes remove the immediate timestamp and
single-page backlog risks, but they do not make every data structure unbounded:

- continuity receipts are currently stored as a relay-backed JSON collection;
- idempotency checks may read transaction history before writing an error;
- transaction history and terminal-error records grow over time;
- multiple processes must not independently mutate one Acorn without effective
  wallet locking and a single-writer policy; and
- changing relay pools can expose older events that precede the current
  checkpoint and therefore require an explicit replay or migration operation;
  and
- a relay that receives a historically timestamped event only after the
  checkpoint has passed that tuple cannot make it visible to an ordinary
  forward scan; explicit replay is required.

Future scaling work should introduce bounded receipt compaction, indexed
idempotency markers, metrics for page depth and terminal failures, and explicit
relay-migration checkpoint policy. Live testing should include large backlogs,
page-boundary timestamps, relay duplicates, injected malformed events, and
process interruption at each persistence boundary.
