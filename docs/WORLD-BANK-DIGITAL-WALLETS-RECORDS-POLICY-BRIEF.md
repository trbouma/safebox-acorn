# Policy Brief: Digital Wallet Trust Frameworks and Portable Records

## Purpose

This brief compares the World Bank's 2026 policy note, *Digital Wallets: Trust Frameworks - Governing the Ecosystem*, with the approach being developed across Acorn, Safebox, and OpenETR in relation to records. The central finding is that the World Bank report provides a strong governance frame for digital wallet ecosystems, while Acorn, Safebox, and OpenETR offer a complementary implementation path for records that must be portable, independently verifiable, and able to retain authority outside a single platform or registry.

The policy question is not whether these approaches conflict. They mostly do not. The better question is how they can be layered: the World Bank model explains how trust frameworks should govern wallet ecosystems; Safebox and Acorn show how a wallet can securely hold, offer, request, and present private records; OpenETR extends the record model toward transferable electronic records where control itself can move over time.

## The World Bank Position

The World Bank report argues that digital wallets are becoming a core part of digital public infrastructure because they allow people to store and present digital identity credentials, personal data, electronic signatures, and payment instruments. Its main warning is that technology alone cannot create trust. A wallet ecosystem becomes reliable only when it is backed by rules, standards, institutional roles, assurance mechanisms, and legal accountability.

The report defines a trust framework as the governance structure that answers a practical relying-party question: why should a verifier trust a credential, issuer, holder, wallet, or technical process it has not seen before? In the World Bank framing, a trust framework determines who may issue credentials, how identity proofing must occur, how wallets protect keys and sensitive data, how compliance is audited, and who bears liability when something goes wrong.

The report proposes five mutually reinforcing layers:

1. Strategy: shared vision, scope, participants, risk posture, governance model, and legal environment.
2. Technology: standards, credential formats, protocols, wallet security, selective disclosure, and device/cloud architecture.
3. Scheme rules: participant onboarding, role definitions, assurance requirements, operating procedures, and wallet/credential lifecycle rules.
4. Compliance: assessment, supervision, certification, audit, and enforcement.
5. Agreements: binding instruments that clarify obligations, rights, liabilities, recognition, and dispute processes.

For interoperability, the report distinguishes three levels:

1. Credential portability: credentials can be read, parsed, issued, transported, and presented across wallets and schemes.
2. Signature verifiability: verifiers can cryptographically confirm authenticity, integrity, provenance, and wallet protection.
3. Legal recognition: credentials and signatures are treated as legally effective across frameworks or jurisdictions.

The World Bank also notes that trust frameworks can be built iteratively. A pilot may begin with a limited rulebook and basic conformance checks, while more formal compliance, accreditation, and legal-recognition arrangements are added as the ecosystem scales.

## The Acorn, Safebox, and OpenETR Position

Acorn, Safebox, and OpenETR approach the same problem from the record outward.

Acorn is the reusable Nostr/Cashu wallet and records component extracted from Safebox. Its purpose is to make the wallet and records runtime portable outside the Safebox web application. In policy terms, Acorn is the lower-level wallet component: it stores wallet data and records, interacts with relays, and provides the runtime capabilities that other applications can build on.

Safebox is the application and protocol surface around that wallet runtime. It combines Cashu ecash, Nostr-native secure messaging, record offer/present/accept flows, NFC-assisted workflows, optional post-quantum payload protection, and blob storage. For records, Safebox treats credentials as a subset of records rather than the other way around. A credential is a record with particular semantics; a record may also be a health note, grant, attestation, PDF, image, receipt, contract, membership proof, commercial artifact, or transferable instrument.

OpenETR extends the same record-first logic into electronic transferable records. Its public framing is "Durable Control. Portable Records." It defines an open scheme for records whose control can be exercised, proven, transferred, endorsed, and independently validated without dependence on a single institution, platform, or registry. Its core primitives are objects, controllers, and events: the object is the record surface, the controller is the key or actor able to exercise control, and events are signed actions such as transfer, endorsement, attestation, and enforcement. This aligns naturally with MLETR-style electronic transferable records such as bills of lading, warehouse receipts, promissory notes, and other trade documents where possession-like control is central.

## Key Comparison

The World Bank report is ecosystem-first. It begins with governments, regulators, credential issuers, wallet providers, verifiers, supervisory authorities, data protection bodies, accreditation bodies, and conformity assessment bodies. It asks: what institutional framework makes wallet-based credentials trustworthy at scale?

