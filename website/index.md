---
title: Acorn
description: A protocol-first component for user-controlled identity, funds and records.
---

<section class="acorn-hero" markdown>

# Acorn

<img class="acorn-hero-mark" src="assets/images/acorn-logo.png" alt="Acorn geometric logo">

<p class="acorn-tagline">A protocol-first component for user-controlled identity, funds and records.</p>

<p class="acorn-intro">A portable foundation for cryptographic identity, private records, value, recovery, and continuity across replaceable infrastructure.</p>

[How Acorn works](how-acorn-works.md){ .md-button .md-button--primary }
[View the source](https://github.com/trbouma/safebox-acorn){ .md-button }

</section>

## Why Acorn exists

People increasingly depend on platforms, services, devices, and applications
to hold the things that matter to them. The convenience is real, but identity,
records, value, and recovery can become inseparable from a particular product
or provider.

Acorn is designed around a simple user need: the ability to change those
surrounding systems without starting over. Applications can provide excellent
experiences and trusted operators can provide dependable services, while the
Acorn protocol state remains portable and recoverable.

The goal is practical independence, not isolation.

## One component, three responsibilities

<div class="acorn-grid" markdown>

<article class="acorn-card" markdown>

### Identity

Identity means the cryptographic identity of the Acorn component—not the civil,
legal, or social identity of a person. A public/private keypair provides
continuity and authority across compatible applications and environments.

</article>

<article class="acorn-card" markdown>

### Funds

Acorn supports user-controlled ecash and Lightning workflows while keeping the
wallet's recovery path independent from any single application interface.
Mints continue to determine the validity and spend state of the value they
issue.

</article>

<article class="acorn-card" markdown>

### Records

Private records are encrypted before being stored on relay infrastructure.
Users can retrieve, replicate, migrate, and recover their record state through
compatible Acorn environments.

</article>

</div>

## Protocol identity, precisely defined

An Acorn identity is a cryptographic public/private keypair associated with an
Acorn component or wallet lineage:

```text
private key (nsec) -> signing, decryption, and authorization
public key (npub)  -> addressing, verification, and encryption to Acorn
seed phrase        -> recovery material when Acorn generated or derived the wallet key
```

The keypair does not claim to be the person. Human-readable names,
credentials, roles, and legal assertions are separate claims that may be
associated with the component through records or external trust frameworks.

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
deployment can be replaced without automatically replacing the Acorn identity
and its controlled state.

This design supports individual use, trusted service providers, community
infrastructure, and appliance-style deployments without requiring every user
to become a full-time infrastructure operator.

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
