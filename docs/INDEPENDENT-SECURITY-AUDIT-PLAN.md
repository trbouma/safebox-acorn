# Safebox Acorn Independent Security Audit Plan

## Status and purpose

This document is a commissioning plan for an independent security review of
Safebox Acorn. It defines the expected scope, threat model, methods,
deliverables, evidence, severity model, and retest process. It is not an audit
report and does not claim that the component has been independently audited.

The plan is informed by the structure of the 2025 Keylabs Passport Prime
security audit: establish adversaries and threats first, evaluate architecture
and implementation separately, identify the exact audited revision, describe
each finding with impact and a recommendation, and perform a documented retest.
For Acorn, those useful disciplines are adapted from hardware and firmware to a
Python protocol component whose principal risks arise from key handling,
bearer proofs, asynchronous state transitions, hostile infrastructure, and
supply-chain dependencies.

The independent reviewer should treat this plan as a minimum. The reviewer
must remain free to change test methods, add attack hypotheses, dispute Acorn's
documented assumptions, and report findings that do not fit the anticipated
workstreams.

## Audit objective

The audit should determine whether Acorn's documented controls and actual
implementation provide reasonable protection against:

- disclosure or misuse of Acorn private keys and recovery material;
- theft, duplication, stranding, or incorrect accounting of Cashu value;
- duplicate or ambiguous Lightning payments;
- unauthorized disclosure or undetected modification of private records and
  encrypted attachments;
- replay, substitution, censorship, stale-state, and equivocation attacks by
  relays or protocol peers;
- unsafe behavior under interruption, cancellation, concurrency, malformed
  input, and partial infrastructure failure; and
- compromise introduced through packaging, native libraries, dependencies,
  or release processes.

The audit should produce actionable evidence rather than a broad assertion
that Acorn is secure. Passing the audit means that the reviewed revision and
configuration were examined under the stated scope. It is not a warranty, a
certification of every deployment, or proof against future vulnerabilities.

## Component under review

The audit target is the installable `safebox-acorn` Python package and its
documented CLI. At the time this plan was prepared, the component includes:

- Nostr key handling, signed events, NIP-44 encryption, and NIP-59 gift wraps;
- encrypted relay-backed wallet configuration, private records, proof state,
  transaction history, and replication;
- Cashu deposits, bearer-token issuance and acceptance, proof checks, swaps,
  repair, and Lightning melts;
- Blossom-backed encrypted attachments;
- BIP39/SLIP-10 Acorn recovery and a separate Record Protection Key scaffold;
- relay, mint, NIP-05, Lightning-address, and public-profile interactions;
- local configuration and secret-input handling; and
- an optional, experimental post-quantum signature extra.

The reviewer should record the following in every private and public report:

| Audit coordinate | Required value |
| --- | --- |
| Repository | `trbouma/safebox-acorn` |
| Commit | Full immutable Git commit hash |
| Package version | Version from `pyproject.toml` |
| Lock file | Hash of the reviewed `poetry.lock` |
| Built artifacts | SHA-256 hashes of wheel and source distribution |
| Python versions | At least 3.11, 3.12, and 3.13 where supported |
| Platforms | Linux plus macOS; FreeBSD arm64 receives a focused install/runtime pass |
| Optional profile | Core install without OQS; post-quantum extra reviewed separately |
| Test configuration | Fake services, controlled live services, timeouts, and relevant environment settings |

## Independence and engagement rules

The primary auditors should not be the authors of the code under review. Any
prior contribution, financial relationship, tooling limitation, or conflict of
interest must be disclosed in the report. Acorn maintainers may explain the
design, provide test infrastructure, and prepare fixes, but must not control
the auditor's severity decisions or remove valid findings from the final
record.

The audit should use a frozen branch or tag. Emergency security fixes may be
reviewed on separate commits, but the final report must distinguish the
original audit target from remediation and retest revisions. Auditor access to
private findings and test secrets must use an agreed encrypted channel.

