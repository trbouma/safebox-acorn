# Acorn Security

## Purpose

Acorn is a protocol-first component for safeguarding user-controlled keys,
funds, and records. It handles Nostr private keys, Safebox Acorn mnemonics,
Protected record mnemonics, encrypted
private records, Cashu bearer proofs, and Lightning payment state. A defect can cause
loss of confidentiality, loss of access, incorrect payment reporting, or loss
of funds.

This document describes Acorn's current security model, safeguards, trust
assumptions, and residual risks. It is intentionally candid. It is not a
certification, warranty, or claim that Acorn is free of vulnerabilities.

## Current security status

Acorn is pre-release software and should presently be treated as a developer
preview or hardened alpha.

- Acorn has not received a comprehensive independent security audit.
- The proposed scope, methods, evidence, and retest requirements for such a
  review are documented in the
  [Independent Security Audit Plan](docs/INDEPENDENT-SECURITY-AUDIT-PLAN.md).
- Its storage and CLI contracts may still change before a stable release.
- Only small test balances and non-critical records should be used.
- Live tests can publish events and spend sats; they are opt-in.
- Security-sensitive changes should be reviewed and tested before release.

The current release plan and remaining gates are documented in
[Roadmap to Releasability](docs/ROADMAP-TO-RELEASABILITY.md).
The public-facing policy rationale for emerging threats is summarized in
[Mitigating AI and Quantum Attacks](website/mitigating-ai-and-quantum-attacks.md).

## Reporting a vulnerability

Please do not disclose an unpatched vulnerability, private key, seed phrase,
Cashu proof, token, invoice, preimage, private record, or production event data
in a public issue.

Use GitHub's private vulnerability-reporting feature for this repository when
it is available under **Security → Report a vulnerability**. If that feature is
not available, open a public issue containing no sensitive or exploit details
and ask the maintainer to establish a private communication channel.

A useful report includes:

- the affected commit or version;
- the affected command, method, event kind, or storage format;
- minimal reproduction steps using disposable keys and test funds;
- the expected and observed result;
- the likely confidentiality, integrity, availability, or fund-safety impact;
  and
- whether the issue is already being exploited or requires urgent action.

No formal response-time service level is offered during the developer-preview
phase. Confirmed high-impact issues should block a release until they are fixed
or explicitly documented with an operational mitigation.

## What Acorn is protecting

The principal protected assets are:

- the Acorn component's Nostr private key (`nsec`) and Safebox Acorn mnemonic;
- independently generated record-protection entropy and Record Protection Key
  (RPK) material when a consuming application enables the scaffold;
- Cashu proofs, tokens, blinding material, and payment capabilities;
- private record labels, contents, attachments, and encryption material;
- wallet configuration and infrastructure pointers;
- transaction history, messages, and private operational context; and
- continuity of access to relay-backed wallet and record state.

The Acorn keypair is not a person's identity, nor does Acorn need to describe
it as the identity of the component. It provides cryptographic continuity and
authority over funds and records. A public key is a stable protocol identifier
for that authority, but identity is interpreted outside Acorn through context
such as NIP-05 names, kind `0` profiles, Lightning addresses, credentials,
relationships, and what another party recognizes or believes about the
controller. Those associations are claims and judgments, not properties
proven by possession of the key.

Signed events provide evidence of key use over time. They can establish that a
key authorized exact event bytes and can support continuity when counterparties
recognize the same key and history. They do not prove that event content is
true, that a timestamp is objective, or that a conscious actor personally
intended the action. Acorn treats trust as an external relying-party judgment:
the belief that an intentional actor continues to control the key, governs any
delegated automation, and can be held accountable for its authorized use.

A valid signature can survive key theft, coercion, or misuse by an over-broad
automation mandate. Security controls must therefore protect the custody and
execution path around the key, preserve explicit confirmation for consequential
actions, and make delegation, recovery, and rotation visible where another
party relies on continuity.

## Trust model

Acorn separates key, code, and data, but this separation does not eliminate
trust. Each layer has a different role.

| Layer | Role | What must be trusted |
| --- | --- | --- |
| Key holder or intentional controller | Authorizes signing, decryption, spending, recovery, and any delegated automation | The key-generation process, backup method, custody environment, delegation limits, and continued alignment between valid key use and the actor's intent |
| Execution environment | Runs Acorn code and handles plaintext in memory | The operating system, Python runtime, installed package, application, and operator |
| Relay | Stores and returns signed encrypted events | Availability, retention, indexing, query correctness, and censorship policy |
| Mint | Issues and validates Cashu proofs | Correct issuance, redemption, spend-state reporting, availability, and operational integrity |
| Lightning infrastructure | Routes deposits and payments | Invoice resolution, routing, settlement reporting, and upstream availability |
| Lightning-address gateway | In a future provider design, maps a public address to an Acorn component and converts settled Lightning into private ecash delivery | Registration integrity, settlement accounting, liquidity, mint selection, bearer-token custody, delivery, retry, refund, and privacy policy |
| VPN and reverse proxy | Provides private reachability, public TLS termination, and forwarded transport metadata for a hosted application | VPN membership and ACLs, certificate handling, exact proxy trust, forwarded-header integrity, firewall policy, and configuration changes |
| Blob server | Stores encrypted attachments | Availability, retention, and resistance to traffic analysis |

