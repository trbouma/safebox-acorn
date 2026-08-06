# Safebox Acorn

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
- [Record Encryption Specification](./docs/RECORD-ENCRYPTION-SPEC.md)
- [Protected Record Profile Design](./docs/PROTECTED-RECORD-PROFILE-DESIGN.md)
- [Recovery Specification](./docs/RECOVERY-SPEC.md)
- [Relay Configuration Specification](./docs/RELAY-CONFIGURATION-SPEC.md)
- [Mint Configuration Specification](./docs/MINT-CONFIGURATION-SPEC.md)
- [CLI Contract](./docs/CLI-CONTRACT.md)
- [Safebox App Boundary](./docs/SAFEBOX-APP-BOUNDARY.md)
- [Stateless Web Integration](./docs/STATELESS-WEB-INTEGRATION.md)
- [Ecash Transfer Kind 7378 Design Note](./docs/ECASH-TRANSFER-KIND-7378-DESIGN.md)
- [Acorn Lightning-Address Gateway Design](./docs/ACORN-LIGHTNING-ADDRESS-GATEWAY-DESIGN.md)
- [Acorn CLI and Safebox Web App Interoperability](./docs/ACORN-WEBAPP-INTEROPERABILITY.md)
- [Relay Migration Runbook](./docs/RELAY-MIGRATION-RUNBOOK.md)
- [Relay Suitability Ledger](./docs/RELAY-SUITABILITY-LEDGER.md)
- [Proof State and Relay Consistency](./docs/PROOF-STATE-RELAY-CONSISTENCY.md)
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
pip install "safebox-acorn @ git+https://github.com/trbouma/safebox-acorn.git"
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
pip install "safebox-acorn[post-quantum] @ git+https://github.com/trbouma/safebox-acorn.git"
```

For local development:

```sh
poetry install -E post-quantum
```

This extra enables the experimental `acorn.post_quantum.PQEvent` implementation.
It is not used by ordinary wallet, record, relay, mint, or ecash operations.

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
funds that wallet with `ACORN_TEST_AMOUNT`, issues a `cashuB` token from the
disposable wallet, accepts the token back into the same wallet, verifies that
the pre-issue balance is restored after relay readback, and checks for matching
debit and credit transaction-history entries. It then refreshes every proof
with `swap_multi_each`, runs a read-only mint-state check, repairs the refreshed
proof set with `repair_proofs`, and confirms after each operation that the mint
reports every sat as unspent and the relay-backed balance is unchanged. Cleanup
burns the wallet and attempts to sweep its funds back to the source wallet.

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
# ACORN_NIP05_TEST_AMOUNT=1
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
