# Beyond Digital Identity, Credentials and Wallets

## A policy vocabulary for user-controlled keys, funds and records

**Policy brief — August 2026**

## Executive summary

Digital policy is increasingly organized around three familiar terms: digital
identity, digital credentials and digital wallets. Each term describes
important work. Together, however, they provide an incomplete vocabulary for
the systems now being built.

A digital wallet is an implementation: a software, service, device, or hardware
container through which a person or application uses digital resources. A
digital credential is an important but specialized kind of record, normally
structured around claims, an issuer, a holder, and a verifier. Digital identity
describes how a person, organization, device, or component is represented and
recognized, but it is too often treated as though it were simply a key or an
identifier. Meanwhile, funds and their control, safekeeping, transfer,
settlement, and recovery sit largely outside this vocabulary.

Policy should begin with the resources that must remain usable and under
appropriate control:

```text
keys, funds and records
```

- **Keys** provide cryptographic continuity and authority. They can contribute
  to identity, but they are not identity themselves.
- **Funds** are controlled units or claims of value. Payments are operations
  that move or settle funds; they are not a substitute for modelling the funds
  a user holds.
- **Records** include credentials, but also private files, attestations,
  transaction histories, configuration, operational state, and transferable
  electronic records.

Keys and signed events also clarify the boundary between identity and trust. A
key supplies cryptographic authority; signed events provide evidence of that
authority being exercised over time. Identity is the contextual interpretation
of the actor behind that continuity. Trust is a relying party's judgment that
an intentional actor continues to govern the key and can be relied upon or held
accountable. None of those human judgments is produced by a signature alone.

This vocabulary does not abolish identity, credentials, wallets, or payments.
It puts them in their proper places: identity is an interpretation and
recognition problem; credentials and payment instructions are particular kinds
of records or operations; and wallets are implementations used to safeguard and
act upon resources.

The policy consequence is practical. Standards, procurement, and public digital
infrastructure should specify how keys, funds, and records can be controlled,
recovered, moved, verified, and used across replaceable applications and
providers. The application called a “wallet” should not become the conceptual
or technical owner of everything placed inside it.

## Why the vocabulary must change