Production keys, records, relays, mints, and balances are out of bounds. All
active tests must use disposable keys, synthetic records, controlled services,
and minimal test funds. Testing a third-party relay, mint, NIP-05 provider, or
Blossom server beyond normal documented use requires the operator's written
authorization.

## Scope boundaries

### In scope

- all source under `acorn/` and exported symbols under `acorn/__init__.py`;
- the `acorn` CLI, including confirmation, JSON, secret-input, and exit behavior;
- serialization and validation in `acorn/models.py`;
- deterministic and live tests insofar as they support or fail to support
  security claims;
- package metadata, lock file, wheel, source distribution, and optional extras;
- Nostr, Cashu, Lightning, Blossom, NIP-05, and configuration boundaries
  exercised directly by Acorn;
- security specifications, recovery instructions, operational runbooks, and
  claims in `SECURITY.md`; and
- compatibility behavior that can expose older wallets, records, or proofs to
  unsafe downgrade or migration paths.

### Separately scoped or excluded

- Safebox Web, Safebox 2, reverse proxies, databases, and service workers,
  except where they demonstrate or misuse Acorn's public contract;
- security of third-party relays, mints, Blossom servers, Lightning nodes, DNS,
  or NIP-05 operators themselves;
- physical attacks, host kernel compromise, root compromise, malicious Python
  interpreters, and hardware side channels;
- the correctness of Bitcoin or Lightning consensus and routing; and
- a production claim for `PQEvent` or liboqs. The optional extra receives a
  boundary and dependency review, not cryptographic certification.

Excluded systems still belong in the threat model when their behavior can
cause Acorn to fail unsafely. For example, the audit does not certify a Cashu
mint, but it must test Acorn against malicious, inconsistent, delayed, and
unavailable mint responses.

## Pre-audit readiness gate

An independent audit is most valuable after known release-blocking defects are
fixed or explicitly accepted as known limitations. Before the formal review,
the maintainer should provide:

- a clean, frozen target commit and reproducible setup instructions;
- passing deterministic tests and a recorded controlled-live baseline;
- a current architecture and trust-boundary diagram;
- protocol/event-kind, encryption-envelope, proof-state, recovery, and CLI
  specifications linked to their implementations;
- an SBOM for the core and optional dependency profiles;
- test doubles for a programmable relay, mint, Blossom server, NIP-05 endpoint,
  and Lightning response boundary;
- a list of known risks, intentionally deferred controls, and unsupported uses;
- disposable test wallets and a bounded test-fund policy; and
- named contacts and an encrypted critical-finding notification channel.

The following are already documented as material known risks and should not be
hidden from the auditor:

- durable handoff/outbox recovery for issued bearer tokens and outgoing ecash
  transfers;
- durable recovery after incoming token refresh but before relay persistence;
- multi-process or multi-device proof-state concurrency;
- server-side request-forgery exposure from token-specified or otherwise
  untrusted infrastructure URLs;
- plaintext local configuration and runtime memory exposure;
- relay deletion and availability limitations; and
- the unimplemented protected-record encryption profile.

If these remain open at audit start, they must be listed as known findings or
scope limitations with explicit severity and release consequences. The
auditor should still test whether their actual impact is broader than currently
described.

## Assets and security invariants

The review should begin by confirming or correcting the following invariants.

### Keys and recovery

1. Private keys, wallet entropy, mnemonics, RPK material, proof secrets,
   preimages, and decrypted records never appear in ordinary logs, errors,
   JSON output, URLs, process arguments, or persistent test artifacts.
2. Generated entropy is cryptographically random and domain-separated
   derivations cannot collide across purposes.
3. A documented recovery input deterministically reconstructs the intended
   authority, while imported `nsec` material never creates a false mnemonic
   claim.
4. Recovery, initialization, replacement, and burn operations cannot silently
   disconnect or destroy an existing wallet.

### Funds and proof state

1. Wallet balance is derived from retained proofs, and no successful operation
   creates or destroys local value except as authorized by a mint transition,
   a bearer-token handoff, or an explicitly reported fee.