Encryption prevents a relay or blob operator from directly reading protected
record content. It does not force the operator to retain, return, or erase the
data. A mint remains authoritative for whether its proofs are spendable. An
operator that controls the Acorn execution environment may be able to observe
keys and plaintext while the component is running unless a stronger hardware
or process isolation boundary is used.

## Implemented safeguards

### Key generation and recovery

- New wallets generate key material through the cryptographic randomness used
  by the underlying key libraries.
- Acorn-generated wallets have a BIP39 Safebox Acorn mnemonic that derives the
  wallet key through the documented SLIP-10 secp256k1 path.
- `acorn init --entropy` accepts exactly 256 bits of externally generated
  entropy through a hidden, confirmed prompt and produces a 24-word BIP39
  phrase.
- Imported `nsec` wallets do not claim to have a recoverable seed phrase. The
  imported key itself must be backed up.
- The target policy hands the Safebox Acorn mnemonic to the operator once at
  initialization and does not retain it in configuration or relay-backed
  state. Existing wallets may still contain an encrypted retained phrase;
  removing it safely is a documented pre-release migration requirement.
- `acorn recover` verifies that the derived wallet state is readable from the
  selected home relay before replacing local configuration.
- Recovery display is explicit and confirmation-gated.
- Acorn can generate an independent 256-bit RPK from operating-system
  cryptographic randomness.
- An application may instead supply exactly 256 bits of separately generated
  external entropy to Acorn's RPK API. Acorn derives the working key using
  HKDF-SHA256 and the domain-separation context
  `safebox-acorn/record-protection-key/v1`; it does not reuse the entropy as the
  key directly.
- RPK entropy must be generated independently from wallet entropy and must not
  be derived from a password or another guessable value. Safebox Web rejects
  exact reuse of the wallet entropy in its creation flow, but cannot detect
  every correlated or weak external source.
- RPK validation returns a canonical 32-byte working-key representation. Acorn
  can encode the exact working key as the checksummed, separately labelled
  24-word **Protected record mnemonic** and decode it directly back to the RPK. It does not
  use the wallet's BIP39-to-SLIP-10 derivation path.

The RPK functions and recovery encoding remain a scaffold for the future
protected-record profile. Acorn does not currently encrypt records with the
RPK or persist it in ordinary configuration. Safebox Web implements an initial
creation, backup-confirmation, authenticated redisplay, and reconnect ceremony,
but it has not yet been independently reviewed. A consuming application that
holds the working RPK in an encrypted session still exposes it to that
application's execution environment while processing requests.

See [Recovery Specification](docs/RECOVERY-SPEC.md) and
[External Entropy Initialization](docs/EXTERNAL-ENTROPY-INITIALIZATION.md). The
separate RPK design is documented in the
[Protected Record Profile](docs/PROTECTED-RECORD-PROFILE-DESIGN.md).

### Secret input and output

Recovery secrets are not accepted as command-line values or supported test
environment variables. Interactive input uses hidden prompts. Automation uses
stdin or a regular secret file with no group or world permission bits.

Ordinary command and JSON output redact private keys and recovery material.
Commands that deliberately export recovery material are separate, explicit
operations and must be handled as sensitive output.

See [Secret Input Specification](docs/SECRET-INPUT-SPEC.md).

### Local configuration

- The default `~/.acorn` directory is created or hardened to mode `0700`.
- Configuration files and lock files are created or hardened to mode `0600`.
- Writes serialize a complete replacement and use atomic replacement.
- File locking prevents concurrent configuration writers from interleaving.
- Malformed configuration is reported rather than silently replaced.
- Merely importing the CLI or displaying help does not create a wallet or key.

The local configuration is permission-protected, not encrypted. This important
limitation is discussed under residual risks.

### Private records and attachments

- Private record metadata is encrypted to the user's own key using NIP-44.
- Record events are signed, providing event integrity and authorship under the
  Nostr key.
- Public lookup tags are derived from the private key and label rather than
  publishing plaintext labels.
- Blob content is encrypted with AES-256-GCM before upload.
- Encrypted blob retrieval treats protected record metadata as authoritative,
  verifies the ciphertext hash, authenticates the GCM ciphertext, and verifies
  the recovered plaintext hash before returning bytes.
