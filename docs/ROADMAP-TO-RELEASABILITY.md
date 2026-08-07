# Roadmap to Releasability

## Summary

Acorn is a protocol-first component for safeguarding user-controlled keys,
funds and records.

Acorn is approaching the point where it can be distributed independently from
Safebox. It already has a standalone package, an editable development workflow,
substantial protocol documentation, live relay and mint tests, and an optional
post-quantum dependency boundary.

Releasability is not the same as feature completeness. A releasable Acorn must
be safe to install, clear about its guarantees, recoverable when infrastructure
fails, and predictable when called by another application. Because Acorn
handles private keys, encrypted records, and spendable ecash, release gates
must emphasize loss prevention and recovery over feature count.

The recommended first public release is an explicitly labelled developer
preview or alpha. A stable release should follow only after the fund-safety,
configuration, concurrency, packaging, and pilot gates in this document are
satisfied.

## Current position

The commissioning scope for an external review is maintained in the
[Independent Security Audit Plan](INDEPENDENT-SECURITY-AUDIT-PLAN.md). It
defines the pre-audit readiness gate, fund-safety and cryptographic workstreams,
independence rules, finding severity, evidence, and retest requirements.

As of July 2026, the project has demonstrated:

- independent installation as `safebox-acorn`;
- an editable local-development workflow;
- a CLI and Python component boundary;
- encrypted private-record storage and retrieval;
- Cashu deposit, payment, transfer, receipt, repair, and burn flows;
- NIP-59 gift-wrapped ecash delivery;
- relay replication and migration;
- operation against controlled and third-party relays;
- operation against controlled and third-party mints;
- recovery interoperability between the CLI and Safebox web application;
- non-live and opt-in live pytest suites;
- optional Open Quantum Safe support through the `post-quantum` package extra;
- specifications covering records, encryption, recovery, relays, mints,
  proof-state consistency, replication, and the Safebox boundary.

This is a credible hardened alpha foundation. The remaining work is primarily
about operational discipline, failure recovery, stable interfaces, and release
automation.

## Recommended execution order

The gates below contain more detail, but the practical sequence is:

| Order | Workstream | Exit criterion |
|---:|---|---|
| 1 | Configuration safety | Private, atomic, non-destructive config handling |
| 2 | Wallet state isolation | Two wallets can run in one process without shared mutable state |
| 3 | Transfer outbox | An interrupted outgoing transfer can be retried without issuing value twice |
| 4 | Incoming idempotency | Duplicate, delayed, and same-timestamp transfers are handled safely |
| 5 | Proof failure injection | Mint and relay failures leave a tested recovery path |
| 6 | Async lifecycle | One event loop per CLI invocation and clean relay-client shutdown |
| 7 | Deterministic test expansion | Core value and record behavior is testable without a live service |
| 8 | Package and CI pipeline | Exact wheels are tested in core and optional-PQ environments |
| 9 | Clean FreeBSD validation | A fresh jail install follows documented, repeatable steps |
| 10 | TestPyPI and pilot | A tagged candidate is installed externally and exercised by pilot users |

The first two workstreams are contained hardening tasks. The transfer outbox is
the most important behavioral addition. Packaging and publication should follow
those safety changes so the first public artifact represents the intended
operational baseline.

## Release levels

### Developer preview

A developer preview is suitable for collaborators who understand that APIs and
storage behavior may still change. It should:

- install cleanly from a Git tag or wheel;
- pass deterministic tests;
- preserve recovery material;
- clearly warn that only small test balances should be used;
- document known limitations and unsupported deployment patterns.

Recommended version form:

```text
0.1.0a1
```

### Pilot release

A pilot release is suitable for a bounded Safebox deployment or another
application integration. It should add:

- reliable transfer recovery;
- protected local configuration;
- repeatable FreeBSD, macOS, and Linux installation;
- stable core Python and CLI contracts;
- operational runbooks and an incident process;
- evidence from a real pilot using replaceable relays and mints.

