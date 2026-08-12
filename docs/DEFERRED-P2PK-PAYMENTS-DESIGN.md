# Deferred P2PK Payments

## Status

This is a deferred design proposal. It is not required for the current
Continuity Payment implementation and should not block work on local bearer
proof transfer and reconciliation.

The proposal applies Cashu
[NUT-11 Pay to Public Key](https://github.com/cashubtc/nuts/blob/main/11.md)
to a specific Safebox scenario: the sender can reach the mint, but the receiver
cannot currently reach it or may not be online to accept the payment.

## User outcome

A sender pays a Safebox address while connected to a compatible mint. The mint
creates proofs locked to a payment public key controlled by the receiving
Acorn. The sender delivers those proofs through the recipient's relay. The
receiver may collect them immediately or later and can redeem them only by
providing the required signature when mint access becomes available.

The receiver does not need to expose whether it is offline. The sender chooses
this delivery mechanism from address capabilities and payment policy, not from
a claim about the receiver's current connectivity.

## Relationship to Continuity Payments

This proposal and the current Continuity Payment solve different outage cases.

### Bearer Continuity Payment

- The sender cannot reach the mint.
- Acorn transfers an exact set of existing ordinary bearer proofs.
- No recipient lock can be added without a mint round trip.
- The receiver holds the proofs provisionally until mint reconciliation.
- Bearer theft and competing-copy risks remain visible.

### Deferred P2PK Payment

- The sender can reach a NUT-11-compatible mint.
- The receiver may be offline or unable to reach the mint.
- The sender asks the mint to create new proofs locked to the receiver's key.
- Relay delivery and receiver collection may happen asynchronously.
- Only the holder of the corresponding private key should be able to satisfy
  the mint-enforced spending condition.

P2PK is therefore a preferred delayed-delivery mechanism when the sender has
mint access. It does not replace bearer continuity when the mint itself is
unavailable.

## Why mint access is required

The P2PK condition is encoded in each proof's secret before the mint signs the
proof. Existing ordinary proofs cannot be retroactively locked to a recipient.

The sender must ask the mint to swap ordinary proofs for new proofs whose
secrets contain a NUT-11 `P2PK` condition and the receiver's public key. The
mint signs those outputs and later enforces the condition when the receiver
spends, swaps, or melts the proofs.

If the mint does not support NUT-11, it may treat an unfamiliar condition as an
ordinary anyone-can-spend proof. Safebox must check the mint's NUT-06 info
response and must not describe a proof as recipient-locked without affirmative
NUT-11 support.

## Address capabilities

A Safebox address should eventually resolve to payment capabilities in addition
to its Nostr public key and delivery relays. The metadata could include:

```json
{
  "npub": "npub1...",
  "relays": ["wss://relay.example"],
  "cashu": {
    "p2pk_pubkey": "02...",
    "accepted_mints": ["https://mint.example"],
    "unit": "sat",
    "nuts": [11]
  }
}
```

The resolved capability is an operational payment route. As with NIP-05, each
counterparty decides what identity meaning to assign to the address and key.

The sender must bind the resolved address, payment key, mint, and relay set to
the payment review. A changed resolution result requires renewed user review.

## Key model

Safebox should derive a dedicated Cashu P2PK key for each Acorn rather than use
the Nostr event-signing key directly. Domain separation reduces cross-protocol
key reuse and leaves room for payment-key rotation without replacing the Acorn
identity.

The design must specify:

- deterministic derivation from Acorn recovery material;
- an explicit derivation context and version;
- compressed secp256k1 public-key encoding required by NUT-11;
- recovery and rotation behavior;
- whether address metadata can advertise multiple active payment keys; and
- how old keys remain available to redeem delayed proofs.

The private payment key must remain within the Acorn component boundary. A web
provider or relay needs only the public key and delivery instructions.

## Sender flow

1. Resolve the Safebox address and obtain its Acorn key, delivery relays,
   payment public key, accepted mints, and protocol versions.
2. Select a mint accepted by both wallets.
3. Query the mint's NUT-06 info endpoint and require affirmative NUT-11 support.
4. Create NUT-11 P2PK output secrets locked to the receiver's payment key.
5. Swap the sender's ordinary proofs for recipient-locked proofs of the exact
   payment amount.
6. Verify the returned proofs and preserve enough state for crash recovery.
7. Deliver the token through the encrypted Acorn kind `7378` transfer inside a
   NIP-59 gift wrap.
8. Record delivery as sent but not yet accepted or redeemed.

The sender must not fall back silently from P2PK to ordinary bearer proofs. A
fallback changes the recipient's security properties and requires explicit
policy or user approval.

## Receiver flow

1. Decrypt and parse the transfer envelope.
2. Verify that every P2PK secret names a payment key controlled by this Acorn.
3. Verify that all proofs use the expected mint, unit, and supported condition.
4. Verify DLEQ proofs offline when the mint and protocol provide them.
5. Store the token as a locked payment awaiting mint confirmation.
6. When the mint is reachable, sign each required NUT-11 message with the
   receiver's payment private key and attach the witness.
7. Submit a swap to the mint and persist the replacement ordinary proofs.
8. Mark the receipt confirmed and add a spendable credit to transaction
   history.

A proof locked to another key must be rejected rather than stored as an
ordinary bearer receipt.

## Delivery and settlement states

The implementation should distinguish:

- `prepared`: the mint created recipient-locked proofs;
- `published`: the encrypted transfer was sent to one or more relays;
- `collected`: the receiving Acorn stored and validated the locked proofs;
- `confirmation-pending`: the receiver has not completed a mint swap;
- `mint-confirmed`: the mint accepted the witness and issued replacement
  proofs;
- `rejected`: the mint rejected the condition, witness, or proof state;
- `unknown`: an interrupted operation has an unresolved outcome.

Relay publication is not recipient acceptance, and recipient acceptance is not
mint confirmation.

## Security properties and limits

NUT-11 materially improves delayed-delivery safety because possession of the
proof material alone should not be sufficient to spend it. It does not remove
all risk:

- the mint remains the final authority on spend state and condition support;
- a malicious or incompatible mint may not enforce the advertised condition;
- address-resolution compromise can substitute an attacker's payment key;
- loss of the receiver's payment private key can make proofs unspendable;
- a sender can still fail to publish after obtaining locked proofs;
- delayed relay retention can prevent collection; and
- implementation mistakes in witness construction can strand funds.

NUT-11 identifies DLEQ verification as important for final offline-receiver
payments. Safebox should not claim strong offline validity without defining and
testing the required DLEQ policy.

## Recovery and refund policy

A later design may use NUT-11 locktime and refund keys so the sender can recover
an uncollected payment after an agreed period. Refund behavior introduces a
second valid spending path and must be visible to the receiver.

The first P2PK milestone should prefer a simple permanent receiver lock unless
operational testing demonstrates that refund support is required. Any refund
path must define the timeout, sender recovery evidence, duplicate-redemption
handling, and user-facing settlement state.

## Implementation prerequisites

Acorn already models proof witnesses, but the complete capability requires:

- NUT-06 mint capability discovery and caching;
- NUT-10 secret serialization;
- NUT-11 P2PK secret creation and validation;
- domain-separated payment-key derivation;
- Schnorr witness signing for swap and melt inputs;
- P2PK-aware mint request construction;
- DLEQ policy and verification;
- address capability publication and resolution;
- durable prepared-payment and receipt journals; and
- integration tests against a NUT-11-compatible mint.

## Deferred decision

P2PK should remain a roadmap capability until these prerequisites are designed
and tested together. The current bearer Continuity Payment remains useful for
local operation during mint outages, provided Safebox continues to label it
provisional and reconcile it when the mint returns.

Related documents:

- [Continuity Payments](CONTINUITY-PAYMENTS-DESIGN.md)
- [Acorn Lightning-Address Gateway Design](ACORN-LIGHTNING-ADDRESS-GATEWAY-DESIGN.md)
- [Lockbox External Dependencies and Offline Transfer](LOCKBOX-EXTERNAL-DEPENDENCIES-AND-OFFLINE-TRANSFER.md)
