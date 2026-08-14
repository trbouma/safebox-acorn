---
title: Mainstay and Lockbox Product Vision
description: How Mainstay and Lockbox bring Acorn, Safebox Web, Grove, Spurline, and optional Clear currencies together.
---

# Mainstay and Lockbox Product Vision

## A community continuity scenario

A satellite link goes down. A distant cloud service starts behaving
unpredictably. A tornado takes out the local registry office and bank. Solar
power and backup systems are keeping the electricity on, but the community has
lost access to much of what it needs to function: payment services, critical
records, local evidence, and the remote systems used to coordinate them.

The people, funds, and records have not disappeared. Access to the distant
infrastructure has. This is the moment Mainstay is intended for: providing a
local point of continuity so a community can keep using the resources already
within reach, coordinate through nearby infrastructure, and reconcile with
external systems when connectivity returns.

**Mainstay** is the future unified local-first application for records,
identity, payments, community resource coordination, and continuity.
**Lockbox** is the hardware-first appliance that gives Mainstay and its
supporting services a dedicated local home.

The product family is intentionally made of sibling projects. Each one should
remain useful on its own, while also fitting into a larger local appliance
profile.

The user path should remain simple. In ordinary conditions, someone can use a
web-connected service. If the hosted service, provider, or wider internet is
unavailable, Mainstay should be able to fall back to local Lockbox services
without becoming a separate emergency-only app.

The existing sibling architecture is the foundation Mainstay will unify:

![Current Lockbox component architecture](assets/images/lockbox-family-architecture.svg)

Clear is the newest optional sibling and is not yet shown in this first
architecture graphic. It sits beside Grove and Spurline as a local service that
Mainstay can use and Lockbox can host.

## Continuity at a glance

The letter-sized poster summarizes the application, appliance, component roles,
and what to do when external services are unavailable.

![Mainstay and Lockbox continuity poster](assets/images/mainstay-lockbox-continuity-poster.png)

[Download the print-ready PDF](assets/images/mainstay-lockbox-continuity-poster.pdf){ .md-button .md-button--primary }
[Open the vector version](assets/images/mainstay-lockbox-continuity-poster.svg){ .md-button }

## The product model

- **Mainstay** is the unified application and primary user entry point.
- **Lockbox** is the dedicated local appliance that runs Mainstay and its
  supporting services.
- **Continuity** is the capability: records and payments keep working across
  connected, local, mobile, and community conditions.
- **Clear** is the optional local mint for organizations that want bounded
  currencies or voucher systems without Bitcoin or Lightning.

Mainstay can also run without dedicated Lockbox hardware. Lockbox is the
integrated deployment for people and communities that want durable local
operation, hardware-backed controls, and appliance simplicity.

## The family

<div class="acorn-grid" markdown>

<article class="acorn-card" markdown>

### Acorn

The wallet, key, signing, record, and recovery runtime at the center of the
stack.

