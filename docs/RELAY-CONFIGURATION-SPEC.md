# Acorn Relay Configuration Specification

## Summary

Acorn uses relays for two different purposes:

- private wallet and record storage;
- public Nostr event discovery and publication.

These concerns should remain distinct. The local config should stay minimal,
while richer relay preferences can be stored as encrypted reserved records.

## Relay types

### Home relay

The home relay is the primary relay for Acorn wallet state.

Example:

```text
wss://relay.getsafebox.app
```

Acorn uses the home relay for:

- wallet metadata;
- private records;
- proofs;
- reserved records;
- lock records;
- recovery verification.

The home relay is part of the recovery bundle.

### General relays

`relays` are generic relay hints used by some read/write paths. With the minimal
config model, if no explicit relay list is configured, Acorn falls back to:

```text
[home_relay]
```

### Public relays

`public_relays` are preferred relays for public Nostr discovery, especially
when looking up events outside the user's home relay.

The primary current use case is zap event lookup:

```sh
acorn zap 21 <event-id> -c "from acorn"
```

If `--relays/-r` is not supplied, zap discovery uses stored public relays when
available.

## Local config

The local config should remain intentionally small:

```yaml
nsec: nsec1...
home_relay: wss://relay.getsafebox.app
```

Older or expanded configs may contain:

```yaml
relays:
- wss://relay.damus.io
public_relays:
- wss://relay.primal.net
replicate_relays:
- wss://nostr-pub.wellorder.net
```

These may still be read for compatibility, but the preferred model is to keep
only `nsec` and `home_relay` locally.

## Encrypted public relay preference

Public relay preferences are stored as an encrypted reserved record labeled:

```text
public_relays
```

Set them with:

```sh
acorn set --public-relays relay.damus.io,relay.primal.net,nos.lol
```

Show them with:

```sh
acorn set --show-public-relays
```

Example output:

```text
public_relays:
- wss://relay.damus.io
- wss://relay.primal.net
- wss://nos.lol
```

## Relay normalization

Relay values are normalized as follows:

- leading and trailing whitespace is removed;
- if the value starts with `wss://`, keep it;
- if the value starts with `ws://`, keep it;
- otherwise prefix `wss://`;
- duplicate normalized relay values are ignored where a unique list is needed.

Examples:

```text
relay.damus.io        -> wss://relay.damus.io
wss://relay.damus.io  -> wss://relay.damus.io
ws://localhost:8080   -> ws://localhost:8080
```

## Zap relay lookup

Zap event lookup follows this order:

1. explicit `--relays/-r` supplied to `acorn zap`;
2. encrypted `public_relays` reserved record;
3. discovery fallback built from home relay, configured relays, and constructor
   public relays.

If lookup fails, the error should include the relays searched:

```text
no event; searched relays: wss://relay.damus.io, wss://relay.primal.net
```

This makes relay failures diagnosable without enabling verbose logging.

## Relay migration and replication

If a home relay becomes unreliable, unavailable, or adversarial, Acorn can copy
the wallet's signed events from one relay to another:

```sh
acorn replicate --target new-relay.example.com
```

By default, the source relay is the current `home_relay`.

The command copies signed events as-is. It does not decrypt and re-encrypt
records. Preserving the original signed events means replicated events keep the
same event IDs and signatures on the target relay.

The default event kinds are core Acorn wallet kinds:

```text
0
5
37375
7375
30000
30001
30002
```

Callers may override the copied kinds:

```sh
acorn replicate --target new-relay.example.com --kinds 0,5,37375,7375
```

Because replication copies encrypted wallet data and visible event metadata to
another relay, the CLI asks for confirmation before publishing unless `--yes`
is supplied.

After replication, a user can test recovery or operation against the new relay
before changing their local `home_relay`.

For the operational migration sequence, see
[Relay Migration Runbook](./RELAY-MIGRATION-RUNBOOK.md).

For the proof-state consistency lessons behind this flow, see
[Proof State and Relay Consistency](./PROOF-STATE-RELAY-CONSISTENCY.md).

For the longer-term ZFS-inspired relay resilience model, see
[Relay Resilience and Replication Design](./RELAY-RESILIENCE-AND-REPLICATION-DESIGN.md).

## Security and privacy considerations

- Relay operators can see event metadata, timing, kind, author, and tags.
- Private records are encrypted, but relay access patterns are not hidden.
- The home relay can censor, fail to retain, or refuse access to wallet data.
- Users should retain recovery material and be prepared to move or replicate
  data if a relay becomes unreliable.
- Replication deliberately exposes the same encrypted events and metadata to
  the target relay. Only replicate to relays you are willing to use as wallet
  infrastructure.

## Non-goals

- Acorn does not attempt to hide that a public key uses a relay.
- Acorn does not guarantee relay availability.
- Acorn does not currently provide automatic multi-home relay failover.
