# Acorn Ecash Transfer Kind 7378 Design Note

## Summary

Kind `7378` is reserved as the inner Acorn ecash-transfer application kind.
In the default production path it is not the relay-visible event kind. The
relay-visible event is a NIP-59 kind `1059` gift wrap containing an inner kind
`7378` transfer.

The goal is to let one Acorn send ecash directly to another Acorn through
Nostr relay infrastructure. The recipient can later query their home relay, or
a specified relay, find incoming transfer events addressed to them, redeem the
Cashu token or proof payload, refresh the proofs, and merge the refreshed
proofs into the normal Acorn wallet proof state.

This design intentionally keeps `7378` separate from existing Acorn wallet
state:

- kind `7375` remains the canonical encrypted wallet proof state;
- kind `7377` remains transaction history;
- kind `7378` identifies an incoming Acorn ecash transfer after unwrap;
- kind `7379` identifies an incoming Clear token transfer after unwrap and is
  stored separately as a pending Clear receipt;
- kind `1059` is the default relay-visible delivery envelope.

This separation is deliberate. A gift-wrapped kind `7375` could technically be
interpreted as a transfer, but it would overload the meaning of `7375`. Acorn
keeps `7375` for durable spendable proof state and `7378` for transfer intent.
After a transfer is accepted, refreshed proofs are merged into kind `7375`; the
kind `7378` payload remains delivery/inbox material, not wallet state.

Clear token transfers deliberately use inner kind `7379` instead. The ordinary
ecash receiver skips those events so it does not treat Clear CMU tokens as
malformed sats ecash. See [Acorn Clear Transfer Kind 7379](CLEAR-TRANSFER-KIND-7379-DESIGN.md).

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

The same delivery primitive can provide the private final hop from a
conventional Lightning address to an Acorn. In that model, a provider receives
and settles the Lightning payment, then publishes a kind `1059` gift wrap
containing an inner kind `7378` transfer to the registered component key. The
registration, settlement, custody, idempotency, and outbox requirements are
specified in [Acorn Lightning-Address Gateway Design](ACORN-LIGHTNING-ADDRESS-GATEWAY-DESIGN.md).

## Recipient resolution

The recipient can be supplied using the normal Acorn key-identifier rules:

- NIP-05 identifier, such as `alice@example.com`;
- Nostr `npub`;
- 64-character hex public key.

When the recipient is a NIP-05 identifier, Acorn resolves both:

- the recipient public key; and
- any relay hints published in the NIP-05 document.

