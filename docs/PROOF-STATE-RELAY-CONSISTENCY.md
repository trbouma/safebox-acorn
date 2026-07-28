# Proof State and Relay Consistency Design Note

## Summary

Acorn proof state lives at the intersection of two systems:

- Nostr relays store encrypted proof events.
- Cashu mints decide whether individual proofs are spendable.

Relays are storage and transport. They are not the source of truth for proof
spend status. The mint is the authority for whether a proof is unspent.

Relay migration exposed an important design lesson: read-only commands must not
mutate wallet proof state, and proof repair must remain explicit.

## What happened in testing

A wallet was replicated from the normal home relay to a test relay:

```text
ws://beelink:8735
```

Records were successfully readable from the test relay.

Then proofs were spent while the wallet was pointed at the replicated relay.
That made the test relay the freshest source of proof events. The original home
relay still contained stale encrypted proof events from before the spend.

When switching back to the original relay, Acorn saw a higher apparent proof
balance because stale proof events were still present. When proof repair checked
those proofs with the mint, the mint reported some as already spent, and Acorn
dropped them.

## Core lesson

Relay-visible proof events are not enough to know wallet value.

The apparent relay balance is:

```text
sum(encrypted proof events visible on relay)
```

The real wallet balance is:

```text
sum(proofs that the mint reports as UNSPENT)
```

These values can diverge during:

- relay migration;
- failed deletion propagation;
- interrupted proof rewrites;
- multi-relay replication;
- stale relay reads;
- adversarial relay behavior.

## Why deletion events matter

When proof state is rewritten, old proof events may be deleted using Nostr
deletion events.

If replication copies only proof events but not deletion events, the target
relay can retain stale proof history.

Therefore proof-state replication should include:

```text
5       deletion events
7375    proof events
```

For full wallet migration, Acorn's default replication includes both.

## Read-only commands must be read-only

Testing showed that `load_data()` could trigger automatic proof reduction when
the proof count exceeded a threshold. This meant a command like:

```sh
acorn balance
```

could start proof maintenance. That is wrong for operator safety.

The corrected rule is:

```text
balance/read commands may load and report state;
they must not swap, repair, consolidate, delete, or rewrite proofs.
```

Proof mutation should happen only through explicit commands such as:

```sh
acorn repair-proofs
acorn swap
acorn swap --consolidate
acorn deposit
acorn pay
acorn issue_token
```

## Explicit repair model

`repair-proofs` is the appropriate tool for reconciling stale relay proof state.

It should:

1. load visible proof events;
2. group and deduplicate proofs;
3. ask the mint for proof states;
4. drop proofs that are already spent;
5. keep or refresh usable proofs;
6. rewrite clean proof state to the current home relay.

Warnings such as:

```text
reason=already_spent
```

are expected when stale relay events are being cleaned.

## Migration consistency pattern

If spending occurs while pointed at a replicated relay, the safest convergence
pattern is:

```text
fresh relay proof state
  -> replicate kinds 5,7375
  -> original relay
  -> repair-proofs
  -> balance
```

Example:

```sh
acorn replicate \
  --source ws://beelink:8735 \
  --target relay.getsafebox.app \
  --kinds 5,7375

acorn set --home wss://relay.getsafebox.app
acorn repair-proofs
acorn balance
```

## Design implications

### Relays are eventually consistent storage

Acorn should assume that relays can be:

- stale;
- incomplete;
- unavailable;
- duplicated;
- adversarial;
- inconsistent with other relays.

### The mint is the spend-state authority

For Cashu value, the mint's `checkstate` and swap responses are decisive.

### Proof writes need verification

After rewriting proof events, Acorn should verify that the expected proof state
can be loaded back from the relay.

### Replication needs verification

Replication should eventually support a verify step that confirms target relay
visibility after publish.

## Possible future improvements

### Proof state epochs

Acorn could publish an encrypted proof-state epoch marker. A relay reader could
prefer the latest epoch and ignore older proof events.

### Latest proof-state pointer

Acorn could maintain a small encrypted reserved record pointing to the latest
valid proof event IDs.

### Relay comparison command

A future command could compare source and target relay event sets:

```sh
acorn relay-diff --source relay-a --target relay-b
```

### Dry-run repair

`repair-proofs` could support:

```sh
acorn repair-proofs --dry-run
```

to report what would be dropped without rewriting state.

### Guided migration command

A future wizard could combine:

1. replicate;
2. verify target;
3. switch home relay;
4. verify balance;
5. optionally replicate proof updates back.

## Operational rule of thumb

When in doubt:

```text
replicate events;
repair proofs explicitly;
trust the mint for spend state;
verify balance before spending again.
```

