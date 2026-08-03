# External Entropy Initialization

## Summary

Acorn can initialize a new wallet from 256 bits of entropy generated outside
Acorn. This supports offline random-number generators, hardware security
devices, audited provisioning systems, and other workflows in which Acorn
should not generate the root randomness.

Run:

```sh
acorn init --entropy
```

Acorn prompts twice for the entropy without echoing it to the terminal. The
value is not supplied as a command-line argument, which keeps it out of normal
shell history and process listings.

This option is different from importing an `nsec`. External entropy produces
an offline BIP39 mnemonic; an imported `nsec` cannot be reversed into its
original mnemonic.

## Input contract

The prompt accepts exactly 64 hexadecimal characters representing 32 bytes
(256 bits):

```text
256-bit entropy (64 hexadecimal characters):
Repeat 256-bit entropy:
```

Uppercase and lowercase hexadecimal characters are equivalent. Acorn strips
leading and trailing whitespace, but it does not accept a `0x` prefix,
separators, or embedded whitespace.

Acorn interprets the value directly as entropy. It does **not** hash it again.
A SHA-256 digest is therefore accepted because it has the required 32-byte
representation, but its security depends entirely on the material and process
that produced it.

Do not use the SHA-256 digest of a password, memorable sentence, username,
document, timestamp, device identifier, or other guessable input. Hashing a
low-entropy secret does not turn it into high-entropy key material.

## Derivation contract

The current derivation is:

```text
32-byte external entropy
    -> English BIP39 encoding with checksum
    -> 24-word offline BIP39 mnemonic
    -> BIP39 seed generation
    -> SLIP-10 secp256k1 root private key
    -> Nostr nsec encoding
```

The 24-word phrase is the wallet's offline mnemonic. The target security
contract displays it during initialization for verified offline backup and
does not retain it in local configuration or encrypted relay-backed wallet
metadata. The local configuration stores the resulting operational `nsec`, not
the original hexadecimal entropy or mnemonic.

Current Acorn wallet metadata may still retain the phrase. This is a known
migration gap documented in the
[Recovery Specification](RECOVERY-SPEC.md#implementation-status-and-migration),
not the intended long-term behavior.

The derivation method is Acorn's current recovery contract. It must remain
stable for existing wallets even if future versions introduce a versioned key
derivation scheme.

## Public compatibility test vector

This vector is public and must never be used for a real wallet:

```text
entropy:
0000000000000000000000000000000000000000000000000000000000000000

seed phrase:
abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon art

nsec:
nsec1yddnfntunakhu3v4ll56ujcuk4sxm79v526j05s2qly026ergt6q682r8v
```

An implementation claiming compatibility with this external-entropy workflow
should reproduce both the phrase and the `nsec` exactly.

## CLI behavior

`--entropy` is mutually exclusive with:

- `--import-nsec` or `--nsec-file`, because one path derives a new key while
  the other imports a final private key; and
- `--keepkey`, because external entropy intentionally selects a new identity.

The home relay and mint can still be supplied normally:

```sh
acorn init --entropy \
  --homerelay relay.example.com \
  --mint mint.example.com
```

Relay and mint normalization is unchanged: missing schemes become `wss://` and
`https://`, respectively.

For forced or machine-readable initialization, `--entropy` still requires the
hidden prompt. `--force` bypasses replacement confirmations; it does not make
secret input non-interactive.

```sh
acorn init --entropy --force --json
```

JSON output identifies the source without exposing secrets:

```json
{
  "ok": true,
  "key_source": "external_entropy",
  "recovery_included": false
}
```

At initialization, recovery secrets appear in JSON only when the caller
explicitly adds `--include-recovery`. This is the one-time machine-readable
handoff of the offline mnemonic; Acorn must not imply that the mnemonic can be
exported again later. Captured output from that mode must be protected as key
material.

## Recovery

An external-entropy wallet can be recovered with the resulting 24-word phrase:

```sh
acorn recover --homerelay relay.example.com
```

Recovery derives the same `nsec`, verifies that the selected relay contains
the wallet bootstrap record, and only then replaces the local configuration.

The original 64-character entropy can also recreate the mnemonic and key
through the same derivation contract, but `acorn recover` accepts the mnemonic
rather than raw entropy. Backing up the offline mnemonic at initialization is
the ordinary Acorn recovery path.

The practical recovery bundle remains:

```text
24-word offline mnemonic + home relay
```

or:

```text
nsec + home relay
```

## Operational security

- Generate entropy with a cryptographically secure random-number generator.
- Prefer an offline or hardware-backed generation environment for high-value
  deployments.
- Never pass entropy as a shell argument, environment variable, URL, or config
  value.
- Do not paste entropy, phrases, or nsecs into chats, tickets, logs, or source
  control.
- Do not use this workflow while screen sharing or recording a terminal.
- Verify and protect the offline mnemonic before funding the wallet. Acorn
  should not be expected to display it again after initialization.
- Keep backups in more than one location without giving a single operator
  unnecessary access to every copy.
- Treat exposure of the entropy, phrase, or `nsec` as compromise of the same
  wallet authority.

The hidden prompt reduces accidental disclosure. It cannot protect against a
compromised terminal, keylogger, process, operating system, clipboard, or
randomness source.

## Live integration coverage

The live pytest suite includes an unfunded external-entropy lifecycle test. For
each selected controlled or third-party relay scenario, it:

1. generates fresh disposable 256-bit entropy;
2. derives the 24-word phrase and expected `nsec`;
3. initializes and reads back the wallet bootstrap record;
4. reconstructs the identity from the phrase in a new `Acorn` object;
5. verifies the same `npub`, phrase, and zero balance;
6. publishes the wallet deletion request; and
7. removes the temporary YAML configuration.

Run it alone against the controlled test relay:

```sh
ACORN_RELAY_SCENARIO=controlled poetry run pytest \
  tests/integration/test_entropy_recovery_live.py \
  -m live -rs -s
```

Run it against only the configured third-party relay:

```sh
ACORN_RELAY_SCENARIO=third-party poetry run pytest \
  tests/integration/test_entropy_recovery_live.py \
  -m live -rs -s
```

The test does not load the source wallet, create proofs, contact a mint for
funds, or spend sats. It records the relay capability
`external-entropy-bootstrap-recovery-burn` in the suitability summary. Relay
deletion remains advisory under NIP-09 even when the test passes.

## Key-source comparison

| Initialization path | Entropy source | Offline mnemonic | Primary recovery material |
| --- | --- | --- | --- |
| `acorn init` with blank key | Acorn CSPRNG | 12-word BIP39 mnemonic | Mnemonic plus home relay |
| `acorn init --entropy` | External 256-bit source | 24-word BIP39 mnemonic | Mnemonic plus home relay |
| `acorn init --import-nsec` or `--nsec-file` | External final private key | Unavailable | `nsec` plus home relay |

These paths create the same kind of Acorn component identity. They differ only
in how the private key originates and which recovery representation is valid.
