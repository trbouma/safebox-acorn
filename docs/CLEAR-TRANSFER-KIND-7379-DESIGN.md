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
3. requires inner kind `7379`;
4. requires payload `type` to be `clear-token`;
5. decodes the Cashu token;
6. validates amount, mint count, unit, and optional keyset ids;
7. stores the token and metadata in `clear_receipts` with status `pending`;
8. advances `clear_transfer_latest` after durable processing; and
9. leaves ordinary proof state, sats balance, `accept_token`, and continuity
   receipt storage untouched.

`Acorn.get_clear_receipts()` returns pending Clear receipt metadata without
including bearer tokens by default.

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

Pending Clear receipts are visible and stored, but they are not yet refreshed
into a spendable Clear balance. A future wallet layer should add explicit Clear
receipt listing, accept/reject/finalize commands, mint-specific balance
grouping, and spending rules by mint and CMU.

