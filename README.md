# Safebox Acorn

Read the [CLI manual](website/cli/index.md), the
[Acorn lifecycle guide](website/cli/lifecycle.md), and the
[complete command reference](website/cli/commands.md). These are published under
**Use Acorn → CLI Manual** in the documentation site.

Acorn is a protocol-first component for safeguarding user-controlled keys,
funds and records.

Safebox Acorn is the standalone Acorn component extracted from Safebox. It
provides:

- the `Acorn` Python runtime class
- the `acorn` command-line interface
- supporting key, Nostr profile, Cashu, Lightning, record, and crypto helpers used
  by Acorn

This package is intended to make Acorn installable into other Python projects
without requiring the Safebox web application.

## Current Clear transfer milestone

Acorn now receives NIP-59 kind `1059` gift wraps containing inner kind `7379`
Clear transfers, validates them, and stores them in a pending journal separate
from ordinary cash/ecash. It groups Clear state by exact mint and CMU, exposes
kind `7380` spendable proof state and kind `7381` append-only history, and
supports durable acceptance or deletion of pending transfers without relay
rediscovery.

In this model, a **transferable unit** is the broad category for a fungible unit
that can move between holders under issuer policy. A CMU is Clear's exact,
keyset-bound transferable unit; Acorn keeps each one in its own balance domain.

Safebox Web uses this path to show organization-issued Clear Balances beside,
but never inside, the sat-denominated Cash Balance. A user can accept a pending
transfer in Safebox Web or with `acorn clear accept <event-id>`, then inspect it
with `acorn clear balances` and `acorn clear history`. Onward Clear spending and
the stronger pre-swap crash-recovery journal remain under development.

[Read the Clear Transfer Wallet Milestone](./docs/CLEAR-TRANSFER-WALLET-MILESTONE-2026-08-17.md).

Record listings request up to 1,024 relay events by default. This is a
configurable query boundary, not a hardcoded wallet ceiling. Set
`ACORN_RECORD_LIMIT` for a deployment-wide default, pass `record_limit=` when
constructing an `Acorn`, or pass `limit=` to `get_user_records()` and
`get_user_record_labels()` for one query:

```python
acorn = Acorn(nsec=nsec, home_relay=relay, record_limit=4096)
recent_records = await acorn.get_user_records(limit=256, reverse=True)
```

The limit applies to relay events, including record revisions. A response that
reaches the configured limit may therefore be incomplete; record listing is
not currently paginated.

Exact record reads use the author, kind, and hashed `d` tag and are bounded
separately by `ACORN_RECORD_EXACT_LOOKUP_LIMIT` (default `16`). Record reads,
writes, existence checks, and catalog access do not require `load_data()` and
therefore do not load Cash or Clear proofs. The encrypted record event is
authoritative; the relay-backed record catalog is a rebuildable display index.
User-record publication uses a bounded verification budget controlled by
`ACORN_RECORD_PUBLISH_VERIFY_TIMEOUT_SECONDS` (default `15`) and bounds each
relay attempt with `ACORN_RECORD_QUERY_ATTEMPT_TIMEOUT_SECONDS` (default `5`).
The first successful record write makes a best-effort catalog build, so new
wallets become navigable without making catalog availability part of the
authoritative write outcome.

Acorn also owns the initial record-protection key primitives. Applications can
request a fresh key from the operating-system cryptographic random source or
derive one deterministically from separate, externally generated 256-bit
entropy:

```python
from acorn import (
    generate_record_protection_key,
    record_protection_key_from_entropy,
    record_protection_key_from_recovery_phrase,
    record_protection_recovery_phrase,
)

rpk = generate_record_protection_key()
external_rpk = record_protection_key_from_entropy("00" * 32)
recovery_phrase = record_protection_recovery_phrase(rpk)
recovered_rpk = record_protection_key_from_recovery_phrase(recovery_phrase)
```

The **Protected record mnemonic** is a checksummed 24-word encoding of the
exact RPK. It is separate from the **Safebox Acorn mnemonic** and never enters
the wallet's SLIP-10 derivation path. Protected-record encryption remains under design;
applications must not make records dependent on an RPK until that profile is
implemented and reviewed.

## Policy and rationale

- [Beyond Digital Identity, Credentials and Wallets: A policy vocabulary for
  user-controlled keys, funds and records](./docs/POLICY-BRIEF-KEYS-FUNDS-RECORDS.md)

