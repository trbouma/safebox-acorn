---
title: Relay Availability and Reciprocal Resilience
description: How encrypted Acorn tenants can replicate, migrate, and receive community-supported availability without sharing custody.
---

# Relay availability and reciprocal resilience

An Acorn wallet stores signed and encrypted protocol state on Nostr relays. A
home relay gives that state a primary location. Replication gives the wallet
more than one path back when a relay, provider, site, or region becomes
unavailable.

The guiding principle is simple:

> One relay gives an Acorn wallet a home. A community of relays creates
> continuity.

## An Acorn wallet is an encrypted tenant

On relay infrastructure, an Acorn wallet is best understood as an isolated
encrypted tenant:

```text
wallet identity
encrypted record namespace
signed event set
wallet and proof metadata
recovery context
```

The relay provides storage and availability for those events. It does not
receive the private key needed to decrypt records or authorize wallet actions.

This differs from a shared account or folder. Several tenants can use the same
relay while retaining separate keys, namespaces, and control boundaries.

## The home relay is a pointer, not destiny

The home relay is Acorn's default read and write location. It can still become
slow, unreliable, unaffordable, censored, hostile, or permanently unavailable.

Acorn's resilience model is inspired by an operator-friendly storage posture:

```text
replicate deliberately
verify before trusting
promote a good replica
operate from multiple locations when necessary
repair inconsistencies explicitly
```

The unit of replication is a signed Nostr event. Copying an event as-is
preserves its identifier, signature, authorship, timestamp, tags, and encrypted
content. The replica does not need the plaintext.

## Replication is not the same as backup completeness

A target relay should be considered useful only after Acorn verifies that it
can return the required events. Relays differ in retention, indexing, deletion,
access policies, rate limits, and support for the event patterns Acorn uses.

Acorn maintains capability tests because accepting a WebSocket connection is
not enough. A relay suitable for ordinary social events may still fail wallet
bootstrap readback, private records, gift-wrapped delivery, or deletion flows.

Large event histories also require care. A bounded query reaching its result
limit does not prove that replication is complete. Backend mechanisms such as
negentropy or a paginated client protocol may be needed for full synchronization.

## Proof state has an additional authority

Relays can replicate encrypted proof events, but they cannot determine whether
Cashu proofs remain spendable. Only the issuing mint can do that.

After recovering from an alternate relay or merging divergent histories, Acorn
must verify proof state with the mint. Relay availability and mint validity are
separate dimensions:

```text
relay -> can the wallet retrieve its recorded proof state?
mint  -> are those proofs still valid and unspent?
```

## Reciprocal resilience

Encrypted tenants allow people and communities to help maintain one another's
recovery paths without becoming custodians of one another's contents.

```text
Alice hosts Bob's encrypted Acorn events.
Bob hosts Alice's encrypted Acorn events.
Neither receives the other's keys or plaintext records.
```

This is reciprocal resilience. It resembles mutual assurance: participants
improve each other's continuity without pooling control of the underlying funds,
records, or secrets.

The model is **reciprocal safes, not a shared folder**.

## A middle path

Relay replication provides a middle path between dependence on one SaaS
provider and requiring every user to operate complete infrastructure alone.

Families, teams, local organizations, professional communities, or trusted
providers can operate suitable relays. Users can choose the degree of
independence and support that fits their needs while encrypted state remains
portable.

This is useful during ordinary provider changes and during physical disruption.
Wildfires, floods, earthquakes, storms, extended power outages, or regional
network failures can make a home, office, device, or data centre unreachable.
Copies in independently operated locations provide additional recovery paths.

## Limits of the model

Replication does not guarantee that:

- every event was copied;
- every relay will retain or return it;
- a deletion request erased every copy;
- encrypted event metadata is private;
- stale proof state is spendable;
- the user's private key is safely backed up; or
- several relay hostnames represent genuinely independent infrastructure.

Resilience comes from explicit policy, verification, operational diversity, and
tested recovery—not merely from adding more URLs to a list.

## Direction of travel

Acorn currently supports manual signed-event replication and target readback.
Future work can develop relay pools, health reporting, freshness comparison,
write policies, continuous replication, and safer promotion workflows.

The operator-facing question should become:

> Is this encrypted tenant available from enough independent places to survive
> the failure that matters to its user?

[Explore deployment and trust](deployment-and-trust.md){ .md-button .md-button--primary }
[Return to recovery and continuity](recovery-and-continuity.md){ .md-button }

## Reference basis

- [Relay Resilience and Replication Design](https://github.com/trbouma/safebox-acorn/blob/main/docs/RELAY-RESILIENCE-AND-REPLICATION-DESIGN.md)
- [Relay Configuration Specification](https://github.com/trbouma/safebox-acorn/blob/main/docs/RELAY-CONFIGURATION-SPEC.md)
- [Relay Migration Runbook](https://github.com/trbouma/safebox-acorn/blob/main/docs/RELAY-MIGRATION-RUNBOOK.md)
- [Relay Suitability Ledger](https://github.com/trbouma/safebox-acorn/blob/main/docs/RELAY-SUITABILITY-LEDGER.md)

