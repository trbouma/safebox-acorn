---
title: Mitigating AI and Quantum Attacks
description: A policy brief on reducing emerging security risks through user control, compartmentalization, cryptographic agility, and transparent trust boundaries.
---

# Mitigating AI and quantum attacks

## Policy brief

Artificial intelligence and quantum computing are often presented as one
undifferentiated future threat. They are not. AI is already changing the speed,
scale, and economics of familiar attacks. Quantum computing presents a
different risk: sufficiently capable future systems could undermine important
public-key algorithms on which today's secure communications depend.

The responsible response is neither complacency nor claims of absolute
security. It is to reduce unnecessary exposure now, separate the consequences
of compromise, preserve the ability to change infrastructure and cryptography,
and describe residual risks plainly.

Acorn applies that philosophy to user-controlled keys, funds and records.

!!! warning "Current status"

    Acorn is a developer preview and has not received a comprehensive
    independent security audit. Its ordinary Nostr operations use classical
    cryptography and must not currently be described as quantum-safe. The
    protected-record profile discussed below is still under design; only its
    initial key-generation primitives have been implemented.

## Two threat horizons

AI does not normally defeat sound encryption by itself. Its immediate effect is
to make conventional attacks cheaper and more convincing. Automated systems can
search for exposed secrets, identify vulnerable dependencies, generate targeted
phishing, imitate trusted communications, probe applications continuously, and
analyse large collections of leaked metadata. The problem is amplification:
more attacks, better tailored, conducted at machine speed.

Quantum risk is more structural. A cryptographically relevant quantum computer
could threaten widely used public-key schemes, including the elliptic-curve
cryptography underlying current Nostr keys and NIP-44 envelopes. Such a machine
does not yet exist at the scale required for these attacks, but sensitive data
collected today may still matter when the capability arrives. This creates a
practical **harvest now, decrypt later** concern.

These risks demand different controls, but they support the same architectural
conclusion: durable protection should not depend on one credential, one
algorithm, one application, or one infrastructure operator.

## The Acorn approach

### 1. Safeguard concrete resources

Acorn deliberately speaks about **keys, funds and records**. This vocabulary
makes the security obligations harder to obscure.

- Keys provide cryptographic authority and continuity. They are not, by
  themselves, the identity of a person.
- Funds are bearer proofs whose validity ultimately depends on their issuing
  mint.
- Records may be private and controllable, but an external issuer or legal
  framework may remain authoritative for their meaning.

This distinction matters in an AI environment. A valid signature establishes
control of a key; it does not prove that every claim made with that key is true,
that generated content is authentic in a broader social sense, or that a
counterparty should trust it. NIP-05 names, profiles, credentials, attestations,
prior relationships, and human judgement remain separate trust signals.

