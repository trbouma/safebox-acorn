# Lockbox Local Integration Milestone

Date: 2026-08-11

## Summary

This milestone demonstrated that Acorn, Spurline, and Grove can operate
together as a local-first stack.

The tested local runtime was:

```text
Acorn        protocol runtime and live test driver
Spurline     local Nostr relay at ws://127.0.0.1:8080
Grove        Blossom blob store at http://127.0.0.1:8001
```

The result is a meaningful Lockbox foundation: local relay continuity through
Spurline, local encrypted blob availability through Grove, and Acorn as the
record, wallet, signing, recovery, and verification runtime.

## Spurline relay progress

Spurline was updated to support NIP-09 deletion visibility for stored events.
Kind `5` deletion events are still stored, but events deleted by their own
author are hidden from ordinary queries.

This allowed Acorn's private-record lifecycle test to pass:

```text
private-record-put-get-list-delete
```

Spurline also passed the local controlled Acorn suitability tests for:

```text
external-entropy-bootstrap-recovery-burn
private-record-put-get-list-delete
gift-wrapped-ecash-transfer
burn-sweep-transfer
token/proof maintenance round trip
```

In third-party scenario mode, Spurline passed:

```text
external-entropy-bootstrap-recovery-burn
private-record-put-get-list-delete
```

Funded third-party tests were not fully evaluated because they were blocked by
source-wallet proof state and source home-relay proof-write verification before
Spurline itself could be tested.

## Grove blob progress

Grove was given a first-class Poetry console entry point:

```bash
poetry run grove --host 127.0.0.1 --port 8001 --data-dir ./data
```

The local Grove instance was then tested with Acorn using:

```bash
ACORN_RELAY_SCENARIO=controlled \
ACORN_TEST_RELAY=ws://127.0.0.1:8080 \
ACORN_TEST_BLOSSOM=http://127.0.0.1:8001 \
poetry run pytest tests/integration/test_grove_blob_live.py -m live -rs -s
```

Observed result:

```text
Passed grove-blob-put-get
```

The same integration path also passed against the hosted Grove instance at
`https://grove.safebox.dev`.

This verifies:

- Acorn uploads encrypted blob bytes to Grove;
- Acorn stores the encrypted record metadata on Spurline;
- Acorn reads the metadata back from Spurline;
- Acorn retrieves the ciphertext from Grove;
- Acorn decrypts and verifies the original bytes;
- Acorn requests cleanup of both the record and associated blob.

## Acorn test and CLI improvements

Acorn's live test suite was extended with:

```text
tests/integration/test_grove_blob_live.py
```

This test covers the integrated Acorn + relay + Blossom path for blob-backed
private records.

The live funded tests were also improved so source-wallet environmental issues
do not incorrectly mark the relay under test as unsuitable. These include stale
proof state, already-spent proofs, and proof-state publish verification
failures on the source wallet's home relay.

The `acorn init` command was adjusted so a fresh initialization uses code
defaults rather than inheriting stale values from an existing YAML config:

```text
home relay: wss://relay.getsafebox.app
home mint:  https://mint.getsafebox.app
```

The `acorn repair-proofs` command now checks first and skips when the wallet is
already clean. A forced full proof refresh remains available:

```bash
poetry run acorn repair-proofs --refresh
```

## Suitability ledger entries

The relay suitability ledger now records Spurline's third-party scenario
result:

```markdown
| `ws://127.0.0.1:8080` | Suitable | Passed external-entropy-bootstrap-recovery-burn, private-record-put-get-list-delete | ~11.1s | Spurline local relay tested in third-party scenario. Funded ecash capabilities were tested separately in controlled mode. |
```

The local Grove integration pass produced:

```markdown
| `ws://127.0.0.1:8080` | Suitable | Passed grove-blob-put-get | ~3.0s | Grove local blob store `http://127.0.0.1:8001` |
```

## Lockbox significance

This milestone shows that the sibling products can already work together in a
local appliance shape:

```text
Safebox Web can use Acorn.
Acorn can use Spurline for relay-backed records and recovery.
Acorn can use Grove for encrypted blob storage.
Spurline and Grove can run locally as ordinary services.
```

That supports the Lockbox product direction:

```text
Lockbox preserves local authority, continuity, and evidence.
```

The important architectural point is that no single hosted service is required
for the local record/blob path once Acorn, Spurline, and Grove are running
together.

## Commands used

Start Spurline:

```bash
cd /Users/trbouma/projects/spurline
poetry run spurline --host 127.0.0.1 --port 8080 --database ./data/spurline.sqlite3
```

Start Grove:

```bash
cd /Users/trbouma/projects/grove
poetry run grove --host 127.0.0.1 --port 8001 --data-dir ./data
```

Run the Grove integration test:

```bash
cd /Users/trbouma/projects/safebox-acorn

ACORN_RELAY_SCENARIO=controlled \
ACORN_TEST_RELAY=ws://127.0.0.1:8080 \
ACORN_TEST_BLOSSOM=http://127.0.0.1:8001 \
poetry run pytest tests/integration/test_grove_blob_live.py -m live -rs -s
```

Run the core local relay suite:

```bash
ACORN_RELAY_SCENARIO=controlled \
ACORN_TEST_RELAY=ws://127.0.0.1:8080 \
poetry run pytest \
  tests/integration/test_entropy_recovery_live.py \
  tests/integration/test_record_lifecycle_live.py \
  tests/integration/test_ecash_transfer_live.py \
  tests/integration/test_burn_wallet_live.py \
  tests/integration/test_token_roundtrip_live.py \
  -m live -rs -s
```

## Next useful tests

- Add a direct Spurline Nostr protocol conformance test independent of Acorn.
- Add a combined local Lockbox smoke test that assumes Spurline and Grove are
  already running.
- Repeat Grove blob tests in third-party relay scenario mode once source-wallet
  proof state and source home-relay write verification are stable.
- Add service-runner documentation for FreeBSD and Raspberry Pi deployment.
