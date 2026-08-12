# Lockbox External Dependencies and Offline Transfer

## Summary

Lockbox should be able to use external systems without becoming unavailable
when those systems are temporarily unreachable.

This matters for the long-term appliance model. Lockbox is intended to run
Acorn, Safebox Web, Grove, and Spurline locally. It may depend on external
systems for issuance, validation, publication, synchronization, or settlement,
but it should still preserve local continuity when the network is absent.

The design principle is:

```text
External systems may provide recognition and settlement.
Lockbox provides local custody, continuity, and deferred synchronization.
```

This note focuses on two important external dependency classes:

- OpenETR-style transferable record ecosystems;
- Cashu mints, including Nutshell-based mints.

## External dependency boundary

Lockbox should distinguish between:

- **local possession**: what the appliance currently holds, protects, and can
  present or transfer;
- **local continuity**: what the appliance has copied, stored, signed, queued,
  and can replay later;
- **external recognition**: what a mint, issuer, verifier, relay network, or
  community ultimately accepts as valid.

Lockbox can preserve and move local state without continuous connectivity. It
cannot force every external party to recognize that state.

That distinction keeps the product useful offline without overstating
settlement finality.

## OpenETR and transferable records

The general OpenETR theory of transferable records fits the Lockbox model.

A transferable record can be understood as:

```text
record + control state + transfer event + recognition rules
```

OpenETR-style events or records may be copied into Lockbox before the appliance
goes offline. Once local copies exist, Lockbox can preserve them, present them,
link them to Acorn-controlled state, and generate new local transfer events.

When the appliance reconnects, locally generated events can be transmitted to
the relevant relays, registries, verifiers, or counterparties.

This enables useful offline or intermittently connected flows:

- preload relevant events and records while online;
- verify local signatures and event chains offline when possible;
- generate local transfer or presentation events;
- queue outbound events for later publication;
- reconcile with external systems when connectivity returns.

The important limitation is recognition. A locally generated event may be
well-formed and signed, but the question of whether it is authoritative is
ultimately decided by the parties, protocols, registries, or communities that
recognize the control graph.

## Cashu proofs as transferable records

Cashu proofs are a concrete example of bearer transferable records.

Acorn can hold minted proofs locally. Lockbox can protect them, back them up,
display them, transfer them, and preserve their history without running a mint
itself.

The mint remains external infrastructure. It issues proofs, tracks spend
state, and ultimately determines whether a proof can be redeemed or swapped.

This gives Lockbox a useful boundary:

```text
Mint operation is external infrastructure.
Proof custody is local capability.
```

Lockbox does not need to run a local mint by default. Running a mint means
operating monetary infrastructure and, in ordinary Cashu deployments,
interfacing with Lightning. That brings liquidity, routing, uptime,
accounting, abuse, and operational risks that are outside the default Lockbox
appliance role.

Instead, Lockbox should be able to use external Cashu mints while keeping
proof custody local.

## Offline proof transfer

Minted proofs can be transferred while connectivity is absent or intermittent.
This can be useful because possession of the proof material can function like
cash between counterparties.

However, offline proof transfer has a double-spend limitation. Until the mint
is contacted, the receiving side cannot know with finality that the transferred
proofs have not also been spent, retained, or transferred elsewhere.

Safebox Web can implement an application guarantee: after transferring proofs,
it can delete those proofs from the sender's local wallet state and mark them
as transferred.

That guarantee is meaningful within the local application boundary. It reduces
accidental reuse and expresses the sender's local intent. It is not the same
as mint-level settlement.

Before Lockbox reconnects to the mint, the system may have:

- local sender state that says the proofs were transferred and deleted;
- local receiver state that says the proofs were received;
- another device or copy that still claims control over the same proof
  material;
- no mint confirmation yet.

That can create competing control graphs.

## Continuity Payments

The term "offline payment" can be misleading. A community may be offline from
the global network while still being online locally. For example, a remote
community may lose satellite connectivity but retain a local network, local
devices, and a local Lockbox appliance.

In that setting, the user-facing capability is better described as
**Continuity Payments**. The underlying mechanism is an **in-kind ecash
transfer** or **in-kind clearing** flow.

The phrase borrows from the idea of exchanging an asset for the same kind of
asset rather than settling through an intermediate cash or account layer. In
this context, the local transfer is not a promise to pay later in some separate
system. It is a transfer of the payment object itself:

```text
proofs for proofs
transferable records for transferable records
locally held payment material for locally held payment material
```

This distinction matters because the community is not necessarily offline in
the ordinary sense. It may still be able to:

- exchange events over a local mesh;
- move Cashu proof material between Acorns;
- preserve signed transfer records in Spurline;
- store related encrypted records or attachments in Grove;
- defer mint, relay, or external registry reconciliation until global
  connectivity returns.

Continuity Payments emphasize the reason this capability matters: people and
communities can keep operating locally when wider infrastructure is degraded.
In-kind ecash transfer describes the mechanism: payment material moves locally
as payment material. Together, the terms keep the settlement boundary visible.
Lockbox can help transfer and preserve payment material locally, but the
external mint, issuer, registry, or counterparty still decides what it
recognizes when the wider network is reachable again.

### Scenario: a global mint with a blocked local link

