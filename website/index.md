---
title: Acorn
description: A protocol-first component for safeguarding user-controlled keys, funds and records.
---

<section class="acorn-hero" markdown>

# Acorn

<img class="acorn-hero-mark" src="assets/images/acorn-logo.png" alt="Acorn geometric logo">

<p class="acorn-tagline">A protocol-first component for safeguarding user-controlled keys, funds and records.</p>

<p class="acorn-intro">Portable cryptographic authority, private records, value, recovery, and continuity across replaceable infrastructure.</p>

[How Acorn works](how-acorn-works.md){ .md-button .md-button--primary }
[View the source](https://github.com/trbouma/safebox-acorn){ .md-button }

</section>

## Why Acorn exists

People increasingly depend on platforms, services, devices, and applications
to hold the things that matter to them. The convenience is real, but keys,
records, value, and recovery can become inseparable from a particular product
or provider.

Acorn is designed around a simple user need: the ability to change those
surrounding systems without starting over. Applications can provide excellent
experiences and trusted operators can provide dependable services, while the
Acorn protocol state remains portable and recoverable.

The goal is practical independence, not isolation.

[Read how Safebox uses Acorn to create a digital lock box](digital-lock-box.md)

## A uniform model for controlled resources

Acorn's work with private records, transferable records, ecash, and Clear
balances points toward a broader architecture: the **Uniform Resource Model**.

URM treats a record as a resource with identity, authority, control,
representations, policy, state, and history. Transferability and fungibility
become explicit resource properties rather than assumptions hidden inside an
application.

[Explore the Uniform Resource Model](uniform-resource-model.md){ .md-button .md-button--primary }

## One component, three responsibilities

<div class="acorn-grid" markdown>

<article class="acorn-card" markdown>

### Keys

Acorn safeguards and exercises a public/private keypair. The keys provide
continuity and cryptographic authority across compatible applications and
environments without claiming to define the identity of the controller.

</article>

<article class="acorn-card" markdown>

### Funds

Acorn supports user-controlled ecash and Lightning workflows while keeping the
wallet's recovery path independent from any single application interface.
Mints continue to determine the validity and spend state of the value they
issue.

Acorn also receives organization-issued Clear transfers through a separate
kind `7379` path. It keeps each Clear balance partitioned by exact mint and CMU
and never adds those units to the sat-denominated Cash Balance.

</article>

<article class="acorn-card" markdown>

### Records

Private records are encrypted before being stored on relay infrastructure.
Users can retrieve, replicate, migrate, and recover their record state through
compatible Acorn environments.

</article>

</div>

[See how Acorn handles Clear transfers](clear-transfers.md){ .md-button .md-button--primary }

## Keys are not identity

An Acorn uses a cryptographic public/private keypair:

```text
private key (nsec) -> signing, decryption, and authorization
public key (npub)  -> addressing, verification, and encryption to Acorn
seed phrase        -> recovery material when Acorn generated or derived the wallet key
```

The keypair supplies authority and a stable protocol identifier, but it is not
identity itself. A counterparty may form an identity judgment from an amalgam
of NIP-05 names, kind `0` profiles, Lightning addresses, credentials,
relationships, prior interactions, and other context. Acorn can carry or
resolve some of those claims; it does not decide what they mean to another
party.

## Protocol-first continuity

Acorn separates the parts that conventional applications often bind together:

```text
keys  -> continuity and authority
code  -> execution environment
data  -> encrypted state on relays
mint  -> value issuance and spend state
app   -> experience and workflows
```

Because these layers are distinct, an application, device, relay, operator, or
deployment can be replaced without automatically replacing the Acorn keys,
authority, and controlled state.

This design supports individual use, trusted service providers, community
infrastructure, and appliance-style deployments without requiring every user
to become a full-time infrastructure operator.

The same separation also makes room for future Continuity Payments. When mints
or wider payment infrastructure are unavailable, nearby Acorns should be able
to transfer previously issued ecash locally, mark the result as provisional,
and reconcile with the issuing mint when connectivity returns.

## Reciprocal resilience

Acorn is designed for continuity that people and communities can help provide
to one another without sharing plaintext data or surrendering control.

> One Acorn node gives encrypted state a home. A community of nodes creates
> continuity.

The model is closer to reciprocal safes than a shared folder: participants can
host encrypted Acorn state for each other while each keyholder retains control
over their own contents.

## Security posture

Acorn handles private keys, encrypted records, and spendable ecash, so security
is treated as part of the component contract rather than an implied property.
The project documents what is protected, what must still be trusted, which
safeguards are implemented, and which risks remain.

Acorn is currently unaudited developer-stage software. It should be used only
with small test balances and non-critical records while fund-safety,
concurrency, packaging, and pilot release gates are completed.

[Read the security statement](security.md){ .md-button .md-button--primary }
[Full technical security policy](https://github.com/trbouma/safebox-acorn/blob/main/SECURITY.md){ .md-button }

## Project status

Acorn is under active development as a standalone component extracted from
Safebox. It has demonstrated encrypted private records, ecash and Lightning
flows, relay replication, recovery interoperability, and operation against
independently operated relays and mints.

The current focus is hardening fund safety, recovery behavior, packaging,
FreeBSD deployment, stable interfaces, and release automation. Until those
release gates are complete, Acorn should be treated as developer-stage software
and used only with small test balances.

The detailed specifications, design notes, operational runbooks, and project
roadmap remain maintained as reference material in the
[repository documentation](https://github.com/trbouma/safebox-acorn/tree/main/docs).