2. Read-only operations never swap, delete, publish, repair, consolidate, or
   otherwise mutate proofs.
3. A proof consumed by a mint is not removed from every recoverable local state
   until its replacement, outgoing token, or pending operation is durably
   recoverable.
4. Interrupted operations are idempotent or produce an explicit unresolved
   state that blocks unsafe retry.
5. Relay-visible proof totals are never represented as mint-confirmed
   spendability without a mint check.
6. Duplicate, replayed, stale, deleted, same-timestamp, and reordered events do
   not produce double credit or erase the newest valid proof state.
7. Concurrent writers cannot both spend or overwrite the same logical proof
   generation without a detectable conflict and recovery path.

### Records and attachments

1. Private record contents and labels are not disclosed in public tags or
   storage objects beyond documented metadata leakage.
2. Decryption requires authentic ciphertext and the correct key; bit flips,
   nonce misuse, key substitution, hash mismatch, and envelope confusion fail
   closed.
3. Blob metadata is authoritative, versioned, bounded, and bound to the
   ciphertext and recovered plaintext.
4. Updating a record cannot silently discard an existing attachment, and
   deletion behavior is accurately described as advisory where infrastructure
   erasure cannot be proven.

### Protocol and API behavior

1. Every accepted event is correctly signed, addressed, scoped, and validated
   before it influences wallet state.
2. Gift-wrap unwrapping, recipient resolution, and relay discovery cannot
   redirect value or records to an unintended key.
3. CLI and Python API success means the documented durable postcondition was
   reached; timeout or partial success is not converted into an ordinary
   success message.
4. Untrusted URLs, payload sizes, event counts, recursion, decompression, and
   network delays are bounded and cannot reach prohibited local resources.

## Threat actors and attack hypotheses

The independent threat model should cover at least:

| Actor or condition | Capabilities to test |
| --- | --- |
| Malicious relay | Omit, delay, duplicate, reorder, retain, fabricate, truncate, or selectively return events; lie about publication; provide very large result sets |
| Malicious or compromised mint | Return malformed keys or proofs, rotate keysets, misreport proof state, delay or contradict melt status, reuse identifiers, fail after consuming proofs |
| Malicious sender | Submit malformed or replayed Cashu tokens, gift wraps, events, labels, attachments, invoices, NIP-05 names, or relay lists |
| Network attacker within the model | Interrupt, delay, replay, or terminate connections; influence DNS where the execution environment permits it |
| Local unprivileged user or process | Read permissive files, race configuration writes, replace paths or symlinks, inspect arguments and ordinary output |
| Concurrent legitimate clients | Load stale views, contend for locks, cancel operations, and write from two processes or devices at once |
| Compromised dependency or build channel | Substitute Python/native packages, alter optional OQS behavior, introduce vulnerable transitive code, or produce a different artifact from the reviewed source |
| Passive observer or infrastructure operator | Correlate event authors, kinds, timing, size, relay queries, Blossom access, mint traffic, and gift-wrap delivery |
| Misconfigured consuming application | Call mutating APIs as reads, mishandle bearer-token returns, retry unresolved payments, expose exceptions, or share one Acorn across unsafe workers |

Host administrator compromise remains outside the protection claim, but the
review should identify unnecessary amplification, such as secrets retained or
copied longer than the component requires.

## Audit workstreams

### 1. Architecture, specifications, and claim validation

- Trace keys, proofs, records, tokens, invoices, and configuration through
  creation, memory, serialization, network boundaries, persistence, recovery,
  replication, and deletion.
- Map every documented security claim to code and tests.
- Distinguish implemented controls from proposed profiles and future work.
- Identify hidden coupling, global or class-level mutable state, undocumented
  trust, and ambiguous sources of truth.
- Review public API boundaries and determine whether callers can safely know
  when an operation is read-only, committed, unresolved, or recoverable.

### 2. Cryptography and key management

