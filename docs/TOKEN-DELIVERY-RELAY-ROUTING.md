# Token Delivery Relay Routing

Status: Initial implementation

For cross-flow state, recovery rules, and known limitations, see
[Transfer resilience](TRANSFER-RESILIENCE.md).

## Purpose

Acorn separates the stable identities involved in a token transfer from the
routes used to complete it:

```text
recipient npub       -> who can decrypt and receive the transfer
Cashu/Clear keyset   -> which mint issued and can redeem the token
relay URL            -> where the encrypted transfer can currently be found
```

A relay URL is not a wallet identity. In particular, a Mainstay-internal Grove
address is only meaningful within that Docker network and cannot be used to
deliver a token between separate Mainstay installations.

## Inbox Relay Record

Acorn uses the NIP-17 kind `10050` event as the recipient's signed external
inbox relay list. The event is authored by the wallet identity and contains one
`relay` tag per externally reachable inbox:

```json
{
  "kind": 10050,
  "content": "",
  "tags": [
    ["relay", "wss://federation.example"],
    ["relay", "wss://backup.example"]
  ]
}
```

The `npub` remains stable when these routes change. Acorn accepts only a validly
signed kind `10050` event authored by the requested recipient and selects the
newest valid event. Operators should keep this list small and include only
relays that an outside sender can reach.

Publish a wallet's external inbox relays with:

```sh
acorn inbox-relays \
  wss://federation.example \
  wss://backup.example
```

Use `--publish-relay` one or more times to control where Acorn publishes or
looks for the record. Without inbox arguments, the command shows the current
signed record:

```sh
acorn inbox-relays
```

## Transfer Route Selection

For Cashu kind `7378` and Clear kind `7379` gift-wrapped transfers, Acorn uses
the following order:

1. An explicit relay supplied by the caller.
2. The recipient's signed NIP-17 kind `10050` inbox relays.
3. Advisory relay hints supplied by a caller that already resolved NIP-05.
4. Relay hints returned while resolving a NIP-05 identifier directly.
5. The sender's home relay as a temporary compatibility fallback.

Transfer results report the selected `relay_source` as `explicit`,
`nip17-inbox`, `recipient-hint`, `nip05-hint`, or `sender-home-fallback`. The
final fallback does
not prove that the recipient monitors the sender's home relay. It remains only
while existing wallets adopt kind `10050`; a future release should fail clearly
when no recipient-reachable route can be resolved.

Callers such as Safebox Web may pass `relay_hints` separately from `relay`.
Hints seed kind `10050` discovery and are used as a compatibility fallback;
they do not override a valid signed inbox record. Transfer results identify
this fallback as `recipient-hint`.

Inbox discovery and relay connection attempts are bounded by
`ACORN_TRANSFER_RELAY_TIMEOUT_SECONDS`, which defaults to five seconds. Before
exporting Cash or Clear bearer value, Acorn opens each selected relay and keeps
only routes that successfully connect. If none connect, it raises a recipient
relay availability error that explicitly confirms no value was sent. A failure
after export or publication begins remains unresolved and must not be presented
as a safe retry.

NIP-05 remains useful for discovering an `npub` and locating the initial signed
inbox record. It is not the durable recipient identity, and its relay hints do
not override a valid kind `10050` event.

## Mainstay Context

Within one Mainstay installation, the wallet's home relay can be an internal
Grove route such as `ws://grove:8080`. Mainstay supplies that context-specific
route, but it must not be published in a public NIP-05 response or external
kind `10050` record. Until Acorn can prove shared Mainstay membership itself,
the caller must pass that internal route explicitly when it knows sender and
recipient share the same context; explicit routes take precedence over the
external inbox record.

For communication between Mainstay installations, each receiving Acorn
advertises at least one mutually reachable external inbox relay. Its receive
worker monitors the union of:

- the internal home relay; and
- the external relays from its signed kind `10050` record.

This permits context-aware callers to keep local transfers local while external
gift wraps arrive through a federation or public relay. A later FIPS route can
replace the external WebSocket transport without changing the wallet `npub`,
mint keyset, or token format.

## General private messages

`secure_dm(nrecipient, message, dm_relays=None)` accepts NIP-05 addresses, npubs,
and hexadecimal public keys. It now reuses the payment-transfer destination
resolver for signed kind `10050` inbox discovery and NIP-05 relay hints:

1. An explicit, non-empty `dm_relays` list overrides discovery, including internal
   `ws://` routes selected by a caller that knows the deployment network.
2. Otherwise prefer the recipient's signed inbox relay list.
3. If no inbox record is available, use recipient NIP-05 relay hints if supplied.
4. If neither exists, fail with a request to configure an inbox or explicit route.
   Unlike the legacy transfer compatibility fallback, DMs do not silently use
   the sender's home relay.

The selected relays are checked for connectivity before publication. Messages
use an explicit kind `14` inner event and encrypted kind `1059` gift wrap.
Publication is awaited; the existing `message sent` API return string means
relay acknowledgement, not recipient retrieval or processing. No automatic
resend is made after an uncertain publication outcome, and no durable DM outbox
or exactly-once application processing guarantee is added here.

The CLI defaults to discovery; `acorn dm alice@example.com "Hello" --relays
ws://spurline:8080` explicitly selects an internal route. The CLI does not echo
message content, but command-line arguments can still be retained by shell
history or exposed through process inspection. Do not use this interface for
secrets that require protection from those local surfaces.

This update concerns sending. The legacy `listen_nip17()` implementation is not
a production executive inbox: it echoes received messages, writes decrypted
content to a local log, and can attempt token acceptance. It is unchanged here.
A Reach receiver needs a separate reviewed design for non-mutating
retrieval, authenticated message handling, durable checkpoints, deduplication,
retention, and explicit authorization before any task or payment action.

## Transfer milestone boundary

This milestone implements kind `10050` publication, signature-checked
resolution, transfer routing precedence, and multi-relay receive discovery. It
does not yet:

- prove that two wallets share the same Mainstay context;
- publish inbox records automatically during Mainstay bootstrap;
- acknowledge that the recipient accepted or refreshed a delivered token; or
- replace WebSocket relay locators with FIPS-native locators.
