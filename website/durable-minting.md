# Durable Cashu issuance

`acorn.minting.DurableCashuMint` is an additive API for callers that persist an
encrypted issuance checkpoint. It moves the restore-first issuance path from
OakGate into Acorn. Existing `Acorn.deposit`, mint, polling, Clear and transfer
methods are unchanged; Safebox Web need not adopt this API or change its calls.

## Responsibilities

Acorn owns quote validation, Cashu blinding, mint requests, NUT-09 restoration,
signature and optional DLEQ verification, and proof construction. The caller
owns authorization, mint endpoint configuration, encrypted durable storage,
job leases, retry scheduling and user presentation. This API neither uses a
user private key nor publishes wallet events. Publish proofs and history through
the existing Acorn APIs, with their own persisted prepared events.

## Calling sequence

```python
from acorn.minting import DurableCashuMint

mint = DurableCashuMint(require_description_hash=False)
item = {"mint": configured_mint_url, "amount": 13}
item.update(await mint.quote(item["mint"], item["amount"], description))
item["prepared"] = await mint.prepare(item)
# Durably encrypt and save item BEFORE returning its invoice to the payer.
# Later, under a per-quote lease:
state = await mint.state(item)
if state.get("state") in {"PAID", "ISSUED"} or state.get("paid") is True:
    item["proofs"] = await mint.issue(item)
    # Durably save proofs BEFORE publishing them through the wallet API.
```

`quote` returns `quote`, `invoice`, `expiry` and `description_hash_bound`.
With `require_description_hash=False`, missing or mismatched description hashes
are accepted; the binding flag is informational. Explicit strict mode continues
to require a matching hash. Amount, network, expiry and recovery checks are unchanged.
It requires NUT-09 support and validates the invoice amount, mainnet network and
expiry. Description-hash binding remains optional by default; a hash supplied
by the mint must match, and strict mode requires it.

`prepare` takes `mint` and integer sat `amount`, reads active mint keys, and
returns a JSON-compatible object containing `outputs`, `secrets`, and `keys`.
Each secret entry contains `secret`, `r`, and `Y`. All of this material is
sensitive. Save it encrypted; do not log it or return it to a browser.

`issue` takes `mint`, `quote`, and the exact persisted `prepared` object. It
calls restore first and matches restored signatures by blinded output, even if
the mint reverses their order. Only an empty restore proceeds to issuance,
using the same outputs. Partial restoration, incomplete responses, mismatched
amounts/keysets or invalid supplied DLEQ proofs raise errors rather than
creating a replacement checkpoint. Do not discard unresolved checkpoints or
blindly retry by calling `prepare` again.

The application must serialize each quote and save each phase before exposing
its result. This library does not itself guarantee persistence or coordinate
multiple workers. After an ambiguous issuance result, a fresh API instance can
resume with the same checkpoint; successful restoration reconstructs the same
proofs without issuing again. Mint availability and correct NUT-09 retention
remain external requirements.

## Compatibility

The persisted format is unchanged from OakGate's original Cashu adapter.
Existing in-flight `prepared` payloads and proof dictionaries require no schema
migration. There is no new dependency and no change to mint acceptance policy.
OakGate retains compatibility imports for its old adapter names, but production
must install an Acorn revision containing this module before using them.
