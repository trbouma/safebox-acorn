# Acorn Recovery Specification

## Summary

Acorn wallet recovery requires enough information to derive or restore the
wallet key and locate the encrypted wallet events. The practical recovery
bundle is:

```text
home_relay
seed_phrase
nsec
```

The seed phrase and `nsec` are sensitive recovery secrets. Anyone with either
one can control the wallet if they can access the wallet's relay-backed data.

## Recovery material

### `home_relay`

The home relay is the relay where Acorn publishes and retrieves wallet state,
private records, proofs, and reserved records.

Example:

```text
wss://relay.getsafebox.app
```

The home relay is not secret, but it is required for practical recovery because
the wallet data is relay-backed.

### `seed_phrase`

The seed phrase is the human backup phrase stored in the encrypted wallet
metadata.

Example format:

```text
word1 word2 word3 ...
```

The seed phrase can be used with:

```sh
acorn recover "<seed phrase>" --homerelay <home relay>
```

### `nsec`

The `nsec` is the Nostr private key encoding used directly by Acorn.

Example format:

```text
nsec1...
```

The `nsec` is often the easiest value to paste into configuration, but it is
also the most direct private-key material. Treat it like a wallet seed.

## Showing recovery information

The CLI exposes a recovery display command:

```sh
acorn set --show-recovery
```

Because this displays sensitive material, the command must ask for confirmation
before printing anything:

```text
Sensitive recovery material will be displayed. Continue? [y/N]:
```

If confirmed, the command prints:

```text
home_relay: wss://relay.getsafebox.app
seed_phrase: ...
nsec: nsec1...
```

The command intentionally avoids printing unrelated profile details, private
hex keys, access keys, balances, or record contents.

## Recovery flow

To recover on a fresh machine:

1. Install Acorn.
2. Run `acorn recover` with the seed phrase and home relay.
3. Acorn derives the `nsec`.
4. Acorn verifies that wallet data exists on the home relay.
5. Acorn writes the local minimal config.

Example:

```sh
acorn recover "word1 word2 word3 ..." --homerelay relay.getsafebox.app
```

Relay names are normalized so a bare relay hostname becomes:

```text
wss://relay.getsafebox.app
```

## Minimal local config after recovery

The local CLI config should only need:

```yaml
nsec: nsec1...
home_relay: wss://relay.getsafebox.app
```

Additional preferences should be stored in encrypted records where possible,
not as plaintext local config.

## Security considerations

- Do not paste recovery output into chats, logs, issue trackers, screenshots, or
  terminal transcripts that may be retained.
- Do not run `--show-recovery` in a shared screen session.
- Prefer writing recovery material to an offline password manager or physical
  backup.
- The `home_relay` is not sufficient to control the wallet, but the `seed_phrase`
  or `nsec` is.
- If recovery material is exposed, assume wallet control may be compromised.

## Open questions

- Whether Acorn should eventually support a machine-readable recovery export
  format.
- Whether `--show-recovery --json` should be supported.
- Whether recovery display should require typing a stronger confirmation phrase
  instead of a yes/no prompt.

