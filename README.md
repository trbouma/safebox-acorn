# Safebox Acorn

Acorn is a protocol-first sovereign data haven: a sovereign protocol component
for identity, records, value, recovery, and reciprocal resilience.

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
- [Record Encryption Specification](./docs/RECORD-ENCRYPTION-SPEC.md)
- [Recovery Specification](./docs/RECOVERY-SPEC.md)
- [Relay Configuration Specification](./docs/RELAY-CONFIGURATION-SPEC.md)
- [Mint Configuration Specification](./docs/MINT-CONFIGURATION-SPEC.md)
- [CLI Contract](./docs/CLI-CONTRACT.md)
- [Ecash Transfer Kind 7378 Design Note](./docs/ECASH-TRANSFER-KIND-7378-DESIGN.md)
- [Relay Migration Runbook](./docs/RELAY-MIGRATION-RUNBOOK.md)
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
