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

Treat migration as a controlled single-writer operation. Stop or quiesce every
other Acorn, Safebox Web, browser page, and service worker using the wallet
before switching its home relay. Do not spend from two relay-backed views of
the same wallet.

## Why proof migration needs special care

Automatic spent-proof reconciliation protects Acorn from stale historical
proofs on the target relay. When the mint definitively reports a proof as
`SPENT`, Acorn removes it before another wallet mutation.

That mechanism cannot recover a newer replacement proof that was never copied
to the target relay. The mint can determine whether a known proof is spendable,
but it cannot reconstruct a replacement proof's secret for the wallet. A
destination containing only old spent proofs may therefore reconcile to a
lower balance even though valid replacement proofs remain on the source relay.

Migration must copy the freshest proof state before changing the home relay.

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

First stop wallet mutations and identify the relay containing the latest
successful payment, issuance, receipt, or repair. That relay is the migration
source even if local configuration currently names another relay.

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

Verify proof and deletion-event replication before switching. Until Acorn has
an exact relay-diff command, compare the replication result and retain access
to the source relay. A matching apparent balance alone is not sufficient: two
different proof sets can have the same total.

As a read-only secondary check, point a separate disposable configuration at
the target and run:

```sh
acorn check-proofs
acorn balance --verify
```

Do not mutate the wallet through this secondary configuration. Continue only
when records are readable, the mint-confirmed balance is expected, and the
replication report does not indicate missing proof or deletion events.

## Switch home relay

After validating the target:

```sh
acorn set --home ws://beelink:8735
```

Confirm:

```sh
acorn set
acorn check-proofs
acorn balance --verify
```

Resume wallet mutations only after these checks pass. Keep the old instance
stopped; its relay-backed lease is independent from the lease on the new home
relay.

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

The repair step performs an explicit whole-wallet refresh. Ordinary mutating
operations also remove mint-confirmed spent proofs automatically. Neither path
can recover replacement proofs that were not copied from the freshest relay.

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
- Stop all wallet writers before replication and keep the old writer stopped
  after switching home relay.
- After spending on a replicated relay, replicate `5,7375` back before relying
  on the old relay.
- Run `repair-proofs` after merging divergent proof history.
- Confirm `acorn check-proofs` and `acorn balance --verify` after every switch.
- Do not interpret automatic removal of spent proofs as recovery of missing
  replacement proofs.

## Recommended test sequence

This is a safe migration rehearsal:

```sh
acorn check-proofs
acorn balance --verify

acorn replicate --target ws://beelink:8735

acorn get_user_records --labels -r ws://beelink:8735

acorn set --home ws://beelink:8735
acorn check-proofs
acorn balance --verify

acorn set --home wss://relay.getsafebox.app
acorn check-proofs
acorn balance --verify
```

Keep all other instances stopped throughout the rehearsal.

If you spend while on the target relay, add:

```sh
acorn replicate \
  --source ws://beelink:8735 \
  --target relay.getsafebox.app \
  --kinds 5,7375

acorn set --home wss://relay.getsafebox.app
acorn repair-proofs
acorn balance --verify
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

### Balance becomes lower after stale proofs are removed

Do not assume the removed value was lost during reconciliation. First determine
whether the freshest source relay contains newer replacement proof events that
were not copied to the current relay. Stop wallet mutations, restore access to
the freshest relay, replicate kinds `5,7375`, and then verify against the mint.

### Two instances used different home relays

Stop both instances. Do not choose a winner based only on apparent balance.
Preserve both relay event sets, identify all replacement proof events, merge
kinds `5,7375` into one controlled destination, and run `check-proofs` before
repairing. Mint-confirmed spend state resolves old inputs, but exact proof-set
comparison is needed to avoid overlooking valid replacements.

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
- Add wallet-state generations and stale-writer conflict detection.
- Add a migration marker identifying source, target, and final generation.
- Add a safer migration wizard that guides the full sequence.
