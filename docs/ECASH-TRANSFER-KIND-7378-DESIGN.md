# Acorn Ecash Transfer Kind 7378 Design Note

## Summary

Kind `7378` is reserved for relay-delivered ecash transfers between Acorn
wallets.

The goal is to let one Acorn send ecash directly to another Acorn through
Nostr relay infrastructure. The recipient can later query their home relay, or
a specified relay, find incoming transfer events addressed to them, redeem the
Cashu token or proof payload, refresh the proofs, and merge the refreshed
proofs into the normal Acorn wallet proof state.

This design intentionally keeps `7378` separate from existing Acorn wallet
state:

- kind `7375` remains the canonical encrypted wallet proof state;
- kind `7377` remains transaction history;
- kind `7378` becomes the transfer inbox for Acorn-to-Acorn ecash delivery.

## Motivation

Acorn already stores wallet state on relays and already knows how to accept
Cashu tokens. A relay-delivered transfer kind turns that into a direct
wallet-to-wallet primitive.

The sender does not need a live connection to the recipient. The sender only
needs to know a recipient public key and a relay where the recipient can later
retrieve the event. The recipient can receive by periodically sweeping their
home relay, a nominated relay, or a relay pool.

This is protocol-first wallet delivery rather than social messaging with money
attached.

## Recipient resolution

The recipient can be supplied using the normal Acorn identity rules:

- NIP-05 identifier, such as `alice@example.com`;
- Nostr `npub`;
- 64-character hex public key.

When the recipient is a NIP-05 identifier, Acorn resolves both:

- the recipient public key; and
- any relay hints published in the NIP-05 document.

If the sender does not provide an explicit `--relay`, those NIP-05 relay hints
should be used as the transfer publication relays. If the recipient is an
`npub` or hex key, or if NIP-05 does not provide relay hints, Acorn falls back
to the sender's configured home relay unless a relay is explicitly supplied.

The resolved public key is the receiving key. This is a critical boundary:
receipt requires control of the private key corresponding to the NIP-05,
`npub`, or hex public key used by the sender.

The receiving key may be different from the wallet key that ultimately stores
the refreshed proofs. In that case, Acorn can use the receiving private key only
as transient decrypting material while depositing accepted proofs into the
wallet's own proof state. The receiving private key must not be stored unless
the user explicitly configures the wallet itself to use that key.

When a transient receiving key is supplied, Acorn can derive its public key and
`npub`, query for that key's kind `0` metadata event, inspect the profile for a
NIP-05 identifier, and resolve that NIP-05 identifier to discover relay hints.
Those relay hints can then be used to find incoming kind `7378` events without
requiring the operator to manually provide a relay.

The NIP-05 relay hints should only be trusted for receive discovery if the
NIP-05 document resolves back to the same receiving public key. This prevents a
stale or misleading kind `0` profile from redirecting receive lookups to relays
for a different key.

## Event kind

```text
kind 7378: Acorn relay-delivered ecash transfer
```

The event is a regular signed Nostr event.

The event should be addressed to the recipient with a `p` tag. Relays and
clients can then query by recipient:

```json
{
  "kinds": [7378],
  "#p": ["<recipient_pubkey>"],
  "since": 1234567890
}
```

## Recommended event shape

```json
{
  "kind": 7378,
  "pubkey": "<sender_pubkey>",
  "content": "<encrypted transfer payload>",
  "tags": [
    ["p", "<recipient_pubkey>"],
    ["protocol", "acorn-ecash-transfer"],
    ["v", "1"],
    ["mint", "https://mint.example.com"],
    ["amount", "21"],
    ["unit", "sat"]
  ]
}
```

The `mint`, `amount`, and `unit` tags are hints for indexing, display, and
debugging. They are not authoritative. The encrypted payload is authoritative.

## Payload

The first implementation should prefer an encrypted Cashu token payload rather
than raw proof transport. This reuses Acorn's existing token acceptance path and
keeps proof-refresh semantics concentrated in one place.

Suggested payload:

```json
{
  "version": 1,
  "type": "cashu-token",
  "token": "cashuA... or cashuB...",
  "mint": "https://mint.example.com",
  "amount": 21,
  "unit": "sat",
  "comment": "optional note",
  "nonce": "optional sender-generated nonce"
}
```

Future versions may support direct proof payloads, but token payloads should be
the baseline because they are already portable and understood by Cashu tooling.

## Encryption

The content should be encrypted to the recipient. The first implementation can
use the same NIP-44 encryption convention already used by Acorn private wallet
records.

The recipient decrypts using the private key for the resolved receiving
identity. That may be the Acorn wallet key, or it may be a transient receiving
key supplied only for the receive operation. If decryption fails, the event is
ignored or reported as an unreadable transfer candidate.

The sender should never publish unencrypted proofs or tokens in kind `7378`.

## Recipient receive

Receiving kind `7378` transfers should be an explicit operation, not an
implicit side effect of checking balance. This keeps `balance` read-only and
avoids assuming that the wallet key is always the NIP-05 owner key.

Proposed receive behavior:

1. Load the wallet's normal proof state from kind `7375`.
2. Determine the receiving key:
   - wallet key by default; or
   - transient receive key supplied for this operation.
3. Determine receive relays:
   - explicit relay override;
   - NIP-05 relays discovered from the transient receiving key's kind `0`
     profile; or
   - wallet home relay fallback.
4. Determine the ecash transfer cursor.
5. Query transfer relays for kind `7378` events addressed to the receiving
   public key.