## Specifications

- [Acorn Product North Star](./docs/ACORN-PRODUCT-NORTH-STAR.md)
- [Acorn Component Boundary](./docs/ACORN-COMPONENT-BOUNDARY.md)
- [Acorn Record Model](./docs/ACORN-RECORD-MODEL.md)
- [Uniform Resource Model Design Note](./docs/UNIFORM-RESOURCE-MODEL-DESIGN-NOTE.md)
- [Bitcoin Silent Payments Capability](./docs/BITCOIN-SILENT-PAYMENTS-SPEC.md)
- [Record Encryption Specification](./docs/RECORD-ENCRYPTION-SPEC.md)
- [Acorn Record Transfer Specification](./docs/RECORD-TRANSFER-SPEC.md)
- [Record Sharing Lessons Learned](./docs/RECORD-SHARING-LESSONS-LEARNED.md)
- [Protected Record Profile Design](./docs/PROTECTED-RECORD-PROFILE-DESIGN.md)
- [Recovery Specification](./docs/RECOVERY-SPEC.md)
- [Relay Configuration Specification](./docs/RELAY-CONFIGURATION-SPEC.md)
- [Transfer Resilience: Identity, Routing, and Payment State](./docs/TRANSFER-RESILIENCE.md)
- [Synthetic Minds: Research and Prototyping Proposal](./docs/SYNTHETIC-MINDS-RESEARCH-DESIGN-NOTE.md)
- [Synthetic Minds Experiment 01: Bounded Economic Agency](./docs/SYNTHETIC-MINDS-EXPERIMENT-01.md)
- [Mint Configuration Specification](./docs/MINT-CONFIGURATION-SPEC.md)
- [Service Identity and Endpoint Records](./docs/SERVICE-IDENTITY-AND-ENDPOINT-RECORDS.md)
- [CLI Contract](./docs/CLI-CONTRACT.md)
- [Safebox App Boundary](./docs/SAFEBOX-APP-BOUNDARY.md)
- [Stateless Web Integration](./docs/STATELESS-WEB-INTEGRATION.md)
- [Ecash Transfer Kind 7378 Design Note](./docs/ECASH-TRANSFER-KIND-7378-DESIGN.md)
- [Clear Transfer Kind 7379 Design Note](./docs/CLEAR-TRANSFER-KIND-7379-DESIGN.md)
- [Clear Spendable Proof State Kinds 7380 and 7381](./docs/CLEAR-SPENDABLE-PROOF-STATE-KINDS-7380-7381-DESIGN.md)
- [Clear Transfer Wallet Milestone](./docs/CLEAR-TRANSFER-WALLET-MILESTONE-2026-08-17.md)
- [Acorn Lightning-Address Gateway Design](./docs/ACORN-LIGHTNING-ADDRESS-GATEWAY-DESIGN.md)
- [Cashu Multipath Payments Design](./docs/CASHU-MULTIPATH-PAYMENTS-DESIGN.md)
- [Acorn CLI and Safebox Web App Interoperability](./docs/ACORN-WEBAPP-INTEROPERABILITY.md)
- [Mainstay Product Vision](./docs/MAINSTAY-PRODUCT-VISION.md)
- [Mainstay and Lockbox Product Vision](./docs/LOCKBOX-PRODUCT-VISION.md)
- [Lockbox Local Integration Milestone](./docs/LOCKBOX-LOCAL-INTEGRATION-MILESTONE-2026-08-11.md)
- [Lockbox External Dependencies and Offline Transfer](./docs/LOCKBOX-EXTERNAL-DEPENDENCIES-AND-OFFLINE-TRANSFER.md)
- [Relay Migration Runbook](./docs/RELAY-MIGRATION-RUNBOOK.md)
- [Relay Suitability Ledger](./docs/RELAY-SUITABILITY-LEDGER.md)
- [Proof State and Relay Consistency](./docs/PROOF-STATE-RELAY-CONSISTENCY.md)
- [Interrupted Swap Recovery Milestone](./docs/INTERRUPTED-SWAP-RECOVERY-MILESTONE-2026-08-25.md)
- [Relay Migration and Incoming Funds Design Correction](./docs/RELAY-MIGRATION-AND-INCOMING-FUNDS-DESIGN-CORRECTION-2026-09.md)
- [Stroma Runtime Migration Milestone](./docs/STROMA-RUNTIME-MIGRATION-MILESTONE-2026-09.md)
- [Relay Resilience and Replication Design](./docs/RELAY-RESILIENCE-AND-REPLICATION-DESIGN.md)
- [Roadmap to Releasability](./docs/ROADMAP-TO-RELEASABILITY.md)
- [FreeBSD Jail Installation](./docs/FREEBSD-JAIL-INSTALL.md)

