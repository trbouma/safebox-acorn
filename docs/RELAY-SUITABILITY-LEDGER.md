# Relay Suitability Ledger

Acorn uses Nostr relays as sovereign, user-selectable infrastructure for
wallet bootstrap state, private records, gift-wrapped ecash transfers, and
relay-backed recovery. Not every public relay is suitable for this role.

This ledger records observed live-test results so relay compatibility can be
tracked over time.

## Suitability definition

A relay is considered suitable as tested when the Acorn live test suite can
complete the following capabilities:

- wallet bootstrap state can be written and read back;
- private records can be put, read, listed, and deleted;
- kind `1059` gift-wrapped ecash transfers carrying inner Acorn kind `7378`
  payloads can be published and received;
- disposable wallet burn can sweep remaining funds back to the source wallet;
- relay behaviour is reliable enough to pass within the configured live-test
  timeout.

Suitability is an observed test result, not a permanent guarantee. Relay
operators can change policies, retention windows, accepted event kinds, rate
limits, authentication requirements, or infrastructure at any time.

## Current results

Last updated: 2026-07-29

| Relay | Status | Observed result | Observed time | Notes |
| --- | --- | --- | --- | --- |
| `ws://beelink:8735` | Suitable | Passed controlled live test matrix | ~58s to ~60s | Local controlled relay used for development. |
| `wss://relay.openetr.org` | Suitable | Passed third-party scenario live test matrix | ~55s | Independently deployed relay controlled by the project operator. |
| `wss://nos.lol` | Suitable | Passed burn-sweep-transfer, gift-wrapped-ecash-transfer, private-record-put-get-list-delete | ~62.1s | Real third-party relay. Passed core Acorn capabilities. |
| `wss://nostr.oxtr.dev` | Suitable | Passed burn-sweep-transfer, gift-wrapped-ecash-transfer, private-record-put-get-list-delete | ~61.3s | Real third-party relay. Passed core Acorn capabilities. |
| `wss://relay.primal.net` | Suitable | Passed third-party scenario live test matrix | ~99s | Real third-party relay. Passed core Acorn capabilities, but slower than `relay.openetr.org` in the observed run. |
| `wss://nostr.openhoofd.nl` | Suitable | Passed third-party scenario live test matrix | ~114s | Real third-party relay. Passed burn sweep, gift-wrapped ecash transfer, and private record lifecycle. |
| `wss://custom.fiatjaf.com` | Unsuitable as tested | wallet-bootstrap-readback: wallet bootstrap state was not readable after initialization | ~0.0s | Failed the basic Acorn home-relay bootstrap readback requirement. |
| `wss://dwebcamp.nos.social` | Unsuitable as tested | wallet-bootstrap-readback: wallet bootstrap state was not readable after initialization | ~0.0s | Failed the basic Acorn home-relay bootstrap readback requirement. |
| `wss://nostrrelay.win` | Unsuitable as tested | wallet-bootstrap-readback: wallet bootstrap state was not readable after initialization | ~0.0s | Failed the basic Acorn home-relay bootstrap readback requirement. |
| `wss://relay.damus.io` | Unsuitable as tested | Failed/skipped relay compatibility checks | ~55s before failure/skip summary | Wallet bootstrap readback and/or burn sweep acceptance was unreliable in the observed run. May be suitable for social Nostr use while still unsuitable as an Acorn home relay. |
| `wss://relay.magiccity.live` | Unsuitable as tested | Timed out during wallet bootstrap initialization | ~257s for mixed controlled/third-party run | Did not complete Acorn disposable wallet initialization within the configured timeout. |

## Test command

Run the live suitability matrix with progress output:

```sh
poetry run pytest -m live -rs -s
```

To test only a third-party relay, set:

```env
ACORN_THIRD_PARTY_RELAY=wss://relay.example.com
ACORN_RELAY_SCENARIO=third-party
```

Then run:

```sh
poetry run pytest -m live -rs -s
```

The output should emit suitability lines such as:

```text
SUITABLE relay capability (... capability=burn-sweep-transfer ...)
SUITABLE relay capability (... capability=gift-wrapped-ecash-transfer ...)
SUITABLE relay capability (... capability=private-record-put-get-list-delete ...)
```

or diagnostic lines such as:

```text
UNSUITABLE relay capability (... capability=wallet-bootstrap-readback ...)
UNSUITABLE relay capability (... capability=burn-sweep-transfer ...)
```

At the end of the pytest run, Acorn also prints a relay suitability summary with
a copy/paste-ready ledger row:

```text
Acorn relay suitability summary
Suitable: wss://relay.example.com (third-party, 58.4s)
  Observed: Passed burn-sweep-transfer, gift-wrapped-ecash-transfer, private-record-put-get-list-delete
  Ledger row: | `wss://relay.example.com` | Suitable | Passed ... | ~58.4s |  |
```

## How to add a result

When testing a new relay:

1. Set `ACORN_THIRD_PARTY_RELAY` to the relay URL.
2. Set `ACORN_RELAY_SCENARIO=third-party`.
3. Run `poetry run pytest -m live -rs -s`.
4. Copy the generated `Ledger row` from the pytest summary into the table
   above, adding any notes that help interpret the result.

Prefer small amounts for live ecash tests. Do not commit real `nsec` values or
`.env` files.

## Interpretation

A suitable relay has demonstrated enough behaviour to act as an Acorn relay in
the tested scenario. It does not mean the relay is trusted, permanent, private,
or commercially supported.

An unsuitable result does not necessarily mean the relay is broken. It may mean
the relay is optimized for social Nostr traffic rather than Acorn's relay-backed
wallet and record lifecycle.

The goal of this ledger is practical: identify relays that can support Acorn's
protocol-first sovereign data model, and make relay choice an explicit,
testable deployment decision.