### Stable release

A stable release means Acorn can be upgraded and embedded without routine
surprises. It requires:

- explicit compatibility and deprecation rules;
- concurrency-safe proof-state behavior;
- reproducible package publication;
- supported recovery and migration paths;
- documented security and trust boundaries;
- a completed pilot with resolved high-severity findings.

## Release principles

The following principles apply to every release level:

1. A failed operation must not silently lose user-controlled value or records.
2. Recovery material must remain usable without the original application.
3. Read-only operations must not mutate proof or record state.
4. Ordinary installation must not require experimental dependencies.
5. Tests that spend sats or mutate live infrastructure must remain opt-in.
6. A release must be tested from the built artifact, not only from the source
   directory.
7. Claims must describe demonstrated behavior and clearly identify experimental
   features.

## Gate 1: Fund and transfer safety

This is the highest-priority release gate.

### Durable outgoing transfers

The sender currently creates and commits an ecash token before relay delivery
is known to be durable. A releasable transfer flow needs a local or
relay-recoverable outbox containing enough information to retry delivery
without spending again.

Required behavior:

- assign an idempotency identifier to every outgoing transfer;
- retain the token until publication is confirmed or explicitly cancelled;
- distinguish `prepared`, `published`, `confirmed`, `failed`, and `recovered`
  states;
- allow an interrupted sender to retry the same transfer;
- provide a recovery command for unpublished or uncertain transfers;
- never issue a second token merely because a relay response timed out;
- make relay acknowledgement and readback policy explicit.

NIP-59 hides the sender and is not inherently sender-deletable. The outbox must
therefore be treated as delivery recovery state, not as a promise that a
gift-wrapped relay event can later be erased.

### Proof-state transactions

Acorn already performs proof readback verification and attempts an emergency
restore after proof rewrites. Before a pilot:

- inject failures before and after mint swap, relay publish, deletion, and
  readback;
- verify that every failure leaves a documented recovery path;
- ensure proof replacement never reports success from a partial relay view;
- preserve mint-to-keyset mappings across repair and migration;
- test duplicate, stale, spent, pending, and unknown proofs;
- record an operation identifier in logs without logging proof secrets;
- enforce the [Secure Logging Specification](SECURE-LOGGING-SPEC.md) at every
  log level, including DEBUG;
- keep regression tests that reject proof, key, invoice, token, message, and
  decrypted-record serialization in log calls; and
- enforce the [Secret Input Specification](SECRET-INPUT-SPEC.md): recovery
  secrets never travel in command arguments, test environment variables, or
  permission-open files.

The Lightning melt path now establishes a recovery baseline: it checkpoints
post-swap proofs, stores an encrypted pending-melt journal, never repeats an
ambiguous melt `POST`, and resumes terminal-state handling by quote ID after a
restart. Deterministic tests cover delayed success, unresolved timeout,
confirmed failure, and restart recovery. Remaining release work is to exercise
the same boundaries with fake relay/mint failure injection and opt-in live
interoperability tests.

### Incoming-transfer idempotency

Timestamp cursors alone are insufficient when several events share a timestamp,
a relay returns events out of order, or processing stops partway through a
batch.

Before a pilot:

- track processed transfer event IDs or nonces;
- make repeated receipt safe;
- retry failed-but-unspent transfers;
- avoid permanently advancing beyond an event that has not been classified;
- define retention for processed-event identifiers.

### Multi-instance concurrency

The relay-backed wallet lock is useful but cannot by itself guarantee
serializable updates across delayed or partitioned relays.

Before a stable release:

- define the supported single-writer or multi-writer model;
- add state generations or optimistic concurrency checks;
- test two Acorn instances acting on the same wallet;
- detect stale writers before destructive proof replacement;
- document conflict recovery after relay divergence.

## Gate 2: Key and configuration safety

The local configuration contains the `nsec` and must be treated as sensitive
bootstrap material.

Before a developer preview:

- create the configuration directory with private permissions;
- write configuration files with mode `0600`;
- use atomic write-and-replace behavior;
- prevent concurrent configuration writers;
- avoid rewriting configuration merely because the CLI module was imported;
- preserve the previous valid config if serialization or disk writes fail;
- verify that normal CLI output and JSON output never expose the `nsec`;
- require explicit confirmation before displaying recovery material.

Before a pilot:

- document filesystem backup and restore behavior;
- define how operator-hosted deployments protect keys;
- add tests for malformed, missing, partially written, and permission-denied
  configs;
- document the future boundary for HSM, hardware, or constrained-signing
  support.

The initial release may store an `nsec` in a protected local YAML file, provided
that this limitation and its trust boundary are stated plainly.

## Gate 3: Runtime and component discipline

### Per-instance state

All mutable wallet data must belong to an `Acorn` instance. Mutable class
attributes can leak state between wallets in a long-running application.

Required work:

- initialize every mutable list, dictionary, cursor, and event collection in
  `__init__`;
- add tests that operate two independent wallets in one process;
- ensure repeated `load_data()` calls replace rather than accumulate state;
- ensure web-service workers cannot share wallet state accidentally.

### Async lifecycle

The CLI currently creates multiple event loops through repeated
`asyncio.run()` calls, while relay clients may own background tasks.

Before a pilot:

- give each CLI invocation one async entry point and one event loop;
- make relay-client shutdown explicit;
- remove test-only cleanup workarounds as lifecycle handling improves;
- move synchronous network calls out of async paths;
- use explicit connection and request timeouts;
- propagate cancellation without leaving locks or clients active.

### Error contracts

Public methods currently use a mixture of exceptions, strings, tuples,
dictionaries, and `None`.

Before a stable release:

- define a small exception hierarchy;
- use typed result models for operations that can partially succeed;
- distinguish retryable infrastructure errors from invalid input and
  irreversible state changes;
- give JSON CLI errors stable fields and non-zero process exit codes;
- remove bare `except` clauses from core security and value paths.

### Internal modularity

The large core module should be separated gradually after behavior is covered
by tests. Candidate boundaries are:

- wallet and proof-state management;
- mint protocol client;
- relay storage and publication;
- record encryption and blob handling;
- ecash transfer orchestration;
- key identifiers, NIP-05 resolution, and external identity claims;
- CLI formatting and command orchestration.

Modularization is not a prerequisite for the first developer preview, but the
highest-risk fund and configuration paths should not continue growing inside a
single module through the pilot.

## Gate 4: Public API and protocol contracts

Before publishing:

- identify the supported Python imports;
- define the public/private keypair consistently as cryptographic continuity
  and authority, not identity; explain that NIP-05, kind `0` profiles,
  Lightning addresses, credentials, relationships, and other external context
  may contribute to identity judgments made outside Acorn;
- document whether `Acorn` construction performs I/O;
- define sync versus async entry points;
- document every CLI command intended to remain supported;
- standardize relay and mint URL normalization;
- ensure automated commands support clean JSON where appropriate;
- document event kinds, encryption profiles, and reserved record labels;
- version stored payloads that may evolve;
- define compatibility for older wallet records and direct kind `7378`
  transfers;
- keep experimental APIs outside the default public surface.

The compatibility import:

```python
from acorn.monstrmore import PQEvent
```

may remain available, but the supported experimental location is:

```python
from acorn.post_quantum import PQEvent
```

Post-quantum behavior must remain explicitly experimental until it has known-good
native-library versions, test vectors, and interoperability review.

## Gate 5: Test strategy

### Deterministic tests

The default suite must never require network access, private keys, or sats.
Priority additions include:

- proof selection and change construction;
- mint response validation;
- proof rewrite rollback;
- duplicate and stale proof handling;
- NIP-44 and NIP-59 round trips and malformed envelopes;
- transfer outbox recovery;
- multiple events with the same timestamp;
- two-wallet state isolation;
- configuration permissions and atomic writes;
- relay URL and mint URL normalization;
- CLI JSON schemas and exit codes;
- recovery vectors and backward compatibility.

