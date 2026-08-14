# Mainstay Product Vision

## Product promise

**Mainstay is a local-first application for records, identity, payments, and
community resource coordination that keeps working across connected and
disrupted conditions.**

It gives individuals, organizations, and communities one dependable place to
manage the information and value they need to continue operating. Hosted
services can assist, but the user experience should not disappear when a
provider, mint, or wider network becomes unavailable.

![Mainstay logo](./assets/mainstay-logo.svg)

## User experience

Mainstay should make sophisticated continuity infrastructure feel ordinary:

- records remain available locally;
- payments can be received and preserved when finalization is unavailable;
- confirmed balance and pending value are always clearly distinguished;
- local activity synchronizes and finalizes when services return;
- one application works across connected, local, mobile, and community modes.

The user should not need to understand relays, proof denominations, blob
storage, or synchronization protocols to know what is available, what is
pending, and what action to take next.

## Product role

Mainstay is the unified application and primary entry point. It coordinates a
family of independently useful components:

- **Safebox** provides approachable records and payment workflows.
- **Acorn** provides portable keys, funds, records, signing, and recovery.
- **Grove** provides local-first encrypted blob storage.
- **Spurline** provides local event continuity and synchronization.
- **Clear** provides optional local-first currencies and voucher systems for
  organizations and communities that want an internal economy without Bitcoin
  or Lightning.

Mainstay does not become the authority or system of record. It presents and
coordinates the authority, evidence, and state preserved by the underlying
protocol components.

## Relationship to Lockbox

**Mainstay is the application. Lockbox is the appliance. Continuity is the
capability.**

Mainstay can run through hosted services or on compatible personal and
community infrastructure. Lockbox is the hardware-first deployment that runs
Mainstay and its supporting services locally with durable storage,
hardware-backed controls, and an appliance-like operating model.

## Design principles

1. **Local-first, not local-only.** Use helpful network services without making
   ordinary local operation depend on their continuous availability.
2. **Continuity without ambiguity.** Show what is confirmed, what is pending,
   and what can be finalized later.
3. **The app is not the authority.** Preserve portable records, keys, funds,
   and evidence outside the application boundary.
4. **One experience across modes.** Do not turn disruption into a separate
   emergency product or unfamiliar workflow.
5. **Useful components, coherent whole.** Keep Safebox, Acorn, Grove, Spurline,
   and Clear independently testable and replaceable while making them feel
   coherent to the user.
6. **Bounded economies remain bounded.** Present each Clear currency with its
   issuer, policy, recognition network, and settlement promise. Never imply
   that separate organizational currencies are interchangeable or legal
   tender.

## Near-term direction

Safebox Web is the practical foundation for Mainstay. Near-term work should
continue proving the component workflows independently, simplify the shared
user experience, and strengthen local operation before assembling the complete
Lockbox appliance profile.

The initial Mainstay experience should prioritize:

- records and payment workflows that already work end to end;
- a clear continuity-mode indicator;
- confirmed balance and pending transaction finalization;
- local Spurline and Grove integration;
- optional Clear currency discovery, distinct balances, and voucher workflows;
- recovery, migration, health, and synchronization visibility.

The goal is calm capability: records and payments remain understandable and
usable when conditions change.

## Related documents

- [Mainstay and Lockbox Product Vision](LOCKBOX-PRODUCT-VISION.md)
- [Continuity Payments](CONTINUITY-PAYMENTS-DESIGN.md)
- [Lockbox External Dependencies and Offline Transfer](LOCKBOX-EXTERNAL-DEPENDENCIES-AND-OFFLINE-TRANSFER.md)
- [Acorn Product North Star](ACORN-PRODUCT-NORTH-STAR.md)
- [Clear](https://trbouma.github.io/clear/)
