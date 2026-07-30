# Relay Resilience and Replication Design

## Summary

Acorn should make relay-backed wallet data resilient in the same spirit that ZFS
makes filesystem data resilient: easy to replicate, easy to verify, and possible
to move to new infrastructure when the current storage target becomes
unreliable.

The design goal is not to clone ZFS literally. Nostr relays are not block
devices, and Cashu proof spend state is ultimately controlled by mints. The goal
is to adopt the same operator-friendly posture:

```text
replicate deliberately;
verify before trusting;
promote a good replica;
operate from a pool when necessary;
repair explicitly.
```

## Motivation

Acorn wallets currently depend on a `home_relay` for wallet metadata, encrypted
records, proof events, and reserved records. This creates a practical dependency
on relay availability and behavior.

A relay can become:

- unreliable;
- slow;
- unavailable;
- censored;
- hostile;
- stale;
- incomplete;
- expensive or operationally inconvenient.

Users should be able to move without losing wallet continuity.

## ZFS-inspired mental model

The useful analogy is:

```text
ZFS dataset       -> Acorn signed event set
ZFS snapshot      -> point-in-time visible relay event state
zfs send/receive  -> relay-to-relay signed event replication
pool health       -> relay pool status and event availability
scrub             -> verify event visibility and proof spend state
promotion         -> move home_relay to a verified replica
```

The analogy is imperfect but helpful. Acorn's replication unit is a signed Nostr
event, not a filesystem block. The important invariant is that signed events can
be copied without rewriting their identity.

## Swarm-style encrypted replicas

Another useful mental model is a swarm of encrypted replicas.

One relay gives the wallet a home. A community of relays creates continuity.
Additional relays can hold encrypted copies of the same signed event set. Those
relays improve availability without receiving plaintext access.

The goal is reciprocal safes, not a shared folder. Each participant can help
hold another participant's encrypted recovery path, but nobody receives pooled
plaintext access or shared account control.

The useful object is isolated encrypted tenant state that can be mirrored
across infrastructure chosen by the user.

The value proposition is reciprocal resilience:

```text
communities can preserve each other's recovery paths without becoming each
other's custodians.
```

In Acorn terms:

```text
primary safe       -> home_relay
mirror safe        -> replicated relay
swarm              -> trusted relay pool
tenant             -> wallet identity and encrypted record namespace
encrypted mirror   -> copied signed encrypted Nostr events
recovery context   -> home_relay + seed phrase + nsec + runbook
```

This framing keeps the focus on continuity. A single relay should not be the
only route back to a user's records, wallet metadata, and recovery context.

### Isolated tenants

The useful unit is an isolated encrypted tenant. In Acorn, this means:

- one wallet identity;
- one encrypted record namespace;
- one recovery context;
- one signed event set;
- one set of relay and mint preferences.

The infrastructure operator can host that tenant's encrypted events without
being able to read the tenant's records or spend its proofs.

### Tenant on relays, client to mints, component behind services

An Acorn instance has several complementary infrastructure relationships:

```text
relay relationship      -> encrypted tenant
mint relationship       -> value client
execution relationship  -> user-authorized component
```

On a relay, an Acorn instance is best understood as an encrypted tenant: a
signed event set associated with one wallet identity and record namespace. The
relay hosts availability for the tenant. It does not become the owner of the
tenant's contents, keys, funds, or record-control decisions.

With a mint, the same Acorn instance is a client. The mint issues, swaps,
melts, and verifies Cashu proofs. The mint is authoritative for proof spend
state, but it is not the user's application account and it does not host the
user's private record namespace.

Acorn may also run as a private component inside an execution environment
operated for the user. The operator is whoever provides the running code or
execution context: the user, a household, a community, an employer, a hosted
service, an appliance, or a product such as Safebox. In that deployment, the
operator can provide web presence, Lightning address support, default relays,
operational monitoring, onboarding, and customer support. The service may make
Acorn accessible to ordinary users without requiring them to run their own
infrastructure.

This operator-run model must be described honestly. If the operator holds or
can exercise key material, the user is delegating operational control to that
operator. If keys are held locally, in hardware, or in a constrained signing
environment, the operator is running more of the service surface than the
authority boundary. Both models can be useful, but they have different trust
assumptions.

This distinction matters:

- relays provide availability for encrypted state;
- mints provide issuance and spend-state validation for ecash proofs;
- applications provide user experience and workflows;
- trusted operators may run user-authorized Acorn components and service
  endpoints;
- the user-controlled key material remains the continuity boundary.

An Acorn tenant can be replicated across relays while remaining a client of one
or more mints. Relay migration changes where encrypted state is available. Mint
choice changes where value proofs are issued and redeemed. Neither should
change the user's application-level identity or private record namespace.

### Reciprocal resilience

Relay resilience does not require every user to own every relay. Users can host
encrypted replicas for each other:

```text
Alice hosts Bob's encrypted Acorn event set.
Bob hosts Alice's encrypted Acorn event set.
Neither receives plaintext access.
```

This is reciprocal infrastructure, not a shared account. It increases recovery
paths without turning every recovery copy into a new plaintext leak.

The broader principle is reciprocal resilience: a community can improve each
member's continuity by hosting encrypted replicas, while cryptographic
boundaries keep custody with each user.

It is closer to mutual assurance than to centralized insurance: participants
help each other stay recoverable without transferring custody of funds,
records, or secrets.

This is also a practical alternative to the false choice between SaaS/cloud
dependency and all-or-nothing self-hosting. Not every user should need to
operate their own full infrastructure. Acorn should support community-backed
models in which trusted people, groups, or service operators provide
availability while cryptographic control stays with the user.

The same model is useful when physical infrastructure is disrupted. Natural
hazards such as wildfires, earthquakes, floods, storms, and extended power or
network outages can make local homes, offices, devices, or data centres
temporarily unreachable. Relay replication gives the user more than one path
back to their encrypted wallet and record state, provided recovery material
remains available.

This should become a core Acorn design value, not merely a replication feature.
Relay pools, migration tools, recovery exports, and future hardware deployments
should all preserve this distinction between helping someone remain recoverable
and taking possession of their secrets.

### Pool health

A future relay pool should expose health in operational terms:

- which relays are reachable;
- which relays have the expected event IDs;
- which relays are missing proof or deletion events;
- which relay appears freshest for proof state;
- whether a relay is safe to promote as the new home relay.

The operator question should become:

```text
Is my encrypted tenant available from enough independent places to survive the
failure I care about?
```

## Core principles

### Signed events are replication units

Acorn should replicate signed Nostr events as-is.

This preserves:

- event IDs;
- signatures;
- authorship;
- encrypted content;
- tags;
- timestamps.

Replication should not decrypt and re-encrypt records unless a future explicit
re-keying workflow is introduced.

### The home relay is a pointer, not destiny

`home_relay` is the primary relay Acorn uses by default. It should be easy to
change after verifying another relay.

The user should think:

```text
my wallet is mine;
the home relay is where it currently lives.
```

### Reads should support merge and dedupe

When operating against multiple relays, Acorn should merge events and dedupe by
event ID.

For replaceable or stateful flows, Acorn must also understand which visible
event should be considered authoritative.

### Writes should support explicit replication policy

Acorn should eventually support multiple write policies:

```text
primary-only
  write only to home_relay

primary-plus-replicas
  write to home_relay and configured replicas

pool-write
  write to every relay in a trusted relay pool

manual-replicate
  write normally, replicate later by command
```

### Proof state requires mint verification

Relay replication can copy encrypted proof events, but relays do not determine
whether Cashu proofs are spendable.

The mint remains the authority for proof spend state.

Therefore proof-related replication should be followed by explicit proof repair
or verification when relay histories diverge.

## Existing capability

Acorn currently supports manual signed-event replication:

```sh
acorn replicate --target ws://beelink:8735
```

The source defaults to the current home relay.

Proof-state synchronization can be targeted:

```sh
acorn replicate \
  --source ws://beelink:8735 \
  --target relay.getsafebox.app \
  --kinds 5,7375
```

The default replication kinds include:

```text
0       profile
5       deletion events
37375   encrypted private records and wallet metadata
7375    encrypted proof events
30000   replaceable metadata, if used
30001   replaceable metadata, if used
30002   replaceable metadata, if used
```

## Desired workflows

### 1. Manual backup replication

Copy the current wallet event set to a backup relay:

```sh
acorn replicate --target ws://backup-relay:8735
```

Then verify:

```sh
acorn get_user_records --labels -r ws://backup-relay:8735
```

### 2. Relay promotion

Promote a verified replica to become the new home relay.

Possible future command:

```sh
acorn relay promote ws://backup-relay:8735
```

Expected behavior:

1. verify the target relay has wallet metadata;
2. verify private records are visible;
3. verify proof events are visible;
4. optionally run proof repair;
5. update local `home_relay`;
6. optionally store the previous home relay as a fallback.

### 3. Relay pool operation

Configure a set of relays for read/write resilience.

Possible future commands:

```sh
acorn relay pool add ws://beelink:8735
acorn relay pool add wss://relay.example.com
acorn relay pool status
acorn relay pool sync
```

Pool mode should support:

- read from many;
- dedupe by event ID;
- write to selected trusted relays;
- report relay lag or missing events;
- repair or resync missing events.

### 4. Scrub / verify

Acorn should eventually support a relay verification command.

Possible future command:

```sh
acorn relay scrub --relays relay-a,relay-b
```

Checks could include:

- wallet record visibility;
- record event count by kind;
- proof event visibility;
- deletion event visibility;
- event ID comparison between relays;
- proof state check against mint.

