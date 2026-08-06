# Acorn Mint Configuration Specification

## Summary

Acorn uses a home mint for Cashu deposit and wallet operations. The home mint
must be explicit enough for users to understand where deposits are requested,
while still allowing the local config to remain minimal.

## Terms

### Acorn tenant and mint client

An Acorn instance is an encrypted tenant on one or more relays, and a client to
one or more mints.

Relays provide availability for signed encrypted wallet and record state. Mints
provide issuance, swap, melt, and spend-state validation for ecash proofs.

In an operator-run deployment, the party providing the execution environment or
running code may also provide web presence and Lightning address support around
the Acorn component. That service layer can improve usability, but it should
not obscure which mint is issuing or redeeming proofs for the wallet.

The tenant/client distinction is specified in
[Relay Resilience and Replication Design](./RELAY-RESILIENCE-AND-REPLICATION-DESIGN.md).

### Mint

A Cashu mint issues and redeems ecash proofs.

Example:

```text
https://mint.getsafebox.app
```

### Home mint

The home mint is the default mint Acorn uses when a command does not provide an
explicit mint.

## Mint fallback chain

Acorn resolves the effective mint in this order:

```text
explicit command mint
→ wallet record mint loaded by load_data()
→ constructor mints[0]
→ DEFAULT_HOME_MINT
```

The current default home mint constant is:

```text
https://mint.getsafebox.app
```

## Mint API proof serialization

Mint-facing API calls must use Cashu proof serialization, not broad wallet model
serialization. In practice this means sending only the fields required by the
mint for proof validation, swap, or melt:

```json
{
  "id": "...",
  "amount": 1,
  "secret": "...",
  "C": "..."
}
```

Optional proof fields such as `witness` must be omitted unless they are actually
present and required by a spending condition. Empty/default witness values are
not harmless with all mints; stricter mints can reject them with errors such as:

```text
witness data not allowed without a spending condition
```

Wallet-local fields, reserved flags, derivation paths, and empty/default values
belong in Acorn's local or relay-backed state, not in mint API payloads.

## Where the home mint is stored

When a wallet is created, Acorn writes the home mint into the encrypted wallet
record as a tag:

```python
["mint", self.mints[0]]
```

On startup, `load_data()` reads the encrypted wallet record and sets:

```python
self.home_mint = normalize_mint_url(each[1])
```

where `each` is the wallet tag whose first value is `"mint"`.

## Constructor behavior

When an `Acorn` object is created, it initializes:

```python
self.mints = [normalize_mint_url(mint) for mint in (mints or [DEFAULT_HOME_MINT])]
self.home_mint = self.mints[0]
```

This gives the object a usable home mint before wallet metadata has been loaded.
If wallet metadata is present, `load_data()` can override this value with the
stored wallet mint.

## CLI behavior

The CLI default mint list is:

```python
["https://mint.getsafebox.app"]
```

The user can inspect the effective wallet-loaded mint with:

```sh
acorn set --show-mint
```

Example output:

```text
home_mint: https://mint.getsafebox.app
```

## Deposit behavior

When running:

```sh
acorn deposit 21
```

Acorn uses the effective home mint and prints it before generating the invoice:

```text
amount: 21 mint:https://mint.getsafebox.app
```

The user may override the mint for a single deposit:

```sh
acorn deposit 21 --mint https://mint.example.com
```

Mint values are normalized so a bare hostname becomes HTTPS.

## Mint normalization

Mint values are normalized as follows:

- leading and trailing whitespace is removed;
- if the value starts with `https://`, keep it;
- if the value starts with `http://`, keep it;
- otherwise prefix `https://`;
- remove trailing `/` characters from the base URL;
- reject query strings, fragments, and values without a valid HTTP(S) host.

Examples:

```text
mint.getsafebox.app          -> https://mint.getsafebox.app
https://mint.getsafebox.app  -> https://mint.getsafebox.app
https://mint.example.com/    -> https://mint.example.com
http://localhost:3338        -> http://localhost:3338
```

Normalization happens inside the Acorn component as well as at the CLI. This
is important because a home mint loaded from older relay-backed wallet state
may contain a trailing slash. Endpoint paths are always appended to the
canonical base URL, preventing malformed paths such as `//v1/mint/quote/bolt11`.

## Quote failure and retry behavior

Creating a deposit quote distinguishes transient availability problems from
permanent request failures:

- connection failures, timeouts, HTTP 408, HTTP 429, and server-side HTTP 5xx
  responses receive a bounded retry;
- other HTTP 4xx responses are treated as permanent and fail immediately;
- the error reports the HTTP status and canonical endpoint without incorrectly
  describing a permanent rejection as a timeout.

This avoids repeatedly sending a request that the mint has already rejected,
while retaining limited recovery from temporary network and service failures.

## Deposit success output

After a deposit confirms, the CLI should print a human-readable summary:

```text
Deposit confirmed.
Amount: 21 sats
Mint: https://mint.getsafebox.app
Balance: 32582 sats in 16 proofs
```

It should not print the paid BOLT11 invoice as the success message.

## Security and operational considerations

- Different mints have different trust and availability properties.
- A home mint can fail, disappear, refuse redemption, or behave adversarially.
- Wallet proofs are mint-specific.
- Applications should make the effective mint visible before deposit requests.
- Future multi-mint support should avoid assuming one mint forever.

## Open questions

- Whether home mint should become an encrypted reserved record separate from the
  wallet record.
- Whether `acorn set --mint` should update the encrypted wallet mint, not just
  local CLI config.
- Whether multi-mint policy should be exposed as a first-class component API.
