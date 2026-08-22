# Uniform Resource Model Design Note

## Status

Conceptual architecture proposed for Acorn and the wider Mainstay product
family.

This note defines a common model and vocabulary. It does not yet define a new
URI scheme, Nostr event kind, serialization format, legal framework, or stable
interoperability standard.

## Summary

The Uniform Resource Model (URM) treats a **record** as a cryptographically
identifiable resource whose useful meaning includes more than content.

A resource may have:

- one or more identifiers;
- one or more Uniform Digest Anchors for exact representations or records;
- one or more representations;
- an issuer or origin authority;
- a current controller or holder;
- policy governing permitted operations;
- state and lifecycle transitions;
- provenance and control history;
- resolution and retrieval methods; and
- verifiers that determine validity or effect in a particular context.

URM extends the concerns addressed by URL, URI, and URN models. Those models
primarily provide syntax and semantics for identifying, naming, or locating a
resource. URM asks additional questions:

```text
What is this resource?
Who issued or originated it?
Who controls it now?
Can it be transferred?
Is it fungible with another resource or unit?
Which operations are permitted?
Which representation is being retrieved?
What evidence establishes its current state?
Who decides whether that evidence has effect?
```

The central architectural statement is:

> A record is a resource with identity, authority, state, representations,
> policy, and history.

## Why this model is emerging

Acorn began with funds and private records. Those appeared to be separate
application features:

- Cashu proofs behaved like wallet funds;
- private records behaved like encrypted documents or structured data;
- transferable electronic records required control history;
- Clear introduced organization-issued units that are both fungible and
  transferable; and
- presentations and temporary record transfers introduced constrained
  capabilities over representations.

The implementations increasingly use the same underlying mechanics:

- cryptographic keys;
- signed and encrypted events;
- issuer and controller authority;
- relay-backed state;
- content-addressed blobs;
- transfer and presentation capabilities;
- append-only history;
- recovery, replication, and migration; and
- external verification and policy.

URM names that common architecture without claiming that every resource has
the same rules.

## Balances are views of fungible records

The working Cash and Clear implementations make an important consequence of
the model concrete: **a balance is a user-facing projection over fungible
records**. It is not a second, unrelated class of protocol state.

Each proof or mint note remains an individually identifiable cryptographic
record. When several valid records represent equivalent quantities within the
same explicit equivalence domain, an application may aggregate those
quantities and present the result as a balance:

```text
fungible records in one equivalence domain -> balance
individually meaningful non-fungible records -> records
```

The projection must preserve its boundary. Cash from different incompatible
domains, and Clear units from different mints or CMUs, do not become fungible
merely because an interface can add their numbers. A displayed balance is
therefore derived state whose integrity depends on the underlying records,
issuer or mint validation, and the applicable equivalence rules.

This gives applications a simple top-level vocabulary without weakening the
uniform model:

- **Balances** present compatible fungible records as quantities.
- **Records** present non-fungible resources individually because their exact
  content, provenance, control, or history matters.

The distinction is a presentation and operating model, not a claim that one
side is stored as records and the other is not.

## Relationship to URI, URL, and URN

URM does not replace the established identifier concepts.

| Concept | Primary concern |
| --- | --- |
| URI | identifying a resource |
| URL | identifying a resource through a location or access mechanism |
| URN | identifying a resource through a persistent name |
| URM | modelling the resource's identity, authority, state, control, representations, policy, and history |

A URM resource may use an HTTPS URL, Nostr event ID, `npub`, `note` identifier,
content hash, domain-specific URN, or an `acorn:` capability URI. The model
does not require every identifier to resolve in the same way.

URM is therefore a semantic and lifecycle model above identifier syntax:

```text
identifier -> names or locates
resolver   -> finds representations or state
model      -> explains authority, control, policy, and lifecycle
```

## Design goals

URM should:

1. provide one vocabulary for funds, records, credentials, transferable
   documents, credits, and other controlled resources;
2. distinguish a resource from its representations and storage locations;
3. make issuer, controller, holder, and verifier roles explicit;
4. model transferability and fungibility as independent properties;
5. distinguish sharing, copying, presentation, and transfer of control;
6. preserve domain-specific policy rather than flattening every resource into
   one asset abstraction;
7. support encrypted and selectively disclosed resources;
8. support portable state across applications and infrastructure;
9. make lifecycle transitions auditable and recoverable; and
10. provide a uniform way to bind attestations and control evidence to exact
    artifacts without owning their native formats or signature schemes; and