[Read A Better Vocabulary for Digital Policy](better-policy-vocabulary.md){ .md-button }
[Read the Acorn Record Model](https://github.com/trbouma/safebox-acorn/blob/main/docs/ACORN-RECORD-MODEL.md){ .md-button }

### 2. Separate keys, code and data

Acorn separates the component key, the code that exercises it, and the
relay-backed encrypted data it controls. A web application may provide the
execution environment, a relay may provide availability, a mint may validate
funds, and a blob server may retain encrypted attachments. None of those roles
should silently be treated as all-powerful or interchangeable.

Compartmentalization does not eliminate trust. The running code necessarily
handles plaintext and working keys in memory. Relays can suppress data. Mints
remain authoritative for proof spend state. Reverse proxies and application
operators can redirect or replace an interface. Making those boundaries
explicit allows deployments to reduce privileges, monitor the right systems,
and avoid pretending that encryption solves operational trust.

[Read Deployment and Trust](deployment-and-trust.md){ .md-button }
[Read the Acorn Component Boundary](https://github.com/trbouma/safebox-acorn/blob/main/docs/ACORN-COMPONENT-BOUNDARY.md){ .md-button }

### 3. Layer confidentiality instead of relying on one envelope

Private record metadata is currently protected with NIP-44. Blob content is
encrypted independently with a fresh AES-256-GCM key before it reaches blob
infrastructure. This is a useful separation: disclosure of an encrypted blob
does not disclose its plaintext without the corresponding blob key.

AES-256 is generally regarded as resistant to known quantum attacks when used
correctly, although quantum search changes its theoretical security margin. The
system as a whole is not therefore quantum-safe. Today, the blob key is held in
a NIP-44-encrypted record, and that public-key-derived envelope remains exposed
to future compromise.

The proposed protected-record profile addresses this gap with an independent
Record Protection Key (RPK). The RPK would wrap record keys inside the ordinary
NIP-44 envelope, so later compromise of the Acorn `nsec` alone would not reveal
protected records. Acorn now generates RPK material from operating-system
randomness or derives it from separately supplied 256-bit entropy using a
domain-separated HKDF. Acorn can encode the exact RPK as a separately labelled,
checksummed 24-word Protected record mnemonic, and Safebox Web implements an initial
backup and reconnect ceremony. Record encryption and migration remain future
work, and the complete profile still requires test vectors and independent
review.

[Read the Record Encryption Specification](https://github.com/trbouma/safebox-acorn/blob/main/docs/RECORD-ENCRYPTION-SPEC.md){ .md-button }
[Read the Protected Record Profile Design](https://github.com/trbouma/safebox-acorn/blob/main/docs/PROTECTED-RECORD-PROFILE-DESIGN.md){ .md-button }

### 4. Preserve cryptographic and infrastructure agility

Long-lived systems must be able to replace algorithms and providers without
discarding user continuity. Acorn uses versioned formats, explicit algorithm
identifiers, portable signed events, and relay replication as foundations for
that transition. Experimental post-quantum code is isolated behind an optional
package extra rather than being presented as ordinary production protection.

This is deliberately cautious. Adding a post-quantum library does not make an
application quantum-safe. Key generation, hybrid composition, serialization,
downgrade resistance, recovery, test vectors, dependency provenance, and
independent review all matter. Cryptographic agility is the capability to make
that migration safely—not a label applied in advance.

The current boundary therefore keeps KEM experiments out of the ordinary Acorn
component and its persisted record formats. Practical progress comes first from
independent AES-256-GCM blob keys, separation of the Acorn key from the Record
Protection Key, and recoverable compartment boundaries. If a KEM is evaluated,
it belongs initially to Safebox Web as an optional application-layer experiment.
Acorn should receive only the resulting validated secret or payload, without
depending on the experimental mechanism that produced it.

[Read the Cryptographic Evolution Roadmap](https://github.com/trbouma/safebox-acorn/blob/main/docs/ROADMAP-TO-RELEASABILITY.md){ .md-button }
[Read the Recovery Specification](https://github.com/trbouma/safebox-acorn/blob/main/docs/RECOVERY-SPEC.md){ .md-button }

### 5. Reduce collection and preserve availability

Encryption protects confidentiality; it does not guarantee availability or
erase metadata. Public relays and blob servers may expose timing, authorship,
traffic patterns, or the existence of ciphertext. Operators may censor, retain,
or delete data contrary to a user's wishes.

Sensitive deployments can reduce the material available for automated or
future cryptanalytic harvesting by placing relays and blob servers behind
firewalls, VPNs, private gateways, or other independent access controls. Data
can also be replicated across suitable providers or community infrastructure.
This creates reciprocal resilience: participants help preserve one another's
encrypted state without sharing plaintext, signing keys, or pooled custody.

Private infrastructure is not a substitute for backups, and replication is not
a substitute for encryption. Together they reduce the chance that one breach,
provider failure, natural hazard, or political disruption becomes permanent
loss.

[Read Relay Availability and Reciprocal Resilience](relay-availability-and-reciprocal-resilience.md){ .md-button }
[Read the Replication Design](https://github.com/trbouma/safebox-acorn/blob/main/docs/RELAY-RESILIENCE-AND-REPLICATION-DESIGN.md){ .md-button }

### 6. Design for machine-speed attack without removing human control

AI-amplified threats make operational discipline more important. Acorn's
current safeguards include hidden secret entry, owner-only configuration,
secret-safe logging rules, explicit recovery verification, authenticated
encryption, proof inspection before repair, payment reconciliation, relay
readback, and automated unit and live interoperability tests.

The objective is not to automate every judgement. High-impact actions—recovery,
wallet replacement, deletion, burning a wallet, and disclosure of recovery
material—need explicit boundaries and understandable confirmation. Automation
should make secure operation repeatable while leaving consequential authority
visible to the user.

[Read the Secure Logging Specification](https://github.com/trbouma/safebox-acorn/blob/main/docs/SECURE-LOGGING-SPEC.md){ .md-button }
[Read the full Security Statement](https://github.com/trbouma/safebox-acorn/blob/main/SECURITY.md){ .md-button .md-button--primary }

## Policy implications

The broader lesson is that emerging-technology policy should evaluate
architecture, not slogans.

1. **Do not accept “AI-proof” or “quantum-safe” as an undifferentiated product
   claim.** Ask which asset, algorithm, attack, and time horizon the statement
   covers.
2. **Require migration paths.** Systems protecting long-lived records should
   version cryptographic formats and demonstrate how algorithms, applications,
   and infrastructure can be replaced.
3. **Separate confidentiality, authenticity and availability.** Encryption may
   protect content while an issuer remains authoritative for a claim and an
   operator remains capable of suppressing access.
4. **Minimize concentrated custody.** Users should have practical recovery and
   portability across compatible execution environments, not merely an export
   from one provider-controlled container.
5. **Treat metadata and retained ciphertext as security-relevant.** Access
   boundaries, retention policy, deletion limits, and replication strategy
   should be disclosed alongside encryption choices.
6. **Fund testing and review, not only new algorithms.** Secure integration,
   dependency integrity, operational testing, usability, and independent audit
   determine whether cryptography protects people in practice.

## A measured objective

Acorn's objective is not invulnerability. It is to make attacks less scalable,
compromise less comprehensive, recovery more portable, and future migration
possible. AI and quantum computing reinforce the value of that approach, but
they do not replace the ordinary work of secure engineering.

The durable policy principle is simple:

> Protect today's keys, funds and records in ways that preserve the user's
> ability to recover, relocate, and adopt stronger protections tomorrow.

[Review Acorn's current security status](security.md){ .md-button .md-button--primary }
[Review the project status](project-status.md){ .md-button }