6. Decrypt each candidate event with the receiving key.
7. Extract the Cashu token.
8. Accept the token using Acorn's existing token acceptance path.
9. Refresh/swap the received proofs through the mint.
10. Write refreshed proofs into the normal kind `7375` proof state.
11. Record a corresponding transaction-history entry.
12. Advance the transfer cursor.
13. Report the updated balance.

This makes `7378` an inbox transport. It does not become the durable wallet
proof store. Durable spendable proof state remains kind `7375`.

## Transaction history

A successfully accepted kind `7378` transfer should generate a corresponding
transaction-history entry.

Transaction history remains separate from the transfer event itself:

- kind `7378` is the delivery/inbox event;
- kind `7375` is the spendable proof state after acceptance;
- kind `7377` is the wallet transaction-history record.

The transaction-history entry should capture enough context for the recipient
to understand where the balance increase came from:

```json
{
  "tx_type": "C",
  "amount": 21,
  "comment": "ecash transfer received",
  "tendered_amount": 21,
  "tendered_currency": "SAT",
  "source_kind": 7378,
  "source_event_id": "<transfer_event_id>",
  "sender_pubkey": "<sender_pubkey>"
}
```

The exact serialized transaction-history schema can follow the existing Acorn
`TxHistory` model. If the model does not yet include source metadata, the first
implementation can include this context in the comment, then promote it to
structured fields later.

## Since cursor

Acorn should maintain a cursor so old transfer events are not rechecked on
every receive operation.

Suggested reserved record:

```text
ecash_transfer_latest
```

Suggested storage:

```text
kind: 37376
label: ecash_transfer_latest
payload: "<latest processed created_at timestamp>"
```

The receive command should also support a manual `since` override for recovery,
debugging, or replay:

```sh
acorn receive-ecash --since 1780000000
```

When `--since` is supplied, it should override the stored cursor for that run.
Whether it updates the stored cursor should be explicit in implementation. A
safe default is:

- normal sweep advances the cursor;
- manual `--since` can advance the cursor only after successful processing;
- a future `--dry-run` or `--no-advance` could inspect without changing state.

## Relay selection

Default transfer sweep:

- recipient home relay first;
- optionally public or configured transfer relays later.

Command override:

```sh
acorn receive-ecash --relay wss://relay.example.com
```

The relay override is useful when a sender publishes the transfer to a relay
that is not the recipient's current home relay.

## Initial implementation commands

Send an Acorn-to-Acorn ecash transfer:

```sh
acorn ecash-transfer 21 <recipient-npub-or-nip05> --relay wss://relay.example.com
```

Receive opportunistically before showing balance:

```sh
acorn receive-ecash
```

Receive from a specific relay:

```sh
acorn receive-ecash --relay wss://relay.example.com
```

Replay from a specific cursor:

```sh
acorn receive-ecash --since 1780000000
```

Use a transient receiving key without storing it:

```sh
acorn receive-ecash --receive-nsec nsec1...
```

When `--receive-nsec` is supplied and `--relay` is omitted, Acorn attempts to
discover receive relays from the transient key's kind `0` profile and verified
NIP-05 relay hints.

Receive a specific event directly:

```sh
acorn receive-ecash --event-id <kind-7378-event-id> --receive-nsec nsec1...
```

Direct event-id receive is useful when a relay stores the event but does not
return it through a `#p` tag query, or when debugging cursor behavior.

## Failure handling

Incoming transfer processing must be conservative.

- A malformed event should not prevent wallet balance from loading.
- A decrypt failure should be skipped or reported as a candidate failure.
- A spent token should be treated as already redeemed or invalid.
- A successful token acceptance should persist refreshed proofs to kind `7375`.
- The cursor should not advance past events that failed due to temporary relay,
  mint, or network errors unless the implementation explicitly marks them as
  permanently unprocessable.

The receiver should record enough information to avoid endlessly retrying known
bad events in future versions. A later implementation may add a processed-event
set or tombstone record.

## Sender-side lifecycle

A sender-side transfer flow should eventually:

1. select spendable proofs;
2. issue a Cashu token for the transfer amount;
3. publish encrypted kind `7378` to the recipient relay;
4. treat the token/proofs as sent and no longer locally spendable;
5. optionally wait for an acknowledgement in a future protocol extension.

Once token issuance has committed, the sender must assume those proofs have
left the wallet. A failed relay publish after token issuance requires careful
recovery UX because the sender may still possess a valid token that should be
resent or safely restored.

## Sender-side deletion

The sender should be able to clean up kind `7378` transfer events it authored.
This is useful after a recipient has accepted the transfer, or when the sender
wants to reduce relay-visible delivery history.

Deletion is performed with a standard NIP-09 deletion request, kind `5`, that
references the authored kind `7378` event ids with `e` tags and includes a
`k=7378` tag.

Initial command:

```sh
acorn delete-ecash-transfers --relay wss://relay.example.com
```

Optional recipient filtering:

```sh
acorn delete-ecash-transfers --recipient alice@example.com
```

Important caveat: NIP-09 is a deletion request, not a universal erasure
guarantee. Relays and clients decide how to honor deletion events, and remote
caches may already have seen the encrypted transfer event.

## Acknowledgements

Acknowledgements are out of scope for the first implementation.

A later version may define either:

- a kind `7378` acknowledgement subtype; or
- a separate kind for transfer receipts.

An acknowledgement could reference the original transfer event with an `e` tag
and include a status such as `accepted`, `failed`, or `expired`.

## Open questions

- Should transfer events be deleted after successful receipt, or should they
  remain as encrypted delivery history?
- Should the receiver track processed event ids separately from the timestamp
  cursor?
- Should raw proof payloads be supported, or should all proof transfer go
  through Cashu token serialization?
- Should transfer relay preferences be a separate reserved record from public
  social relays?
