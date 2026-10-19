# Safebox wallet discovery

`acorn.safebox_discovery` provides an additive version-1 directory API. It does
not change existing Acorn NIP-05, social, messaging or transfer methods. Neither
an HTTP lookup nor a directory response signs events, exports tokens or sends money.

```python
from acorn.safebox_discovery import CASH, resolve_safebox_address

destination = await resolve_safebox_address("alice@example.com")
if destination.supports(CASH, "sat"):
    # A caller must still review/authorize the operation and apply relay policy.
    wallet_key = destination.pubkey
    relay_hints = destination.relays
```

The endpoint is `https://example.com/.well-known/safebox.json?name=alice`.
`SafeboxDestination` provides the canonical address, validated wallet key, relay
hints, known capabilities, `source="safebox-v1"` and `to_dict()`. `supports()` never
infers wallet support from an unknown capability or a generic NIP-05 response.
The immutable result returns fresh capability dictionaries; unknown fields do
not introduce mint restrictions or override transfer policy.

Providers use `build_safebox_document(address, pubkey, relays, cash=True,
clear=False, clear_units=())`; consumers can validate an already obtained document
with `parse_safebox_document(payload, expected_address)`. Both share the same
schema validation. The builder does not advertise wallet messaging yet.

Lookups default to a five-second total budget and 64 KiB response limit. They
pin a validated public DNS address to HTTPS with the original TLS hostname,
reject redirects and duplicate JSON keys, and do not use ambient proxies.
Public keys are validated through Stroma. The resolver does not follow arbitrary
URLs from the response or make any relay connection.

`SafeboxNotFound` denotes HTTP 404 only. `SafeboxHTTPError.status_code` preserves
other HTTP failures (including redirects, 410, 429 and 503). Other failures raise
`SafeboxDiscoveryError`. None triggers automatic NIP-05 or Lightning fallback.
A 404 cannot distinguish an absent endpoint from an absent handle. The caller
must implement any deliberate compatibility policy before initiating a payment.

The protocol fixture is `tests/fixtures/safebox_discovery_v1.json`; parser and
network boundary tests live in `tests/unit/test_safebox_discovery.py`.

Publish this Acorn change before updating the applications' dependency lockfiles.
Their first release dual-publishes the new directory and existing NIP-05 responses;
reader migration and separate social identities follow later. The older
`safebox.json/<name>` route and nonce/kind-21401 flow are not this contract.

See the [family contract and staged migration](https://github.com/trbouma/oakgate/blob/main/docs/018-safebox-address-discovery.md).
