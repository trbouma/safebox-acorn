---
title: Lockbox Product Vision
description: How Acorn, Safebox Web, Grove, and Spurline fit together as a local-first appliance family.
---

# Lockbox Product Vision

Lockbox is the long-term appliance direction for the Acorn stack: a local-first
runtime that brings together custody, records, storage, and relay continuity
under local control.

The product family is intentionally made of sibling projects. Each one should
remain useful on its own, while also fitting into a larger local appliance
profile.

![Lockbox family architecture](assets/images/lockbox-family-architecture.svg)

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

The human-facing web application for custody, records, offers, grants, and
workflows.

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

</div>

## The appliance direction

Lockbox packages these components into a local runtime for individuals and
communities. The initial target platform is FreeBSD on Raspberry Pi 4 with a
physical keypad and a TROPIC01 HSM.

That hardware direction matters. The keypad provides local presence for
unlock, approval, and recovery flows. The HSM provides a hardware-backed
boundary for sensitive key material and signing operations. The web interface
can request authority, but local hardware should govern high-risk actions.

> Network services can assist. Local presence controls authority.

## Product roles

Acorn is the protocol authority layer. It coordinates keys, signing, encrypted
records, wallet state, transfer flows, and recovery material.

Safebox Web is the user-facing application. It gives people a browser-based
workflow surface without becoming the system of record.

Grove is the blob-storage surface. It stores opaque bytes and attachments
without needing to understand plaintext records.

Spurline is the relay surface. It preserves relevant Nostr events locally and
creates a base for local continuity, network synchronization, and future mesh
operation.

Lockbox is the appliance packaging. It runs the family locally with predictable
services, durable local storage, health checks, hardware-backed controls, and a
clear operator experience.

## Why this matters

The goal is not to make every user become an infrastructure operator. The goal
is to make local continuity practical when it matters.

An individual, family, organization, or community should be able to run a
credible local home for keys, records, funds, storage, and relay state without
being trapped by any single application, hosted operator, relay, or storage
provider.

Acorn gives the stack portable protocol authority. Safebox Web makes it usable.
Grove preserves encrypted blobs. Spurline preserves events. Lockbox brings
them together as a local appliance.

[Read the detailed product note](https://github.com/trbouma/safebox-acorn/blob/main/docs/LOCKBOX-PRODUCT-VISION.md){ .md-button .md-button--primary }
[How Acorn works](how-acorn-works.md){ .md-button }
