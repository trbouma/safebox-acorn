# Acorn Record Model

Acorn implements a user-controlled record model for funds and private records,
anchored by user-controlled keys. The core idea is that user-controlled
wallets can hold, receive, issue, present, and replicate encrypted records over
Nostr relay infrastructure.

A public/private keypair provides continuity across compatible environments
and authority over the funds and records controlled through it. The keypair is
not identity. Human or organizational identity is interpreted outside Acorn
from claims and context that may include a NIP-05 name, kind `0` profile,
Lightning address, credential, relationship, legal record, or prior
interaction. Possession of the keypair alone proves control of the key, not who
the controller is.

Signed events make that control observable as a cryptographically verifiable
history. They show that the key authorized particular event bytes and allow
state and provenance to continue across relays. They do not prove that the
content is true, that the declared timestamp is objective, or that a conscious
actor personally intended the action. Identity is a counterparty's contextual
interpretation of the key and its history. Trust is the further judgment that
an intentional actor continues to govern that key—including any delegated
software—and can be relied upon or held accountable over time.

This matters for controllable records. Valid key authorization is necessary for
many operations, but the meaning of an issued, presented, transferred, or
revoked record also depends on issuer rules, holder intent, delegation,
counterparty recognition, and applicable legal context.

This model initially used two major record classes:

- transferable records, where control can move from one wallet to another; and
- non-transferable private issued records, where an issuer creates a private
  record for a holder, but the record is not itself a spendable transferable
  asset.

The [Uniform Resource Model](UNIFORM-RESOURCE-MODEL-DESIGN-NOTE.md) extends
this initial transferability split with fungibility as a second independent
axis. It also distinguishes the conceptual resource from protocol records,
representations, identifiers, control state, issuer policy, and verification.

Ecash is the most concrete transferable-record example. Private issued records
are the complementary Safebox record primitive.

## Controllable records

The broader concept is a controllable record: a protocol object whose useful
state is defined not only by its content, but by who can control, update,
present, transfer, spend, revoke, or recover it.

This is why Acorn's primary description is:

```text
Acorn is a protocol-first component for safeguarding user-controlled keys,
funds and records.
```

In this model, "user-controlled" is not just a privacy preference. It is a
record property. Keys supply the cryptographic continuity and authority through
which the user controls funds and records. A record is more useful and resilient
when the user can preserve that control across applications, relays, mints,
devices, and deployment operators.

Control can mean different things for different record classes:

| Record class | What control means |
| --- | --- |
| Transferable records | The current holder can transfer or spend the record, and the protocol can determine when control has moved. |
| Non-transferable private issued records | The holder can store, recover, decrypt, and present the record, but presentation does not by itself transfer ownership or spendable control. |
| Configuration records | The user can recover and change the infrastructure pointers that make the wallet usable, such as home relay, public relays, and home mint. |

This framing helps keep Acorn small and reusable. Acorn does not need to own
every possible domain schema. It needs to provide the mechanics for
user-controlled records: cryptographic keys, encrypted relay-backed
storage, transfer/receive flows, proof refresh, transaction history, recovery,
and replication.

The result is a common kernel for both funds and records:

```text
content is private;
control is explicit;
state is portable;
infrastructure is replaceable.
```

Operationally, an Acorn instance is an encrypted tenant on relays and a client
to mints. Relays make encrypted state available. Mints validate and refresh
spendable value records.

## Transferable records

Transferable records represent controlled state that can move between holders.
Ecash is the canonical Acorn example.

In the ecash case:

- the mint is the issuer;
- Cashu proofs or tokens are the issued record material;
- wallet control is the ability to spend or redeem the proofs;
- transfer is delivery of a token/proof payload to another wallet;
- acceptance requires validation and refresh through the mint;
- the recipient's durable spendable state is written back into their wallet.

The current Acorn event model separates transport, transfer intent, and durable
wallet state:

| Kind | Role |
| --- | --- |
| `1059` | Relay-visible NIP-59 gift-wrap envelope for private delivery. |
| `7378` | Inner Acorn ecash-transfer application record. |
| `7375` | Durable spendable wallet proof state after acceptance. |
| `7377` | Transaction history / accounting trail. |