11. allow incremental profiles over existing protocols such as Nostr, Cashu,
    HTTPS, and Blossom.

## Non-goals

URM does not:

- declare that every record is property or a financial asset;
- make all records transferable;
- make all units interchangeable;
- define legal ownership or legal title by itself;
- make a cryptographic signature proof of truth, identity, or intent;
- replace issuer, mint, registry, court, or verifier authority;
- require all representations to be public;
- guarantee physical deletion from relays or storage providers;
- define one universal resolver or global registry; or
- turn Acorn into the schema owner for every application domain.

## Core terms

### Resource

A **resource** is the conceptual object being identified, controlled, used, or
verified.

Examples include:

- a private health record;
- a membership credential;
- an electronic bill of lading;
- a ticket;
- a Cashu-denominated amount;
- an organization-issued Clear balance;
- a quota or allowance; and
- a content-addressed original document.

### Record

A **record** is the protocol expression of a resource or a state transition
affecting that resource.

A record may contain the resource directly, refer to a separate
representation, describe current control, carry a transfer intent, or preserve
history.

The words are related but not identical:

```text
resource       -> the conceptual controlled object
record         -> protocol evidence or state about that object
representation -> bytes, data, or media expressing it
```

### Representation

A **representation** is one encoding or rendition of a resource.

The same resource may have:

- structured JSON metadata;
- an encrypted Nostr event;
- a PDF original;
- a thumbnail;
- a translated rendition;
- a content-addressed blob;
- a Cashu token transport encoding; or
- a human-readable wallet view.

Copying a representation does not necessarily create a new resource or
transfer control of the existing resource.

### Uniform Digest Anchor

A **Uniform Digest Anchor (UDA)** is a cryptographic digest of the exact bytes
within a declared scope. It gives every artifact format the same kind of stable
evidence reference:

```text
uniform_digest_anchor = hash(exact_target_bytes)
```

The target scope and hash algorithm must be explicit. A UDA may identify an
Original Record, one representation of a resource, or a canonical descriptor
defined by a URM profile. For an immutable artifact, the UDA may also serve as
its canonical artifact identifier. A mutable resource or a resource with
several renditions may have several anchors without becoming several conceptual
resources.

Uniform means the binding mechanism is consistent across formats. It does not
mean that different encodings, renditions, or versions produce the same digest.
A PDF, PKPASS, mdoc, SD-JWT VC, image, or opaque binary object can each be
anchored without URM interpreting its native signature or verification scheme.

A UDA allows signed evidence to state precisely which bytes it concerns:

```text
resource
  -> exact representation
  -> Uniform Digest Anchor
  -> native verification, attestations, provenance, and control events
```

The anchor establishes byte identity only. It does not establish truth,
authorship, issuer authority, current validity, operative control, ownership,
or legal effect. Those conclusions belong to native verification, attestation,
control, recognition, and policy layers.

For encrypted Original Records, the plaintext artifact digest and encrypted
storage digest have different scopes. Acorn's `origsha256` is a UDA for the
original plaintext bytes. A Blossom digest identifies the stored ciphertext
and must not silently replace the artifact anchor.

### Identifier

An **identifier** names a resource, record, representation, state event, or
capability. Its scope must be explicit.

Examples:

- Nostr event ID identifies one signed event;
- SHA-256 digest identifies exact bytes;
- `npub` identifies a Nostr public key;
- `cmu-<keyset-id>` identifies one Clear Mint Unit;
- mint URL plus CMU identifies one Clear balance domain; and
- `acorn:record-transfer:` identifies a temporary bearer capability.

One identifier should not silently be treated as another. A blob hash is not a
resource identifier when several representations belong to one resource. A
friendly alias is not a canonical CMU.

### Issuer and originator

The **issuer** creates or authorizes a resource under a policy. The
**originator** creates a record or representation.

These roles may be filled by the same key but have different semantics. An
issuer may attest to a credential; a holder may later originate a
presentation record without becoming the credential issuer.

### Controller and holder

The **controller** has protocol-recognized authority to perform one or more
operations on a resource. The **holder** possesses or can access a
representation or bearer capability.

Possession and control coincide for some bearer resources. They differ for
many records:

- a person may hold a copy without authority to transfer the original;
- a service may hold encrypted bytes without decryption authority;
- a wallet may control a key while a mint remains authoritative over proof
  spend state; and
- a delegated application may perform a bounded operation without receiving
  unrestricted control.

### Verifier

A **verifier** evaluates evidence under a policy and decides what effect to
give it.