Use fake relay and fake mint implementations to inject timeouts, rejection,
partial reads, malformed responses, and delayed indexing.

### Live tests

Live tests should remain in the GitHub repository and out of the runtime wheel.
They must:

- remain opt-in through `-m live`;
- use small configurable amounts;
- use disposable wallets for mutation-heavy scenarios;
- use the source wallet only as a funding and recovery anchor;
- stop before spending sats when wallet bootstrap readback fails;
- clearly summarize relay and mint suitability;
- sweep remaining disposable funds when possible;
- never commit `.env`, wallet configs, nsecs, tokens, or invoices.

The relay suitability ledger should record the date, runtime, observed
capabilities, Acorn version, and whether the relay was controlled or independent.

### Installed-artifact tests

Repository tests prove source behavior. Release tests must additionally prove
the built wheel.

For every release candidate:

1. build the wheel and source distribution;
2. install the ordinary wheel in a fresh virtual environment;
3. verify that `oqs` is neither installed nor imported;
4. run Python import and CLI smoke tests;
5. install the wheel with `[post-quantum]` in another fresh environment;
6. verify OQS provider loading and the `PQEvent` boundary;
7. run a small external contract suite that imports only public APIs.

The full pytest suite does not need to be included in the wheel. Downstream
packagers may benefit from tests in the source distribution, but live tests
must remain disabled by default.

## Gate 6: Platform and dependency support

The initial support matrix should be explicit rather than implied.

Recommended release matrix:

| Platform | Python | Required validation |
|---|---:|---|
| macOS arm64 | 3.11-3.13 | Core install, CLI, deterministic tests |
| Linux x86_64 | 3.11-3.13 | Core install, CLI, deterministic tests |
| FreeBSD arm64 | 3.11 | Core install, CLI, live smoke test |

Before a pilot:

- repeat the
  [FreeBSD jail installation](./FREEBSD-JAIL-INSTALL.md) from a clean jail;
- confirm the ordinary package installs without `liboqs`;
- document optional OQS installation separately;
- test native dependencies such as coincurve, cryptography, secp256k1, and
  pyzmq where applicable;
- record a known-good FreeBSD package and Python version matrix;
- avoid making experimental native libraries prerequisites for core Acorn.

Dependency discipline should include:

- a current lock file for development;
- minimum and maximum versions justified by testing;
- automated vulnerability and license review;
- a documented process for urgent dependency updates;
- removal of dependencies that are not part of the component boundary.

## Gate 7: Packaging and publication

### Package metadata

Before PyPI publication, complete:

- package description and long description;
- project and documentation URLs;
- source and issue-tracker URLs;
- license metadata;
- Python classifiers;
- supported Python versions;
- author or maintainer contact;
- package keywords;
- explicit inclusion of required package data;
- explicit exclusion of secrets, local configs, logs, and test output.

### Distribution contents

The wheel should contain:

- the `acorn` Python package;
- required package metadata;
- license information;
- runtime resources genuinely required by Acorn.

It should not contain:

- `.env` files;
- wallet configuration;
- recovery material;
- pytest or test helpers;
- live-test fixtures;
- local logs or `test.out`;
- build caches or virtual environments.

### Installation forms

GitHub core install:

```sh
pip install "safebox-acorn @ git+https://github.com/trbouma/safebox-acorn.git@<tag>"
```

GitHub install with experimental PQ support:

```sh
pip install "safebox-acorn[post-quantum] @ git+https://github.com/trbouma/safebox-acorn.git@<tag>"
```

PyPI core install:

```sh
pip install safebox-acorn
```

PyPI install with experimental PQ support:

```sh
pip install "safebox-acorn[post-quantum]"
```

Local package development:

```sh
poetry install
poetry install -E post-quantum
```

External editable development:

