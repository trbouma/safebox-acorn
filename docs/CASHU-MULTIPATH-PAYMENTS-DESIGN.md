# Cashu Multipath Payments

## Status

Proposed for implementation.

This note defines how Acorn should implement Cashu
[NUT-15 partial multipath payments](https://github.com/cashubtc/nuts/blob/main/15.md)
without weakening its existing proof-persistence and Lightning melt recovery
guarantees.

The current code contains an older, disabled MPP prototype. That code is useful
as evidence of the intended product behavior, but it must not be enabled as
written. The implementation should be rebuilt as a grouped extension of the
current durable melt workflow.

## User outcome

An Acorn may hold spendable cash across several Cashu mints. A Lightning
invoice can exceed the balance held at any one mint even though the combined
balance is sufficient.

With multipath payments, Acorn can ask several compatible mints to pay partial
amounts of the same Lightning invoice. The receiving Lightning node combines
the partial payments. Lightning MPP is atomic at the receiver: the invoice is
settled only when all required parts arrive.

For example:

```text
Invoice                         1,000 sats
Safebox Mint spendable balance    650 sats
Minibits spendable balance         500 sats

No single mint can pay 1,000 sats.
The combined balances can pay it, subject to each mint's fees.
```

The normal `acorn pay` experience should eventually select MPP automatically
when no single compatible mint can cover the invoice and fees.

## Protocol basis

NUT-15 extends the normal NUT-05 melt quote request with an `options.mpp`
object:

```json
{
  "request": "lnbc...",
  "unit": "sat",
  "options": {
    "mpp": {
      "amount": 650000
    }
  }
}
```

The partial `amount` is expressed in **millisatoshis**, not satoshis. All
partial amounts across all participating mints must add up exactly to the
invoice amount in millisatoshis.

A mint is eligible only when its NUT-06 info response advertises NUT-15 for the
`bolt11` method and `sat` unit:

```json
{
  "nuts": {
    "15": {
      "methods": [
        {
          "method": "bolt11",
          "unit": "sat"
        }
      ]
    }
  }
}
```

The mint must also advertise an enabled NUT-05 `bolt11`/`sat` melt method.
Capability must be discovered from the mint; Acorn must not infer support from
software names or versions.

## Scope

The first implementation covers:

- fixed-amount BOLT11 invoices;
- whole-satoshi wallet balances and partial amounts;
- two or more independent Cashu mints;
- one or more spendable keysets at each mint;
- NUT-15 capability discovery;
- fee-aware path planning;
- concurrent melt submission;
- durable grouped recovery;
- one cash transaction-history entry for the complete payment; and
- explicit CLI diagnostics for planned, pending, failed, and inconsistent
  payment groups.

The first implementation does not cover:

- amountless invoices;
- sub-satoshi wallet accounting;
- Clear balances or CMUs;
- splitting a direct kind `7378` ecash transfer;
- moving proofs between mints before payment;
- non-BOLT11 payment methods;
- choosing mints based on exchange rates or non-`sat` units; or
- hiding from participating mints that they were asked to pay the same
  invoice.

## Core invariants

MPP must preserve the same bearer-fund safety properties as a single-mint
melt.

### Exact invoice allocation

```text
sum(path.partial_amount_msat) == invoice.amount_msat
```

The first implementation should require the invoice amount to be an exact
number of satoshis and allocate whole-satoshi parts:

```text
path.partial_amount_msat == path.partial_amount_sat * 1000
```

This avoids silently truncating or rounding an invoice.

### Group by mint, not keyset

A payment path is a mint. A keyset identifies proofs and signing keys within a
mint; it is not an independent Lightning node.

Acorn must first group spendable proofs by normalized mint URL. If one mint has
proofs in several keysets, Acorn may combine or swap those proofs into outputs
signed by that mint's active `sat` keyset.

### Prepare before submitting

Before any melt request is submitted, Acorn must:

1. obtain all final partial melt quotes;
2. prepare exact spend proofs and change for every path;
3. persist the complete post-swap wallet proof state;
4. write the complete grouped pending-melt journal; and
5. verify journal readback from the home relay.

No mint may receive a melt submission until all paths have crossed this
durability barrier.

### Submit each quote at most once

Each path's `POST /v1/melt/bolt11` is sent at most once. A timeout,
disconnect, HTTP error, or `PENDING` response is followed only by:

```http
GET /v1/melt/quote/bolt11/{quote}
```

Acorn must never create a replacement payment group merely because one path's
outcome is unknown.

### Inspect every concurrent result

Concurrent execution may use `asyncio.gather(..., return_exceptions=True)` so
that one failed task does not cancel observation of the other paths. Acorn must
inspect and persist every returned result or exception. Exceptions must never
be silently discarded.

### One logical cash transaction

An MPP group pays one invoice. Transaction history should contain one debit for
the total invoice amount and aggregate fees, not one user-visible payment for
each mint path.

## Capability discovery

Acorn should add a small capability layer that:

1. normalizes the mint URL;
2. retrieves `GET /v1/info`;
3. verifies NUT-05 `bolt11`/`sat` melting is enabled;
4. verifies NUT-15 `bolt11`/`sat` support;
5. captures method minimum and maximum amounts when advertised; and
6. returns a typed capability result with a useful rejection reason.

Capability responses may be cached briefly for planning, but they must be
revalidated for a new payment after a cache expiry. A stale positive capability
must produce a pre-submission planning failure, not a fallback to an
unadvertised protocol.

## Balance model

The current `_proofs_by_keyset()` representation remains useful for proof
operations. MPP planning also needs a mint-level view:

```text
mint URL
  keysets
    proofs
  total spendable amount
  active sat keyset
  input fee policy
  NUT-15 capability
```

Only cryptographically compatible, mint-confirmed spendable proofs may enter
the planner. Pending incoming transfers, incompatible historical proofs,
reserved outgoing proofs, and unresolved melt proofs are excluded.

## Planning

Planning is a read-only operation until a complete feasible allocation has
been found.

### Inputs

The planner receives:

- the BOLT11 invoice and decoded amount in millisatoshis;
- the payment hash and description hash;
- eligible mint balances;
- mint capabilities and method limits;
- keyset input fees;
- the payment comment and tender context; and
- an optional policy limiting or preferring mints.

### Path allocation

The planner should prefer fewer mints because every additional path adds a fee
reserve, another failure surface, and more privacy exposure.

A conservative initial strategy is:

1. try the existing single-mint path, including fees;
2. sort eligible mints by usable balance descending;
3. select the smallest set whose estimated net capacities cover the invoice;
4. allocate whole-satoshi partial amounts across those mints;
5. request an MPP melt quote for each proposed partial amount;
6. reduce a path if its amount plus fees exceeds its available balance;
7. reallocate the difference to another eligible path; and
8. request final quotes until allocation and quoted fees converge or a bounded
   retry limit is reached.

Unused exploratory quotes do not spend proofs. Their identifiers should be
retained in debug logs but must not enter the pending-melt journal.

### Fee calculation

For each path, available proofs must cover at least:

```text
partial invoice amount
+ melt fee reserve
+ applicable keyset input fee
```

Swap input fees required to create exact melt inputs must also be included in
proof preparation. The planner must not assume that `fee_reserve` includes
NUT-02 input fees.

The initial implementation may preserve Acorn's existing conservative handling
of fee reserves. NUT-08 change-output support can later return unused fee
reserve, but MPP must not report an estimated reserve as an exact fee when the
mint returns authoritative fee or change information.

### Plan result

The planner should return a structured object similar to:

```json
{
  "invoice_amount_msat": 1000000,
  "invoice_amount_sat": 1000,
  "payment_hash": "...",
  "paths": [
    {
      "mint": "https://mint.getsafebox.app",
      "partial_amount_msat": 600000,
      "partial_amount_sat": 600,
      "fee_reserve_sat": 2,
      "spend_amount_sat": 602,
      "quote": "..."
    },
    {
      "mint": "https://mint.minibits.cash/Bitcoin",
      "partial_amount_msat": 400000,
      "partial_amount_sat": 400,
      "fee_reserve_sat": 2,
      "spend_amount_sat": 402,
      "quote": "..."
    }
  ]
}
```

No proof secrets should appear in plan output or logs.

## Proof preparation

After planning succeeds, Acorn acquires the wallet mutation lock and repeats
the usual preflight checks:

- reconcile mint-confirmed spent proofs;
- require all older pending melts to be resolved;
- verify relay proof persistence is available; and
- reload balances before committing the plan.

If balances or capabilities changed, Acorn discards the plan and starts a new
planning pass before any melt submission.

For each mint path, Acorn then:

1. selects sufficient proofs across that mint's keysets;
2. checks proof states with their mint;
3. swaps as required into the exact path spend amount plus retained change;
4. uses the mint's active `sat` keyset for new outputs;
5. uses only standard Cashu wire fields for blinded outputs;
6. records canonical proof `Y` values for the melt inputs; and
7. updates the in-memory post-swap wallet state.

Proof preparation may proceed sequentially while holding the wallet lock.
Melt submission must wait until all prepared state has been persisted.

## Grouped recovery journal

The existing encrypted `pending_melts` journal already stores a list and can
represent several quotes. MPP requires explicit grouping and an atomic group
write.

Each path entry should include:

```json
{
  "operation": "multipath_melt",
  "group_id": "mpp:<payment-hash>:<random-id>",
  "path_index": 0,
  "path_count": 2,
  "quote": "...",
  "mint": "https://mint.example",
  "keysets": ["..."],
  "spend_ys": ["..."],
  "partial_amount_msat": 600000,
  "partial_amount_sat": 600,
  "invoice_amount_msat": 1000000,
  "invoice_amount_sat": 1000,
  "fee_reserve": 2,
  "invoice": "lnbc...",
  "payment_hash": "...",
  "invoice_description_hash": "...",
  "comment": "...",
  "created_at": 1780000000
}
```

The journal stores proof identifiers, never proof secrets.

Acorn should add a group upsert operation that writes all path entries in one
replaceable-record update and verifies exact readback. Repeated per-path
upserts are not sufficient because a process exit between writes could leave
an incomplete recovery description.

## Concurrent execution

Once proof and journal readback succeed, Acorn submits every path concurrently.
Each task uses the existing submit-once behavior:

1. send the path's melt `POST` once;
2. accept `PAID` or `UNPAID` as terminal;
3. query the quote after ambiguous or `PENDING` responses; and
4. return a structured result or an unresolved outcome.

Acorn waits for all path tasks to return or reach the bounded recovery window.
It then evaluates the group state.

## Group states

| Path results | Group state | Wallet action |
| --- | --- | --- |
| Every path `PAID` | `PAID` | Remove every submitted proof, persist remaining proofs, write one cash debit, remove the group journal. |
| Every path `UNPAID` | `UNPAID` | Retain all prepared proofs and remove the group journal. |
| Any path `PENDING` or `UNKNOWN` | `PENDING` | Keep the complete group journal and block another spend. |
| Terminal mix of `PAID` and `UNPAID` | `INCONSISTENT` | Preserve evidence, remove only mint-confirmed spent proofs, block another spend, and require reconciliation or operator review. |

A temporary mix of `UNPAID` and `PENDING` is still pending because the
remaining paths may settle to `UNPAID`. A terminal `PAID`/`UNPAID` mixture
violates the expected atomic outcome and must never be presented as success.

## Reconciliation

`acorn reconcile-payments` should group journal entries by `group_id` and query
every unresolved path. Reconciliation must be idempotent across restarts.

For a successful group:

1. remove all path spend proofs from local proof state;
2. persist the remaining proof state;
3. write one transaction-history debit using a group marker such as
   `cashu-mpp:<group-id>`;
4. aggregate authoritative fees across paths;
5. include the invoice payment hash and available preimage evidence; and
6. remove every journal entry in the group atomically.

If individual mints return the same preimage, Acorn may retain one copy. A
missing preimage from one mint must not override authoritative `PAID` quote
states from all paths.

Legacy single-mint journal entries without `group_id` continue through the
existing reconciliation path.

## Transaction history

One completed MPP group produces one Cash Transaction:

```text
type: debit
amount: full invoice amount in sats
fees: aggregate actual fee or conservative reserve
invoice: original BOLT11 invoice
payment_hash: invoice payment hash
description_hash: cashu-mpp:<group-id>
comment: user payment comment
```

Mint-path details are operational metadata, not separate user payments. A
structured diagnostic view may show the participating mints, partial amounts,
quotes, and fees without duplicating transaction history.

## CLI and component behavior

The mature behavior should remain simple:

```sh
acorn pay 1000 recipient@example.com
```

Acorn first attempts a single-mint payment. If no one mint can cover amount and
fees, it may automatically plan MPP across compatible mints.

During initial development, an explicit opt-in is preferable:

```sh
acorn pay 1000 recipient@example.com --multipath
```

Useful diagnostic modes are:

```sh
acorn pay 1000 recipient@example.com --multipath --preview
acorn reconcile-payments
acorn reconcile-payments --json
```

`--preview` must stop before proof swaps, journal writes, or melt submissions.
It should show proposed mint paths, partial amounts, fee reserves, and total
required balance.

The Python component should return structured path and group results while the
CLI formats them for people.

## Privacy and trust considerations

MPP reveals the same invoice and payment hash to every participating mint.
Those mints may correlate timing, amount, destination routing information, and
wallet behavior. Using fewer paths reduces this exposure.

MPP does not combine mint trust. Each proof remains a liability of its mint,
and each mint remains authoritative for its quote and proof state. A wallet
must not present aggregate cash balance as though every mint has identical
availability, policy, or reliability.

The coordinator also increases operational exposure: one unavailable mint can
leave the entire payment group unresolved. The wallet must make this tradeoff
visible in diagnostics and preserve all recovery evidence.

## Existing code disposition

The disabled MPP branch in `Acorn.pay_multi()` demonstrates the earlier intent
but has known incompatibilities:

- it is bypassed by an unconditional "not implemented" error;
- it treats keysets as independent payment paths;
- it sends NUT-15 partial amounts in sats instead of millisats;
- it does not verify NUT-15 mint capabilities;
- its fee allocation is provisional;
- it does not durably journal the complete group before submission;
- it ignores exceptions returned by concurrent tasks; and
- it does not reconcile the paths into one payment history entry.

Implementation should replace this branch and its `_multi_melt()`,
`_do_mpp_requests()`, and `_post_request()` helpers after equivalent behavior
is covered by the new planner and grouped state machine.

## Prerequisites

Before live MPP execution is enabled:

1. every swap and mint path must select an active output keyset for the
   requested unit instead of selecting the first advertised keyset;
2. wallet-only proof fields such as cached `Y` values must not be sent as
   blinded-message wire fields;
3. mint-level balance grouping must be implemented and tested;
4. the grouped journal write and readback barrier must exist; and
5. single-mint payment and recovery tests must continue to pass unchanged.

## Implementation phases

### Phase 1: Capability and planner

- Add typed NUT-05 and NUT-15 capability discovery.
- Add spendable balances grouped by normalized mint URL.
- Decode invoice amounts without truncation.
- Build fee-aware whole-satoshi MPP plans.
- Add `--multipath --preview` with deterministic tests.
- Do not mutate or spend proofs.

### Phase 2: Preparation and grouped journal

- Fix active-keyset selection in all swap paths.
- Prepare exact inputs and change per mint.
- Persist the complete post-swap proof state.
- Atomically write and verify the full MPP journal group.
- Add crash tests at every durability boundary.

### Phase 3: Concurrent execution and recovery

- Submit every melt exactly once and concurrently.
- Inspect every path result.
- Reconcile grouped quote states across restarts.
- Finalize one transaction-history entry.
- Expose pending and inconsistent group diagnostics.

### Phase 4: Controlled live testing

- Use disposable wallets and very small balances.
- Fund at least two independently implemented NUT-15 mints.
- Pay a controlled BOLT11 invoice that supports MPP.
- Exercise successful, rejected, timed-out, and restarted flows.
- Verify balances and proof states directly with every mint.
- Keep automatic MPP disabled until the live matrix is repeatable.

### Phase 5: Default wallet behavior

- Enable automatic MPP when no single mint can cover the payment.
- Retain an option to require a single mint.
- Add Safebox Web progress and recovery presentation.
- Document privacy, fee, and availability tradeoffs for users.

## Test plan

Deterministic tests must cover:

- exact conversion of satoshi parts to NUT-15 millisatoshi amounts;
- rejection of fractional-satoshi invoices in the first implementation;
- capability acceptance and rejection from NUT-06 responses;
- multiple keysets at one mint producing one path;
- two mints with enough combined net balance;
- combined gross balance that becomes insufficient after fees;
- mint minimum and maximum method amounts;
- allocation requiring a quote adjustment after fee discovery;
- planner preference for the smallest number of paths;
- active-keyset selection during swaps;
- exact grouped journal readback before submission;
- no melt submission after any preparation or journal failure;
- concurrent submission with all paths `PAID`;
- all paths `UNPAID`;
- one timeout followed by quote-query recovery;
- process exit after one or more requests were submitted;
- temporary mixed pending states;
- terminal inconsistent states;
- no repeated melt `POST` during recovery;
- one idempotent transaction-history entry; and
- unchanged single-mint payment behavior.

Live tests should be explicitly enabled because they spend sats and depend on
external Lightning and mint infrastructure. Test logs must record mint URLs,
quote IDs, group IDs, states, and amounts without recording proof secrets,
private keys, or complete bearer tokens.

## Acceptance criteria

MPP is ready for opt-in use when:

- a preview produces an exact, fee-aware plan across at least two mints;
- both melt quote requests use NUT-15 millisatoshi amounts;
- all prepared proof and journal state survives a forced process exit;
- each melt quote is submitted no more than once;
- restart reconciliation reaches the same final wallet state as uninterrupted
  execution;
- a successful payment writes exactly one Cash Transaction;
- failed payments retain spendable proofs;
- unresolved or inconsistent payments block further proof mutation; and
- deterministic and controlled live tests pass across two independently
  implemented NUT-15 mints.

## Related documents

- [Lightning Melt Recovery](LIGHTNING-MELT-RECOVERY.md)
- [Proof State and Relay Consistency](PROOF-STATE-RELAY-CONSISTENCY.md)
- [Fund Safety Hardening Milestone](FUND-SAFETY-HARDENING-MILESTONE-2026-08-13.md)
- [Acorn Lightning-Address Gateway Design](ACORN-LIGHTNING-ADDRESS-GATEWAY-DESIGN.md)
- [Cashu NUT-05: Melting tokens](https://github.com/cashubtc/nuts/blob/main/05.md)
- [Cashu NUT-15: Partial multipath payments](https://github.com/cashubtc/nuts/blob/main/15.md)