## Documentation website

The public website is deliberately separate from the detailed reference
material:

- `docs/` contains specifications, design notes, runbooks, and project records;
- `website/` contains only material deliberately selected for publication;
- MkDocs publishes `website/` and does not automatically include `docs/`;
- `site/` is generated output and is not committed.

Install the separate documentation toolchain and preview the site locally:

```sh
poetry install --with docs
poetry run mkdocs serve
```

Validate the production build before committing:

```sh
poetry run mkdocs build --strict
```

The GitHub Pages workflow publishes committed website changes from `main`.
Repository Pages settings must use **GitHub Actions** as the source.

## Install from this repository

From another project:

```sh
pip install "safebox-acorn @ git+https://github.com/trbouma/safebox-acorn.git@<tag-or-commit>"
```

For local development:

```sh
cd safebox-acorn
poetry install
poetry run acorn --help
```

The ordinary installation does not require Open Quantum Safe. Experimental
post-quantum event support can be installed explicitly:

```sh
pip install "safebox-acorn[post-quantum] @ git+https://github.com/trbouma/safebox-acorn.git@<tag-or-commit>"
```

For local development:

```sh
poetry install -E post-quantum
```

This extra enables the experimental `acorn.post_quantum.PQEvent` implementation.
It is not used by ordinary wallet, record, relay, mint, or ecash operations.
It does not enable a KEM or change Acorn's ordinary record and blob formats.
KEM experiments are currently an application-layer concern for Safebox Web,
not a dependency or protocol commitment of Acorn.

Acorn owns its Nostr Silent Payments Bitcoin primitives directly. Install the
optional Bitcoin transaction dependency for address derivation, txid-targeted
receipt detection, sweep preview, and explicit broadcast:

```sh
pip install "safebox-acorn[bitcoin]"
```

For local development:

```sh
poetry install -E bitcoin
```

To install both optional capability profiles:

```sh
poetry install -E post-quantum -E bitcoin
```

## Updating Acorn in an application

Acorn is an embedded component, not an independently deployed service. Pin a
tested tag or commit in the consuming application's dependency declaration and
lock file. To update it, change that pin, regenerate the lock, run Acorn's test
suite, and run the consuming application's integration tests before deploying
the application. Acorn does not have a separate service identity, container
lifecycle, or refresh command.

The Bitcoin implementation has no runtime dependency on OpenETR. OpenETR was
the experimental origin of the NSP derivation, but Acorn is now the canonical
implementation owner for user-controlled receipt detection and spending.

## Smoke test

After installing into a fresh virtual environment:

```sh
python -c "from acorn import Acorn; print(Acorn)"
acorn --help
```

Expected result:

- Python prints the `acorn.acorn.Acorn` class.
- The `acorn` command lists the available CLI commands.

An ordinary installation should not import `oqs` or emit Open Quantum Safe
version warnings. When the optional post-quantum extra is installed, its Python
wrapper and native `liboqs` library still need to be a compatible pair.

## Testing

Acorn uses pytest for repeatable tests. Test dependencies are dev-only and are
not required by the installable runtime component.

Run the default test suite:

```sh
poetry install --with dev
poetry run pytest
```

Live relay/mint tests are skipped by default. To run them, copy the template
and provide local secrets:

```sh
cp .env.example .env
```

### Paced first-time-user suitability test

The [suitability matrix](docs/RELAY-SUITABILITY-LEDGER.md) distinguishes
**implementation suitability** (protocol/lifecycle support, preferably tested
on deployments under the tester's control) from **user suitability** (a paced
workflow on the actual service under normal user policies). Service certification
as tested requires recorded passes of both assessments for the applicable
deployment/configuration; neither test alone certifies a service.

This separate, explicitly enabled test creates a fresh wallet, receives an ecash
payment, sends a payment back to the funding wallet, then creates, edits and
deletes a private record. It verifies finalized balances (allowing for mint fees),
record contents after both writes, and removal from the record listing.