Cryptographic verification can establish exact bytes, signatures, and event
relationships. A verifier still decides whether the issuer is recognized,
whether the policy applies, whether the evidence is current, and what
real-world consequence follows.

### Attester and notarization

An **attester** signs a statement about a resource, record, representation, or
Uniform Digest Anchor. Anyone may be able to create an attestation; whether it
has effect depends on the attester's recognized identity, authority, evidence,
policy, and context.

**Notarization** is an attestation profile with defined statement types,
signer requirements, time semantics, and verifier policy. It may express
creation, inspection, custody, provenance, control, transfer, acceptance,
revocation, or supersession. Calling an event a notarization does not itself
make the signer a legally recognized notary or make the statement true.

## Two independent classification axes

URM classifies resources along at least two independent axes:

1. **Transferability:** can protocol-recognized operative control move between
   controllers?
2. **Fungibility:** can one resource or represented unit satisfy the same
   obligation as another within a defined equivalence domain?

This produces four principal classes:

| | Non-transferable | Transferable |
| --- | --- | --- |
| **Non-fungible** | credential, personal record, signed receipt, issued certificate | title, ticket, negotiable document, controlled original |
| **Fungible** | account-bound quota, personal allowance, non-transferable service entitlement | cash proofs, Clear Mint Units, bearer credits |

These are resource profiles, not universal declarations. A ticket may be
transferable before an event and non-transferable after check-in. A regulatory
rule may restrict transfer of an otherwise bearer-like resource.

### Transferable units

A **transferable unit** is the fungible, transferable resource class expressed
as a quantity within a defined equivalence domain. Control of the quantity can
move between holders, and equivalent quantities can satisfy the same
issuer-defined obligation.

The term describes a resource property, not a claim that the resource is money.
Cash, a Clear Mint Unit, a gym guest pass, and a service credit may all be
transferable units while having different issuers, acceptance rules,
redemption effects, and legal character. A CMU is Clear's concrete,
keyset-bound implementation of a transferable unit.

Clear provides the issuance, circulation and redemption machinery. That common
machinery may support instruments ranging from drink vouchers and guest passes
to ownership interests or regulated securities. The applicable URM profile
must preserve the instrument's actual authority, policy, transfer restrictions,
redemption effects, and legal or regulatory character rather than infer them
from the shared token machinery.

## Transferability

Transfer is not merely movement or copying of data.

> Transfer is a policy-recognized transition of operative control from one
> controller to another.

A transfer profile must specify:

- the resource being transferred;
- the current controller;
- the proposed next controller;
- required authorization;
- acceptance rules;
- issuer, registry, or mint validation;
- exclusivity or double-control prevention;
- effective time and finality;
- failure and recovery behavior; and
- evidence by which a verifier reconstructs current control.

### Sharing is not transfer

Sharing grants access to a representation or capability. It does not
necessarily change control.

### Presentation is not transfer

Presentation gives another party evidence or temporary access for a purpose.
It does not necessarily create ownership, control, or a durable copy.

### Copying is not issuance

Copying bytes creates another representation. It does not create another valid
resource unless issuer policy says that a new resource was issued.

### Delivery is not acceptance

Delivery proves that transfer material reached a recipient-controlled inbox.
Acceptance may require mint refresh, registry update, countersignature, or
durable state transition.

## Fungibility

Fungibility is always scoped.

Two units are fungible only within an explicit **equivalence domain**, which
may include:

- issuer or mint;
- unit or denomination;
- keyset;
- policy version;
- expiry or validity period;
- jurisdiction or program;
- encumbrance or restriction; and
- settlement or redemption rules.

For Clear, the minimum balance identity is:

```text
(normalized mint URL, canonical CMU)
```

Two balances are not fungible merely because both display `CMU`, `credits`, or
the same friendly name.

### Unique records can represent fungible units

A Cashu proof has a unique secret and signature. The proof record is
non-identical to every other proof. The amount it represents may nevertheless
be fungible with amounts represented by other valid proofs in the same mint,
unit, keyset, and policy domain.

URM therefore distinguishes:

```text
record identity     -> this exact proof or note record
resource class      -> the issuer-defined unit or obligation
quantity            -> amount represented by the record
equivalence domain  -> rules under which quantities may be combined
```

### Example: transferable gym guest passes

A gym can issue a fixed allocation of guest-pass units to a member. Each unit
represents the same entitlement: one guest admission under the gym's program
rules. The member may transfer any of those units to another person without
asking the gym to mediate the transfer.