```sh
poetry add --editable -E post-quantum /path/to/safebox-acorn
```

### Publication controls

Recommended publication sequence:

1. merge through a reviewed pull request;
2. update the version and changelog;
3. create a clean release commit;
4. build artifacts in CI;
5. test the exact artifacts in fresh environments;
6. publish first to TestPyPI;
7. install from TestPyPI and repeat smoke tests;
8. create an annotated Git tag;
9. create a GitHub release with checksums and release notes;
10. publish to PyPI using trusted publishing;
11. verify installation from public PyPI;
12. retain the artifacts and test evidence.

Do not build the final PyPI artifact from an uncommitted local working tree.

## Gate 8: Documentation and operations

Before a developer preview:

- installation from GitHub;
- installation with and without post-quantum extras;
- minimal initialization;
- recovery-material handling;
- safe use of small test balances;
- known limitations;
- license and support location.

Before a pilot:

- FreeBSD jail installation;
- relay migration and replication;
- proof repair and stale-relay recovery;
- wallet burn and remaining-fund handling;
- backup and recovery drill;
- mint and relay trust boundaries;
- operator-hosted Safebox deployment;
- upgrade and rollback instructions;
- incident reporting and security contact.

Before a stable release:

- versioned Python API reference;
- versioned CLI contract;
- storage and protocol compatibility policy;
- deprecation policy;
- security model and threat assumptions;
- support window and release cadence.

An `acorn doctor` command would be useful for installed-package diagnostics. It
should report package version, optional features, configuration path and
permissions, effective relay and mint, and non-mutating connectivity checks. It
must not expose keys, mutate proofs, or spend sats.

## Gate 9: Pilot validation

The pilot is where user polish and operational assumptions become visible.

