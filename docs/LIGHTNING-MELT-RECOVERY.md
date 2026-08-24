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

Acorn submits a particular melt exactly once. A timeout, disconnect, server
error, or `PENDING` response is followed only by:

```http
GET /v1/melt/quote/bolt11/{quote}
```

The original melt `POST` is not repeated.

A mint HTTP 4xx response is a definitive request rejection, not an ambiguous
Lightning outcome. Acorn reports its status and response body and does not
misclassify an unchanged `UNPAID` quote as a Lightning routing failure.

## Fee-aware melt inputs

A fee-charging mint can apply two distinct NUT-02 input fees during payment:

1. the fee charged when wallet proofs are swapped into payment and change
   proofs; and
2. the fee charged when the newly created payment proofs become inputs to the
   final melt.

The melt quote's Lightning `fee_reserve` does not include the second fee.
Acorn therefore prepares melt inputs sufficient for:

```text
invoice amount + Lightning fee reserve + melt proof-input fee
```

The melt proof-input fee depends on how many binary-denomination proofs
represent that total. Acorn calculates the smallest proof total whose value
after `input_fee_ppk` covers the invoice and Lightning reserve. This preserves
compatibility with zero-fee mints while preventing fee-charging mints from
rejecting an otherwise valid melt as underfunded.

## Returning unused Lightning reserve

When a mint advertises NUT-08, Acorn does not treat the quoted Lightning fee
reserve as the final routing fee. It creates the required blank blinded
outputs, includes them in the melt request, and unblinds any `change` returned
by the mint after payment. Those recovered proofs are restored to the wallet.

The resulting accounting is:

```text
actual Lightning fee = quoted fee reserve - returned change
actual total fee = mint input fees + actual Lightning fee
```

If the mint does not advertise NUT-08, the conservative outcome remains in
effect: no fee change can be requested, so the full reserve may be retained by
the mint. Acorn reports the reserve separately from mint fees so this remains
visible rather than presenting it as a measured route fee.

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
transaction-history context. When NUT-08 is used, it also stores the randomly
generated secrets and blinding factors needed to recover the returned change.
This material is inside the same encrypted private record and is written and
verified on the relay before the melt is submitted. It is removed with the
journal after terminal finalization.

Persisting the post-swap proofs before submission means a restarted Acorn can
identify and remove the submitted proofs after a confirmed payment, or retain
them after a confirmed failure.

## State handling

| Mint state | Acorn action |
| --- | --- |
| `PAID` | Remove submitted proofs, recover and persist any NUT-08 fee-change proofs, write debit history using the actual fee, and remove the journal entry. |
| `UNPAID` | Keep the post-swap proofs, write an idempotent error entry to transaction history, record any preparatory swap fee that was actually consumed, and remove the journal entry. |
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
- a definitive HTTP 400 rejection whose mint response remains visible;
- nonzero `input_fee_ppk` melt totals, including denomination boundaries;
- restart recovery of a `PAID` melt;
- restart recovery of an `UNPAID` melt.

## Failure history and fee truthfulness

A failed payment is not necessarily a zero-cost attempt. Preparing exact melt
inputs can require a proof swap, and that swap may consume the keyset's
`input_fee_ppk` even when the Lightning melt is later rejected or confirmed
`UNPAID`. Acorn therefore writes a kind `7377` advisory (`tx_type="X"`) for a
terminal failure. It records the requested amount as context, the current
post-attempt balance, and only the preparatory swap fee known to have been
consumed. The payment value, final melt-input fee, and Lightning fee reserve
are not reported as spent when the mint confirms `UNPAID`.

The failure marker is keyed by melt quote, making reconciliation idempotent
after a restart. An unknown or pending outcome remains in the encrypted
pending-melt journal and must not be labelled as a confirmed failure. An
application may add a separate review advisory, but eventual `PAID` or
`UNPAID` reconciliation remains authoritative.

The tests assert that the melt `POST` occurs at most once. Live Lightning tests
remain opt-in because they spend sats and depend on external mint and Lightning
infrastructure.

The independent-mint failure that prompted this accounting work and its live
verification are recorded in the
[Mint-Fee Interoperability Milestone](MINT-FEE-INTEROPERABILITY-MILESTONE-2026-08-24.md).