A community may normally rely on a mint that enables global payments. During
ordinary operation, Acorns deposit, pay, receive, and refresh proofs through
that mint. The mint provides the final spend-state check, while local Acorns
hold the issued bearer proofs.

The failure may be local rather than global. A cruise ship may have a blocked
or rationed satellite link. A remote community may have intermittent satellite
service. An emergency response site may retain a local network but lose
internet, mobile service, bank terminals, Lightning routes, and access to the
mint.

In that situation, the community is globally disconnected but locally online.
Lockbox can support local payment continuity:

- Acorns use previously issued proofs already held by their wallets;
- local network, mesh, or appliance transport carries encrypted payment
  transfers;
- Spurline preserves signed local payment events and evidence;
- the receiving Acorn marks the payment as provisional;
- when the mint becomes reachable, the receiver checks, refreshes, or swaps
  the proofs to establish finality.

This is useful for small, bounded local payments: meals and supplies on a ship,
community store purchases, clinic logistics, local transport, emergency fuel,
or temporary mutual-aid activity. It should not be presented as unconditional
settlement. It is a continuity mechanism for payment material until the
external mint can be consulted again.

When mints are unavailable, a payment may not be exact. Without mint access,
the sending Acorn may not be able to swap proofs into exact denominations. The
user app should calculate a close transferable amount and ask the user to
approve the difference before sending:

- requested amount;
- transferable amount available now;
- overage or shortfall;
- pending mint-finality status;
- reconciliation action when the mint becomes reachable.

## Competing control graphs

Offline transfer systems must tolerate the possibility of competing claims.

For OpenETR-style records, two parties may present different event histories or
control graphs. For Cashu proofs, two holders may attempt to redeem, swap, or
transfer the same proof material.

Lockbox should preserve enough evidence to explain what happened:

- locally observed prior state;
- locally generated events;
- signatures and timestamps;
- transfer records;
- application deletion markers;
- publication attempts;
- later mint, verifier, relay, or counterparty responses.

But Lockbox should not pretend to be the final judge for every external
recognition system.

Which control graph is treated as valid is ultimately left to the party or
system deciding to recognize it:

- a Cashu mint decides whether proofs are spendable;
- an issuer or registry may decide which transferable-record graph it accepts;
- a counterparty may decide which evidence it trusts;
- a community may decide which event history it recognizes;
- a court or governance process may decide a disputed real-world claim.

Lockbox can make those decisions more transparent by preserving the evidence.
It cannot eliminate the need for recognition rules.

## Deferred synchronization

Lockbox should support deferred synchronization as a first-class behavior.

When online, it can:

- fetch relevant OpenETR or Nostr events;
- query relays and mints;
- swap or redeem Cashu proofs;
- publish locally generated events;
- update local views of external recognition state.

When offline, it can:

- preserve copied events and records;
- verify what can be verified locally;
- generate signed local events;
- transfer proof material;
- queue outbound synchronization tasks;
- mark local application state and intent.

When connectivity returns, it can:

- publish queued events through Spurline and external relays;
- reconcile local events with external event graphs;
- contact Cashu mints to confirm or swap proof state;
- show conflicts explicitly rather than hiding them;
- retain local evidence even when an external system rejects a claim.

## Business and community continuity

The continuity goal is broader than ordinary application availability.

For an organization, Lockbox supports business continuity: the ability to keep
custody, records, payment material, local evidence, and operational workflows
usable when external services are degraded or unreachable.

For a remote community, the same model becomes community continuity. A
community that loses satellite network connectivity should still be able to
operate locally:

- local records remain available;
- local events can still be generated and exchanged;
- local proof transfers can still express payment intent or bearer-value
  movement;
- local evidence can still be preserved;
- pending outbound synchronization can wait until connectivity returns.

When the network comes back, Lockbox can publish, reconcile, and settle what
happened locally. It may still encounter conflicts or rejected claims, but the
community does not lose its local operating memory simply because the upstream
network was unavailable.

## Component implications

### Acorn

Acorn should treat transferable records and Cashu proofs as protocol state
that can be held locally, protected, moved, and recovered.

It should preserve enough metadata to distinguish local custody state from
external recognition state.

### Safebox Web

Safebox Web should provide human workflows for offline transfer, deletion
intent, pending settlement, conflict display, and later reconciliation.

It can delete local proofs after transfer as an application-level guarantee,
but it should not present that deletion as mint-level finality.

### Spurline

Spurline should preserve local events and queued outbound events. It should
support later publication and synchronization with the broader relay network
and local mesh.

### Grove

Grove should store any opaque encrypted blobs or attachments associated with
transferable records without needing to understand their recognition semantics.

### Lockbox

Lockbox should integrate these behaviors into an appliance experience:

- clear online/offline state;
- clear pending-settlement state;
- durable local queues;
- explicit conflict and recognition status;
- local backup and recovery of proofs, events, and records;
- hardware-backed controls for high-risk local actions.

## Product posture

Lockbox can use OpenETR ecosystems and Cashu mints without requiring them to be
available at every moment.

It can safeguard copied events, generate new local events, transfer bearer
proofs, and preserve evidence while offline. When connectivity returns, it can
publish, reconcile, and settle.

The product promise should be local continuity, not unilateral finality:

```text
Lockbox preserves local authority, continuity, and evidence.
External systems decide what they recognize.
```