- Verify entropy generation, BIP39 strength selection, SLIP-10 derivation,
  Bech32 conversions, recovery vectors, external entropy validation, and RPK
  HKDF domain separation.
- Review secp256k1 signing and verification, NIP-44 conversation-key use,
  NIP-59 rumor/seal/gift-wrap construction, recipient tags, ephemeral keys,
  timestamps, and replay assumptions.
- Review AES-256-GCM key and nonce generation, authenticated data choices,
  envelope versioning, ciphertext/plaintext hashes, and failure behavior.
- Test malformed encodings, mixed case, noncanonical encodings, invalid curve
  points, signature substitution, nonce reuse, truncated tags, and cross-profile
  confusion.
- Compare implementation behavior with published Nostr, Cashu, BOLT11, BIP39,
  SLIP-10, HKDF, and AEAD specifications and known test vectors.
- Confirm that optional post-quantum code cannot silently alter or become a
  required dependency of the ordinary runtime.

### 3. Cashu value conservation and transactional safety

- Model deposit, quote confirmation, issue, accept, swap, repair, send,
  receive, burn, sweep, and melt as explicit state machines.
- Inject failure before and after every mint request, proof-state write,
  relay publication, readback, deletion request, history write, lock action,
  and return to the caller.
- Verify value conservation across full-balance issuance, change creation,
  fees, multi-mint and multi-keyset balances, keyset rotation, duplicate
  proofs, unknown keysets, and malformed DLEQ material where applicable.
- Test pending-melt persistence and reconciliation for PAID, UNPAID, PENDING,
  unknown, contradictory, unavailable, and replayed quote responses.
- Verify that unresolved operations prevent unsafe retries and that successful
  reconciliation cannot finalize twice.
- Test the exact crash windows identified in the known-risk register, including
  bearer-token return, outgoing transfer publication, and incoming refreshed
  proof persistence.

### 4. Relay state, event integrity, replication, and concurrency

- Test stale and divergent relay histories, authored kind `5` deletions,
  delayed indexing, false publication acknowledgement, incomplete reads,
  pagination/limits, duplicate IDs, same-second timestamps, and clock skew.
- Verify filters use NIP-01 tag semantics correctly and never accept an event
  merely because an unverified field resembles a filter match.
- Test NIP-59 transfer privacy and integrity, direct-mode compatibility,
  expiration tags, replay cursors, alternate receive keys, and transient-key
  non-persistence.
- Exercise replication and migration with missing deletions, partial target
  writes, mixed relay capability, and verification failure.
- Run two-process and two-device schedules against the same wallet, including
  stale reads, lock theft/expiry, cancellation, and simultaneous deposits,
  receives, swaps, and payments.

### 5. Records, blobs, and privacy

- Review deterministic lookup-tag construction and quantify offline label
  guessing or correlation risks after different compromise scenarios.
- Test create/read/list/update/delete behavior with malicious JSON, Unicode,
  oversized labels and payloads, duplicate records, conflicting timestamps,
  invalid signatures, and attachment preservation.
- Test encrypted blob upload and retrieval against content substitution,
  MIME confusion, hash mismatch, truncation, oversized responses, server-side
  error bodies, malicious filenames, and legacy unencrypted envelopes.
- Confirm private content is not included in Blossom authorization, logs,
  exception chains, cache files, or temporary files.
- Document metadata visible to relays, mints, Blossom operators, NIP-05
  providers, and passive network observers.

### 6. Network inputs and endpoint policy

- Fuzz Cashu CBOR tokens, BOLT11 invoices, LNURL/NIP-05 responses, Nostr events,
  NIP-19 values, relay URLs, mint URLs, and Blossom responses.
- Test DNS rebinding, redirects, embedded credentials, fragments, alternate IP
  spellings, IPv4/IPv6 loopback, private/link-local/cloud-metadata addresses,
  unusual ports, trailing slashes, and scheme confusion.
- Verify connection, read, write, and overall timeouts; response-size limits;
  redirect policy; TLS verification; and error-body redaction.