- A blob server's reported MIME type cannot downgrade an encrypted record into
  the legacy unencrypted retrieval path.
- Encryption profiles and record envelopes are versioned so incompatible
  changes require an explicit migration.

See the detailed envelope model, attacker paths, failure semantics, and test
requirements in the
[Record Encryption Specification](docs/RECORD-ENCRYPTION-SPEC.md#blob-security-design).

#### Quantum-resistance boundary for encrypted blobs

Each blob is encrypted under an independently generated 256-bit AES key with
AES-256-GCM and a fresh 96-bit nonce. Only the authenticated ciphertext is sent
to Blossom. Under currently known attacks, that blob ciphertext in isolation is
considered quantum-resistant: Grover's algorithm reduces the idealized cost of
exhaustive AES-256 key search toward a 128-bit security level, which remains a
strong security margin. NIST recommends AES-256-GCM with a random IV for
authenticated encryption in post-quantum designs. See the
[NIST Post-Quantum Cryptography FAQ](https://csrc.nist.gov/Projects/post-quantum-cryptography/faqs).

The AES key and nonce are not stored with the Blossom object. They are stored
inside the corresponding NIP-44-encrypted private-record event, together with
the blob reference and integrity metadata. Consequently, obtaining a Blossom
ciphertext alone is insufficient to decrypt the attachment. An attacker would
also need to recover the blob key, for example by:

- compromising the Acorn `nsec` or its execution environment;
- obtaining and decrypting the corresponding private-record event;
- exploiting an implementation or key-handling defect; or
- eventually breaking the secp256k1-based protection underlying the current
  Nostr and NIP-44 envelope.

The attacker does not need to establish the human identity of the controller.
The Acorn component's public key is enough to identify its authored events, and
Blossom authorization, timing, access patterns, or operator logs may help
correlate a ciphertext with an event. A future quantum-capable attacker that
derives the `nsec` from that public key could decrypt retained NIP-44 records,
recover their AES keys, and then decrypt the associated blobs.

The precise security claim is therefore limited: **the independently encrypted
blob ciphertext is quantum-resistant, but Acorn's present NIP-44 key envelope
and ordinary protocol stack are not yet post-quantum resistant.** Long-lived
records remain subject to harvest-now-decrypt-later risk until that envelope is
replaced or augmented by a reviewed post-quantum or hybrid construction.

The proposed
[Protected Record Profile](docs/PROTECTED-RECORD-PROFILE-DESIGN.md) would add an
independent user-backed-up symmetric key that wraps per-record keys. This could
preserve protected-record confidentiality after compromise of the `nsec` alone,
but it would add a separate, unrecoverable backup obligation for the user.
Acorn now provides the narrow key-material scaffold: it can generate an RPK
from operating-system randomness, deterministically derive one from explicitly
supplied 256-bit entropy using a domain-separated HKDF, and validate its working
representation. Acorn also provides a checksummed 24-word direct encoding of
the RPK, and Safebox Web exercises an initial backup and reconnect ceremony. No
current record is encrypted with that key; the protected-record encryption
profile remains unimplemented.

Its primary purpose is harvest-now-decrypt-later resistance: retained NIP-44
events may become readable after a future `nsec` or secp256k1 compromise, while
the RPK-protected inner record and its blob key should remain confidential. The
proposal does not claim availability. A holder of the `nsec` or an infrastructure
operator may still suppress or delete data, and current Blossom authorization
may permit author-based blob enumeration or deletion.

Sensitive deployments can reduce those availability and collection risks by
placing relays and blob servers behind firewalls, VPNs, or private gateways with
access controls independent of the `nsec`. This is defense in depth, not a
replacement for replication: provider diversity, reciprocal resilience,
encrypted backups, and tested restoration remain necessary.

### Ecash transfers and proof state

- Ecash transfers use NIP-44 encryption and default to a NIP-59 kind `1059`
  gift wrap containing an inner kind `7378` transfer event.
- Received proofs are accepted and refreshed through the mint before becoming
  part of the wallet's proof state.
- Direct token acceptance requires one identifiable issuing mint. Acorn rejects
  ambiguous tokens containing proofs from multiple mints.
- A previously unseen mint can be learned from a valid token. Acorn associates
  incoming keysets and any rotated keyset returned by the mint with that
  issuing mint.
- Refreshed proofs are published as encrypted kind `7375` events. Direct token
  acceptance retries idempotent publication and requires relay readback before
  reporting success.
- The in-memory balance is derived from the actual retained and refreshed proof
  set rather than incremented or decremented independently.
- Accepted transfers create transaction-history entries.
- The receiving operation is explicit rather than hidden inside a read-only
  balance command.
- Proof inspection can query mint state without mutating the wallet.
- Proof repair and proof swapping are separate mutating operations. The
  read-only proof check is intended to precede repair when wallet state is in
  doubt.
- Relay-visible balance is not presented as mint-confirmed value. Use
  `acorn balance --verify` when spendability matters.
- Authored kind `5` deletion events are applied client-side when loading proof
  events, even when a relay continues returning the referenced kind `7375`
  history.
- Automatic receive-side maintenance is disabled by default. Deposits and
  token acceptance do not initiate whole-wallet swaps or consolidation.
- Swap replacements are published and verified incrementally before another
  independent input or keyset is consumed. Source-event deletion occurs only
  after all replacements are durable.
- Wallet updates use relay readback checks and a lock record to reduce
  conflicting writers.

The wallet's total balance can span multiple mints and keysets. An ordinary
Lightning melt is currently constrained to one keyset, so the total balance is
not necessarily available for one Lightning payment. `acorn balance` reports
the largest mint-mapped keyset as the pre-fee Lightning capacity. The exact
payable amount can be lower after the selected mint quotes its fee reserve.

Gift wrapping reduces straightforward sender-recipient correlation. It does
not provide complete traffic-analysis resistance.

See [Ecash Transfer Design](docs/ECASH-TRANSFER-KIND-7378-DESIGN.md) and
[Proof State Consistency](docs/PROOF-STATE-RELAY-CONSISTENCY.md).

### Lightning payment ambiguity

Lightning payments through a Cashu mint have an unavoidable ambiguous period:
a client can time out after the mint has paid but before the response is safely
processed. Retrying blindly can pay twice.

Acorn records encrypted pending-melt state, checkpoints proof changes, queries
the existing mint quote after interruption, and blocks another payment while a
previous melt remains unresolved. This reduces duplicate-payment risk but
cannot make an inconsistent or unavailable mint authoritative response appear.

### Future Lightning-address gateway

The proposed Lightning-address gateway is not currently an implemented Acorn
safeguard. It would let an Acorn register a public key, delivery relays, and an
accepted-mint policy with a provider through signed challenge-response. The
provider would receive a conventional Lightning payment, obtain ecash, and
deliver it as a NIP-59 kind `1059` gift wrap containing an inner kind `7378`
transfer.

This introduces a provider trust interval that does not exist in a direct
wallet-to-wallet ecash transfer. After Lightning settlement and before
recipient acceptance or a valid refund, the provider controls value owed to
the recipient. Relay publication proves neither recipient acceptance nor
completion of that obligation.

A production gateway therefore requires registration replay protection,
payment-hash idempotency, a durable encrypted bearer-token outbox, explicit
mint and fee policy, bounded delivery retries, unclaimed-payment handling, and
auditable recovery from ambiguous external operations. It must not request or
store the recipient's `nsec`.

See [Acorn Lightning-Address Gateway Design](docs/ACORN-LIGHTNING-ADDRESS-GATEWAY-DESIGN.md).

### Relay continuity

- Signed encrypted events can be replicated without decrypting and re-encrypting
  them.
- Relay and mint endpoints are normalized and remain explicit configuration
  choices.
- Initialization and record writes use readback verification where applicable.
- Relay suitability tests exercise bootstrap readback, private-record lifecycle,
  gift-wrapped transfer, and burn-sweep behavior.
- Migration and replication tools allow a user to move away from an unreliable
  home relay.

NIP-09 deletion requests remain advisory. Successful publication of a deletion
event is not proof that every relay, mirror, backup, or observer erased the
original event.

See [Relay Resilience and Replication Design](docs/RELAY-RESILIENCE-AND-REPLICATION-DESIGN.md)
and [Relay Suitability Ledger](docs/RELAY-SUITABILITY-LEDGER.md).

### Logging

Logs are treated as untrusted disclosure channels. Acorn avoids logging:

- private keys, Safebox Acorn mnemonics, RPKs, Protected record mnemonics,
  and entropy;
- Cashu proofs, proof secrets, tokens, and blinding material;
- Lightning invoices, preimages, and complete mint request bodies;
- decrypted records, private labels, message plaintext, and complete events;
  and
- secret-bearing exception content.

Regression tests inspect logging calls for known prohibited patterns. This is a
defense against accidental disclosure, not a proof that every future exception
or third-party dependency will always be sanitized.

See [Secure Logging Specification](docs/SECURE-LOGGING-SPEC.md).

### Dependency isolation and post-quantum experiments

Open Quantum Safe support is isolated behind the optional `post-quantum`
package extra. Ordinary wallet, record, relay, mint, and ecash operations do
not require or load it.

The optional `PQEvent` code is experimental. Acorn's normal Nostr key handling,
NIP-44 record encryption, and Cashu interoperability continue to use classical
cryptography. Acorn must not currently be described as quantum-safe.

Acorn does not currently implement a key-encapsulation mechanism (KEM) in its
stable component API or persisted record formats. That omission is deliberate.
Independent AES-256-GCM blob keys, separation of the Acorn key from the RPK,
and the proposed RPK wrapping profile provide practical compartmentalization
without making ordinary Acorn installation or interoperability depend on a new
post-quantum algorithm. The optional `PQEvent` signature experiment is not a
KEM and must not be presented as one.

If a KEM is evaluated now, the experiment belongs at the consuming-application
boundary, initially Safebox Web. It must remain optional, versioned, and
separate from ordinary Acorn records. Safebox Web may hand Acorn an ordinary
validated secret or payload produced by that experiment, but Acorn should not
need to know whether the material came from a KEM, secure hardware, a hidden
form, or another trusted source. Moving a KEM into Acorn would require a stable
algorithm choice, interoperable envelope, test vectors, downgrade and migration
rules, recovery semantics, supported-platform evidence, and independent review.

### AI-enabled attack scaling

Acorn does not treat artificial intelligence as a new cryptographic primitive
or claim to be “AI-proof.” AI systems may instead increase the speed, volume,
and personalization of familiar attacks: secret discovery, dependency and
endpoint probing, phishing, impersonation, malicious-content generation,
metadata analysis, and exploitation of operational mistakes.

A valid signature proves control of a key, not the truth of generated content
or the civil identity of its controller. Material transfers and recovery
decisions may therefore require independently verified recipient keys,
challenge-response, trusted prior relationships, or human review outside
Acorn. Current mitigations include compartmentalized roles, secret-safe
interfaces and logging, authenticated encryption, explicit confirmations,
readback checks, deterministic tests, and transparent trust boundaries. These
controls reduce exposure; they do not prevent social engineering, endpoint
compromise, or attacks through trusted operators.

The approach is consistent with treating security and resilience as ongoing
risk-management work rather than a one-time product label. See the public
[Mitigating AI and Quantum Attacks](website/mitigating-ai-and-quantum-attacks.md)
brief and the
[NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework).

### Testing

The repository contains deterministic unit tests and opt-in live integration
tests. Tests cover configuration safety, key derivation, recovery, secret
input, secure logging, relay-backed records, proof inspection, interrupted
payments, optional dependency behavior, disposable wallet lifecycle, relay
suitability, and controlled spending flows.

The disposable-wallet live lifecycle includes funding, local `cashuB`
issuance, acceptance of that same token, relay and transaction-history
readback, full proof refresh, proof repair, mint-state confirmation, balance
preservation, burn, and attempted sweep-back to the source wallet. Cleanup
retains an issued test token in memory and attempts to accept it if the test
fails before normal acceptance. This reduces test-fund loss during an
in-process assertion failure; it is not a durable production token outbox.

A live-test regression exposed an accounting defect when a wallet issued its
entire balance: proof persistence had already recomputed the retained balance
as zero, after which issuance subtracted the amount a second time. The defect
was fixed by deriving balance from retained proofs, and a deterministic
regression test now covers full-balance issuance. The incident also reinforced
that an issued bearer token must survive the handoff from wallet state to its
recipient.

Passing tests demonstrate the behavior covered by those tests. They do not
replace adversarial review, fuzzing, dependency analysis, or an independent
audit.

## Residual risk register

The following risks remain material. The ordering is descriptive rather than a
formal audited severity score.

| Area | Residual risk | Current mitigation or planned response |
| --- | --- | --- |
| Security review | The code has not received a comprehensive independent audit. Unknown implementation flaws may exist. | Release initially as a developer preview; require review, failure injection, and pilot evidence before stable release. |
| Local key storage | `config.yml` contains the `nsec` in plaintext. File permissions do not protect against the user account, root, malware, backups, or disk acquisition. | Enforce `0600`/`0700`; minimize config; recommend encrypted disks and protected backups; design future OS keychain or HSM integration. |
| Runtime key exposure | Python objects and process memory contain keys, proofs, and plaintext while in use. Memory is not reliably zeroized. | Minimize lifetime and logging; keep execution hosts trusted; pursue constrained signing or hardware-backed key custody. |
| Recovery export | A confirmed recovery display can still be captured by terminals, screenshots, shell recording, clipboard tools, remote sessions, or observers. | Keep export explicit; warn users; prefer offline backup and trusted local terminals. |
| Combined safekeeping message | The mobile-friendly Safebox Acorn safekeeping message deliberately places the Safebox Acorn mnemonic and Protected record mnemonic together for reliable backup and transfer to a password-manager vault. Anyone who obtains that one message gains both the signing-key recovery path and the RPK, so the backup no longer provides independent custody of the two factors. Clipboard managers and device synchronization may create additional copies. | Label the message as highly sensitive; require explicit backup confirmation; use `Cache-Control: no-store`; keep it out of logs, URLs, databases, and JavaScript state; warn before clipboard use and clear the clipboard afterward. High-assurance users should maintain separately protected copies or distinct storage locations in addition to any combined convenience backup. |
| Key loss | Loss of both the recovery secret and usable backup means permanent loss of control. | Make recovery material available at initialization; document backup and recovery drills; support relay replication for state availability. |
| RPK lifecycle | The RPK scaffold and 24-word Protected record mnemonic exist, and Safebox Web implements an initial backup and reconnect ceremony. The ceremony is not independently reviewed. A session-only RPK disappears when the session expires or is cleared, and placing the RPK beside the `nsec` in one application session does not isolate either secret from that execution environment. | No current record depends on the RPK. Require the separately stored Protected record mnemonic before relying on the key. Do not enable protected-record creation until the encryption format, rotation, migration, compatibility vectors, and recovery UX are implemented, tested, and reviewed. Treat application session storage only as an expiring working copy. |
| Host/operator compromise | Whoever controls the running code can potentially alter behavior or observe secrets and plaintext. | Make the trust boundary explicit; pin and verify releases; isolate deployments; work toward hardware-backed authority boundaries. |
| Relay metadata | Relays can observe event kinds, timestamps, sizes, authors for non-gift-wrapped events, lookup patterns, network addresses, and replication relationships. | Encrypt content and labels; use gift wrapping for transfers; avoid claims of metadata anonymity; consider network privacy tools and relay diversity. |
| Relay availability and correctness | A relay can censor, omit, delay, reorder, retain, or return a partial view of events. Replicas can diverge. | Readback verification, suitability tests, replication, migration, health checks, and future relay-pool reconciliation. |
| Deletion | NIP-09 cannot guarantee physical erasure from relays, mirrors, logs, or backups. | Describe deletion as advisory; encrypt sensitive content so loss of ciphertext availability is not the only confidentiality control. |
| Mint trust | A mint can fail, censor, misreport proof state, disappear, or become compromised. Cashu privacy does not remove issuer operational risk. A valid token can introduce a mint that was not previously configured. | Track keyset-to-mint mappings; expose balances by mint; check proof state; support repair and future migration guidance; use small balances during preview; add explicit first-use mint approval before stable release. |
| Token-specified mint endpoint | Accepting an untrusted token causes Acorn to contact the mint URL carried by that token. A malicious URL may target an unexpected host or internal service from the Acorn execution environment. | Accept tokens only from expected sources during preview; restrict host network egress; require one issuing mint per token; add URL-policy validation, private-address blocking, and/or explicit operator approval before broad deployment. |
| Bearer proof theft | Anyone obtaining valid Cashu proofs or tokens may be able to spend them. | Encrypt relay-backed proof state; prohibit proof logging; refresh received proofs; protect process memory and backups. |
| Bearer-token issuance and handoff | `issue_token` commits removal of the issued value from the wallet proof set before returning the bearer token to its caller. A crash, assertion, application error, or lost response during that handoff can strand funds even though the mint created valid outgoing proofs. | Derive balance from retained proofs; use small amounts; make callers capture and protect the returned token immediately; live-test cleanup attempts in-memory recovery; implement a durable encrypted token outbox and acknowledged handoff before pilot release. |
| Accepted-token persistence gap | The mint can successfully refresh an incoming token before Acorn proves that the new kind `7375` event is readable from the home relay. If the process terminates during a persistent relay failure, the refreshed proofs may exist only in memory. | Retry idempotent proof publication; require relay readback before reporting success; keep the process running while resolving failures; design a durable encrypted receive journal or emergency recovery export before stable release. |
| Outgoing-transfer crash window | An interruption between bearer-token issuance and gift-wrapped transfer publication can create uncertainty or unsafe retry behavior. A complete durable transfer outbox remains a release gate. | Use small test amounts; preserve transaction evidence; implement the roadmap's idempotent transfer outbox and acknowledged delivery state before pilot release. |
| Concurrent wallet writers | Multiple processes, workers, devices, or stale relay views can race and overwrite proof state. Relay locks reduce but do not eliminate distributed concurrency risk. | Lock records, readback checks, proof audits, and repair tools; complete wallet-state isolation and failure-injection gates before stable release. |
| Balance interpretation | Total wallet balance may be distributed across independent mints or keysets and may exceed what one Lightning melt can spend. Fee reserves further reduce the payable amount. | Report mint/keyset balances and the largest single-keyset pre-fee Lightning capacity; obtain a melt quote before claiming an exact payable amount; keep multi-part payments out of scope until implemented and tested. |
| Stale relay proof history | A relay can retain or return kind `7375` events after an authored deletion request, causing a relay-visible sum to include already-spent proofs. | Apply authored kind `5` references during proof loading; label relay totals explicitly; use read-only mint verification before spending or repair; continue work on proof-state epochs or manifests for stronger ordering. |
| Partial proof swap | A mint swap consumes bearer inputs before all later inputs or keysets have completed. A process or network failure can strand replacement proofs if they exist only in memory. | Publish and verify each successful replacement batch immediately; retain source events until all replacements are durable; inject later-step failures in tests; keep automatic maintenance disabled. |
| Incoming replay and ordering | Delayed, duplicated, same-timestamp, or malicious transfer events can stress cursor and idempotency behavior. | Refresh proofs at the mint and maintain receive state; expand deterministic replay and same-timestamp tests as a release gate. |
| Lightning ambiguity | Network or mint timeouts can leave payment outcome uncertain. | Persist pending melts and reconcile by quote ID; never blindly repeat an ambiguous payment; require operator review if the mint remains unavailable. |
| Gateway registration control | A replayed, weakly bound, or improperly recovered registration could redirect a Lightning address to an attacker's key, relay, or mint policy. | Treat the gateway as future work; require short-lived single-use challenges, exact NIP-98 URL/method/body/public-key binding, versioned updates, explicit revocation, and old-key-authorized rotation. |
| Gateway funds in transit | After Lightning settles, a future gateway temporarily controls value until the recipient accepts ecash or receives a valid refund. Provider failure, insolvency, or dishonest accounting can lose or delay funds. | Do not describe the bridge as trustless or non-custodial; use bounded amounts, explicit fees and mint policy, durable accounting, reconciliation, operational reserves, and an unclaimed-payment/refund policy before pilot use. |
| Gateway bearer-token outbox | A gateway must retain an issued bearer token while delivery is pending. Theft permits spending; loss can strand settled value; a retry can issue value twice. | Encrypt the outbox at rest, restrict credentials and access, key every payment by Lightning payment hash, persist the exact serialized event for retry, inject failures at every transition, and never issue again merely because publication was ambiguous. |
| Gateway metadata correlation | A gateway can correlate a Lightning address, Acorn public key, relay set, invoice, amount, mint, timing, and delivery outcome. Gift wrapping does not hide this information from the gateway. | Minimize retention and logs, avoid public address-to-`npub` mappings by default, disclose the privacy boundary, and separate support identifiers from bearer secrets. |
| NIP-05 directory trust | A NIP-05 name is resolved through infrastructure controlled by its domain owner, reverse-proxy operator, and application operator. DNS, TLS routing, proxy configuration, code, or database compromise can remap a name or advertise attacker-controlled relays without compromising the original Acorn key. | Treat NIP-05 as a domain assertion rather than proof of human identity or permanent ownership; verify the resolved `npub` independently for material transfers; prefer an already trusted raw public key where recipient certainty is critical. |
| Reverse-proxy operator | A designated TLS reverse proxy can observe encrypted session cookies, choose the upstream application, replace responses, or route the public domain to a different service. An application-side proxy allowlist authenticates forwarded metadata only; it cannot compel an authorized proxy to reach the intended backend. | Treat the proxy operator and configuration as part of the trusted execution path; restrict administrative access; pin and review configuration; monitor the public endpoint independently; verify high-value NIP-05 mappings or recipient keys through another channel. |
| Reverse-proxy header spoofing | If an application trusts forwarded headers from arbitrary peers, a direct HTTP caller can claim that its request arrived over HTTPS and influence scheme or client metadata used by security decisions. | Restrict network access with VPN ACLs or a firewall; allow forwarded headers only from the designated immediate proxy; test that direct HTTP fails and trusted forwarded HTTPS succeeds; never confuse binding to `0.0.0.0` with proxy authorization. |
| Blob storage availability and metadata | A Blossom server can refuse, delay, retain, or delete encrypted objects and can observe ciphertext size, hash, timing, authorization, and access patterns. Encryption does not provide availability or traffic-analysis resistance. | Verify ciphertext and plaintext integrity on retrieval; use bounded uploads; disclose metadata exposure; support multiple or replaceable blob servers and replication before relying on one provider for durable availability. |
| Network privacy | Acorn does not itself provide Tor, VPN, traffic padding, or protection against endpoint correlation. | Deploy network privacy separately where required; use multiple infrastructure providers carefully; document metadata exposure. |
| Dependency supply chain | Python packages, native cryptographic libraries, build tools, and their release channels may be compromised or incompatible. | Keep optional dependencies isolated; use lock files, hashes and reproducible artifacts where possible; add CI, SBOM, provenance, and dependency scanning before release. |
| AI-enabled attack scaling | Automated systems can increase the volume and quality of phishing, impersonation, secret discovery, vulnerability probing, metadata analysis, and malicious inputs. A valid key signature does not prove that content is truthful or human-authored. | Keep secrets out of routine interfaces and logs; preserve explicit confirmation for consequential actions; validate and bound untrusted inputs; independently verify high-value recipient keys and claims; monitor dependencies and endpoints; retain human review where context matters. |
| Cryptographic evolution | Blob ciphertext independently protected by AES-256-GCM is quantum-resistant under currently known attacks, but secp256k1/Nostr and the NIP-44 envelope containing each blob key are not post-quantum. A future compromise of that envelope could expose retained blob keys and enable harvest-now-decrypt-later attacks. | Maintain versioned formats and cryptographic agility; preserve independent per-blob keys; treat current PQ support as experimental; develop reviewed hybrid envelope profiles and test vectors before claiming system-level post-quantum protection. |
| Side channels | Timing, sizes, access patterns, exceptions, and resource use can reveal information even when content is encrypted. | Reduce unnecessary metadata and sensitive logs; no formal side-channel resistance is currently claimed. |
| Denial of service | Large event sets, hostile relay responses, malformed data, or resource exhaustion may degrade service. | Apply limits and validation where implemented; add fuzzing, bounded-resource tests, and operational monitoring before broad deployment. |
| Schema and upgrade compatibility | A code or storage-format change could make old state unreadable or cause incorrect interpretation. | Version envelopes; document migrations; add compatibility fixtures and upgrade tests before stable release. |
| Application integration | A consuming application can bypass safe CLI behavior, mishandle API-returned secrets, or weaken storage and logging controls. | Treat the Python API boundary explicitly; require integrators such as Safebox to preserve Acorn's recovery, logging, configuration, and trust rules. |

## Deployment guidance

For the current developer-preview phase:

1. Use disposable wallets and small balances.
2. Keep the host patched and restrict access to the Acorn user account.
3. Use full-disk encryption and protected, tested recovery backups.
4. Do not place seed phrases, private keys, proofs, or tokens in command
   arguments, `.env` files, logs, tickets, chats, or source control.
5. Use TLS (`wss://` and `https://`) outside explicitly isolated local test
   networks.
6. Select relays for availability and policy, then replicate before a failure.
7. Treat third-party mints as independent trust domains and limit exposure.
8. Accept tokens only when the mint endpoint is expected, or constrain the
   execution environment so token-provided URLs cannot reach sensitive
   internal services.
9. Treat an issued token as funds in transit: capture it immediately and do not
   assume it can be reconstructed from the relay-backed wallet after issuance.
10. Run `acorn check-proofs` before repair when proof state is uncertain. Do not
    deliberately interrupt proof swap or repair operations.
11. Interpret total balance and single-keyset Lightning capacity separately;
    actual capacity is lower when the mint requires a fee reserve.
12. Do not interpret a successful deletion request as guaranteed erasure.
13. Run deterministic tests before deployment and opt-in live tests only with a
    funded test wallet whose possible loss is acceptable.
14. Monitor unresolved pending payments and stop rather than retrying an
    ambiguous Lightning payment blindly.

The future Lightning-address gateway must not be used for production value
until its signed registration, durable encrypted outbox, idempotent settlement,
retry, unclaimed-payment, and refund behavior have passed deterministic failure
injection and bounded live tests. Provider publication of a delivery event must
not be reported as recipient acceptance.

Highly sensitive deployments may place relays behind firewalls or private
networks and run Acorn in a dedicated jail, appliance, or constrained service
environment. That reduces exposure but does not remove the need for recovery,
replication, dependency control, and a trustworthy execution host.

## Security boundaries and non-claims

Acorn currently does not claim:

- independent audit assurance;
- guaranteed preservation or deletion by relays;
- trustless or non-custodial behavior by a Cashu mint;
- trustless or non-custodial behavior during a future Lightning-to-ecash
  gateway handoff;
- proof that relay publication means the intended recipient accepted a
  payment;
- anonymity against network, timing, or traffic analysis;
- protection after compromise of the `nsec` or execution environment;
- safe use of large balances or irreplaceable records;
- complete distributed multi-writer consistency;
- hardware-backed key isolation or memory zeroization; or
- post-quantum security for ordinary Acorn operations;
- protection from AI-assisted phishing, impersonation, malicious inputs, or
  compromise of a trusted endpoint or operator; or
- proof that signed content was created by a human or that its claims are true.

The intended direction is user control with explicit, replaceable
infrastructure—not the elimination of every dependency or trust relationship.

## Maintaining this document

Security-relevant changes should update this file when they alter:

- protected assets or trust assumptions;
- key generation, secret input, recovery, or configuration storage;
- encryption, signing, event kinds, or record formats;
- proof selection, transfer, payment, repair, or burn behavior;
- relay, mint, blob, network, or operator dependencies;
- logging and diagnostic output;
- known residual risks or release gates; or
- the project's audit and support status.

Last reviewed: 2026-08-06.
