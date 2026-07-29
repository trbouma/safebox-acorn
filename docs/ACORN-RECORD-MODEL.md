# Acorn Record Model

Acorn implements a sovereign record model for funds and private records. The
core idea is that user-controlled wallets can hold, receive, issue, present, and
replicate encrypted records over Nostr relay infrastructure.

This model has two major record classes:

- transferable records, where control can move from one wallet to another; and
- non-transferable private issued records, where an issuer creates a private
  record for a holder, but the record is not itself a spendable transferable
  asset.

Ecash is the most concrete transferable-record example. Private issued records
are the complementary Safebox record primitive.

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
sovereign encrypted records with different control semantics.

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

- cryptographic identity;
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

This keeps Acorn reusable as a sovereign protocol component while allowing
Safebox and other applications to specialize.
