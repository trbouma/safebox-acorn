# Acorn Clear Spendable Proof State Kinds 7380 and 7381 Design Note

## Status

Foundation implemented: encrypted event writing, strict loading, grouped
balances, append-only history, read-only CLI access, replication, and wallet
burn coverage. Receipt acceptance, mint refresh, recovery journaling, and
spending remain proposed.

Kind assignments `7380` and `7381` are provisional Acorn application kinds and
must be checked against the current Nostr kind registry before a stable release.

## Summary

Acorn already receives Clear transfers as NIP-59 kind `1059` gift wraps whose
inner event is kind `7379`. It validates the Clear token and stores it in the
separate `clear_receipts` pending journal. This note defines the next stage:
accepting a pending receipt into a spendable Clear balance without mixing Clear
proofs with the wallet's cash proofs.

```text
kind 1059  NIP-59 gift wrap
    -> kind 7379  incoming Clear transfer
    -> clear_receipts  pending inbox
    -> mint refresh
    -> kind 7380  spendable Clear proof state
    -> kind 7381  Clear transaction history
```

The proposed kinds are:

| Kind | Meaning |
| --- | --- |
| `7375` | Existing spendable cash/ecash proof state |
| `7377` | Existing Acorn cash transaction history |
| `7378` | Incoming cash/ecash transfer intent |
| `7379` | Incoming Clear transfer intent |
| `7380` | Proposed spendable Clear proof state |
| `7381` | Proposed Clear transaction history |

Kind `7379` remains delivery and inbox material. It never becomes durable
wallet proof state.

## Decision

Finalized Clear proofs will be stored in encrypted, owner-authored kind `7380`
events. Clear balance changes will be recorded in encrypted, owner-authored
kind `7381` events.

Clear proofs must not be merged into kind `7375`, even though the NIP-60 token
shape supports units other than `sat`. Existing Acorn cash code treats kind
`7375` as the cash wallet's spendable proof state. A separate kind provides a
hard boundary against:

- adding CMU amounts to a sats balance;
- selecting Clear proofs for a Lightning payment;
- refreshing Clear proofs against the cash mint;
- displaying unlike Clear balances as one amount; and
- deleting cash proof events during a Clear state transition.

This separation is an Acorn safety boundary, not a claim that kind `7375` is
incapable of representing another Cashu unit.

## Terminology

In this note:

- **pending receipt** means a validated kind `7379` token stored in
  `clear_receipts` but not yet accepted;
- **acceptance** or **finalization** means refreshing a pending token with its
  mint and durably storing the resulting spendable proofs;
- **Clear balance** means proofs sharing one exact `(mint, CMU)` identity;
- **CMU** means the canonical Clear Mint Unit string advertised by the mint;
  and
- **Clear transaction** means a balance-changing operation recorded separately
  from the cash transaction journal.

Friendly currency names and unit aliases are display metadata. They must never
be used as balance identifiers.

## Clear balance identity

The wallet groups Clear proofs by the exact pair:

```text
(normalized mint URL, canonical CMU)
```

Proofs remain partitioned by keyset ID inside that balance:

```text
Clear wallet
└── mint URL
    └── canonical CMU
        └── keyset ID
            └── spendable proofs
```

Amounts may be summed within one exact `(mint, CMU)` balance. Amounts from
different mints or CMUs must never be summed into a cross-currency total.

The mint URL stored in the token is authoritative for protocol operations.
Aliases fetched from `/v1/info` may label the balance but cannot change its
identity.

## Kind 7380: spendable Clear proof state

Kind `7380` is a regular, owner-authored encrypted event. It follows the useful
state-transition properties of a NIP-60 token event while remaining outside
Acorn's cash proof loader.

Example decrypted content:

```json
{
  "type": "clear-proof-state",
  "version": 1,
  "mint": "https://clear.safebox.dev",
  "unit": "cmu-000051c14ceac8ee",
  "proofs": [
    {
      "id": "016b09b41b6d290f...",
      "amount": 16,
      "secret": "...",
      "C": "..."
    }
  ],
  "del": ["previous-7380-event-id"],
  "source_receipts": ["clear-transfer-event-id"]
}
```

Required fields:

- `type` must be `clear-proof-state`;
- `version` starts at `1`;
- `mint` is the normalized mint URL;
- `unit` is the canonical CMU;
- `proofs` contains standard Cashu proofs for exactly that mint and CMU; and
- `del` lists superseded kind `7380` events when performing a rollover.

`source_receipts` is optional audit linkage. It contains identifiers, never
bearer tokens.

The entire payload must be NIP-44 encrypted to the wallet owner. Public tags
should not reveal the mint, CMU, amount, keyset, sender, or receipt identifiers.

An event must not contain proofs from more than one mint or CMU. Acorn may
publish multiple kind `7380` events for one balance and may include multiple
keysets in an event only when every keyset is valid for the same canonical
CMU.

## Kind 7381: Clear transaction history