- Determine which network calls are synchronous inside async operations and
  whether they can block cancellation or exhaust workers.

### 7. Local configuration, CLI, and secret handling

- Test initial and existing file modes, parent-directory permissions, atomic
  replacement, locking, symlink/hard-link races, crash consistency, malformed
  YAML, partial writes, backup behavior, and concurrent writers.
- Inspect every CLI option for accidental secret acceptance through process
  arguments or environment variables.
- Test confirmation and `--force` behavior for initialization, recovery,
  deletion, burn, replication, and funded-wallet destruction.
- Verify JSON output schemas, exit codes, stdout/stderr separation, terminal
  control characters, redaction, and noninteractive failure behavior.
- Search source, tests, examples, tracked files, built artifacts, logs, and
  exception paths for secrets and real wallet material.

### 8. Async lifecycle, resource exhaustion, and error contracts

- Inspect task, websocket, relay-client, HTTP-client, file, and lock cleanup on
  normal completion, cancellation, timeout, exception, and event-loop shutdown.
- Test bounded behavior with hostile event counts, proof counts, record sizes,
  nested JSON/CBOR, slow streams, and repeated connection failures.
- Identify broad exception handlers, exception laundering, partial mutation
  hidden behind generic errors, and messages that encourage unsafe retry.
- Verify one Acorn instance cannot leak keys, relays, mints, proofs, cursors,
  locks, or history into another instance.

### 9. Dependencies, packaging, and release integrity

- Generate CycloneDX or SPDX SBOMs for core and post-quantum profiles.
- Run vulnerability, license, secret, and static-analysis tools against direct
  and transitive Python and native dependencies.
- Review `monstr`, `coincurve`, `secp256k1`, `cryptography`, Cashu-related code,
  Blossom, CBOR, YAML, HTTP, and optional liboqs boundaries with priority given
  to native code and parsers.
- Build wheel and source distribution from the frozen commit; inspect contents;
  install into clean environments; and compare artifact hashes and imports.
- Confirm the core wheel installs and operates without liboqs and that enabling
  the optional extra fails clearly when its native runtime is incompatible.
- Review GitHub Actions permissions, pinned actions, release credentials,
  trusted publishing, dependency update policy, provenance, and rollback.

## Required testing methods

The engagement should combine:

- manual source review by at least one reviewer experienced with payment or
  wallet state machines and one reviewer experienced with applied cryptography;
- automated static analysis and dependency scanning, with findings manually
  triaged rather than reported verbatim;
- property-based tests for parsers, serialization, key derivation, value
  conservation, and state transitions;
- coverage-guided fuzzing of unauthenticated and remote-controlled inputs;
- deterministic fake-relay, fake-mint, fake-Blossom, and fake-NIP-05 services;
- systematic fault injection and cancellation at security-relevant await and
  persistence boundaries;
- concurrency and model-based state-machine testing;
- installed-wheel and platform smoke tests; and
- carefully bounded live interoperability tests after deterministic testing.

Useful tools may include Hypothesis, Atheris or equivalent Python fuzzing,
Bandit/Semgrep/CodeQL, pip-audit or OSV-Scanner, detect-secrets or Gitleaks,
CycloneDX/SPDX generation, coverage analysis, and mutation testing. Tool output
is evidence and a lead source, not a substitute for reviewer judgment.

## Priority test matrix