This is deliberately not modelled as a gift-wrapped `7375` transfer. Kind
`7375` means current wallet proof state. Kind `7378` means incoming transfer
intent. After the transfer is accepted, the refreshed proofs are merged into
`7375`.

The lifecycle is:

```text
mint issues proofs
sender controls proofs
sender creates transfer token
sender publishes kind 1059 gift wrap containing inner kind 7378
recipient unwraps and accepts token
mint validates/refreshes proofs
recipient persists spendable proofs in kind 7375
recipient records transaction history in kind 7377
```

Transferable records need issuer validation or state transition rules. In the
ecash case, the mint provides anti-double-spend validation and proof refresh.

## Transferable records and control

Transferability is not just movement of data. It is movement of control.

This is the point shared with the control-layer work being developed in
[OpenETR](https://github.com/trbouma/openetr). OpenETR applies the control
model to electronic transferable records and digital trade documentation. Acorn
applies the same general pattern to funds and private wallet records.

In both cases, the central question is:

```text
Who has operative control of this record now, and what evidence makes that
control observable?
```

For Acorn ecash, control is concrete and mechanical:

- the holder controls spendable Cashu proofs;
- the mint validates whether those proofs remain spendable;
- transfer delivers token/proof material privately to a recipient;
- acceptance refreshes control into the recipient's wallet state;
- the durable proof state is then stored as kind `7375`.

For OpenETR-style transferable records, the control layer generalizes this
pattern beyond funds. The record may represent a trade document or other
electronic transferable record rather than sats, but the model still requires a
clear control chain:

- an issuer or originator creates the record;
- a controller has the authority to act with respect to the record;
- transfer changes the controller according to protocol and legal rules;
- verifiers can inspect evidence of current control without depending on a
  single proprietary platform.

Acorn should not absorb the full OpenETR control layer. Instead, Acorn should
stay focused on the funds-and-records kernel while remaining compatible with
the broader control-layer model:

- Acorn ecash demonstrates transferable control over value records.
- Acorn private issued records demonstrate encrypted holder-controlled records.
- OpenETR develops the domain-specific control model for electronic
  transferable records and trade documentation.

The shared architectural lesson is that records become more useful when control
is explicit, portable, recoverable, and verifiable.

## Non-transferable private issued records

Non-transferable private issued records are records created or attested by an
issuer for a holder. They can be stored, retrieved, presented, and verified, but
they are not transferred like ecash proofs.

Examples include:

- private credentials;
- healthcare records;
- membership or permission records;
- grants, offers, and requests;
- attestations and signed documents;
- private operational records.

The holder may receive a private record from an issuer and keep it in their
wallet. The holder may later present it or use it in a workflow, but presenting
the record does not necessarily transfer control of the record to a new owner.

This class emphasizes:

- issuer authenticity;
- holder privacy;
- encrypted storage;
- integrity of the issued payload;
- optional blob attachment handling;
- replay, presentation, and verification semantics;
- recovery and relay replication.

## Why both classes belong in Acorn

The Acorn kernel is not only a wallet and not only a document store. It supports
encrypted user-controlled records with different control semantics.

Transferable records answer:

```text
Who controls this value or asset now?
```

Non-transferable private issued records answer:

```text
Who issued this private record, who can hold it, and how can it be privately
retrieved or presented?
```

Both record classes need the same foundation:

- cryptographic keys and authority;
- encrypted relay-backed storage;
- user-controlled keys;
- recovery material;
- relay migration and replication;
- clear CLI and application interfaces.

That shared foundation is why they belong in the Acorn component instead of
being treated as unrelated application features.

## Relationship to Safebox

Safebox can be built on top of Acorn as a product surface for funds and private
records.

Acorn provides the kernel:

- wallet proof state;
- private record storage;
- record issue and receive primitives;
- ecash transfer and receive primitives;
- transaction history;
- recovery and relay mobility.

Safebox can then provide product-specific UX, policy, workflow, and support
around those primitives.

## Design boundary

Acorn should stay protocol-first. It should provide record mechanics, not own
every domain schema.

Domain-specific schemas for healthcare, trade documentation, identity,
membership, or other ecosystems should build on top of Acorn's record model
without forcing Acorn to become a domain-specific application.

This keeps Acorn reusable as a user-controlled protocol component while allowing
Safebox and other applications to specialize.
