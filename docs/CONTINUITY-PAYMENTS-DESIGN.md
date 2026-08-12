# Continuity Payments

## Status

This note defines the first experimental implementation of Continuity Payments
between Safebox wallets. It is intentionally narrow. The purpose is to preserve
useful local payment capability during an external outage without describing a
provisional transfer as settled.

## User outcome

A user can choose **Continuity** while paying another Safebox address. Safebox
then transfers previously issued Cashu proofs directly to the recipient without
contacting the mint or attempting a Lightning payment.

This supports a community that remains connected locally while its wider
network path is unavailable. A ship, remote community, or emergency site can
continue exchanging payment material over its available relay or mesh and
reconcile with the mint after connectivity returns.

## Two payment modes

Safebox keeps two explicit modes:

- **Confirmed** checks mint spend state and may use Lightning for an address
  outside Safebox.
- **Continuity** does not contact a mint or use Lightning. It works only when
  the address resolves to another Safebox recipient.

Continuity is an affirmative user choice. Mint unavailability does not silently
change a Confirmed payment into a provisional payment.

## Exact in-kind transfer

The first implementation transfers exactly the requested amount or does
nothing. Acorn selects an exact subset of locally held proofs from one mint. It
does not ask the mint to split, combine, refresh, or check those proofs.

If no exact subset exists, the payment fails before wallet state changes. A
failure response may advise the nearest lower and higher amounts that the
current single-mint proof sets can form. The user must submit a new payment for
one of those amounts; Safebox never changes the amount silently.

After selection, the sender removes the transferred proofs from its
relay-backed wallet and publishes the encrypted transfer. This prevents normal
reuse by that Acorn instance. It does not prove that another copy of the same
proof material does not exist.

## Provisional receipt

The transfer payload declares `payment_mode=continuity` and
`settlement=provisional`. A receiving Acorn stores the token in its encrypted
`continuity_receipts` reserved record. It does not add the proofs to spendable
wallet balance and does not contact the mint while receiving them.

The receiver can therefore preserve the payment evidence locally while keeping
the settlement boundary visible. When the user checks for incoming funds, Acorn
also attempts to refresh every provisional receipt with its mint. A successful
refresh adds replacement proofs to spendable balance, records a confirmed
credit in transaction history, marks the receipt `mint-confirmed`, and removes
the bearer token from the pending journal. If the mint remains unavailable or
rejects the refresh, the receipt and bearer token remain provisional for a
later attempt.

## Address boundary

The Safebox app uses its existing NIP-05 resolution flow to determine whether a
payment address identifies a Safebox recipient and to obtain that recipient's
public key and relay. Continuity mode may use locally available name and relay
infrastructure, but it does not fall back to an external Lightning payment.

If the address cannot be resolved as Safebox, the app fails without spending.
This includes an ordinary Lightning address outside the Safebox network.

## Authority and risk

The mint remains the final authority on proof spend state. During a Continuity
Payment neither participant can establish mint finality. A proof may have gone
stale or may exist in competing wallet state. The recipient is accepting a
provisional bearer record and the associated double-spend risk until
reconciliation.

Safebox records what it observed and did:

- sender and recipient public keys;
- encrypted transfer event and relay location;
- amount, mint, nonce, and comment;
- local removal of the sender's proofs;
- provisional receipt state;
- eventual mint reconciliation result.

The application preserves evidence and local intent. It does not replace the
mint's recognition decision.

## Failure rules

The first implementation follows these rules:

- no mint or Lightning request in the Continuity send and receive paths;
- no payment to a recipient that is not resolved as Safebox;
- no approximate amount;
- no addition of provisional proofs to spendable balance;
- no automatic retry after an unresolved delivery outcome;
- no claim of settlement before mint reconciliation.

## Follow-on work

The current reconciliation path distinguishes `provisional` and
`mint-confirmed` receipts. A later milestone should add explicit `spent`,
`pending`, and `unknown` outcomes, strengthen recovery across interruption
between mint refresh and journal update, and define recovery behavior when
relay publication succeeds but delivery confirmation is uncertain.

Related context is in
[Lockbox External Dependencies and Offline Transfer](LOCKBOX-EXTERNAL-DEPENDENCIES-AND-OFFLINE-TRANSFER.md)
and [Proof State and Relay Consistency](PROOF-STATE-RELAY-CONSISTENCY.md).
The deferred sender-online/receiver-offline mechanism is described in
[Deferred P2PK Payments](DEFERRED-P2PK-PAYMENTS-DESIGN.md).
