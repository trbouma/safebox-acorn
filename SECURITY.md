# Acorn Security

## Purpose

Acorn is a protocol-first component for user-controlled identity, funds, and
records. It handles Nostr private keys, recovery phrases, encrypted private
records, Cashu bearer proofs, and Lightning payment state. A defect can cause
loss of confidentiality, loss of access, incorrect payment reporting, or loss
of funds.

This document describes Acorn's current security model, safeguards, trust
assumptions, and residual risks. It is intentionally candid. It is not a
certification, warranty, or claim that Acorn is free of vulnerabilities.

## Current security status

Acorn is pre-release software and should presently be treated as a developer
preview or hardened alpha.

- Acorn has not received a comprehensive independent security audit.
- Its storage and CLI contracts may still change before a stable release.
- Only small test balances and non-critical records should be used.
- Live tests can publish events and spend sats; they are opt-in.
- Security-sensitive changes should be reviewed and tested before release.

The current release plan and remaining gates are documented in
[Roadmap to Releasability](docs/ROADMAP-TO-RELEASABILITY.md).

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

- the Acorn component's Nostr private key (`nsec`) and recovery phrase;
- Cashu proofs, tokens, blinding material, and payment capabilities;
- private record labels, contents, attachments, and encryption material;
- wallet configuration and infrastructure pointers;
- transaction history, messages, and private operational context; and
- continuity of access to relay-backed wallet and record state.

The Acorn keypair is the identity of the component, not necessarily the civil
or social identity of a person. It provides continuity and signing authority
over the component's funds and records. Applications may associate that
component identity with a person, organization, device, or service, but those
claims are outside the keypair itself.

## Trust model

Acorn separates key, code, and data, but this separation does not eliminate
trust. Each layer has a different role.

| Layer | Role | What must be trusted |
| --- | --- | --- |
| Key holder | Authorizes signing, decryption, spending, and recovery | The key-generation process, backup method, and device or secret store |
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
- Acorn-generated wallets have a BIP39 offline mnemonic that derives the
  wallet key through the documented SLIP-10 secp256k1 path.
- `acorn init --entropy` accepts exactly 256 bits of externally generated
  entropy through a hidden, confirmed prompt and produces a 24-word BIP39
  phrase.
- Imported `nsec` wallets do not claim to have a recoverable seed phrase. The
  imported key itself must be backed up.
- The target policy hands the offline mnemonic to the operator once at
  initialization and does not retain it in configuration or relay-backed
  state. Existing wallets may still contain an encrypted retained phrase;
  removing it safely is a documented pre-release migration requirement.
- `acorn recover` verifies that the derived wallet state is readable from the
  selected home relay before replacing local configuration.
- Recovery display is explicit and confirmation-gated.

See [Recovery Specification](docs/RECOVERY-SPEC.md) and
[External Entropy Initialization](docs/EXTERNAL-ENTROPY-INITIALIZATION.md).

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
- Encryption profiles and record envelopes are versioned so incompatible
  changes require an explicit migration.

See [Record Encryption Specification](docs/RECORD-ENCRYPTION-SPEC.md).

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

- private keys, seed phrases, and entropy;
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

The optional `PQEvent` code is experimental. Acorn's normal Nostr identity,
NIP-44 record encryption, and Cashu interoperability continue to use classical
cryptography. Acorn must not currently be described as quantum-safe.

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
| Key loss | Loss of both the recovery secret and usable backup means permanent loss of control. | Make recovery material available at initialization; document backup and recovery drills; support relay replication for state availability. |
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
| Reverse-proxy header spoofing | If an application trusts forwarded headers from arbitrary peers, a direct HTTP caller can claim that its request arrived over HTTPS and influence scheme or client metadata used by security decisions. | Restrict network access with VPN ACLs or a firewall; allow forwarded headers only from the designated immediate proxy; test that direct HTTP fails and trusted forwarded HTTPS succeeds; never confuse binding to `0.0.0.0` with proxy authorization. |
| Network privacy | Acorn does not itself provide Tor, VPN, traffic padding, or protection against endpoint correlation. | Deploy network privacy separately where required; use multiple infrastructure providers carefully; document metadata exposure. |
| Dependency supply chain | Python packages, native cryptographic libraries, build tools, and their release channels may be compromised or incompatible. | Keep optional dependencies isolated; use lock files, hashes and reproducible artifacts where possible; add CI, SBOM, provenance, and dependency scanning before release. |
| Cryptographic evolution | secp256k1/Nostr and current NIP-44 formats are not post-quantum. Long-lived ciphertext may face harvest-now-decrypt-later risk. | Maintain versioned formats and cryptographic agility; treat current PQ support as experimental; develop reviewed hybrid profiles and test vectors before claiming protection. |
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
- post-quantum security for ordinary Acorn operations.

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

Last reviewed: 2026-08-03.