```sh
ACORN_SOURCE_CONFIG="$HOME/.acorn/test-source-new.yml" \
ACORN_TEST_WALLET_CONFIG="./.acorn-test/user-wallet.yml" \
ACORN_THIRD_PARTY_RELAY=wss://nos.lol \
ACORN_RELAY_SCENARIO=third-party \
ACORN_RUN_USER_JOURNEY=1 \
poetry run pytest -m live -rs -s tests/integration/test_user_journey_live.py
```

Use `wss://spurline.safebox.dev` or `wss://relay.getsafebox.app` to test your
own implementations. Run only this file, not the entire live suite, for an
isolated user-paced measurement. Do not use the funding wallet concurrently.

Defaults are 30 seconds before each user action and 5 seconds before each
verification read: about 4 minutes 40 seconds of deliberate waiting, plus
network time. Adjust `ACORN_USER_ACTION_PAUSE` (minimum 5 seconds),
`ACORN_USER_READ_PAUSE` (minimum 1 second), and `ACORN_USER_STEP_TIMEOUT`
(default 120 seconds per operation). These are simulated reading/typing delays,
not empirically measured usage. Internal Acorn operations retain their normal
network behavior; pacing reduces bursts but cannot guarantee avoidance of a
relay's rate limits. It does not bypass relay policies.

The funded source needs more than 32 sats and enough additional spendable funds
for mint fees. `ACORN_USER_RECEIVE_AMOUNT` defaults to 32 sats;
`ACORN_USER_SEND_AMOUNT` defaults to 8 sats, leaving fee headroom. Higher-fee
mints may require larger amounts. This tests gift-wrapped ecash, not Lightning.
Transfers explicitly use the relay under test, independently of
`ACORN_TEST_TRANSFER_RELAY`. Bootstrap uses the source home mint unless
`ACORN_TEST_MINT` overrides it.

A unique `-user-journey-<id>` suffix is added to the test configuration filename.
The private key is saved before bootstrap, and the wallet/configuration is
**retained on success and failure**, including remaining funds and recovery
state. The printed path can be used with `ACORN_CONFIG` to inspect it. Never
share that file. There is no automatic burn, funded retry, or cleanup after a
timeout/rate limit. Inspect unfinished transfers before starting another run;
each run creates a new wallet and spends real mint fees. A pending receipt or
unverified readback is not a pass. A pass establishes this journey only, not all
relay capabilities or permanent deletion guarantees under NIP-09.

### Full live suite

For implementation suitability alone, exclude the separately opted-in user journey:

```sh
poetry run pytest -m live -rs -s --ignore=tests/integration/test_user_journey_live.py
```

Then edit `.env` and run:

```sh
poetry run pytest -m live
```

To see live progress messages while relay and mint operations are running, add
`-s`:

```sh
poetry run pytest -m live -rs -s
```

The external-entropy live test can be run independently and does not require or
spend sats:

```sh
ACORN_RELAY_SCENARIO=controlled poetry run pytest \
  tests/integration/test_entropy_recovery_live.py \
  -m live -rs -s
```

It creates a uniquely named temporary wallet config, initializes an unfunded
wallet from fresh 256-bit entropy, reads it back, reconstructs the same keypair
from its 24-word phrase, burns its relay-backed data, and removes the config.
NIP-09 deletion is advisory, so a successful burn confirms publication of the
deletion request rather than guaranteed physical erasure by the relay.

Live tests use the default Acorn profile, normally `~/.acorn/config.yml`, as
the source wallet. This source wallet should already be initialized and should
have a small spendable balance when running ecash transfer tests.

The source wallet is the funding and recovery anchor for live testing. Most
mutation-heavy tests should run against disposable wallets so the source wallet
stays understandable and easy to inspect in the Safebox web app.

Disposable test wallets use an explicit config file, configured by
`ACORN_TEST_WALLET_CONFIG`. By default, live tests create this wallet if it is
missing and burn/remove it after the test. Unless `ACORN_TEST_MINT` is set
explicitly, disposable wallets inherit the mint from the loaded source wallet:

```env
ACORN_TEST_WALLET_CONFIG=./.acorn-test/test-wallet.yml
ACORN_TEST_CREATE_WALLET=true
ACORN_TEST_BURN_AFTER=true
```

You can also create it manually:

```sh
acorn --config ./.acorn-test/test-wallet.yml init \
  --homerelay "${ACORN_TEST_RELAY:-ws://beelink:7777}" \
  --force
```

If the config file does not exist, `init` creates the parent directory and YAML
config file.

Set `ACORN_TEST_RELAY` to point disposable test-wallet operations at a local
relay, for example:

```env
ACORN_TEST_RELAY=ws://beelink:7777
```

To run the same live tests against a third-party relay, set
`ACORN_THIRD_PARTY_RELAY`. The controlled relay scenario still runs, and pytest
adds a second scenario using a separate disposable wallet config suffix:

```env
ACORN_THIRD_PARTY_RELAY=wss://relay.example.com
```

To run only one relay scenario, set `ACORN_RELAY_SCENARIO`:

```sh
ACORN_RELAY_SCENARIO=third-party poetry run pytest -m live -rs -s
```

Supported values are:

```text
all
controlled
third-party
```

For example, the default disposable wallet config:

```text
./.acorn-test/test-wallet.yml
```

is paired with:

```text
./.acorn-test/test-wallet-third-party.yml
```

This lets you confirm Acorn works against relays you control while also testing
whether an external relay behaves well enough for Acorn's record, ecash, and
burn lifecycle. Observed compatibility results are tracked in the
[Relay Suitability Ledger](./docs/RELAY-SUITABILITY-LEDGER.md).

Ecash transfer tests publish transfer events to `ACORN_TEST_TRANSFER_RELAY` if
set, otherwise to `ACORN_TEST_RELAY`, otherwise to the test wallet's
`home_relay`. Leave `ACORN_TEST_TRANSFER_RELAY` unset when you want the
third-party relay scenario to publish transfer events to
`ACORN_THIRD_PARTY_RELAY` as well.

Testing lanes:

- Source wallet: funds the suite, receives sweep-backs, and runs the minimal
  source-wallet ecash self-transfer used for web-app interoperability. It is
  also used to fund opt-in sends to external NIP-05 wallets and Lightning
  addresses because those prove interoperability with independently operated
  recipients and real payment behavior.
- Disposable wallet: receives most test mutations, including record lifecycle
  and burn-wallet flows. It also exercises a complete local Cashu token
  round-trip: receive funding, issue a token, accept that same token, verify
  balance and transaction history, and sweep the remaining funds back.
- Separate opt-in tests: NIP-05 recipient resolution and real
  lightning-address payments.

The burn live test creates a separate disposable burn wallet config next to the
main test wallet, funds it from the source wallet, burns it, and verifies that
remaining funds are swept back.

The token round-trip live test creates another separate disposable wallet. It
funds that wallet with `ACORN_TEST_AMOUNT` (default 10 sats), issues a `cashuB`
token using at most half its funded balance to leave fee headroom, accepts the
token back into the same wallet, verifies that
the balance is restored less mint fees after relay readback, and checks for matching
debit and credit transaction-history entries. It then refreshes every proof
with `swap_multi_each`, runs a read-only mint-state check, repairs the refreshed
proof set with `repair_proofs`, and confirms after each operation that the mint
reports every sat as unspent and the relay-backed balance is unchanged. Cleanup
burns the wallet and attempts to sweep its funds back to the source wallet.
The legacy per-proof swap/repair portion is explicitly skipped on mints charging
input fees because those methods request equal-value outputs. The completed
token round-trip is still reported in the relay capability summary; a skipped
maintenance check is not a suitability pass. Ten sats provides headroom for
ordinary small input fees, not a guarantee for every mint's fee schedule.
If your existing `.env` sets `ACORN_TEST_AMOUNT=1`, change it to `10` or override
it on the command line. Fund the disposable source wallet with extra fee headroom.

Ecash burn sweeps reserve the mint input fee and require a single keyset. Wallet
deletion stops if the sweep fails, readback is uncertain, or value remains.
Incomplete burn tests retain their wallet records and local configuration for
recovery. Token cleanup retains configuration on an unconfirmed sweep; Grove
cleanup refuses to burn a wallet with funds or pending receipts. Review retained
test wallets before rerunning; do not use a production account as a disposable wallet.

The live test flow can also be used as a manual interoperability check with the
Safebox web app: create or recover the same source wallet in the web app and
verify that deposits, ecash transfers, burn sweeps, balances, and transaction
history are visible from both surfaces. See
[Acorn CLI and Safebox Web App Interoperability](./docs/ACORN-WEBAPP-INTEROPERABILITY.md).