| Priority | Scenario | Required result |
| --- | --- | --- |
| P0 | Crash after mint consumes swap inputs but before relay persistence | Replacement value remains durably recoverable or operation is explicitly blocked as unresolved |
| P0 | Crash after token issuance but before caller receives or publishes token | Exact bearer token is recoverable without issuing a second token |
| P0 | Melt timeout after possible Lightning settlement | Pending quote blocks retry and later reconciliation finalizes exactly once |
| P0 | Two writers spend from one stale proof view | At most one commits; conflict is detected without silent value loss |
| P0 | Malicious token supplies internal or metadata-service mint URL | Connection is blocked or requires explicit trusted policy |
| P0 | Ordinary logs/errors during every key and value flow | No prohibited secret material is emitted |
| P1 | Relay returns deleted, duplicate, reordered, and same-time proof events | Current state is deterministic and mint verification remains authoritative |
| P1 | Incoming transfer replayed across relays and receive cursors | Credited at most once; cursor advancement cannot hide an unprocessed valid transfer |
| P1 | Blob ciphertext, metadata, MIME, or hashes are substituted | Retrieval fails closed and returns no unauthenticated plaintext |
| P1 | Recovery from 12-word, 24-word, external entropy, imported `nsec`, and RPK mnemonic | Documented keys reproduce exactly and unsupported claims are rejected |
| P1 | Relay/mint response is oversized, malformed, or indefinitely slow | Resource use is bounded and no partial mutation is reported as success |
| P1 | Core artifact installed without optional OQS dependencies | Ordinary Acorn operations and CLI smoke tests pass |
| P2 | Privacy observation across relay, mint, Blossom, and NIP-05 traffic | Report accurately documents correlatable metadata and practical mitigations |

Any P0 scenario without a safe, tested outcome should block a pilot release
that holds meaningful funds.

## Finding format and severity

Every finding should include:

- stable identifier and title;
- severity, likelihood, affected asset, and confidentiality/integrity/
  availability/fund-safety classification;
- affected commit, file, function, protocol object, and configuration;
- prerequisites and attacker capabilities;
- description and root cause;
- minimal reproduction using disposable material;
- observed and expected behavior;
- maximum credible impact and any factors that bound it;
- recommended remediation and safer design alternatives;
- regression-test requirement;
- maintainer response; and
- status: open, accepted, mitigated, fixed-pending-retest, or verified fixed.

CVSS may be included for interoperability with vulnerability programs, but it
must not replace wallet-specific impact. Use the following project scale:

| Severity | Acorn interpretation |
| --- | --- |
| Critical | Practical unauthorized private-key or broad bearer-proof compromise; unauthenticated arbitrary value transfer; repeatable double payment or systemic value loss; release/build compromise affecting users |
| High | Realistic loss or stranding of meaningful funds; recovery-secret disclosure; cross-wallet state compromise; durable private-record decryption; bypass of an essential authorization or integrity boundary |
| Medium | Bounded loss, privacy breach, denial of recovery, SSRF with constrained reach, state corruption requiring significant preconditions, or unsafe behavior with a workable operational mitigation |
| Low | Defense-in-depth weakness, limited metadata exposure, hardening gap, or low-impact deviation that does not directly compromise protected assets |
| Informational | Documentation, maintainability, observability, or best-practice improvement without a demonstrated security impact |

Likelihood and impact must be reported separately. Physical-host compromise,
malicious infrastructure, or user interaction should not automatically reduce
severity if those capabilities are explicitly within the documented threat
model.

## Deliverables

The engagement should produce:

1. **Kickoff scope record** - target commit, exclusions, contacts, environment,
   schedule, known risks, and rules of engagement.
2. **Independent threat model** - assets, trust boundaries, adversaries, abuse
   cases, data flows, and corrected security invariants.
3. **Coverage and evidence matrix** - each workstream and invariant mapped to
   reviewed code, tests performed, and limitations.
4. **Immediate critical notifications** - encrypted notification without
   waiting for the draft report.
5. **Private draft report** - executive summary, methodology, architecture
   assessment, strengths, findings, systemic themes, and recommendations.
6. **Remediation register** - finding owner, decision, fix commit, regression
   test, and target release.
7. **Retest report** - exact remediation commit and evidence for every finding,
   including findings that remain accepted or partially fixed.
8. **Public report** - mutually coordinated disclosure with no live secrets or
   unnecessarily weaponized details, while preserving finding counts,
   severities, scope, limitations, and unresolved risks.