This brief builds on [*The Niels Bohr Moment for Digital
Architecture*](https://trbouma.substack.com/p/the-niels-bohr-moment-for-digital),
which argues that a field sometimes needs better questions before it needs
another architecture. Today's vocabulary was shaped by applications,
databases, user accounts, authentication, and authorization. It is now being
asked to describe cryptographic authority, AI agents, digital assets,
electronic transferable records, and software actions with legal and financial
consequences.

The essay distinguishes five concerns:

- **identity** — who is participating;
- **intent** — what they are trying to accomplish;
- **control** — who can exercise authority over an object;
- **recognition** — what legal, contractual, or institutional meaning applies;
- **evidence** — why another party should believe a claim.

These are related, but none answers the others. A cryptographic signature may
provide evidence that a key authorized an action. It does not, by itself,
establish the human identity of the controller, the controller's intent, legal
title to the object, or the institutional recognition of the action.

The same discipline should be applied to the nouns used in digital policy. A
wallet is not the resources it contains. A credential is not the entire universe
of records. A key is not a person. A payment is not the funds from which it is
made. When these distinctions are blurred, standards become overextended and
systems become harder to migrate, recover, and govern.

## Where the current terms fall short

| Common term | What it usefully describes | What it can obscure | Resource-oriented interpretation |
| --- | --- | --- | --- |
| **Digital identity** | Representation and recognition of a participant in a context | A key or identifier can be mistaken for the identity of a person; identity evidence, social context, and recognition are collapsed into authentication | Keys provide continuity and authority; records carry claims and evidence; counterparties and institutions make identity judgments |
| **Digital credential** | A structured, often issuer-backed set of verifiable claims | Credentials are only one record class and do not cover private notes, configuration, blobs, histories, mutable state, or many transferable records | A credential is a typed record with particular issuance, presentation, verification, and status rules |
| **Digital wallet** | An application, service, device, or hardware environment used to hold and present digital material | The container is confused with the resources, and portability can mean moving between screens rather than retaining control across providers | A wallet is one replaceable implementation for safeguarding and exercising keys, funds, and records |
| **Digital payment** | An instruction or transaction that transfers value over a rail | The persistent funds state, custody, proof validity, fees, recovery, and settlement dependencies remain outside the model | A payment is an operation on funds; funds must also be represented as a controlled resource |

The [W3C Verifiable Credentials Data Model](https://www.w3.org/TR/vc-data-model/all/)
provides a strong model for expressing claims made by an issuer. Its
issuer-holder-verifier pattern is appropriate for credentials. It should not be
required to describe every record a person or component needs to safeguard.
Likewise, the [European Digital Identity Wallet framework](https://eur-lex.europa.eu/eli/reg/2024/1183/oj?locale=en)
properly emphasizes user control over identification data and attestations.
The policy opportunity is to extend this attention to control and portability
beyond identity material, without weakening the specialized rules that make
credentials and identity wallets useful.

## A resource-oriented vocabulary

### Keys

Keys are cryptographic resources used for signing, decryption, addressing, and
authorization. A public/private keypair can provide continuity across devices,
applications, and providers. Control of the private key can demonstrate that a
particular key authorized an operation.

That is not the same as proving who the controller is. Identity may be formed
from names, profiles, credentials, attestations, legal records, relationships,
prior interactions, and what a counterparty or institution recognizes. A key
can anchor or verify some of that evidence without becoming the identity
itself.

Policy should therefore ask how keys are generated, protected, delegated,
rotated, recovered, and replaced—and separately ask what identity or legal
meaning others attach to them.

### From key control to identity and trust

Digital systems often compress a longer chain of reasoning into the statement
that an identity has signed something. A more precise model is:

```text
keypair
  -> cryptographic authority
signed events over time
  -> verifiable continuity and evidence of key use
identity
  -> contextual interpretation of the actor behind that continuity
trust
  -> willingness to rely on intentional control and accountability over time
```

A signature proves that a key authorized exact bytes. A continuing series of
signed events can provide useful evidence of provenance, relationships, prior
conduct, and protocol state. Neither proves that the content is true, that the
event timestamp is independently established, or that a conscious actor
personally intended the action.

For this brief, an **intentional actor** is a person, or people acting through
an organization, capable of forming purposes and accepting responsibility.
Software and AI agents can exercise delegated authority, but a valid signature
does not prove that the software is conscious. Trust in an automated action is
ultimately trust in the actor who authorized, constrained, supervised, or
accepted accountability for that automation.

Trust is therefore not stored inside a key or produced automatically by a
signature. It is a relying party's judgment that a key and its signed history
remain under intentional control and that the controller's mandate, behaviour,
and accountability are sufficient for the decision at hand. Key theft,
coercion, hidden delegation, or uncontrolled automation can preserve perfectly
valid signatures while breaking that trust relationship.

This layered model also makes rotation and recovery clearer. A new key can
continue an existing identity or trust relationship only when the transition is
credibly authorized and recognized. Possession of replacement key material is
not, by itself, proof of continuity.

This use of **trust** should be distinguished from **operational reliance**.
A system may depend on a relay for availability, a mint for spend-state
validity, or an application operator for correct execution. Those are important
trust dependencies, but they are not evidence that the provider is the actor
represented by a key. Policy should name both questions: who intentionally
controls an authority over time, and which infrastructure must behave correctly
for that authority to be useful.

### Funds

Funds are controlled units or claims of value. Depending on the system, their
validity may depend on a bank, mint, ledger, payment network, or legal issuer.
The relevant questions include who can spend them, how validity is checked,
where settlement occurs, how double spending is prevented, how balances are
recovered, and how users exit an intermediary.

“Digital payment” usually names the act of paying or the rail used to do so. It
does not fully describe the value state before and after the transaction. A
resource-oriented model makes funds first-class while retaining the distinct
roles and obligations of issuers and payment providers.

This does not imply that identity and payment systems should be administratively
merged. It means their technical boundaries should be explicit and
interoperable when a use case requires both.

### Balances as a practical projection

Working implementations now make a more general product vocabulary visible.
Fungible controlled records can be aggregated within an explicit equivalence
domain and presented as a **balance**. Non-fungible records remain individually
meaningful:

```text
fungible controlled records     -> balances
non-fungible controlled records -> records
```

This does not turn a balance into an application-owned account entry. The
balance remains derived from underlying records and bounded by their issuer,
unit, keyset, policy, and validation rules. Nor does it make every transfer a
payment. Payment is the value or settlement leg of an economic transaction;
allocation, gifting, benefits, refunds, issuance, and treasury disbursement may
use transfers without being payments.

Accordingly, **keys, balances and records** is often the clearest product-level
vocabulary, while **funds** remains the appropriate domain term for monetary
value and regulated claims.

### Records

Records are digital objects whose content, provenance, control, and lifecycle
matter. They include:

- verifiable credentials and attestations;
- private personal, healthcare, and organizational records;
- files and encrypted blobs;
- configuration and recovery pointers;
- transaction and audit histories;
- grants, permissions, offers, and requests;
- transferable electronic records and digital instruments.

Records may be public or private, mutable or immutable, issued or self-created,
transferable or non-transferable. A credential is one valuable record profile,
not the general category. Starting with “records” lets policy define the rules
appropriate to each profile rather than forcing all important data into a
credential-shaped model.

### Containers and components

A wallet, application, browser, phone, secure element, hardware module, or
hosted service is an execution and safekeeping environment. It may be highly
trusted and useful, but it should remain distinguishable from the resources it
operates upon.

This distinction makes an important policy objective visible: a user should be
able to replace the container without abandoning the keys, funds, and records
that give the container its purpose. “User-controlled” does not require every
person to self-host. A trusted provider can supply execution, availability, and
support, provided the trust is disclosed and there is a credible path to
recovery, export, migration, and provider replacement.

## Policy recommendations

### 1. Specify resources before products

Legislation, standards, and procurement should identify which keys, funds, and
records are in scope before specifying a wallet, application, or platform. For
each resource, requirements should state who exercises control, who supplies
validity or recognition, and what evidence is available to other parties.

### 2. Treat portability as continuity of control

Exporting a file or switching user interfaces is not sufficient. Portability
should mean that authorized users or components can continue to locate,
decrypt, verify, present, transfer, and recover their resources through another
compatible implementation, subject to the legitimate rules of issuers and
regulated intermediaries.

### 3. Keep identity claims separate from key control

Identity systems should state precisely what a key, identifier, credential, or
authentication event proves. Possession of a key proves control of that key at
a point in time; it should not silently become proof of a person's legal or
social identity. Recognition and liability rules must remain explicit.

Policy should also distinguish signed-event continuity from intentional
control. Systems should disclose whether consequential signatures are produced
directly by a person, by an organization, or by delegated automation; how that
authority is constrained and revoked; and what evidence supports recovery or
key rotation. Trust frameworks should identify the actor expected to exercise
intent and bear accountability rather than attributing intent to the key
itself.

### 4. Treat credentials as a record profile

Credential standards should continue to provide strong issuance,
presentation, verification, privacy, and status mechanisms. Broader digital
infrastructure should also support records that do not have an issuer-holder-
verifier lifecycle. Common storage, encryption, transport, recovery, and
authorization primitives can serve several record profiles without erasing
their differences.

### 5. Make funds a first-class requirement

Where digital services are expected to support economic activity, policy
should address funds as well as payment initiation. Requirements should cover
balance integrity, issuer and settlement dependencies, proof or account state,
fees, failed-payment reconciliation, recovery, and movement between compatible
providers. Identity-wallet policy should not be assumed to cover these issues
merely because a payment credential can be stored in a wallet.

### 6. Require modularity and credible exit

Public infrastructure should favour protocol-based components and documented
interfaces over indivisible platforms. Tests should include device loss,
provider failure, infrastructure migration, key recovery, record replication,
and funds reconciliation. Procurement should evaluate whether the operator can
be replaced without the user losing practical control.

## A simple policy test

Before approving a digital wallet, identity, credential, or payment initiative,
decision-makers should ask:

1. What keys, funds, and records does the system safeguard or act upon?
2. Who controls each resource, and what does “control” permit?
3. Which issuer, institution, protocol, or legal framework gives each resource
   validity or recognition?
4. What evidence supports identity, intent, control, and transaction history?
5. Can the resources be recovered and used through another application,
   device, provider, or infrastructure operator?
6. What remains possible when a provider, relay, mint, network, or local
   facility becomes unavailable?

These questions do not prescribe a single architecture. They expose where an
architecture has combined distinct concerns or made an implementation
container the permanent point of dependency.

## Acorn as practical evidence

[Acorn](./ACORN-PRODUCT-NORTH-STAR.md) is one concrete exploration of this
vocabulary. It is a protocol-first component for safeguarding user-controlled
keys, funds, and records:

- keys provide cryptographic continuity and authority without being described
  as the user's identity;
- Cashu proofs represent funds, while Lightning provides payment
  interoperability;
- encrypted relay-backed records cover private data, configuration, history,
  and issued record types;
- applications such as Safebox Web provide replaceable service and user
  interfaces over the component.

Acorn is not proposed as a mandatory architecture, and Nostr or Cashu need not
be the only protocols used to implement the model. Its value to policy is as a
working demonstration that the resource boundary can be made concrete: keys
can remain distinct from identity, funds can exist alongside records, and an
application can use these resources without becoming their only system of
record.

The related [Acorn Record Model](./ACORN-RECORD-MODEL.md) explores transferable
and non-transferable records in more detail.

## Limits and safeguards

The proposed vocabulary does not settle every policy question:

- “funds” may have different legal and regulatory meanings across systems and
  jurisdictions;
- user control does not eliminate issuer, mint, bank, custodian, or network
  dependencies;
- technical control of a key or record does not necessarily establish legal
  ownership, authority, identity, or consent;
- portable records still require privacy, data-protection, retention, and
  disclosure rules;
- recovery mechanisms can improve continuity while creating new security and
  coercion risks;
- trusted execution providers and reverse proxies may see sensitive material
  during processing even when an application does not persist it.

These are reasons to make the boundaries visible, not reasons to return to a
single overloaded term such as “wallet” or “identity.”

## Conclusion

Digital identity, digital credentials, digital wallets, and digital payments
remain useful specialist terms. The mistake is treating them as a complete
model of the user's digital resources.

Keys, funds, and records offer a more direct starting point. They make it
possible to discuss authority without calling a key an identity, to discuss
credentials without reducing every record to a claim, to discuss funds rather
than only payment instructions, and to treat wallets as replaceable
implementations rather than permanent containers of dependency.

The next generation of digital policy does not need to discard the work already
done. It needs a vocabulary broad enough to connect that work while preserving
the distinctions on which trust, control, recovery, and accountability depend.

## References

- Timothy Bouma, [*The Niels Bohr Moment for Digital Architecture*](https://trbouma.substack.com/p/the-niels-bohr-moment-for-digital)
- W3C, [*Verifiable Credentials Data Model v2.0*](https://www.w3.org/TR/vc-data-model/all/)
- W3C, [*Verifiable Credentials Overview*](https://www.w3.org/TR/vc-overview/)
- European Union, [Regulation (EU) 2024/1183 establishing the European Digital Identity Framework](https://eur-lex.europa.eu/eli/reg/2024/1183/oj?locale=en)