An important pre-pilot boundary milestone was demonstrated in August 2026
using the independently packaged
[Safebox Web application](https://github.com/trbouma/safebox-web). A funded
Acorn resolved an external NIP-05 recipient and sent a gift-wrapped ecash
transfer; the recipient attached its Acorn to Safebox Web, explicitly received
the transfer, and observed the accepted funds and credit transaction. Safebox
Web delegated relay, encryption, mint, proof, and journal operations to Acorn
rather than duplicating wallet logic or storing wallet state in its database.

This result is evidence that the package/application boundary is usable and
that CLI-to-web interoperability works for an external recipient. It does not
replace the remaining pilot work on interruption recovery, concurrency,
operational support, usability, or sustained testing.

At least one pilot should exercise:

- Acorn as a private component operated through Safebox;
- CLI and web-app recovery interoperability;
- a controlled relay and an independent relay;
- a controlled mint and an independent mint;
- relay migration after simulated failure;
- configuration backup and restoration;
- interrupted transfer and proof-operation recovery;
- multiple application processes without wallet-state leakage;
- operator support procedures.

Pilot findings should be classified:

- fund or key safety;
- data loss or recovery;
- protocol interoperability;
- operational reliability;
- usability;
- documentation;
- performance.

No unresolved fund-loss, key-exposure, or unrecoverable-data finding should
remain at stable release.

## Post-preview workstream: Lightning-address gateway

Lightning-address registration and inbound Lightning-to-ecash delivery are a
separate provider workstream, not a gate for the initial Acorn developer
preview. The Acorn package can be releasable before it operates or registers
with such a gateway.

The first Safebox Web implementation is now deployed and has completed a real
small-value payment through LNURL discovery, a durable provider-payment row,
service-Acorn mint settlement, and gift-wrapped ecash delivery. It runs one
Docker image as a web container and a singleton wallet-worker container. This
validates the principal architecture while leaving the reliability controls
below as pre-pilot work.

The target design lets an Acorn prove control of its component key, register
delivery relays and an accepted-mint policy, and receive settled Lightning as a
gift-wrapped kind `7378` ecash transfer. The provider supplies public
reachability and a temporary delivery bridge without receiving the Acorn
`nsec` or becoming the permanent store of wallet state.

Before this capability enters a Safebox pilot, complete:

- canonical registration request and response schemas;
- short-lived, single-use challenge verification with exact NIP-98 request and
  body binding;
- signed update, suspension, revocation, and old-key/new-key rotation flows;
- payment-hash idempotency and versioned registration selection;
- a durable encrypted bearer-token outbox and restart reconciliation;
- explicit gateway fees, mint policy, liquidity, and whole-satoshi behavior;
- bounded relay publication and readback without equating publication with
  recipient acceptance;
- duplicate-safe recipient processing and transaction history;
- unclaimed-payment, retry, refund, and manual-review procedures;
- deterministic failure injection at every settlement and delivery state; and
- small-value live tests using disposable recipients and suitable relays.

The public LNURL service, Lightning settlement infrastructure, provider
liquidity, registration directory, and refund operations belong to Safebox or
another gateway service. Acorn should supply the reusable signing, registration
client, transfer, receipt, and validation primitives. The same operator may run
both layers, but their trust and release boundaries remain distinct.

See [Acorn Lightning-Address Gateway Design](ACORN-LIGHTNING-ADDRESS-GATEWAY-DESIGN.md).

## Release automation

The repository should have CI jobs for:

- formatting and linting;
- static type checking;
- deterministic pytest suite;
- Python 3.11, 3.12, and 3.13;
- wheel and source-distribution build;
- package metadata validation;
- clean core-wheel installation;
- clean `[post-quantum]` installation;
- check that core import does not load `oqs`;
- artifact-content inspection;
- secret scanning;
- dependency and license review.

Live tests should run manually or on a protected scheduled workflow with
restricted secrets and spending limits. They should not run automatically for
untrusted pull requests.

## Release checklist

### Source

- [ ] Working tree is clean.
- [ ] Version is intentional and follows the release level.
- [ ] Changelog and release notes are complete.
- [ ] No secrets or generated test output are tracked.
- [ ] Documentation matches current CLI and Python behavior.

### Safety

- [ ] Transfer interruption has a recovery path.
- [ ] Proof mutation failure tests pass.
- [ ] Configuration permissions and atomic-write tests pass.
- [ ] Recovery drill succeeds from documented bootstrap material.
- [ ] Read-only commands are confirmed non-mutating.

### Tests

- [ ] Deterministic suite passes.
- [ ] Controlled live tests pass.
- [ ] At least one independent relay passes required capabilities.
- [ ] At least one independent mint passes required capabilities.
- [ ] FreeBSD jail smoke test passes.
- [ ] Safebox interoperability test passes.

### Artifacts

- [ ] `poetry check --lock` passes.
- [ ] Wheel and source distribution build successfully.
- [ ] Artifact contents contain no tests, secrets, logs, or configs.
- [ ] Core wheel installs without OQS.
- [ ] Post-quantum extra installs separately.
- [ ] Public imports and CLI smoke tests pass from the wheel.
- [ ] TestPyPI installation succeeds.

### Publication

- [ ] Git tag matches package version.
- [ ] GitHub release notes identify known limitations.
- [ ] PyPI publication uses CI and trusted publishing.
- [ ] Published checksums match tested artifacts.
- [ ] Public PyPI installation is verified.
- [ ] Support and security-reporting channels are active.

## Definition of releasable

Acorn is releasable as a developer preview when a fresh user can install the
core package, initialize a test wallet, use records and small-value ecash,
recover the wallet, and uninstall or burn it without relying on the Safebox
source tree.

Acorn is releasable for a pilot when interrupted value operations are
recoverable, local key material is protected, supported platforms install
repeatably, and Safebox can operate Acorn without violating the documented key,
code, data, relay, and mint boundaries.

Acorn is releasable as stable software when those properties are enforced by
automated tests and release gates, compatibility rules are explicit, and a
pilot has demonstrated that ordinary users can recover from infrastructure and
application failure without losing control of their funds or records.