## Relay-native replication and negentropy

Acorn-level replication is intentionally simple: query signed events from a
source relay and publish those same signed events to a target relay. This works
with ordinary Nostr relay behavior and does not require special backend support.

Some relay implementations support more efficient backend or protocol-level
synchronization. For example, strfry supports negentropy sync, and NIP-77
defines a Negentropy set-reconciliation protocol for efficiently determining
which events differ between two event sets.

These mechanisms are complementary to Acorn's replication model:

```text
Acorn replicate
  application/component-level copy of the user's signed event set

Relay-native sync / negentropy
  relay/backend-level set reconciliation and efficient event transfer
```

Where available, relay-native sync can make replication faster and more
complete, especially for large event sets or ongoing relay mirroring. Acorn
should not require it, because not every relay supports the same sync protocol.
But Acorn should be designed to take advantage of it later.

Future Acorn relay tooling could:

- detect whether a relay advertises NIP-77 or negentropy support;
- prefer negentropy for relay diff/scrub when supported;
- fall back to ordinary Nostr filters when unsupported;
- expose operator guidance for strfry-style backend sync;
- verify that relay-native sync actually produced the expected event set.

The invariant remains the same: Acorn cares about the signed event set becoming
visible on the target relay. The transport mechanism can be ordinary query and
publish, negentropy reconciliation, relay backend sync, or another future sync
method.

### 5. Relay diff

Compare two relays before promotion.

Possible future command:

```sh
acorn relay diff --source relay-a --target relay-b
```

Expected output:

```text
Source: relay-a
Target: relay-b
Missing on target: 3
Extra on target: 1
Kinds:
- 37375: source=28 target=28 missing=0
- 7375: source=2 target=1 missing=1
- 5: source=1 target=0 missing=1
```

## Proof consistency model

Proof consistency is more subtle than record consistency.

For private records:

```text
if the signed encrypted event exists and decrypts, the record is present.
```

For proofs:

```text
if the signed encrypted proof event exists, the proof is visible;
if the mint says the proof is UNSPENT, the proof has value.
```

This distinction matters during migration. A stale relay can show proof events
for proofs already spent elsewhere.

Therefore:

- `balance` must remain read-only;
- `repair-proofs` must be explicit;
- proof repair should check the mint;
- deletion events should replicate with proof events;
- relay promotion should verify proof spend state before spending again.

See [Proof State and Relay Consistency](./PROOF-STATE-RELAY-CONSISTENCY.md).

## Reserved records and future relay metadata

Acorn already uses encrypted reserved records for some preferences, such as
`public_relays`.

Future relay resilience metadata could also be stored as encrypted reserved
records:

```text
relay_pool
replication_policy
last_replication_status
preferred_home_relay
previous_home_relay
```

The local plaintext config should remain minimal:

```yaml
nsec: nsec1...
home_relay: wss://relay.getsafebox.app
```

The richer policy can live in encrypted relay-backed records.

## Failure modes

### Target relay accepts some events but not all

Replication should eventually verify target visibility and report missing event
IDs.

### Source relay is stale

Replicating from a stale source can propagate stale state. Operators should
choose the freshest source relay, especially for proof events.

### Relays disagree

Acorn should prefer deterministic merge rules:

- dedupe exact events by event ID;
- for replaceable events, prefer the latest valid event by Nostr rules;
- for proof spend state, ask the mint.

### Relay deletes or censors events

Replication to another relay is the primary escape path. A future pool mode
should make this less manual.

## Practical security boundaries

Relay-backed does not have to mean public-internet hosted. Acorn should support
a range of deployment postures.

For ordinary data, a public or hosted relay may be acceptable because Acorn
records are encrypted before publication. For highly sensitive data, the user
can choose a stricter relay boundary:

- a relay behind a firewall;
- a relay reachable only on a private LAN;
- a relay inside a FreeBSD jail;
- a relay on a personal appliance;
- a relay reachable only over VPN, Tor, WireGuard, or Tailscale;
- a relay mirrored between trusted homes, offices, or jurisdictions.

This is part of the user-controlled security model. Security is not delegated
entirely to a corporate provider. The user can decide where encrypted protocol
state lives, who operates the infrastructure, and how many independent
locations should hold replicas.

## Near-term implementation roadmap

### Already implemented

- `acorn replicate --target <relay>`
- source relay override;
- kind override;
- confirmation prompt;
- JSON output;
- default inclusion of deletion events.

### Next candidates

1. `acorn relay diff`
2. `acorn relay verify`
3. `acorn relay promote`
4. encrypted `relay_pool` reserved record
5. pool read mode for records and proofs
6. pool write mode for critical wallet state
7. proof-state epoch or latest-proof pointer

## Operator rule of thumb

Use this mental model:

```text
replicate like ZFS send;
verify like scrub;
promote only after verification;
repair proofs explicitly;
trust the mint for spend state.
```