```text
gym issues guest-pass units
  -> member holds the units
  -> member transfers a unit to a guest
  -> guest presents the unit at the gym
  -> gym verifies, redeems, and retires the unit
```

The units are transferable and fungible within the equivalence domain defined
by the gym, program, validity period, and redemption policy. Their bearer
proofs remain unique records. Retirement permanently removes a redeemed unit
from circulation and prevents the same entitlement from being exercised
again.

This example also separates governance from custody. The gym controls issuance
and defines what a unit can be redeemed for, while holders control valid units
and may transfer them freely until presentation or expiry. The units represent
an in-kind service entitlement, not cash and not a promise of monetary
redemption.

## Resource descriptor

A URM profile should define a descriptor containing or resolving the following
conceptual fields. Profiles may encode them differently and may keep sensitive
fields encrypted.

```text
resource_id       canonical identifier within a declared scope
resource_type     schema or profile identifier
version           model or schema version
digest_anchors    scoped algorithm-and-digest references to exact bytes
issuer            issuing or originating authority
controller        current operative controller, when applicable
holder            intended holder or audience, when applicable
quantity          amount for quantified resources
unit              exact unit and equivalence domain
representation    inline data or references to representations
policy            rules for use, transfer, expiry, redemption, and revocation
state             current lifecycle state
provenance        origin and derivation evidence
attestations      signed statements bound to the resource or an exact anchor
history           state-transition or control-history references
resolver          methods for locating current state or representations
verifier          policy or method for evaluating evidence
relationships     links to parent, child, superseding, or supporting resources
created_at        asserted creation time
expires_at        expiry or review boundary
```

Not every profile needs every field. Omission must not imply an unsafe default.
For example, absent transfer policy should not mean freely transferable.

## Resource operations

URM uses a shared operation vocabulary while allowing each profile to define
which operations are valid.

| Operation | Meaning |
| --- | --- |
| issue | create or authorize a new resource |
| resolve | locate current state or available representations |
| retrieve | obtain one representation |
| attest | make a signed statement about a resource, record, representation, or Uniform Digest Anchor |
| present | disclose evidence or a representation for a purpose |
| share | grant bounded access without changing operative control |
| transfer | change operative control |
| accept | complete recipient-side validation and control transition |
| split | divide represented quantity or rights under policy |
| merge | combine compatible quantities or rights under policy |
| spend | exercise a bearer or payment capability |
| pay | use a value transfer to settle or discharge an economic obligation |
| redeem | return a resource to its issuer for an external consequence |
| retire | permanently remove an issued resource or quantity from circulation |
| revoke | issuer or authority invalidates future recognition |
| supersede | replace current state or representation with a later one |
| recover | restore control or access through an authorized recovery process |
| replicate | copy encrypted state or representations without changing control |
| delete | request removal of a record or representation |

An operation name does not guarantee a particular legal effect. A profile must
define its authority, preconditions, transition evidence, and finality.

### Payment is an economic role of a transfer

**Transfer** is the general protocol operation. **Payment** is the economic
interpretation of a transfer when it supplies the value or settlement leg of a
larger transaction.

Not every balance transfer is a payment. A transfer may instead be an
allocation, gift, benefit, treasury disbursement, refund, issuance, or
redemption. Conversely, a purchase or exchange is not exhausted by its payment
leg: it may also involve delivery of a service, transfer of control over a
non-fungible record, and evidence of the parties' respective obligations.

```text
economic transaction
  -> resource, service, or control leg
  -> value or settlement leg (payment)
```

This vocabulary lets Cash, Clear, and OpenETR participate in one transaction
without collapsing their distinct semantics. Fungible records can satisfy the
value leg, while a non-fungible record and its control history can describe
what was issued, delivered, attested, or transferred in return.

## Lifecycle and state

URM separates immutable evidence from derived current state.

A generic lifecycle may include:

```text
proposed
issued
delivered
pending
accepted
active
transferred
presented
redeemed
retired
revoked
superseded
expired
rejected
recovery_required
```

Profiles select only meaningful states. A private health record may be issued,
active, superseded, or revoked. A bearer note may be issued, transferred,
redeemed, and retired. A transfer may be delivered but remain pending until
acceptance.

Current state should be a deterministic conclusion from authoritative records
and profile rules, not merely the newest event returned by one relay.

## Authority model

URM separates authorities that conventional applications often collapse:

| Role | Authority |
| --- | --- |
| issuer | creates or recognizes the resource |
| controller | performs allowed control operations |
| holder | possesses or accesses a representation |
| operator | runs software or infrastructure |
| resolver | returns identifiers, state, or representations |
| storage provider | stores events or blobs |
| validator | establishes protocol validity or spend state |
| verifier | decides whether evidence has effect in context |
| recovery authority | participates in restoring control or access |

One actor may fill several roles, but the model should not erase their
different responsibilities.

Examples:

- A Clear organization governs a credit program.
- A Clear mint validates issuance, proofs, and retirement.
- A treasurer authorizes routine CMU issuance.
- Acorn controls recipient wallet keys and encrypted state.
- A Nostr relay stores signed events.
- Grove stores opaque content-addressed representations.
- Safebox Web supplies human workflows.
- A merchant or program verifier decides whether to recognize a CMU.

## Representation and storage model

URM resources may be represented across several storage systems:

```text
signed event       -> authority, metadata, state transition, references
encrypted content  -> private structured record or wallet state
blob               -> large exact representation
Uniform Digest Anchor -> scoped integrity and exact-byte identity
resolver hint      -> where a representation may be retrieved
```

Storage location is not resource authority. Replicating an encrypted event or
blob improves availability without transferring the resource.

Deletion is also representation-specific. Deleting one relay event or blob
does not prove every copy disappeared and does not necessarily revoke the
resource.

## Nostr mapping

Nostr is a useful transport and event substrate for URM profiles:

- event ID identifies exact signed event bytes;
- author key identifies signing authority;
- kind identifies an application record class;
- tags express public routing or relationships;
- encrypted content protects private state;
- replaceable events express current state under defined rules;
- regular events preserve append-only history;
- deletion events or tombstones express removal intent; and
- relays provide replaceable availability.

URM must not assume that a relay's returned event set is complete,
authoritative, or correctly ordered. Profiles need canonicalization,
readback, replication, conflict, and recovery rules.

## Existing Acorn mappings

### Non-transferable, non-fungible

Acorn private records, credentials, signed documents, and protected originals
fit this class when they can be stored, recovered, and presented but do not
carry protocol-recognized transferable control.

The current temporary `record-presentation` capability discloses a
representation without making it importable through conforming Acorn APIs.

### Transferable, non-fungible

Electronic transferable records, negotiable documents, titles, tickets, and
controlled originals fit this class.

Acorn's current `record-transfer` capability imports a copy into another
wallet. It does not yet establish exclusive transfer of an original or a
canonical control chain. OpenETR's control-history work is the closer model
for this resource class.

### Transferable, fungible

Cashu ecash and Clear Mint Units fit this class at the represented-unit level.
Both are transferable units, but only the sat-denominated ecash path is
presented as the wallet's general-purpose Cash Balance. Clear units remain
issuer-specific Clear Balances.

Cash transfer:

```text
kind 7378 transfer intent
  -> mint refresh
  -> kind 7375 spendable proof state
  -> kind 7377 cash history
```

Clear transfer:

```text
kind 7379 transfer intent
  -> pending clear_receipts journal
  -> future mint refresh
  -> kind 7380 Clear proof state
  -> kind 7381 Clear transfer history
```

### Non-transferable, fungible

Account-bound quotas, personal allowances, usage credits, and
non-transferable service entitlements fit this class.

Acorn does not yet define a dedicated profile for these resources. A future
profile must distinguish consumption, delegation, expiry, and issuer
adjustment from transfer.

## Interoperability profiles

URM becomes implementable through profiles, not one universal payload.

A profile should specify:

1. resource type and version;
2. canonical identifier scope;
3. issuer and controller authority;
4. transferability and fungibility;
5. equivalence domain and quantity rules;
6. allowed operations;
7. state transition model;
8. representation formats;
9. event kinds or transport envelopes;
10. encryption and disclosure rules;
11. resolver and storage behavior;
12. validation and verification rules;
13. conflict, replay, and double-control protection;
14. recovery and replication behavior;
15. privacy and metadata exposure; and
16. compatibility and migration rules.

Profiles may use existing standards directly. URM should avoid inventing a new
encoding when a suitable one already exists.

## Product-family mapping

The Mainstay product family provides a practical decomposition:

| Product | URM responsibility |
| --- | --- |
| Acorn | keys, controller authority, encrypted resource state, transfer and recovery mechanics |
| Safebox Web | human workflows, presentation, confirmation, and explanation |
| Clear | issuance, validation, transfer, redemption, and retirement of fungible transferable units represented as CMUs |
| OpenETR | provenance and control history for non-fungible transferable records |
| Grove | opaque content-addressed representations |
| Spurline | event storage, synchronization, and availability |
| Mainstay | unified application across resource profiles |
| Lockbox | locally controlled execution and storage environment |