The default source-wallet ecash transfer test is intentionally narrow. It exists
to prove web-app interoperability: the source wallet funds the transfer, sends
to its own npub through the active relay scenario, receives the gift-wrapped
transfer, refreshes proofs, and writes web-app-visible transaction history back
to the same source wallet. Broader mutation-heavy behavior should remain on
disposable wallets.

Recommended default for source-wallet/web-app interoperability testing:

```env
ACORN_SOURCE_CONFIG=~/.acorn/config.yml
# ACORN_TEST_MINT=
```

Before a live run, check for ambient shell overrides that may not be visible in
`.env`:

```sh
env | grep '^ACORN_'
```

The most common testing mistake is leaving old `ACORN_*` variables exported
from an older wallet. In the default flow, the source wallet should provide
funding and stay recoverable/inspectable, while disposable wallets carry most
test churn.

NIP-05 recipient resolution and lightning-address payments are separate opt-in
tests:

```env
# External NIP-05 ecash transfer test. This spends source-wallet sats and
# requires separate confirmation in the recipient wallet.
# ACORN_NIP05_RECIPIENT=someone@example.com
# ACORN_NIP05_TEST_AMOUNT=10
# ACORN_NIP05_TEST_COMMENT=pytest nip05 ecash transfer

# Real lightning-address payment test. This spends source-wallet sats and runs
# when set.
# ACORN_LIGHTNING_ADDRESS=someone@example.com
# ACORN_LIGHTNING_TEST_AMOUNT=1
```

The real `.env` file is gitignored. Do not commit real `nsec` values.

### Initialize from external entropy

For an Acorn-generated wallet, initialization uses a 12-word BIP39 offline
mnemonic by default. Select a 24-word mnemonic explicitly when desired:

```sh
acorn init --words 24
```

Both valid 12-word and 24-word Acorn mnemonics are accepted by `acorn recover`.
The word-count option applies only to newly generated keys; it cannot be
combined with imported keys, `--keepkey`, or `--entropy`.

Acorn can derive a recoverable wallet from 256 bits generated by an external
CSPRNG or hardware device:

```sh
acorn init --entropy
```

Enter the 64-character hexadecimal value twice at the hidden prompt. Acorn
encodes it as a 24-word BIP39 phrase and derives the wallet `nsec`; it does not
hash the input again. Do not use the hash of a password or other guessable
text. `--entropy` cannot be combined with `--import-nsec`, `--nsec-file`, or
`--keepkey`.

Recovery secrets are never accepted as command-line values or test environment
variables. Use hidden prompts for interactive work, or an owner-only file/stdin
for controlled automation. See [Secret Input Specification](docs/SECRET-INPUT-SPEC.md).

See [External Entropy Initialization](docs/EXTERNAL-ENTROPY-INITIALIZATION.md)
for the derivation contract, public compatibility vector, recovery behavior,
and operational-security guidance.

## Config files

By default, Acorn stores local bootstrap configuration in:

```text
~/.acorn/config.yml
```

For disposable wallets, tests, or project-specific environments, pass an
explicit config file:

```sh
acorn --config ./test-wallet.yml balance
```

You can also set `ACORN_CONFIG=/path/to/config.yml`.

## Wallet burn lifecycle

For disposable test wallets, Acorn can create, fund, exercise, and burn a wallet.
Burning publishes NIP-09 deletion requests for the wallet's relay-backed data
and removes the local wallet config by default.

```sh
acorn burn --send-to alice@example.com
```

If the wallet has funds, choose one of the explicit fund handling modes before
deletion:

```sh
# Sweep remaining funds as Acorn/Nostr ecash to a NIP-05, npub, or pubkey.
acorn burn --send-to alice@example.com

# Pay a Lightning address before burning.
acorn burn --pay-to alice@example.com --pay-amount 21

# Sweep the maximum payable amount to a Lightning address.
acorn burn --pay-to alice@example.com
```

`--send-to` is an Acorn ecash transfer rail. `--pay-to` is a Lightning address
payment rail. Do not use both in the same burn command.

If `--pay-amount` is omitted, Acorn quotes the Lightning invoice and mint melt
fee reserve first, then automatically reduces the payment amount so the payment
amount plus fees fit the wallet's spendable proofs. If `--pay-amount` is
provided, Acorn treats it as an exact requested payment amount and may fail if
that amount plus fees cannot be paid from the wallet.