[Acorn source](https://github.com/trbouma/safebox-acorn)

</article>

<article class="acorn-card" markdown>

### Safebox Web

The current standalone app for custody, records, payments, handles, and
workflows, and an important foundation for Mainstay.

[Safebox Web source](https://github.com/trbouma/safebox-web)

</article>

<article class="acorn-card" markdown>

### Grove

A local-first Blossom server for opaque, content-addressed encrypted blobs and
attachments.

[Grove site](https://trbouma.github.io/grove/) ·
[Grove source](https://github.com/trbouma/grove)

</article>

<article class="acorn-card" markdown>

### Spurline

A local-first Nostr relay for event continuity, community infrastructure, and
mesh synchronization.

[Spurline site](https://trbouma.github.io/spurline/) ·
[Spurline source](https://github.com/trbouma/spurline)

</article>

<article class="acorn-card" markdown>

### Clear

An optional local-first Cashu mint for organization-defined points, vouchers,
and internal economies without Bitcoin or Lightning settlement.

[Clear site](https://trbouma.github.io/clear/) ·
[Clear source](https://github.com/trbouma/clear)

</article>

</div>

### Mainstay

Mainstay will provide one coherent entry point across these sibling products.
It does not replace their protocol boundaries or prevent them from remaining
independently useful.

## The appliance direction

Lockbox packages these components into a local runtime for individuals,
organizations, and communities. A deployment may optionally include Clear when
it needs a locally governed currency. The initial target platform is FreeBSD
on Raspberry Pi 4 with a physical keypad and a TROPIC01 HSM.

That hardware direction matters. The keypad provides local presence for
unlock, approval, and recovery flows. The HSM provides a hardware-backed
boundary for sensitive key material and signing operations. The web interface
can request authority, but local hardware should govern high-risk actions.

> Network services can assist. Local presence controls authority.

## Continuity modes

Lockbox gives the user app four plain operating modes:

| Mode | User meaning |
| --- | --- |
| **Connected Mode** | Normal connected use with hosted services, relays, external mints, optional Clear currencies, synchronization, and updates available. |
| **Local Mode** | Direct local use of the Lockbox appliance, including any configured Clear mint, when upstream internet or hosted services are unavailable. |
| **Mobile Mode** | A phone or nearby device supplies temporary upstream connectivity while Lockbox remains the local authority environment. |
| **Community Mode** | Nearby Lockboxes or participating devices exchange signed events, encrypted records, replicas, and provisional payment messages locally. |

The current Safebox Web app can start by showing **Connected Mode**. Later
versions can determine mode from service reachability, local pairing, bridge
state, and community mesh participation.

## Local internal economies with Clear

Clear extends the Mainstay family beyond globally connected payments. It is an
optional local-first mint for organizations and communities that want to create
their own bounded points or voucher system without adopting Bitcoin or running
Lightning infrastructure.

A Clear currency has its own governing authority, authorized treasurers,
operational mint, ledger, and recognition network. The organization decides
what the currency represents and which providers accept it. Clear provides
private Cashu bearer proofs, supply accounting, swaps, spent-state checks, and
retirement.

This can support:

- church meal, transportation, or benevolence vouchers;
- food-bank credits recognized by participating providers;
- campus, event, camp, or emergency allocations; and
- a resort payment system for guest credits, staff allowances, shops,
  restaurants, and activities on the resort's own network.

In the resort example, the resort treasury governs issuance and settlement. A
local Clear mint issues the resort-specific currency. Guests and staff hold
proofs in Acorn-backed wallets, participating services accept them, and
providers return proofs for retirement and reimbursement or internal
accounting.

```text
Organization establishes policy
            -> treasurer issues vouchers
            -> people use recognized local providers
            -> providers return proofs for retirement and settlement
```

The currency is not legal tender and does not need universal acceptance.
Ordinary money can fund the program and settle with providers, while Clear
coordinates the purpose-specific allocation in between with cash-like
possession, direct transfer, voluntary recognition, and privacy.

A locally reachable Clear mint also provides a stronger form of local payment
continuity. It can validate, swap, issue, and retire its own currency entirely
inside the local network. By contrast, proofs from an unreachable external
mint remain provisional until that mint returns. Mainstay should show this
difference clearly: local Clear finality is not the same state as a pending
Continuity Payment.

Clear remains optional. Mainstay should present configured currencies without
combining them, and Lockbox should never silently create a currency or imply
that operating an appliance grants authority to issue one.

## Continuity Payments

Continuity Payments are a future Lockbox capability for local commerce when
normal payment infrastructure is unavailable.

If a mint, Lightning path, hosted service, or upstream internet connection is
temporarily unreachable, nearby Acorns should still be able to transfer
previously issued ecash to one another. The receiving Acorn can hold that value
as provisional local payment material, and refresh or swap the proofs with the
mint when connectivity returns.

This is especially important for community continuity. A remote community might
lose satellite connectivity while still having a local network, local devices,
and local Lockbox services. Continuity Payments let local activity continue
with clear settlement boundaries:

- local transfer can happen now;
- mint finality is pending;
- reconciliation happens when the mint is reachable again.

A practical example is a cruise ship, remote community, or emergency response
site that normally uses a mint connected to global payments. If the satellite
link is blocked, rationed, or unreliable, the people nearby may still be able
to reach each other over a local network or mesh. Continuity Payments would let
them keep making small local payments from ecash already held by their Acorns,
then refresh or reconcile those proofs with the mint when the global link
returns.

When the mint is offline, a payment may not be exact because proofs cannot be
swapped for change. Safebox Web should show the closest transferable amount,
the difference from the requested amount, and ask the user to approve the
provisional transfer.

## Product roles

Mainstay is the unified application. It coordinates records, identity,
payments, synchronization, and continuity modes without becoming the system of
record.

Acorn is the protocol authority layer. It coordinates keys, signing, encrypted
records, wallet state, transfer flows, and recovery material.

Safebox Web is the current user app and foundation for Mainstay. It gives
people browser-based workflows without becoming the system of record.

Grove is the blob-storage service. It stores opaque bytes and attachments
without needing to understand plaintext records.

Spurline is the relay service. It preserves relevant Nostr events locally and
creates a base for local continuity, network synchronization, and future mesh
operation.

Clear is the optional local mint. It supports independently governed points,
vouchers, and internal economies while remaining separate from Bitcoin,
Lightning, and external Cashu mints.

Lockbox is the hardware-first appliance. It runs Mainstay and the family
locally with predictable services, durable local storage, health checks,
hardware-backed controls, and a clear operator experience.

## Why this matters

The goal is not to make every user become an infrastructure operator. The goal
is to make local continuity practical when it matters.

An individual, family, organization, or community should be able to run a
credible local home for keys, records, funds, storage, and relay state without
being trapped by any single application, hosted operator, relay, or storage
provider.

Acorn gives the stack portable protocol authority. Safebox Web provides the
current application foundation. Grove preserves encrypted blobs. Spurline
preserves events. Clear can support bounded local economies. Mainstay becomes
the unified entry point, and Lockbox brings the complete experience together
as a local appliance.

[Read the detailed product note](https://github.com/trbouma/safebox-acorn/blob/main/docs/LOCKBOX-PRODUCT-VISION.md){ .md-button .md-button--primary }
[How Acorn works](how-acorn-works.md){ .md-button }
