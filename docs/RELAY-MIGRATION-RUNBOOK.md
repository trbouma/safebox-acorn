# Relay Migration Runbook

## Summary

This runbook describes how to migrate Acorn wallet data from one relay to
another when a home relay becomes unreliable, unavailable, or adversarial.

Acorn records and proofs are stored as signed Nostr events. Migration copies
those signed events to another relay. The records remain encrypted, but relay
metadata is still visible to the target relay.

## When to use this runbook

Use this runbook when:

- a home relay is unreliable;
- a relay operator becomes untrusted;
- you want a tested backup relay;
- you want to move an Acorn wallet to new infrastructure;
- you are validating disaster recovery.

Do not spend from multiple relays at the same time unless you understand the
proof-state consistency risks.

## Terms

### Source relay

The relay you are copying events from.

### Target relay

The relay you are copying events to.

### Home relay

The relay currently configured in local Acorn config as the primary wallet
relay.

Check it with:

```sh
acorn set
```

or:

```sh
acorn set --show-recovery
```

## Basic migration

To copy the current home relay data to a target relay:

```sh
acorn replicate --target ws://beelink:8735
```

Acorn shows the source, target, and default event kinds, then asks for
confirmation.

The default copied event kinds are:

```text
0       profile
5       deletion events
37375   private wallet and record events
7375    proof events
30000   replaceable metadata, if used
30001   replaceable metadata, if used
30002   replaceable metadata, if used
```

## Verify the target relay

Before switching home relay, query records directly from the target:

```sh
acorn get_user_records --labels -r ws://beelink:8735
```

Expected output is a list of record labels and a count.

You can also inspect proof visibility by temporarily switching:

```sh
acorn set --home ws://beelink:8735
acorn balance
```

If the balance and records look right, the target relay has enough data for
basic operation.

## Switch home relay

After validating the target:

```sh
acorn set --home ws://beelink:8735
```

Confirm:

```sh
acorn set
acorn balance
```

## Spending while on a replicated relay

If you spend while pointed at the new relay, the new relay now has the freshest
proof state. The old relay may still have stale proof events.

In that situation, do not assume the old relay is current.

To copy the latest proof state back to the old relay:

```sh
acorn replicate \
  --source ws://beelink:8735 \
  --target relay.getsafebox.app \
  --kinds 5,7375
```

Then switch back:

```sh
acorn set --home wss://relay.getsafebox.app
```

Repair and verify:

```sh
acorn repair-proofs
acorn balance
```

The repair step checks proofs against the mint and removes stale spent proofs.

## Expected repair warnings

During repair, warnings such as this can be normal after relay migration:

```text
reason=already_spent
```

This means a relay still had an encrypted proof event containing a proof that
the mint now reports as spent. The repair command drops it and rewrites the
wallet's proof state.

## Important safety rules

- Do not treat relays as the authority for proof spend status.
- The mint is the authority for whether a proof is spendable.
- Do not spend from two divergent relay states.
- After spending on a replicated relay, replicate `5,7375` back before relying
  on the old relay.
- Run `repair-proofs` after merging divergent proof history.
- Confirm `acorn balance` after every migration step.

## Recommended test sequence

This is a safe migration rehearsal:

```sh
acorn balance

acorn replicate --target ws://beelink:8735

acorn get_user_records --labels -r ws://beelink:8735

acorn set --home ws://beelink:8735
acorn balance

acorn set --home wss://relay.getsafebox.app
acorn balance
```

If you spend while on the target relay, add:

```sh
acorn replicate \
  --source ws://beelink:8735 \
  --target relay.getsafebox.app \
  --kinds 5,7375

acorn set --home wss://relay.getsafebox.app
acorn repair-proofs
acorn balance
```

## Troubleshooting

### Records appear but balance is wrong

Records and proofs use different event kinds. Replicate proof events too:

```sh
acorn replicate --source <source> --target <target> --kinds 5,7375
```

Then run:

```sh
acorn repair-proofs
```

### Balance shows stale higher amount

The relay likely contains old proof events. Run:

```sh
acorn repair-proofs
```

### Balance command emits maintenance warnings

Balance should be read-only. If `acorn balance` triggers proof mutation or swap
warnings, that is a bug. Run explicit maintenance with:

```sh
acorn repair-proofs
```

or:

```sh
acorn swap --consolidate
```

## Future improvements

- Add a dry-run replication mode.
- Add replication verification after publish.
- Add a command to compare source and target relay event IDs.
- Add proof-state epoch markers to reduce ambiguity.
- Add a safer migration wizard that guides the full sequence.