Acorn, Safebox, and OpenETR are record-first. They begin with the record as an artifact that must survive platform boundaries. They ask: what minimal cryptographic, protocol, and presentation machinery allows a record to be held, transferred, presented, verified, and later recognized by whatever trust framework applies?

The difference is productive:

| Policy dimension | World Bank trust-framework model | Acorn, Safebox, and OpenETR approach |
|---|---|---|
| Starting point | Wallet ecosystem governance | Portable records and control over records |
| Primary object | Credential in a wallet | Record, credential, artifact, grant, blob, or transferable instrument |
| Trust source | Scheme rules, assurance, audit, supervision, legal agreements | Cryptographic validity, holder continuity, attestation, recognition, and local acceptance policy |
| Interoperability | Data portability, signature verifiability, legal recognition | Nostr event portability, artifact digests, secure transmittal, independent verification, local recognition |
| Governance posture | Formal scheme governance | Protocol neutrality plus higher-layer governance |
| Legal posture | Trust frameworks create enforceable obligations and recognition | Protocol provides evidence; legal effect remains with policy, contract, law, or relying-party recognition |
| Inclusion posture | Wallets may be national, sectoral, federated, cloud-based, or device-based | QR/NFC bootstrap, relays, encrypted records, and wallet/agent parity support low-infrastructure and edge workflows |
| Records model | Credentials and personal data held in wallets | Records are the primitive; credentials are one record type |

## Where They Align

First, both approaches reject the idea that cryptography alone is enough. The World Bank says that valid keys and signatures can still produce fraudulent credentials if identity proofing, issuer governance, or liability is weak. Safebox's Acceptance Model makes a similar distinction: validation asks whether a claim fits the system, while verification and acceptance ask whether enough has been established for reliance in context.

Second, both approaches separate technical proof from legal or operational reliance. The World Bank's third interoperability level is legal recognition. OpenETR's comparable phrase is "transact globally, validate locally": events may circulate globally, but recognition remains with the assessor, attestor, relying party, or applicable legal framework. Safebox similarly treats recognition as verifier-local policy, not as something automatically granted by the issuer.

Third, both approaches value iterative deployment. The World Bank explicitly supports building trust frameworks in stages. Safebox already follows an incremental structure: human-operated flows first, then agent parity; QR/NFC bootstrap first, then secure transmittal; baseline signature verification first, then attestation, Web-of-Trust, stronger profiles, and post-quantum payload protection where needed.

Fourth, both approaches emphasize portability. The World Bank focuses on credential portability across wallets and schemes. Safebox and OpenETR broaden portability to include original artifacts, blob-backed records, signed Nostr events, issuer/holder semantics, and transferable control histories.

## Where Acorn, Safebox, and OpenETR Extend the World Bank Frame

The World Bank note is mainly about credentials. It recognizes that wallets may later include electronic signatures, payments, AI-assisted interactions, and other services, but the core analysis is still credential-centric. Safebox and OpenETR generalize the unit of analysis from "credential" to "record."

This matters because many policy-relevant artifacts are not naturally credentials. A bill of lading, warehouse receipt, private apostille, medical record, inspection photo, signed grant, community birth attestation, or commercial PDF may need integrity, provenance, presentation, control, and recognition, but not necessarily a fixed credential schema. The record-first model avoids forcing every artifact into a credential category before it can be governed.

Safebox also separates bootstrap channels from payload channels. QR and NFC carry minimal session or authorization information through `nauth` and `nembed`; actual record payloads move over secure negotiated channels. This supports the World Bank's privacy and data-minimization goals, but does so in a way that works for large records, original blobs, and constrained physical interactions.

OpenETR adds a further layer: transferable control. The World Bank's wallet model asks whether a holder can present a credential and whether a verifier can trust it. OpenETR asks whether a record can function more like a transferable instrument, where control can move without reissuance or platform lock-in. That is a different legal and commercial problem, closer to MLETR and trade documentation than to ordinary identity credential presentation.

## Policy Implications

Governments and institutions should treat record infrastructure as a broader category than credential infrastructure. Credential trust frameworks remain necessary, especially for identity, eligibility, and regulated services. But a complete digital public infrastructure strategy should also support portable private records, evidentiary records, community records, commercial records, and transferable records.

