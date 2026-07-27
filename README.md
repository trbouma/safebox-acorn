# Safebox Acorn

Acorn is the reusable Nostr/Cashu wallet and records component extracted from
Safebox. It provides:

- the `Acorn` Python runtime class
- the `acorn` command-line interface
- supporting Nostr, Cashu, Lightning, record, and crypto helpers used by Acorn

This package is intended to make Acorn installable into other Python projects
without requiring the Safebox web application.

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

## Python usage

```python
from acorn import Acorn

wallet = Acorn(nsec="nsec...", home_relay="wss://relay.getsafebox.app")
```

## Notes

This is the first standalone packaging boundary. Safebox still contains its
current in-tree Acorn implementation while this component package is stabilized.
