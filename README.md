# Safebox Acorn

Acorn is a protocol-first component for user-controlled funds and records.

Safebox Acorn is the standalone Acorn component extracted from Safebox. It
provides:

- the `Acorn` Python runtime class
- the `acorn` command-line interface
- supporting Nostr, Cashu, Lightning, record, and crypto helpers used by Acorn

This package is intended to make Acorn installable into other Python projects
without requiring the Safebox web application.

## Specifications

- [Acorn Product North Star](./docs/ACORN-PRODUCT-NORTH-STAR.md)
- [Acorn Component Boundary](./docs/ACORN-COMPONENT-BOUNDARY.md)
- [Acorn Record Model](./docs/ACORN-RECORD-MODEL.md)
- [Record Encryption Specification](./docs/RECORD-ENCRYPTION-SPEC.md)
- [Recovery Specification](./docs/RECOVERY-SPEC.md)
- [Relay Configuration Specification](./docs/RELAY-CONFIGURATION-SPEC.md)
- [Mint Configuration Specification](./docs/MINT-CONFIGURATION-SPEC.md)
- [CLI Contract](./docs/CLI-CONTRACT.md)
- [Safebox App Boundary](./docs/SAFEBOX-APP-BOUNDARY.md)
- [Ecash Transfer Kind 7378 Design Note](./docs/ECASH-TRANSFER-KIND-7378-DESIGN.md)
- [Acorn CLI and Safebox Web App Interoperability](./docs/ACORN-WEBAPP-INTEROPERABILITY.md)
- [Relay Migration Runbook](./docs/RELAY-MIGRATION-RUNBOOK.md)
- [Relay Suitability Ledger](./docs/RELAY-SUITABILITY-LEDGER.md)
- [Proof State and Relay Consistency](./docs/PROOF-STATE-RELAY-CONSISTENCY.md)
- [Relay Resilience and Replication Design](./docs/RELAY-RESILIENCE-AND-REPLICATION-DESIGN.md)

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

## Smoke test

After installing into a fresh virtual environment:

```sh
python -c "from acorn import Acorn; print(Acorn)"
acorn --help
```

Expected result:

- Python prints the `acorn.acorn.Acorn` class.
- The `acorn` command lists the available CLI commands.

If you see an Open Quantum Safe warning such as:

```text
liboqs version (major, minor) ... differs from liboqs-python version ...
```

that warning is currently non-blocking if the import completes and the CLI
loads. It indicates that the native `liboqs` library and Python wrapper are not
the same release series. Future releases should document a known-good OQS
version matrix.

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
  also used for opt-in NIP-05 and lightning-address payment tests because those
  prove source-wallet interoperability and real payment behavior.
- Disposable wallet: receives most test mutations, including record lifecycle
  and burn-wallet flows.
- Separate opt-in tests: NIP-05 recipient resolution and real
  lightning-address payments.

The burn live test creates a separate disposable burn wallet config next to the
main test wallet, funds it from the source wallet, burns it, and verifies that
remaining funds are swept back.

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
# Source-wallet-only NIP-05 ecash transfer test. The identifier must resolve to
# the source wallet pubkey.
# ACORN_NIP05_RECIPIENT=trbouma@getsafebox.app

# Real lightning-address payment test. This spends sats and runs when set.
# ACORN_LIGHTNING_ADDRESS=someone@example.com
# ACORN_LIGHTNING_TEST_AMOUNT=1
```

The real `.env` file is gitignored. Do not commit real `nsec` values.

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

If you need to see import-time OQS warnings while debugging:

```sh
ACORN_SHOW_IMPORT_WARNINGS=1 acorn --help
```

## Python usage

```python
from acorn import Acorn

wallet = Acorn(nsec="nsec...", home_relay="wss://relay.getsafebox.app")
```

## Notes

This is the first standalone packaging boundary. Safebox still contains its
current in-tree Acorn implementation while this component package is stabilized.
