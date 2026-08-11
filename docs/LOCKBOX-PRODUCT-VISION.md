# Lockbox Product Vision

## Summary

Lockbox is the future local-first appliance product for the Acorn stack.

It packages Acorn, Safebox Web, Grove, and Spurline into a single local runtime
for individuals and communities that want custody, records, storage, and relay
continuity under local control.

The initial target platform is:

```text
FreeBSD on Raspberry Pi 4
with a physical keypad and TROPIC01 HSM
```

Lockbox should feel like an appliance rather than a hosted web application. It
should boot predictably, run locally, expose a clear local web interface, keep
state on durable local storage, and use hardware-backed controls for sensitive
authority.

## Product relationship

Acorn remains the protocol runtime at the center of the system. The sibling
products use Acorn or are used by Acorn:

- **Acorn**: wallet, identity, signing, record, and protocol runtime.
- **Safebox Web**: human-facing web application for custody, records, offers,
  grants, and workflows.
- **Grove**: local-first Blossom storage for encrypted blobs and attachments.
- **Spurline**: local-first Nostr relay for event continuity, community
  infrastructure, and mesh synchronization.
- **Lockbox**: appliance packaging that runs the full stack locally.

The intended relationship is:

```text
                     Lockbox
        local appliance / bundled runtime
                           |
        ------------------------------------------------
        |                    |                         |
   Safebox Web            Grove                   Spurline
   human workflows      blob storage             local relay
        \                    |                         /
         \                   |                        /
          ---------------- Acorn ---------------------
             wallet, keys, signing, records, recovery
```

Lockbox should not collapse these products into a monolith. Each component
should remain independently useful, testable, and replaceable. Lockbox provides
the integrated runtime, operating profile, hardware boundary, and local
operator experience.

## Positioning

Working sentence:

```text
Lockbox packages Safebox Web, Acorn, Grove, and Spurline into a local-first
appliance for individuals and communities.
```

Alternate:

```text
Lockbox is the local home for the Acorn stack: custody, records, storage, and
relay continuity running under your control.
```

The product should emphasize practical local continuity rather than isolation.
Network services can assist, but local presence controls authority.

## Appliance model

The target Lockbox appliance combines:

- **FreeBSD** as the base operating system.
- **Raspberry Pi 4** as the initial low-cost hardware target.
- **Safebox Web** as the local user interface.
- **Acorn** as the wallet, identity, signing, record, and recovery runtime.
- **Grove** as the local encrypted blob store.
- **Spurline** as the local Nostr relay.
- **TROPIC01 HSM** as the hardware-backed key protection and signing boundary.
- **Keypad** as the physical presence and approval interface.

The keypad and HSM are not decorative peripherals. They define the custody
boundary:

- the keypad supports local presence, PIN entry, unlock, approval, and recovery
  flows;
- the HSM protects key material and constrains sensitive operations;
- the web interface can request authority, but local hardware should approve or
  deny high-risk actions.

## Design principle

```text
Network services can assist, but local presence controls authority.
```

This principle should shape both the product experience and the internal
architecture:

- remote relays may help with availability, but Spurline preserves local event
  continuity;
- remote storage may be useful, but Grove preserves local encrypted blobs;
- web workflows may be convenient, but Acorn owns the protocol runtime;
- browser sessions may request actions, but keypad and HSM-backed policies
  should govern sensitive authority;
- hosted operators may provide support, but Lockbox should keep a credible path
  to local continuity.

## FreeBSD platform

FreeBSD is not just an implementation detail. It supports the appliance
direction by encouraging a small, inspectable, service-oriented deployment
model:

- predictable service supervision;
- conservative package and operating-system boundaries;
- clear filesystem layout;
- strong networking primitives;
- jails as a future isolation strategy;
- boring startup and shutdown behavior;
- suitability for long-running local infrastructure.

The initial Raspberry Pi 4 target imposes useful constraints: low power,
limited resources, local storage, simple thermal behavior, and a small physical
footprint. Those constraints should keep the stack disciplined.

## Component roles inside Lockbox

### Safebox Web

Safebox Web is the human-facing surface. It should provide the local browser UI
for records, custody, offers, grants, payments, recovery, and device status.

Safebox Web should not become the system of record. It uses Acorn and presents
flows around it.

### Acorn

Acorn is the continuity and authority runtime. It coordinates keys, signing,
wallet state, Nostr events, encrypted records, transfer flows, and recovery
material.

Acorn should remain protocol-first and usable outside Lockbox.

### Grove

Grove provides local-first Blossom storage for opaque encrypted blobs and
attachments. It should store bytes durably without needing to understand the
plaintext records they represent.

### Spurline

Spurline provides the local-first Nostr relay. It should preserve events
locally, support continuity during network disruption, and eventually
participate in selective synchronization with the broader relay network and
local mesh.

### TROPIC01 HSM

The TROPIC01 HSM is the intended hardware-backed trust boundary for sensitive
key material and signing operations. The integration should be designed so that
software compromise does not automatically imply unrestricted key use.

### Keypad

The keypad provides local presence. It should support flows such as unlock,
approve, deny, reset, and recovery confirmation without requiring trust in a
remote browser session.

## Early product requirements

Lockbox should eventually provide:

- single-device local startup for all stack services;
- predictable local URLs and ports;
- health and status views for Acorn, Safebox Web, Grove, and Spurline;
- local data directories with clear backup and migration semantics;
- service supervision and restart behavior suitable for FreeBSD;
- HSM initialization and health checks;
- keypad enrollment and approval flows;
- safe shutdown and restart behavior;
- local recovery and export flows;
- minimal dependence on external hosted services for ordinary local operation.

## Non-goals for the first appliance shape

The first Lockbox appliance should not try to be:

- a generic home server platform;
- a full hosted multi-tenant service;
- a replacement for all public relays;
- a replacement for all cloud backup;
- a monolithic rewrite of Acorn, Safebox Web, Grove, or Spurline.

The first goal is a coherent local appliance profile for the existing sibling
products.

## Open questions

- Which Acorn operations must be HSM-backed from the first appliance release?
- Which operations require keypad approval, and which can be policy-approved by
  the local runtime?
- Should Lockbox run each service directly under FreeBSD service supervision,
  inside jails, or in a phased hybrid model?
- What is the minimum viable local UI for setup, unlock, backup, recovery, and
  health?
- How should the appliance expose remote access without weakening the local
  authority boundary?
- What is the expected data backup model for the Raspberry Pi target?
- How should Spurline participate in mesh synchronization while preserving
  selective local storage?

## Product direction

Lockbox should make the Acorn stack feel dependable, local, and physical.

The long-term product promise is not that every user becomes an infrastructure
operator. It is that individuals and communities can run a credible local home
for keys, records, funds, storage, and relay continuity when that matters.

Acorn gives the stack portable protocol authority. Safebox Web gives it a human
interface. Grove preserves encrypted blobs. Spurline preserves events. Lockbox
brings them together as an appliance.