Use `--allow-funded` only when you intentionally want to burn relay data while
leaving funds unswept/unpaid. Use `--keep-local-config` for dry-run-like
development flows where you want relay deletion without removing the local
config file.

NIP-09 deletion is advisory: relays and clients ultimately decide whether
matching events are hidden, retained, or garbage-collected.

## Record output

Normal record reads are formatted for humans:

```sh
acorn get "Field Notes"
```

Example output:

```text
Record: Field Notes
Kind: 37375
Type: generic

Apr 30: Moving
Apr 25: Dog Walk
```

Use raw output when debugging the underlying record object:

```sh
acorn get "Field Notes" --raw
```

Use JSON output when calling Acorn from another program:

```sh
acorn get "Field Notes" --json
acorn get_user_records --labels --json
acorn balance --json
acorn balance --verify
acorn info --json
```

Use verbose mode when debugging relay, wallet, or payment behavior:

```sh
acorn --verbose get "Field Notes"
```

## Public relay preference

Acorn keeps the local CLI config intentionally small. The local
`~/.acorn/config.yml` only needs the private key and home relay:

```yaml
nsec: nsec...
home_relay: wss://relay.getsafebox.app
```

For commands that need broader public-event discovery, such as zaps, store a
preferred public relay list as an encrypted reserved record:

```sh
acorn set --public-relays relay.damus.io,relay.primal.net,nos.lol
```

Then `acorn zap` uses those relays when `--relays/-r` is not supplied:

```sh
acorn zap 21 <event-id> -c "from acorn"
```

You can still override per command:

```sh
acorn zap 21 <event-id> -c "from acorn" -r relay.damus.io,nos.lol
```

To inspect the optional OQS provider after installing the `post-quantum` extra:

```sh
python -c "import oqs; print(oqs.oqs_version())"
```

## Python usage

```python
from acorn import Acorn

wallet = Acorn(nsec="nsec...", home_relay="wss://relay.getsafebox.app")
```

## Notes

This is the first standalone packaging boundary. Safebox still contains its
current in-tree Acorn implementation while this component package is stabilized.
## Copy private records to a new Acorn

Use the configured account as the source and an **already initialized** Acorn
as the destination:

```bash
acorn records copy --destination-relay wss://relay.example.com --dry-run
acorn records copy --destination-relay wss://relay.example.com \
  --destination-blossom https://blossom.example.com
```

The hidden prompt accepts an nsec, a hexadecimal private key, or a BIP39 recovery
phrase. Phrase derivation matches `acorn recover`; use `--legacy` only for a
wallet created with that legacy derivation. No additional BIP39 passphrase is
supported by this flow. Secrets are not command-line options or saved to config.

Before offering to write, the command verifies the destination's signed kind
37375 `wallet` record (used by Safebox Web and normal wallet loading), or the
older CLI's `wallet_config` record when `wallet` is absent, and decrypts it using
the supplied key. Malformed existing `wallet` data is not bypassed by falling
back to another record. It displays
both public identities and relays for confirmation. An unreachable relay,
missing/unreadable destination configuration, or same-identity copy stops the
operation. It does not call `load_data`, inspect funds, or reconcile payments.

Only labeled user records in kind 37375 are copied. Configuration, operational
state, locks, payment recovery records, proofs, public profiles, and other event
kinds are excluded. Unknown/unreadable legacy records are reported as skipped.
Issuer-signed payloads and extra record metadata are preserved, not reissued;
copying does not change a credential's holder or transfer identity authority.

Records are re-encrypted and signed for the destination, with newly derived
private lookup tags, then read back and decrypted for comparison. Conflicts are
skipped; matching records are reported as already present, making retries safe.
The source is never deleted or updated. Pause other destination writers during
copying: relay publication has no atomic compare-and-swap guarantee.