This resolution inherits the NIP-05 provider's trust boundary. The domain
owner controls DNS, the reverse-proxy operator controls TLS termination and
upstream routing, and the application operator controls the directory response
and its database. Any of them can redirect a handle to a different public key
or relay. A successful lookup means that the domain
currently asserts the mapping; it does not independently prove the human
identity of the recipient or permanent control of the name. For material
transfers, callers should verify the resolved `npub` through an independent
channel or use an already trusted raw public key.

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
inner kind 7378: Acorn relay-delivered ecash transfer
outer kind 1059: default NIP-59 gift-wrap envelope
```

The Acorn transfer payload is represented as an inner kind `7378` event. By
default, that inner event is delivered inside a NIP-59 gift wrap whose public
relay-visible outer event is kind `1059`.

The outer gift-wrap event should be addressed to the recipient with a `p` tag.
Relays and clients can then query by recipient:

```json
{
  "kinds": [1059, 7378],
  "#p": ["<recipient_pubkey>"],
  "since": 1234567890
}
```

The kind `7378` query remains for direct/debug transfers and legacy Acorn
gift-wrapped transfers that used `7378` as the outer kind.

## Recommended event shape

The production/default transfer format is gift-wrapped. The public relay event
is a NIP-59 kind `1059` wrapper authored by a transient key and addressed to the
recipient with a `p` tag:

```json
{
  "kind": 1059,
  "pubkey": "<transient_pubkey>",
  "content": "<encrypted gift wrap>",
  "tags": [
    ["p", "<recipient_pubkey>"]
  ]
}
```

Inside the gift wrap, the recipient can recover the sender-authored transfer
payload as an inner kind `7378` Acorn transfer. Public observers can see that a
transient key published to the recipient, but they cannot directly correlate the
sender wallet key to the recipient from the outer event.

For debugging and legacy compatibility, Acorn also supports direct kind `7378`
events:

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
In gift-wrapped mode these hints should not be placed on the outer event,
because that would leak transfer metadata.

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

By default, the transfer should be NIP-59 style gift-wrapped using NIP-44
encryption. The recipient decrypts the outer wrapper using the private key for
the resolved receiving key, then decrypts the sealed inner event to obtain
the sender-authored inner kind `7378` transfer payload.

For direct mode, the event `content` itself is NIP-44 encrypted to the
recipient.

The receiving key may be the Acorn wallet key, or it may be a transient
receiving key supplied only for the receive operation. If decryption fails, the
event is ignored or reported as an unreadable transfer candidate.

The sender should never publish unencrypted proofs or tokens in kind `7378`.

## Recipient receive

Receiving Acorn ecash transfers should be an explicit operation, not an implicit
side effect of checking balance. This keeps `balance` read-only and avoids
assuming that the wallet key is always the NIP-05 owner key.

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
5. Query transfer relays for kind `1059` gift wraps and legacy/direct kind
   `7378` events addressed to the receiving public key.
6. Unwrap/decrypt each candidate event with the receiving key.
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
  "comment": "funds transfer received",
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

## Receive checkpoint and pagination

Acorn maintains a deterministic checkpoint so old transfer events are not
rechecked on every receive operation and events sharing a Nostr timestamp are
not collapsed into one cursor position.

Suggested reserved record:

```text
ecash_transfer_latest
```

Current storage:

```json
{
  "version": 2,
  "created_at": 1780000000,
  "event_id": "<64-character event id>"
}
```

The tuple `(created_at, event_id)` defines deterministic ascending processing
order. Nostr `since` is inclusive, so Acorn queries the checkpoint second again
and discards tuples at or below the stored checkpoint. Timestamp-only cursor
records from earlier releases are accepted and migrated without replaying their
final second.

Relay reads are paginated backwards from a fixed snapshot time. Consecutive
pages deliberately overlap at their oldest timestamp, and event IDs deduplicate
the overlap. Acorn then processes the complete collected backlog in ascending
checkpoint order. The checkpoint advances only through events whose receipt,
skip decision, or terminal error has been durably recorded.

If pagination reaches its configured page limit or a relay repeatedly returns
a saturated page from one timestamp, Acorn stops before processing and leaves
the checkpoint unchanged. Guessing at that boundary could permanently skip a
valid transfer.

The receive command should also support a manual `since` override for recovery,
debugging, or replay:

```sh
acorn receive-ecash --since 1780000000
```

When `--since` is supplied, it should override the stored cursor for that run.
The current behavior is:

- normal sweep advances the cursor;
- manual `--since` can advance the cursor only after successful processing;
- preview mode and direct event-ID lookup do not advance the stored cursor;
- operational failures stop at the last safely processed tuple.

See [Incoming Funds Reliability and Scaling](INCOMING-FUNDS-RELIABILITY-AND-SCALING.md)
for invariants, failure boundaries, and residual limits.

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

Gift wrapping is the default. For direct sender-authored debugging mode:

```sh
acorn ecash-transfer 21 <recipient-npub-or-nip05> --direct
```

Receive opportunistically before showing balance:

```sh
acorn receive-ecash
```

Preview pending incoming funds without accepting them or advancing the cursor:

```sh
acorn receive-ecash --preview
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
acorn receive-ecash --receive-key
```

When `--receive-key` or `--receive-nsec-file` is supplied and `--relay` is
omitted, Acorn attempts to
discover receive relays from the transient key's kind `0` profile and verified
NIP-05 relay hints.

Receive a specific event directly:

```sh
acorn receive-ecash --event-id <kind-1059-or-7378-event-id> --receive-key
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
3. publish a kind `1059` gift wrap containing an inner kind `7378` transfer to
   the recipient relay;
4. treat the token/proofs as sent and no longer locally spendable;
5. optionally wait for an acknowledgement in a future protocol extension.

Once token issuance has committed, the sender must assume those proofs have
left the wallet. A failed relay publish after token issuance requires careful
recovery UX because the sender may still possess a valid token that should be
resent or safely restored.

## Sender-side deletion

The sender should be able to clean up direct kind `7378` transfer events it
authored. This is useful after a recipient has accepted the transfer, or when
the sender wants to reduce relay-visible delivery history.

For default gift-wrapped transfers, the relay-visible event is kind `1059` and
is authored by a transient outer key. Unless the sender retains that transient
key, the sender cannot later author a valid deletion request for that outer
event. This is the privacy tradeoff of gift wrapping.

Future-dated gift wraps may include a NIP-40 tag on the signed outer event:

```json
["expiration", "<Unix timestamp in seconds>"]
```

Acorn exposes this as the optional `expiration` argument to
`send_ecash_transfer()` and as `acorn ecash-transfer --expires-in <seconds>`.
A supporting relay should stop serving the event after that time and should
delete it. NIP-40 remains advisory: a relay may retain expired data, a relay
that does not advertise NIP-40 support should not be assumed to enforce it,
and third parties may already have copied the encrypted event. Expiration is a
retention instruction, not a confidentiality or secure-erasure mechanism.

Deletion is performed with a standard NIP-09 deletion request, kind `5`, that
references the authored direct kind `7378` event ids with `e` tags and includes
a `k=7378` tag.

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

Gift-wrapped transfers are authored by a transient outer key. Unless the sender
retains that transient private key, the sender cannot later publish an
authoritative deletion request for the outer event. This is the main operational
tradeoff for hiding sender-recipient correlation.

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
