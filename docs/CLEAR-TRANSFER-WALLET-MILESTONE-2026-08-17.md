# Clear Transfer Wallet Milestone

Date: 2026-08-17

## Summary

Safebox Acorn now provides the wallet-side protocol boundary for receiving
organization-issued Clear Mint Units (CMUs) without mixing them with ordinary
cash/ecash proofs.

The demonstrated flow begins at a public Clear mint, passes through a private
NIP-59 transfer, and ends as a pending Clear transfer controlled by the
recipient's Acorn key. The same Acorn continues to manage its sat-denominated
Cash Balance independently.

This is a working receive and storage milestone. Acceptance into spendable
Clear proof state and onward wallet spending are not yet implemented.

## Why Acorn is the boundary

Clear is the mint and supply authority. Safebox Web is the human-facing
application. Acorn owns the wallet protocol state between them:

```text
Clear mint and treasury
  -> kind 1059 NIP-59 gift wrap
  -> inner kind 7379 Clear transfer
  -> Acorn decrypts and validates
  -> clear_receipts pending journal
  -> Safebox Web reads recipient-controlled state
```

The recipient's Nostr key provides addressing, decryption, and authority over
the encrypted wallet record. The relay transports and stores events but does
not become the wallet or mint.

## Implemented receive path

`Acorn.sweep_clear_transfers()`:

1. queries relay-visible kind `1059` gift wraps for the recipient;
2. unwraps NIP-59 using the recipient key;
3. requires inner kind `7379`;
4. requires the `clear-token-transfer` payload shape;
5. decodes the Cashu token;
6. validates amount, one mint, canonical CMU, and keyset IDs;
7. stores bearer material in the separate `clear_receipts` journal;
8. advances a dedicated Clear transfer checkpoint; and
9. leaves cash proof state and cash transaction history untouched.

The CLI exposes the receiver:

```sh
acorn receive-clear
acorn receive-clear --preview
acorn balance
```

Safebox Web calls the same receiver through **Check for Clear Transfers**.

## Hard separation from cash

The current event model is:

| Kind or record | Purpose |
| --- | --- |
| `7375` | spendable cash/ecash proof state |
| `7377` | cash transaction history |
| `7378` | incoming cash/ecash transfer |
| `7379` | incoming Clear transfer |
| `clear_receipts` | pending encrypted Clear transfer journal |
| `7380` | spendable Clear proof state foundation |
| `7381` | append-only Clear transfer history foundation |

Kind `7378` handling continues to refresh ordinary ecash before adding it to
the cash wallet. Kind `7379` never enters that path and cannot increase the sat
balance.

## Multiple mints and CMUs

Clear balances are identified by:

```text
(normalized mint URL, canonical CMU)
```

Proofs remain partitioned by keyset within that balance. Acorn can represent
several Clear balances from several mints, but it never calculates a
cross-currency total.

The kind `7380` loader, balance grouping, rollover deletion reconstruction,
kind `7381` journal, replication, and wallet-burn coverage are implemented.
These are foundations for finalized balances; they do not mean pending
receipts are accepted automatically.

## Pending transfer deletion

A user may delete a pending Clear transfer before finalization.

`delete_pending_clear_receipt(event_id)` erases the Cashu bearer token and
transfer metadata from the encrypted journal. It keeps a minimal deletion
tombstone containing the event ID so a targeted or repeated relay scan skips
the deleted transfer instead of restoring it.

Deletion is restricted to pending transfers. It does not delete kind `7380`
proof state or kind `7381` history.

## Demonstrated interoperability

The working test crossed three independently deployable products:

```text
Clear
  -> issues canonical CMU
  -> holds it in clear-lab treasury
  -> sends exact amount to NIP-05 address

Acorn
  -> receives kind 7379
  -> preserves pending transfer on relay-backed wallet state

Safebox Web
  -> shows mint and CMU aliases
  -> keeps Clear Balances separate from Cash Balance
  -> checks for and deletes pending transfers
```

The transfer remained discoverable through the relay until the recipient
performed an explicit receive check. A deleted transfer remained deleted after
subsequent scans.

## Remaining wallet work

The next safety-critical operation is pending-transfer acceptance:

1. validate the pending token again;
2. check the exact mint, CMU, and keysets;
3. refresh proofs through the Clear mint;
4. persist outputs in kind `7380`;
5. verify exact relay readback;
6. append kind `7381` history;
7. remove bearer material from the pending journal; and
8. recover safely from interruption between mint mutation and relay storage.

Only after that workflow is durable should ordinary wallet-to-wallet Clear
spending be treated as implemented.

## Safety status

Acorn remains developer-stage and unaudited. Clear transfers should currently
carry test value only. The wallet correctly preserves boundaries between cash
and Clear, but the full finalized Clear lifecycle is incomplete.