With `--destination-blossom`, attachments are downloaded, decrypted, and verified
before being encrypted with a fresh random AES-256-GCM key and nonce. Plaintext
stays in memory; it is not uploaded or written to a temporary file. The original
plaintext digest is preserved, while the ciphertext digest, file key, and location
change. The uploaded copy is downloaded, decrypted, and compared before the new
record is published. Unencrypted source attachments become encrypted too.
Encrypted sources without a valid plaintext digest or supported encryption
parameters fail safely. Signed payloads are preserved verbatim; embedded references
to old ciphertext digests are not rewritten. Re-encryption cannot revoke access
to old copies. Previously copied records with old file keys remain conflicts and
are not overwritten automatically. Repeat runs recognize fresh-key copies by
comparing record metadata and verified plaintext at both ends. Without
this option, records with attachments are skipped, not copied as broken links.
An interrupted write may leave an uploaded attachment or an unverified record;
inspect the report and rerun the preview. The destination catalog is rebuilt
after successful copies. This is a copy/migration tool, not a standalone archive
export, a funds transfer, or proof that a relay returned every record: queries
are bounded to 10,000 events and fail on saturation, but relay-side omission
cannot be ruled out. Review all skipped/failed entries before retiring a source.

Copy results are printed as each record completes. Failures include a stage
and the source hostname when downloading files. For missing or outdated source
locations, repeat `--source-blossom` to supply preferred candidates:

```bash
acorn records copy --destination-relay wss://spurline.safebox.dev \
  --source-blossom https://grove.safebox.dev \
  --source-blossom https://blossom.getsafebox.app \
  --destination-blossom https://grove.safebox.dev
```

Record copying uses Stroma's `BlossomPool`: explicit source servers are raced
first, then stored/discovered locations if necessary. Only digest-verified bytes
are accepted. Acorn additionally verifies decrypted content before publishing
the destination record. Servers must be public HTTPS origins (no URL paths),
with a 25 MiB encrypted-file limit. For trusted private-network HTTPS servers,
opt in with `--allow-private-blossom`; this does not enable plain HTTP.

Explicit sources are tried first, then discovered/stored sources if needed.
Duplicate URLs are tried once per retrieval; a failed download or wrong digest
falls through to the next source. Only ciphertext matching the record's digest
is decrypted. These options do not change saved configuration, copy files to
source servers, or delete source files. Source and destination may use the same
server; re-encryption still creates a fresh ciphertext object.

Failures include a stage
(source resolution/download/decryption, destination encryption/upload/readback,
or record publication/readback) and a sanitized reason. HTTP status codes are
reported without server response bodies, authorization headers, file keys, or
private exception messages. Missing `origsha256` is reported explicitly; this
does not bypass integrity verification. A failure after upload or record
publication can still leave partial destination data. Rerun the preview before
retrying and share only the stage/reason lines when requesting support.


## Restart-safe incoming payment writes

Hosts that maintain a durable payment journal can ask Acorn to prepare a write,
persist the opaque result, and deliver that same result after a restart. Acorn
owns encryption, signing, payload validation, publication and verification.

- `await acorn.add_proofs_obj(proofs, prepare_only=True)` returns prepared events.
  Set `known_mints` for the proof keysets first. Deliver with
  `await acorn.add_proofs_obj(proofs, prepared_events=saved_events)`.
- `await acorn.add_tx_history(..., prepare_only=True)` returns a prepared history
  event. Deliver with the same transaction arguments and `prepared_event=saved`.
  Use `created_at=paid_at` for the original payment time and
  `use_wallet_balance=False` when an accurate historical balance is unavailable.
- `await acorn.add_zap_receipt(request_json, invoice, paid_at, prepare_only=True)`
  returns a signed receipt. Deliver separately to each public relay using those
  same arguments, `relay=url` and `prepared_event=saved`.

Persist before delivery, and record verified completion afterward. Prepared
writes reuse their event IDs, including after an acknowledgment is lost. Acorn
rejects foreign, invalidly signed or mismatched prepared events. Prepared proof
batches must fit one event and use one mint; prepared private writes target the
home relay and verify readback. Receipt writes require acknowledgment and use
public secure relay destinations with DNS-address and redirect checks. Only call
receipt creation after payment and proof delivery have been confirmed.

Existing callers that omit the prepared-write arguments retain their current
behavior. Preparing is not publishing, and publishing a history entry is not a
payment operation. Do not repeat mint issuance when delivery needs retrying.


Custodial hosts should also use `Acorn.generate_recovery_material()`,
`Acorn.recover_material(phrase, legacy=False)`, and `acorn.public_identity()`
instead of performing user-key generation, recovery or public-key derivation
outside Acorn. The first two return custody material for protected storage;
`public_identity()` returns only the public hex and npub representations.