Kind `7381` is an informational Clear journal. It is not proof state and cannot
be used to calculate a spendable balance.

Example decrypted content:

```json
{
  "type": "clear-transaction",
  "version": 1,
  "direction": "in",
  "operation": "accept",
  "amount": 25,
  "mint": "https://clear.safebox.dev",
  "unit": "cmu-000051c14ceac8ee",
  "memo": "Initial Clear Funding",
  "created": ["new-7380-event-id"],
  "destroyed": [],
  "source_event": "clear-transfer-event-id",
  "counterparty": "sender-pubkey"
}
```

Required fields identify the direction, operation, amount, mint, and canonical
CMU. Event references record which kind `7380` proof-state events were created
or superseded.

Supported initial operations should be:

- `accept`: pending incoming Clear transfer accepted into a balance;
- `send`: Clear proofs exported or delivered to another wallet;
- `receive`: reserved for a future direct finalized receive path;
- `retire`: proofs redeemed or retired without a recipient; and
- `repair`: wallet proof state changed by explicit reconciliation.

The content must be NIP-44 encrypted. Counterparty and memo fields are optional
and private. A missing kind `7381` event must not change the proof balance; kind
`7380` is authoritative.

## Acceptance workflow

`accept_clear_receipt(event_id)` should perform these steps under the wallet's
mutation lock:

1. Reload the pending receipt journal and current kind `7380` proof state.
2. Require exactly one pending receipt matching `event_id`.
3. Decode the stored token and repeat structural validation.
4. Require one mint and one canonical CMU.
5. Fetch the mint's current keysets and verify that every proof ID belongs to
   the advertised CMU.
6. Check or refresh the incoming proofs through that mint. Acceptance must not
   call the ordinary cash `accept_token` path.
7. Create one or more kind `7380` events containing the refreshed proofs.
8. Verify relay acknowledgement and exact read-back of the new proof state.
9. Publish a kind `7381` incoming `accept` history event.
10. Mark the pending receipt `accepted`, record resulting kind `7380` event
    IDs, and remove the embedded bearer token from the receipt journal.

After step 6, the incoming proofs may have been spent by the refresh. The
resulting output proofs are therefore the wallet's only funds. Acorn must not
report success or discard output material until the kind `7380` state is
durable.

## Acceptance recovery journal

Mint mutation and relay persistence cannot be one distributed transaction. A
crash after mint refresh but before kind `7380` publication could otherwise
lose the refreshed proofs.

Before beginning a refresh, Acorn should write an encrypted acceptance
operation record containing:

- a unique operation ID;
- the source receipt event ID;
- mint and canonical CMU;
- current phase;
- input proof references;
- prepared output secrets and blinded messages needed for recovery; and
- resulting proofs as soon as the mint returns them.

The operation phases should be:

```text
PREPARED
MINT_SUBMITTED
MINT_COMPLETE
PROOFS_PERSISTED
HISTORY_PERSISTED
RECEIPT_ACCEPTED
COMPLETE
RECOVERY_REQUIRED
```

The operation record belongs in encrypted operational metadata, not kind
`7380` or `7381`. It may use the existing kind `37376` operational record path
with a unique label such as `clear_acceptance:<operation-id>`.

Retrying an operation must be idempotent. Acorn must first inspect the
operation record, the receipt status, and referenced kind `7380` events before
contacting the mint again.

## Receipt state

The existing `clear_receipts` journal should support:

```text
pending
finalizing
accepted
rejected
recovery_required
```

An accepted receipt retains non-secret audit metadata:

- source event ID;
- sender public key;
- mint;
- canonical CMU;
- amount;
- memo;
- timestamp;
- source keyset IDs; and
- resulting kind `7380` event IDs.

It must not retain the original token or duplicate spendable proofs after the
kind `7380` state has been verified.

Rejected receipts may retain the encrypted token until the user explicitly
deletes or returns it. Rejecting a receipt must not spend its proofs.

## Spending and rollover

A Clear spend selects proofs from exactly one `(mint, CMU)` balance. It must
never select cash proofs or combine separate Clear balances.

When proofs are consumed:

1. select kind `7380` proof events for one balance;
2. perform a mint swap when exact denomination or change is required;
3. construct the outgoing Clear token;
4. persist any unspent proofs and change in new kind `7380` events;
5. publish kind `5` deletions for fully superseded kind `7380` events using a
   `k=7380` tag;
6. include superseded IDs in the new event's encrypted `del` field;
7. publish a kind `7381` outgoing `send` history event; and
8. deliver the token as a NIP-59 gift wrap with inner kind `7379`, or return it
   through an explicit export operation.

Outgoing operations need the same encrypted recovery journal discipline as
acceptance. A delivery failure must be distinguishable from a proof-state
failure. Once a bearer token has been exported, the wallet must treat those
proofs as no longer locally spendable even if the recipient has not accepted
the transfer.

## Loading and balance calculation

`Acorn.load_data()` should load kind `7380` independently from kind `7375`.
The Clear loader should:

