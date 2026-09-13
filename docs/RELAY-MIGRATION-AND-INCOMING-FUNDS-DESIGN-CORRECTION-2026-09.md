# Relay Migration and Incoming Funds Design Correction

**Status:** Implemented architectural correction  
**Date:** September 2026  
**Applies to:** Safebox Acorn receive processing and Safebox Web handle routing

## Why this note exists

Testing an independently deployed Safebox Web instance exposed several related
design defects rather than one isolated operational error. A Lightning payment
could settle successfully, the provider could create and publish the resulting
ecash transfer, and the intended Acorn could still fail to show it because the
provider and receiver were using different relay routes.

The confirmed wallet balance was not lost in the observed incident. Historical
delivery events were found on the older relay. Replaying them exposed a second
problem: tokens conclusively reported spent by their mint were being treated as
temporary failures and left in the user interface as pending funds.

These findings required changes to the routing, checkpoint, idempotency, and
failure-classification model. This note records the defects and the corrected
invariants so later work does not accidentally reintroduce them.

## What happened

The affected handle still had its older `home_relay` in the Safebox Web
directory. The Acorn session and public relay hints had moved to a newer relay.
Provider payments therefore used the valid but stale directory route captured
when their invoices were created.

An ordinary receive scan on the old relay found no new events because Acorn had
one wallet-wide receive checkpoint. That checkpoint had advanced while scanning
the newer relay and incorrectly implied that the same point had been reached on
the older relay. An explicit historical scan found four transfer events.

The four bearer tokens were already spent. That can mean they were previously
accepted by this or another wallet instance, duplicated, replayed, or otherwise
consumed. The mint response was conclusive, but first-pass receive processing
classified all acceptance exceptions as retryable. The events consequently
appeared as pending even though retrying could never make those proofs unspent.

## Original design defects

### 1. A mutable route was treated as durable registration data

The NIP-05 handle mapping correctly bound a public name to an Acorn public key,
but it also stored a delivery relay. The route was refreshed only when the user
explicitly re-submitted the handle form. Moving an Acorn did not therefore move
its provider delivery route as part of ordinary authenticated use.

### 2. One checkpoint represented several independent relay streams

A `(created_at, event_id)` checkpoint is stable within one observed stream. It
is not a proof that every other relay has supplied all earlier events. Using one
wallet-wide checkpoint across changing relay selections allowed activity seen on
one relay to hide older activity available on another.

### 3. Retryability was inferred from the stage, not the evidence

The receive path treated any mint acceptance exception as temporary. A timeout
is temporary; a conclusive mint response that the proofs are already spent is
terminal. Collapsing those states caused impossible work to remain pending and
weakened the meaning of the pending balance.

### 4. Delivery, receipt, and settlement identities were not used together

The Nostr event ID identifies delivery. The Cashu proofs and mint identify the
bearer instrument and its spend state. The transaction-history marker identifies
whether this Acorn already credited that event. Correct reconciliation requires
all three; no single one is sufficient.

## Corrected design invariants

### Authenticated routing refresh

Safebox Web now refreshes a claimed handle's `home_relay` when that authenticated
Acorn opens its wallet or handle page. The browser cannot submit an arbitrary
public key or route for this operation: both come from the Acorn established by
the encrypted session.

New provider-payment requests use the refreshed route. Existing invoice rows
retain the public key and relay captured when the request was created. Keeping
that snapshot makes the original delivery decision auditable and prevents a
route change from silently altering an in-flight payment contract.

### Receiver-and-relay-set-scoped checkpoints

Cash and Clear receive checkpoints now include:

- the transfer family;
- the receiving key scope; and
- a stable digest of the normalized selected relay set.

Selecting a new relay set therefore starts a bounded historical scan instead of
inheriting an unrelated later checkpoint. Checkpoints remain encrypted Acorn
kind `37376` records on relays. No local wallet journal or application-owned
proof state has been introduced.

### Event-ID idempotency

Historical rescanning is expected and must be safe. Acorn stores receipts by
delivery event ID and uses stable transaction-history markers:

- `cashu-receipt:<event-id>` for a credited transfer; and
- `cashu-receipt-error:<event-id>` for an unexplained terminal spent transfer.

A receipt already marked `mint-confirmed`, terminal, or deleted is not accepted
again. Rescanning cannot legitimately create a second credit for the same event.

### Evidence-based failure classification

The receive path now distinguishes:

- **confirmed replay:** the mint says spent and the successful event marker
  exists; restore confirmed receipt status, add no credit, and add no error;
- **terminal spent transfer:** the mint says spent and no successful marker
  exists; retire the token, write one type `X` audit entry, and advance;
- **terminal malformed event:** journal the structural error and advance; and
- **retryable operational failure:** retain the receipt and token as pending,
  without advancing past an event whose safe disposition was not persisted.

“Pending” now means that another attempt could still produce a valid outcome.
It no longer means merely that some earlier operation raised an exception.

## Upgrade and migration behaviour

The first receive operation after upgrading may scan older events because the
new scoped checkpoint does not reuse the former wallet-wide label. This is a
one-time safety cost for each receiver and relay-set combination.

Operators should expect the first scan to:

1. query historical transfer pages up to the configured bounds;
2. skip receipts already resolved by event ID;
3. reconcile provisional receipts with their issuing mints;
4. retire conclusive unexplained spent replays; and
5. write the new scoped checkpoint only after each event has a durable outcome.

For Safebox Web, an affected user should connect the Acorn and open `/wallet` or
`/handle` once after deployment. That authenticated request refreshes the local
handle route for future provider invoices. Previously created invoice rows keep
their original route and may require scanning that earlier relay.

## Security and trust consequences

The directory operator remains trusted to serve the correct handle mapping and
route provider requests. The reverse proxy and domain operator remain part of
that public assertion path. The correction does not turn NIP-05 into independent
identity proof.

The Acorn kernel does not trust directory routing as proof of payment. Relay
delivery creates only a provisional receipt. Spendable balance changes only
after the issuing mint validates and refreshes the bearer proofs and Acorn
persists the resulting relay-backed state.

No recovery action should prune or credit a token merely because its delivery
event exists. Likewise, a mint's spent response must not be interpreted as proof
that this particular Acorn received value unless the event-ID success marker is
also present.

## Residual risks and follow-up

- A provider invoice intentionally snapshots its route. If the Acorn moves
  before delivery, the recipient may need to inspect the earlier relay.
- A relay can accept a historically timestamped event after a scoped checkpoint
  has passed it. Ordinary forward scans cannot prove the absence of arbitrarily
  late backfilled events; periodic bounded overlap or an explicit historical
  scan remains the recovery mechanism.
- A new relay set can contain a large backlog. Pagination bounds fail safely but
  may require several operator-visible attempts or adjusted limits.
- Transaction history and receipt journals still require future compaction and
  indexed lookup as their size grows.
- Concurrent writers still require effective Acorn locking and a single-writer
  policy for each mutation boundary.

These are explicit availability and scaling limits. They do not justify making
local application storage authoritative for Acorn proofs or records.

## Verification

The correction is covered by tests that establish:

- cursor labels are stable across relay ordering and change with the relay set;
- a mint-confirmed receipt is skipped during a historical replay;
- a conclusive unexplained spent token becomes terminal rather than pending;
- an existing successful event marker restores confirmed status without a
  duplicate credit or error; and
- authenticated Safebox Web wallet access refreshes a stale handle route.

At implementation time, the full suites passed with 340 Safebox Acorn tests and
457 Safebox Web tests.

## Related documents

- [Incoming Funds Reliability and Scaling](INCOMING-FUNDS-RELIABILITY-AND-SCALING.md)
- [Relay Migration Runbook](RELAY-MIGRATION-RUNBOOK.md)
- [Relay Resilience and Replication Design](RELAY-RESILIENCE-AND-REPLICATION-DESIGN.md)
- [Proof State and Relay Consistency](PROOF-STATE-RELAY-CONSISTENCY.md)
- [Safebox Web NIP-05 Handle Directory](https://github.com/trbouma/safebox-web/blob/main/docs/NIP-05-HANDLE-DIRECTORY.md)
