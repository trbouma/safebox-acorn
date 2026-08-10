# Bitcoin Silent Payments Capability Specification

## Status

This specification defines Acorn's initial Bitcoin capability. The code was
first explored in OpenETR, but Safebox Acorn is now the canonical implementation
owner. Acorn has no runtime dependency on OpenETR for address derivation,
receipt detection, transaction construction, or broadcast.

The capability is experimental and installed through the optional `bitcoin`
package extra. It has deterministic unit coverage and its compatible predecessor
successfully detected and constructed a sweep preview for a controlled mainnet
receipt. Final broadcast and destination settlement remain release gates.

## Purpose

An Acorn can use its existing Nostr key as the root of a reusable Nostr Silent
Payments (NSP) receive capability. It can:

1. derive the same public `sp1...` address from either its `npub` or `nsec`;
2. inspect a user-supplied Bitcoin txid;
3. privately determine whether the transaction contains an output controlled
   by that Acorn;
4. distinguish unconfirmed, confirmed-and-unspent, and unavailable outputs;
5. construct a fee-disclosed sweep to a user-selected Bitcoin address; and
6. broadcast only through a separate explicit operation.

This is a user-controlled Bitcoin capability. It is not a provider swap,
Lightning settlement service, background wallet scanner, or general Bitcoin
wallet implementation.

## Derivation contract

Let `d` be the normalized BIP-340 private scalar and `P = dG` its even-y public
point. Acorn derives:

```text
t_scan  = H_tag("nostr-sp/scan", P)
t_spend = H_tag("nostr-sp/spend", P)

ScanPub  = P + t_scan G
SpendPub = P + t_spend G

sp1... = bech32m(v0 || ScanPub || SpendPub)
```

When the `nsec` is available:

```text
scan_priv  = d + t_scan mod n
spend_priv = d + t_spend mod n
```

The tags and even-y normalization are compatibility-critical. Changing them
would create a different receive identity for the same Acorn key.

## Public API

The initial component API is:

```python
from acorn import (
    derive_nostr_silent_payment_address,
    detect_silent_payment_receipts,
    create_silent_payment_sweep_preview,
    broadcast_silent_payment_sweep,
)
```

Address derivation accepts an `npub` or `nsec`. Detection and spending require
the `nsec`, but returned values must never contain the `nsec`, private scan key,
private spend key, receipt tweak, reconstructed output key, or signed
transaction bytes.

## Detection contract

Detection is deliberately txid-targeted:

1. validate the 64-character hexadecimal txid;
2. fetch that transaction from a configured Blockstream-compatible backend;
3. derive scan material in process memory;
4. extract eligible transaction input public keys;
5. apply the BIP-352 shared-secret scan against Taproot outputs;
6. query the exact matched output's UTXO state; and
7. return sanitized public receipt fields.

The backend can observe the txid and derived one-time output-address lookup. It
does not receive the Acorn key or private derivation material.

Each match reports:

- txid and exact output index;
- original value in sats;
- one-time source address;
- confirmation state and block height; and
- `available`, `unconfirmed`, or `spent_or_unavailable` status.

Output indexes must come from the transaction array position. They must not
default to zero when the upstream transaction JSON omits a `vout` field.

## Sweep contract

Preview and broadcast are separate operations.

Preview:

- rescans the transaction;
- requires the exact selected output index;
- requires the output to be confirmed and unspent;
- validates the destination;
- calculates the fee using the caller-supplied positive fee rate;
- rejects dust and insufficient-value results;
- constructs and signs in process memory; and
- returns only the public transaction summary.

Broadcast:

- repeats detection and UTXO validation against current state;
- reconstructs and signs a fresh transaction;
- broadcasts exactly once;
- verifies that the backend response equals the locally expected txid; and
- treats timeout or ambiguous failure as an uncertain result that must not be
  automatically retried.

The first implementation requires confirmation before spending. Zero-confirmed
sweeps are not supported.

## Ownership boundaries

Acorn owns:

- NSP key and address derivation;
- targeted private receipt detection;
- exact UTXO availability checks;
- receipt-output private-key reconstruction;
- fee calculation and signed sweep construction;
- secret-safe result shaping; and
- explicit single-attempt broadcast semantics.

Consuming applications own:

- selecting and disclosing the Bitcoin backend;
- fee-rate policy;
- collecting the txid and destination;
- authentication, CSRF protection, and explicit user confirmation;
- presentation and accessibility;
- provider treasury, swap, Lightning, or ecash settlement workflows; and
- durable job coordination and reconciliation.

## Packaging

Install the Bitcoin capability with:

```sh
pip install "safebox-acorn[bitcoin]"
```

For local Poetry development:

```sh
poetry install -E bitcoin
```

The extra currently supplies BTClib transaction primitives. Acorn contains the
NSP implementation itself and does not install OpenETR.

## Security requirements

- Never log or return private scan, spend, receipt, or signed transaction data.
- Never scan or broadcast as a side effect of address derivation.
- Never broadcast as a side effect of detection or preview.
- Never accept a signed transaction from the browser for rebroadcast.
- Recheck the outpoint before broadcast.
- Never automatically retry an uncertain broadcast.
- Bind every sweep to a txid, output index, destination, and fee rate.
- Reject malformed keys, txids, transaction payloads, destinations, dust, and
  non-positive fee rates.
- Treat the Bitcoin backend as metadata-visible and replaceable infrastructure.

The derived private scan key is root-equivalent under this NSP construction:
because the tweak is public, disclosure of `scan_priv` permits recovery of the
underlying Acorn private scalar. It must receive the same protection as the
`nsec`.

## Validation requirements

Before stable release, add or retain tests for:

- public and private derivation equivalence;
- fixed derivation vectors;
- P2WPKH, wrapped SegWit, Taproot, and legacy eligible inputs;
- receipts at output indexes other than zero;
- multiple matching outputs;
- unconfirmed, confirmed, spent, and reorged outputs;
- malformed and unsupported transactions;
- dust and unreasonable fee conditions;
- broadcast timeout, mismatch, and already-broadcast behavior;
- mainnet/testnet mismatch; and
- supported Linux, macOS, FreeBSD, and ARM64 installation paths.