1. fetch owner-authored kind `7380` and relevant kind `5` events;
2. decrypt and validate every event;
3. reject mixed-mint or mixed-CMU payloads;
4. resolve `del` transitions and deletion events;
5. deduplicate proofs by `(mint, unit, keyset ID, secret)`;
6. expose balances grouped by exact `(mint, unit)`; and
7. preserve proof-to-event ownership for safe rollover.

Malformed or unverifiable Clear events must not reduce the cash balance and
must not be silently included in a Clear balance. They should produce a
separate Clear proof-state advisory.

## Proposed Acorn API

The first implementation should expose explicit Clear methods rather than add
flags to cash methods:

```text
get_clear_receipts(status=None, include_tokens=False)
get_clear_balances(verify=False)
get_clear_transaction_history()
accept_clear_receipt(event_id)
reject_clear_receipt(event_id)
export_clear_token(mint, unit, amount)
send_clear(mint, unit, amount, address, memo=None)
check_clear_proofs(mint=None, unit=None)
```

Suggested CLI commands:

```sh
acorn receive-clear
acorn clear pending
acorn clear accept <event-id>
acorn clear balances
acorn clear history
acorn clear send <amount> <address> --mint <url> --unit <cmu>
acorn clear export <amount> --mint <url> --unit <cmu>
acorn clear check
```

Commands that spend or accept proofs must identify one unambiguous Clear
balance. A friendly alias is never sufficient as a command-level identifier.

## Safebox Web behavior

Safebox Web should continue to present two independent domains:

- **Cash Balance** and **Cash Transactions** use kinds `7375`, `7377`, and the
  cash finalization workflow; and
- **Clear Balances** and **Clear Transactions** use pending `clear_receipts`,
  kind `7380` proof state, and kind `7381` history.

The Clear page may display mint-provided friendly aliases, but it must keep the
canonical mint URL and CMU available. Pending receipts and spendable balances
must be labelled separately. The cash finalization button must never process a
kind `7379` receipt.

## Security invariants

The implementation must preserve all of these invariants:

1. Kind `7375` never contains Clear proofs.
2. Kind `7380` never contains cash proofs or more than one mint and CMU.
3. Clear amounts from different `(mint, CMU)` identities are never summed.
4. Bearer tokens and proof secrets are always encrypted at rest on relays.
5. Bearer material is excluded from logs and default JSON output.
6. A receipt is not marked accepted until refreshed proofs are durably stored.
7. A kind `7381` history event cannot create or destroy spendable value.
8. Alias metadata cannot select a mint, CMU, keyset, or proof.
9. Every mutating operation is locked, idempotent, and recoverable.
10. Clear proof failures do not mutate or conceal the cash proof state.

## Compatibility and migration

No migration is required for the current implementation. Existing kind `7379`
receipts remain pending in `clear_receipts` until the acceptance workflow is
available.

Older Acorn clients will ignore kinds `7380` and `7381`. They will therefore
under-report Clear balances but must continue to load cash safely. A wallet
should not finalize Clear receipts on one client until every client expected to
spend that Clear balance understands kind `7380` state transitions.

The first implementation should include a feature/version marker in wallet
metadata so clients can warn when Clear proof-state support is unavailable.

## Testing requirements

The implementation is not complete without tests covering:

- kind `7379` acceptance into kind `7380` and kind `7381`;
- two Clear mints using the same friendly alias;
- two CMUs from one mint;
- multiple keysets under one CMU;
- duplicate receipt acceptance;
- mint rejection and already-spent incoming proofs;
- relay failure before and after mint refresh;
- crash recovery from every operation phase;
- rollover with exact spend and with change;
- deletion and `del` graph reconstruction;
- malformed, mixed-unit, and mixed-mint kind `7380` events;
- proof verification without cash-state mutation;
- outgoing delivery failure after proof export; and
- complete isolation from kind `7375` cash balances and cash history.

## Implementation sequence

1. Reserve and document provisional kinds `7380` and `7381`.
2. Add encrypted kind `7380` parsing, loading, and grouped balance reporting.
3. Add the acceptance recovery journal and idempotent receipt state machine.
4. Implement mint refresh and kind `7380` persistence.
5. Add kind `7381` incoming history.
6. Expose Clear balances, pending receipts, and acceptance in the CLI.
7. Update Safebox Web to distinguish pending and spendable Clear amounts.
8. Implement proof selection, rollover, export, and kind `7379` sending.
9. Add outgoing kind `7381` history and recovery handling.
10. Complete relay replication, backup, and compatibility documentation.

## Relationship to existing specifications

This note extends
[Acorn Clear Transfer Kind 7379](CLEAR-TRANSFER-KIND-7379-DESIGN.md).
The kind `7379` note remains authoritative for delivery and pending receipt
storage. This note is authoritative for the proposed finalized proof state and
Clear transaction journal.

The event shapes intentionally resemble NIP-60 state transitions, but kinds
`7380` and `7381` are Acorn application kinds unless and until adopted by a
broader specification.