These are good boundaries, not barriers. A common resource model lets the
products interoperate without assigning every responsibility to one service.

## Security and trust considerations

URM implementations must treat the following distinctions as security
boundaries:

- identifier versus friendly label;
- representation possession versus operative control;
- event delivery versus resource acceptance;
- signature validity versus claim truth;
- current controller versus issuer;
- copying versus issuance;
- sharing versus transfer;
- deletion request versus physical erasure;
- fungibility within a domain versus superficial similarity;
- relay availability versus authoritative state;
- operator access versus user authority; and
- cryptographic evidence versus legal effect.

A matching Uniform Digest Anchor proves that the target bytes match. It does
not prove that an attestation is true, that its signer has relevant authority,
or that a control event has legal effect. Profiles must also provide algorithm
agility and must reject ambiguous anchor scopes.

Bearer capabilities and proofs are secrets. They must not appear in logs,
public tags, URLs not designed as bearer descriptors, analytics, or
transaction-history records.

## Privacy model

URM must support resources whose identifiers, type, issuer, controller,
quantity, or relationships are private.

Profiles should minimize public tags and expose only what transport or
discovery requires. Encryption protects content, but traffic patterns, relay
queries, blob sizes, timing, mint access, and presentation contexts may still
reveal metadata.

Selective disclosure should be profile-specific. It must not be represented as
perfect privacy or proof that a recipient did not retain disclosed content.

A public UDA is also a durable correlation handle. Publishing an anchor for a
sensitive or predictable artifact can reveal that two parties hold the same
bytes and may permit dictionary testing. Profiles should support private
attestations, access-controlled evidence, or salted commitments where a public
plaintext digest would disclose too much.

## Recovery and continuity

Resource control is not useful if it cannot survive application or
infrastructure replacement.

A URM profile should define:

- which keys or capabilities must be recovered;
- how current state is reconstructed;
- how incomplete event sets are detected;
- how relays or storage providers are changed;
- how concurrent writers are handled;
- how interrupted transfers are resumed;
- how issuer or mint state is reconciled; and
- which operations are irreversible.

Acorn's role is to provide this portable control and recovery kernel without
claiming authority that belongs to the resource issuer or verifier.

## Proposed implementation sequence

1. Adopt URM terminology in the Acorn Record Model and product architecture.
2. Define a small typed resource descriptor, including scoped Uniform Digest
   Anchors, independent of any one event kind.
3. Map existing private record, record presentation, ecash, and Clear payloads
   into URM profiles without changing their wire formats.
4. Define explicit `share`, `present`, `copy`, and `transfer` capability
   semantics.
5. Complete crash-recoverable Clear acceptance as the first fungible transfer
   profile using kind `7380` and `7381`.
6. Define a non-fungible control-chain profile with OpenETR rather than
   treating record import as exclusive transfer.
7. Define resolver behavior for event IDs, content hashes, NIP-05 addresses,
   mint URLs, and `acorn:` descriptors.
8. Add conformance fixtures covering all four resource classes.
9. Review naming, kind assignments, privacy, and compatibility before
   proposing any stable external standard.

## Open questions

- Is **Uniform Resource Model** sufficiently distinct from existing uses of
  the term in standards and software architecture?
- Should the common object be called a resource, record, controlled resource,
  or resource record?
- Does a stable resource need one canonical identifier, or can profiles define
  an identifier set with scoped equivalence?
- When is a Uniform Digest Anchor also a canonical resource identifier, and
  when does it identify only one representation?
- Which commitment schemes should be supported when publishing a plaintext
  digest would create an unacceptable correlation handle?
- How should controller rotation differ from transfer?
- How should shared or multi-party control be represented?
- Which state belongs in replaceable records and which belongs in append-only
  history?
- How should legal control and protocol control be related without conflating
  them?
- Can fungibility policy change over time, and how are existing units treated?
- Which resolver hints may be public without leaking private relationships?
- Should capability URIs be part of the resource identifier set or remain
  separate temporary access instruments?

## Decision boundary

URM is accepted here as an architectural lens and working vocabulary.

It should guide new Acorn designs, but no existing wire format should be
renamed or migrated merely to appear uniform. A concrete protocol change
requires its own versioned specification, compatibility plan, threat model,
tests, and operational recovery design.