Trust frameworks should define acceptance profiles, not only credential schemas. Safebox's issued-to-holder profile is a useful example: a verifier may require that the record is signature-valid, that the presenter is the holder, that the issuer is recognized under the verifier's root-authority policy, and optionally that the issuer has attested control of the issuing Safebox. This maps well to the World Bank's assurance logic while preserving local policy choice.

Legal recognition should be layered on top of independent verification, not substituted for it. A record should be mechanically verifiable before a government, bank, court, port authority, school, clinic, cooperative, or verifier decides what legal or operational effect to give it. This is especially important for cross-border and low-trust environments, where relying parties may not share the same registry or platform.

Wallet trust frameworks should anticipate transferable records. If a national wallet strategy only plans for static credentials, it may miss high-value use cases in trade, logistics, finance, community recordkeeping, private authentication, and commercial evidence. OpenETR suggests a path where MLETR-aligned records can be represented through durable object identifiers, signed control events, and independent validation.

Inclusion policy should not assume every user has a smartphone or persistent connectivity. The World Bank recognizes wallet-less credentials and offline verification as important for accessibility. Safebox's NFC and QR flows, along with relay-backed asynchronous record exchange, provide a practical bridge between wallet-based and edge-channel use cases. This is especially relevant for community-led recordkeeping, field health records, local cooperative records, and low-infrastructure environments.

## Recommended Combined Architecture

A combined policy architecture could use the World Bank model as the governance envelope and Acorn, Safebox, and OpenETR as implementation layers:

1. Governance layer: adopt the World Bank five-layer trust-framework model for strategy, technology, scheme rules, compliance, and agreements.
2. Wallet runtime layer: use Acorn-like components for wallet state, encrypted records, relay interaction, and reusable protocol operations.
3. Application flow layer: use Safebox-like offer, grant, request, presentation, NFC, QR, secure transmittal, and verification flows.
4. Record format layer: use PRF-like artifact anchoring for documents, images, PDFs, and structured records.
5. Transferable-record layer: use OpenETR-like object/controller/event semantics where records must support durable control, transfer, endorsement, or MLETR-style legal effect.
6. Acceptance layer: define domain-specific policies for when a verifier treats a record as sufficient for action.

This architecture keeps the layers honest. The protocol proves origin, integrity, control history, holder continuity, and presentation facts. The trust framework decides who is authorized, what assurance is required, what compliance regime applies, what liability follows, and when records are legally or operationally recognized.

## Conclusion

The World Bank report is right that digital wallets will not become trusted public infrastructure through technology alone. Trust must be designed, shared, governed, audited, and recognized. Acorn, Safebox, and OpenETR do not replace that requirement. They make it more concrete for the record layer.

Their contribution is to show that records can be treated as durable, portable, independently verifiable objects rather than as platform-bound database entries or narrowly defined credentials. Safebox gives users and institutions practical flows for holding, offering, requesting, presenting, and verifying records. Acorn makes those wallet and record capabilities reusable. OpenETR extends the pattern to transferable records where control itself must move.

The policy opportunity is to combine these approaches: use trust frameworks to govern ecosystems, but use open record infrastructure to ensure that the records themselves can survive, travel, and be verified beyond any one ecosystem. That is the path from digital wallets as applications to digital wallets as public infrastructure for trustworthy records.

## Sources

- World Bank. 2026. *Digital Wallets: Trust Frameworks - Governing the Ecosystem. Digital Wallet Policy Note Series, No. 2.*
- OpenETR public site: https://trbouma.github.io/openetr/
- OpenETR README: https://github.com/trbouma/openetr/blob/main/README.md
- Safebox README: `README.md`
- Acorn README: `packages/acorn/README.md`
- Safebox record flow and verification specs: `docs/RECORD-FLOWS.md`, `docs/specs/PORTABLE-RECORD-FORMAT-PRF.md`, `docs/specs/WALLET-RECORD-STORAGE-PLAINTEXT-AND-SAFEBOXRECORD.md`, `docs/specs/RECORD-PRESENTATION-NAUTH-STRATEGY.md`, `docs/specs/WOT-ATTESTATION-AND-RECORD-VERIFICATION.md`, `docs/specs/ISSUED-TO-HOLDER-PRESENTATION-PROFILE.md`, and `docs/specs/ACCEPTANCE-MODEL.md`.