9. **Supporting artifacts** - SBOMs, artifact hashes, reusable test vectors,
   non-sensitive harnesses, and machine-readable finding data where possible.

The final report should include both strengths and weaknesses, but praise must
be supported by reviewed mechanisms and tests. Planned controls must never be
described as implemented.

## Retest and disclosure process

Each fix should be isolated where practical, include a deterministic regression
test, and cite the original finding. The auditor should verify the fix against
the remediation commit and also check for bypasses, adjacent variants, and
regressions. Maintainer assertion or a passing project test alone is not a
verified retest.

The original severity and finding count should remain visible after remediation.
The retest status should say whether the issue is fixed, partially fixed,
mitigated, accepted, or not retested. A public report should identify the
original and final commits so readers can distinguish reviewed code from later
changes.

Recommended disclosure sequence:

1. encrypted immediate notice for suspected Critical or actively exploited issues;
2. private draft and factual review;
3. remediation window based on severity and exploitability;
4. independent retest;
5. release of fixed packages and operational guidance; and
6. coordinated public report after affected users can update.

## Estimated engagement shape

The audit supplier should provide its own estimate after scoping. For planning,
Acorn's protocol breadth, native dependencies, approximately ten-thousand-line
core class, and fund-safety state machines justify at least two reviewers and a
multi-week engagement.

An indicative sequence is:

| Phase | Indicative effort |
| --- | --- |
| Readiness, setup, and scope freeze | 2-4 reviewer days |
| Independent threat model and architecture review | 3-5 reviewer days |
| Cryptography, keys, records, and protocol review | 8-12 reviewer days |
| Cashu/Lightning state machines and fault injection | 10-15 reviewer days |
| Network, CLI, dependency, packaging, and platform review | 6-10 reviewer days |
| Report, factual review, and evidence packaging | 4-6 reviewer days |
| Retest | 3-8 reviewer days, depending on findings |

This is roughly 33-60 reviewer days, excluding maintainer remediation. A
shorter engagement should explicitly reduce scope rather than imply equivalent
assurance.

## Audit completion criteria

The engagement is complete when:

- every in-scope workstream has evidence or an explicit limitation;
- all findings have stable IDs, severities, affected revisions, and dispositions;
- every Critical and High finding intended for release has been independently
  retested as fixed, or the release is blocked;
- accepted Medium risks have an owner, operational mitigation, and target date;
- the public security model and residual-risk register match the audited behavior;
- SBOMs and reviewed artifact hashes are retained with the report;
- deterministic security regressions run in CI; and
- the final report states what was not tested and what changed after the audit.

## Relationship to existing Acorn documents

The auditor should begin with, but independently challenge:

- [`SECURITY.md`](../SECURITY.md)
- [Roadmap to Releasability](ROADMAP-TO-RELEASABILITY.md)
- [Acorn Component Boundary](ACORN-COMPONENT-BOUNDARY.md)
- [Record Encryption Specification](RECORD-ENCRYPTION-SPEC.md)
- [Recovery Specification](RECOVERY-SPEC.md)
- [Secret Input Specification](SECRET-INPUT-SPEC.md)
- [Secure Logging Specification](SECURE-LOGGING-SPEC.md)
- [Proof State and Relay Consistency](PROOF-STATE-RELAY-CONSISTENCY.md)
- [Lightning Melt Recovery](LIGHTNING-MELT-RECOVERY.md)
- [Ecash Transfer Design](ECASH-TRANSFER-KIND-7378-DESIGN.md)
- [Relay Resilience and Replication](RELAY-RESILIENCE-AND-REPLICATION-DESIGN.md)
- [Mint Configuration Specification](MINT-CONFIGURATION-SPEC.md)
- [External Entropy Initialization](EXTERNAL-ENTROPY-INITIALIZATION.md)
- [Protected Record Profile Design](PROTECTED-RECORD-PROFILE-DESIGN.md)

These documents are evidence of design intent. The independent audit must
verify whether source, artifacts, tests, and observed behavior actually satisfy
them.
