# Acorn Clear Transfer Kind 7379 Design Note

## Status

Implemented as a separate receiver and pending storage path.

## Summary

Kind `7379` is the inner Acorn-compatible Clear token transfer kind. It is
delivered inside a NIP-59 kind `1059` gift wrap and is intentionally separate
from ordinary sats/ecash kind `7378` transfers.

```text
outer relay-visible event: kind 1059
inner Clear transfer: kind 7379
protocol tag: clear-token-transfer
storage label: clear_receipts
cursor label: clear_transfer_latest
```

Clear transfers contain Cashu tokens denominated in a Clear Mint Unit such as
`cmu-00ce29eeaf094301`. Acorn stores those transfers as pending Clear receipts.
It does not add them to normal sats proofs, sats balance, or kind `7375` proof
state.

## Why a separate path

Regular Acorn ecash receive, kind `7378`, refreshes sats proofs through a mint
and merges the refreshed proofs into the wallet's spendable proof state.

Clear CMU tokens are different:

- they may come from different Clear mints;
- they are denominated by keyset-bound CMUs, not `sat`;
- they currently represent lab or policy-defined value, not ordinary wallet
  sats; and
- accepting them should not interfere with existing ecash receive behavior.

For that reason, `sweep_ecash_transfers` skips gift-wrapped inner events whose
inner kind is `7379`. Clear receive is handled by `sweep_clear_transfers`.

## NUT-18 interoperability

Acorn also recognizes the standard NUT-18 Nostr transport. A `creqA...`
payment request advertises a Nostr NIP-17 transport, and a compatible sender
returns a payment payload in a private kind `14` message containing:

```json
{
  "id": "receiver-generated-request-id",
  "memo": "optional sender memo",
  "mint": "https://clear.example",
  "unit": "cmu-00ce29eeaf094301",
  "proofs": []
}
```

`sweep_clear_transfers()` adapts this standard payload to the same pending
Clear receipt model used by native kind `7379` transfers. The receipt retains
the request ID and records the protocol as `cashu-nut18-nip17`. An unrelated
kind `14` message is skipped without advancing it into Clear proof state.

This compatibility path does not mix protocol roles: NUT-18 describes the
receiver-generated request and transported payment payload, while kinds
`7379`, `7380`, and `7381` remain Acorn's native transfer, spendable-state, and
history model.

## Payload

The encrypted inner event content is JSON:

```json
{
  "type": "clear-token",
  "version": 1,
  "token": "cashuA...",
  "mint": "http://127.0.0.1:3338",
  "unit": "cmu-00ce29eeaf094301",
  "amount": 25,
  "keyset_ids": ["00ce29eeaf094301"],
  "memo": "test CMU"
}
```

The Cashu token is bearer material. It must not be logged, displayed in
ordinary summaries, or included in JSON output unless an explicit token export
path is added.

## Receive behavior

`Acorn.sweep_clear_transfers()`:

1. queries relay-visible kind `1059` gift wraps addressed to the receiving
   public key;
2. unwraps the NIP-59 event;
3. requires native inner kind `7379` or a valid NUT-18 NIP-17 kind `14`
   payment payload;
4. requires payload `type` to be `clear-token`;
5. decodes the Cashu token;
6. validates amount, mint count, unit, and optional keyset ids;
7. stores the token and metadata in `clear_receipts` with status `pending`;
8. advances `clear_transfer_latest` after durable processing; and
9. leaves ordinary proof state, sats balance, `accept_token`, and continuity
   receipt storage untouched.

`Acorn.get_clear_receipts()` returns pending Clear receipt metadata without
including bearer tokens by default.

## Deleting a pending receipt

`Acorn.delete_pending_clear_receipt(event_id)` lets a wallet user discard a
pending Clear transfer before finalization. The operation is limited to receipts
whose status is `pending`.

Deletion removes the Cashu bearer token and all transfer metadata from the
relay-backed `clear_receipts` record. It retains only the source event ID,
`deleted` status, and deletion timestamp as a tombstone. A later relay rescan
recognizes that tombstone and skips the kind `7379` transfer instead of
restoring it. Deleted tombstones are excluded from normal receipt listings.

This operation does not delete finalized kind `7380` proof state or kind
`7381` transaction history.

## CLI

Sweep Clear transfers:

```sh
acorn receive-clear
```

Preview without storing receipts or advancing the cursor:

```sh
acorn receive-clear --preview
```

Check the pending indicator:

```sh
acorn balance
```

Example output:

```text
Relay-visible balance: 9836 sats in 67 proofs.
Mint state not checked. Use 'acorn balance --verify'.
Lightning payment capacity: up to 9836 sats before mint fees.
Pending Clear transactions: 25 unit(s) in 1 receipt(s).
- cmu-00ce29eeaf094301: 25 unit(s) in 1 receipt(s)
```

Machine-readable balance output includes:

```json
{
  "pending_clear": {
    "pending": true,
    "count": 1,
    "amount": 25,
    "units": [
      {
        "unit": "cmu-00ce29eeaf094301",
        "amount": 25,
        "count": 1
      }
    ]
  }
}
```

## Relationship to Safebox Web

Safebox Web advertises Clear receive support through NIP-05:

```json
{
  "clear": {
    "alice": {
      "protocols": ["clear-token-transfer"],
      "transports": ["nip59"],
      "kinds": [7379]
    }
  }
}
```

Acorn uses that advertisement during sending or receive discovery, but final
validation happens after the gift wrap is decrypted.

## Current boundary

Pending Clear transfers are visible, grouped by mint and CMU, deletable, and
explicitly acceptable into spendable kind `7380` state. Acorn can export or
send units from one exact mint and CMU as another private kind `7379` transfer.
It never combines Clear balances or routes them through Cash state.

The remaining hardening boundary is crash-recoverable outgoing delivery after
proof export, together with broader mint interoperability and security review.
Acorn carries a NUT-18 request ID into the receipt, but it does not yet persist
an outstanding-request registry or mark a single-use request complete.

The proposed finalized wallet model is defined in
[Acorn Clear Spendable Proof State Kinds 7380 and 7381](CLEAR-SPENDABLE-PROOF-STATE-KINDS-7380-7381-DESIGN.md).
