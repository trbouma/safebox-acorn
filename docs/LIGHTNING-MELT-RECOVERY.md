# Lightning Melt Recovery

## Summary

A Lightning payment can reach the mint even when the client times out before
receiving the response. Acorn must therefore distinguish a confirmed failure
from an unknown outcome. Retrying an unknown melt as a new payment can pay the
recipient twice.

Acorn uses a durable, encrypted pending-melt journal and idempotent quote
queries to resolve this ambiguity.

## Safety invariant

After a melt request has been submitted:

```text
no response != payment failure
```

Acorn submits a particular melt exactly once. A timeout, disconnect, HTTP
error, or `PENDING` response is followed only by:

```http
GET /v1/melt/quote/bolt11/{quote}
```

The original melt `POST` is not repeated.

## Durable ordering

For a single-mint Lightning payment, Acorn performs these operations:

1. obtain the Lightning invoice and mint melt quote;
2. swap selected wallet proofs into the exact payment amount and change;
3. persist all post-swap proofs to the home relay;
4. write an encrypted `pending_melts` journal entry;
5. submit the melt once;
6. classify the response or query the melt quote;
7. finalize according to the terminal state.

The journal is a parameterized replaceable private record. It stores the quote,
mint, keyset, submitted proof `Y` values, amount, fee reserve, invoice, and
transaction-history context. It does not store proof secrets.

Persisting the post-swap proofs before submission means a restarted Acorn can
identify and remove the submitted proofs after a confirmed payment, or retain
them after a confirmed failure.

## State handling

| Mint state | Acorn action |
| --- | --- |
| `PAID` | Remove submitted proofs, persist the remaining proofs, write debit history, and remove the journal entry. |
| `UNPAID` | Keep the post-swap proofs and remove the journal entry. |
| `PENDING` | Keep the journal and refuse another spend until rechecked. |
| `UNKNOWN` or unreachable | Keep the journal and refuse another spend until rechecked. |

Transaction history uses `cashu-melt:{quote}` as an idempotency marker. Restart
recovery checks this marker before writing another debit entry.

## Operator recovery

Reconciliation runs automatically before another Lightning payment or
proof-mutating operation. It can also be requested explicitly:

```sh
acorn reconcile-payments
acorn reconcile-payments --json
```

Example unresolved result:

```text
Lightning payment reconciliation
Paid and finalized: 0
Confirmed unpaid: 0
Still unresolved: 1
- quote-id: PENDING
Do not retry unresolved payments; run this command again later.
```

An unresolved result is not a failed payment. The operator should wait and run
the reconciliation command again. The recipient and mint may also provide
independent evidence, but the mint quote remains authoritative for Acorn proof
finalization.

## Failure messages

Acorn distinguishes these cases:

- **confirmed success:** payment and local proof state are finalized;
- **confirmed failure:** the mint reports `UNPAID`, so the retained proofs can
  be used again;
- **outcome unknown:** do not retry or spend; the pending journal remains;
- **finalization incomplete:** the mint reports `PAID`, but proof or history
  persistence failed; do not retry, and resume reconciliation after restart.

The CLI returns these messages as command errors rather than printing a vague
success-status line.

## Test coverage

Deterministic unit tests cover:

- a timed-out melt that later becomes `PAID`;
- a melt that remains `PENDING` through the recovery window;
- a definitive `UNPAID` response;
- restart recovery of a `PAID` melt;
- restart recovery of an `UNPAID` melt.

The tests assert that the melt `POST` occurs at most once. Live Lightning tests
remain opt-in because they spend sats and depend on external mint and Lightning
infrastructure.

