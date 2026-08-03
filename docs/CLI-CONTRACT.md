# Acorn CLI Contract

## Summary

The `acorn` command-line interface is part of the Acorn component. It should be
usable by humans, useful for smoke testing, and predictable enough for scripts
when JSON output is explicitly requested.

The CLI is not the Safebox web application UI.

## Goals

- Provide a stable operational interface for standalone Acorn users.
- Keep default output readable and low-noise.
- Offer JSON output for selected commands used by programs.
- Avoid exposing sensitive material without explicit confirmation.
- Keep local configuration minimal.

## Local config contract

The preferred local config is:

```yaml
nsec: nsec1...
home_relay: wss://relay.getsafebox.app
```

The config contains sensitive bootstrap material. Acorn therefore:

- creates a new config directory with mode `0700`;
- writes config files with mode `0600`;
- serializes a complete replacement before changing the existing file;
- uses an atomic replacement so an interrupted write preserves the previous
  valid config;
- uses a file lock to prevent concurrent writers from interleaving;
- treats malformed or non-mapping YAML as an explicit configuration error;
- does not create a key, directory, or config merely because the CLI module is
  imported or help is displayed.

When a real CLI command opens a valid config created by an older Acorn version,
Acorn upgrades the file permissions without rewriting its YAML. The default
`.acorn` directory is also upgraded to `0700`.

Configuration creation must be intentional. Supported creation paths are:

```sh
acorn init
acorn recover --homerelay relay.example.com
acorn set --import-nsec --home relay.example.com
```

An ordinary command without an initialized config should explain how to run
`acorn init`; it must not silently generate a replacement identity.

The command:

```sh
acorn set --minimal
```

rewrites compatible expanded configs to the minimal form.

Ordinary `acorn set` output redacts the `nsec`. Recovery material is displayed
only through an explicit recovery flow with confirmation.

## Human output

Human output should be concise and useful.

Example:

```sh
acorn get "Field Notes"
```

Expected style:

```text
Record: Field Notes
Kind: 37375
Type: generic

Apr 30: Moving
```

Debug logs should not appear in normal output. Verbose logs are available with:

```sh
acorn --verbose ...
```

## JSON output

Commands that are likely to be called from programs should support `--json`.

Current examples:

```sh
acorn info --json
acorn init --json
acorn balance --json
acorn check-proofs --json
acorn get "Field Notes" --json
acorn get_user_records --labels --json
```

JSON output should avoid extra human text, debug lines, or incidental prints.

## Read-only proof inspection

Before choosing a mutating repair, operators can inspect proof state at the
relevant mints:

```sh
acorn check-proofs
acorn check-proofs --json
```

`check-proofs` loads the wallet's relay-backed state and calls each mint's
Cashu `/v1/checkstate` endpoint. It reports wallet-visible proof totals and
mint-reported `UNSPENT`, `SPENT`, `PENDING`, and `UNKNOWN` totals.

The command is strictly read-only: it does not acquire the wallet lock, swap
proofs, delete events, rewrite proof state, or create transaction history.
Duplicate copies are queried only once so the mint-confirmed amount is not
overstated. A pending, unknown, or unreachable state is reported as
inconclusive and should be rechecked before running a repair.

Proof mutation remains an explicit operator decision:

```sh
acorn repair-proofs
```

## Lightning payment recovery

A Lightning melt timeout is an unknown outcome, not a confirmed failure. Acorn
checkpoints post-swap proofs and an encrypted pending-melt journal before
submitting the melt. It never repeats the melt `POST`; it resolves uncertainty
through the mint's quote-status endpoint.

Operators can resume recovery explicitly:

```sh
acorn reconcile-payments
acorn reconcile-payments --json
```

`PAID` removes the submitted proofs and writes idempotent transaction history.
`UNPAID` retains the post-swap proofs. `PENDING`, an unknown state, or an
unreachable mint keeps the recovery journal and blocks another spend.

See [Lightning Melt Recovery](LIGHTNING-MELT-RECOVERY.md) for the state model
and durable ordering.

## Wallet burn

`acorn burn` deletes local bootstrap config by default and publishes NIP-09
deletion requests for relay-backed wallet data. Because NIP-09 deletion is
advisory, this command must describe deletion as a request, not a guaranteed
erase.

Funded wallets require an explicit fund-handling choice:

```sh
# Acorn/Nostr ecash sweep.
acorn burn --send-to alice@example.com

# Lightning address payment.
acorn burn --pay-to alice@example.com --pay-amount 21

# Lightning address sweep, automatically reduced for mint fee reserve.
acorn burn --pay-to alice@example.com

# Dangerous/explicit: burn while funds remain.
acorn burn --allow-funded
```

`--send-to` treats the recipient as a NIP-05, npub, or raw pubkey and sends a
gift-wrapped Acorn ecash transfer before deletion.

`--pay-to` treats the recipient as a Lightning address and pays through the
wallet's mint melt flow before deletion. If `--pay-amount` is omitted, Acorn
first quotes the Lightning invoice and mint melt fee reserve, then pays the
largest amount that fits the wallet's spendable proofs after fees. If
`--pay-amount` is provided, it is treated as an exact requested payment amount
and may fail if that amount plus fees cannot be paid. `--send-to` and
`--pay-to` are mutually exclusive.

## Wallet initialization

`acorn init` creates or replaces the local wallet bootstrap configuration.
Because this can disconnect the local CLI from an existing wallet, it must be
conservative by default.

Human flow:

- if an existing config is present, show that an existing wallet was detected;
- offer to display the existing operational `nsec` and relay before
  continuing, but do not promise that an offline mnemonic can be recovered;
- require confirmation before replacing the local config;
- generate a new `nsec` by default;
- import an existing `nsec` only through `--import-nsec` and a hidden prompt,
  or through `--nsec-file`;
- prompt for home relay and home mint;
- accept externally generated 256-bit entropy through `--entropy` and a hidden,
  confirmed prompt;
- use default home relay and home mint if blank/default choices are accepted;
- offer to display the newly created offline mnemonic and operational `nsec`
  through an explicit sensitive-output flow. This is the one-time mnemonic
  handoff; the operator should verify the offline backup before funding.

External entropy initialization is explicit:

```sh
acorn init --entropy
```

The prompt accepts exactly 64 hexadecimal characters (32 bytes). Acorn encodes
those bytes as a 24-word English BIP39 phrase and derives the wallet `nsec`
through the same SLIP-10 secp256k1 path used by `acorn recover`. It does not hash
the supplied value again. `--entropy` is mutually exclusive with
`--import-nsec`, `--nsec-file`, and `--keepkey`.

The entropy is intentionally entered through a hidden prompt rather than as a
command-line value. `--force` and `--json` do not remove that prompt. Normal
human and JSON output must not echo the entropy, phrase, or `nsec`.

Automation flow:

```sh
acorn init --json
```

If an existing config is present and `--force` is not supplied, the command must
not mutate local config or relay state. It returns a machine-readable refusal:

```json
{
  "ok": false,
  "reason": "confirmation_required",
  "confirmations_completed": false
}
```

For non-interactive replacement, callers must opt in explicitly:

```sh
acorn init --force --json
```

With `--force`, omitted values are resolved without prompts: a new `nsec` is
generated, the default home relay is used, and the default home mint is used.
When `--entropy` is present, its hidden secret-input prompt remains mandatory.
Successful JSON output is redacted by default and reports `key_source` as
`acorn_generated`, `external_entropy`, `imported_nsec`, or `existing_nsec`.
Newly generated recovery material is included only when `--include-recovery`
is also supplied. The offline mnemonic is available only during the creating
invocation and is not a later export contract.

If initialization writes wallet material but cannot read it back from the
selected home relay, the command must fail clearly and must not replace the
local config. Human output should explain likely relay causes, such as rejected
event kinds, delayed indexing, authentication requirements, or relay policy
restrictions. JSON output should return:

```json
{
  "ok": false,
  "reason": "relay_wallet_readback_failed",
  "local_config_replaced": false
}
```

Because a new key may already have been generated for the attempted wallet,
the same initialization invocation must still offer its newly generated
offline mnemonic after a human failure, or include it when
`--json --include-recovery` was requested. Ordinary failure output remains
redacted. A later command must not imply that it can reconstruct the mnemonic
from the `nsec`.

See [External Entropy Initialization](EXTERNAL-ENTROPY-INITIALIZATION.md) for
the derivation contract, test vector, and operational guidance.

## Raw output

Some commands may expose `--raw` for debugging internal objects. Raw output is
not considered a stable machine contract. Prefer `--json` for scripts.

## Ecash transfer commands

`acorn ecash-transfer` and `acorn receive-ecash` expose the Acorn
transferable-record path for ecash.

Default transfer mode is gift-wrapped:

```text
outer relay-visible event: kind 1059
inner Acorn transfer: kind 7378
durable proof state after acceptance: kind 7375
transaction history: kind 7377
```

Human output for `acorn ecash-transfer` should make the outer/inner distinction
clear:

```text
Ecash transfer published.
Kind: 1059
Inner transfer kind: 7378
Mode: gift-wrapped
```

The `--direct` option is for debugging and legacy compatibility. It publishes a
sender-authored direct kind `7378` event instead of a default NIP-59 kind `1059`
gift wrap.

`acorn receive-ecash` should receive:

- standard kind `1059` gift wraps containing inner kind `7378` transfers;
- legacy kind `7378` gift wraps;
- direct sender-authored kind `7378` transfers.

Receiving ecash is an explicit mutating operation. It may accept a token through
the mint, refresh proofs, write updated kind `7375` proof state, and write kind
`7377` transaction history. It must not be hidden inside `acorn balance`.

When `--receive-key` is supplied, Acorn obtains transient receiving material
through a hidden prompt. `--receive-nsec-file` provides the protected
file/stdin automation path. The key may be used to unwrap incoming transfer
events, but it must not be stored in the wallet config.

Seed phrases, external entropy, and private keys must never be accepted as
command argument values or test environment variables. Named secret files must
be regular files with mode `0600`; `-` means stdin. See
[Secret Input Specification](SECRET-INPUT-SPEC.md).

JSON output for these commands should include enough protocol detail for
scripts to distinguish transport from transfer intent, including:

```json
{
  "kind": 1059,
  "transfer_kind": 7378,
  "mode": "gift-wrapped"
}
```

## Read-only inspection options

Inspection flags under `acorn set` should be read-only when used by themselves.
They should not print `set!` or rewrite config.

Examples:

```sh
acorn set --show-mint
acorn set --show-public-relays
acorn set --show-recovery
```

## Sensitive output

Ordinary profile, recovery, forced initialization, and JSON initialization
output must not expose an `nsec`, raw private key, seed phrase, access key, or
internal lock private key.

The confirmed human-facing operational-key export path is:

```sh
acorn set --show-recovery
```

Machine-readable initialization may include the newly generated offline
mnemonic and other recovery secrets only through the explicit combination:

```sh
acorn init --json --include-recovery
```

Callers using `--include-recovery` must prevent stdout from entering shell,
application, CI, or observability logs.

Commands that display recovery secrets must require explicit confirmation.

The recovery display command is:

```sh
acorn set --show-recovery
```

It must prompt:

```text
Sensitive recovery material will be displayed. Continue? [y/N]:
```

Under the target offline-mnemonic policy, if confirmed it may display:

```text
home_relay: ...
offline_mnemonic: unavailable (not retained after initialization)
nsec: ...
```

The newly generated offline mnemonic is displayed only by the initialization
flow that creates it. Existing wallets may temporarily redisplay an encrypted
retained phrase until the migration described in the
[Recovery Specification](RECOVERY-SPEC.md#implementation-status-and-migration)
is complete.

It should not display unrelated private material such as private hex keys,
access keys, record contents, or profile internals.

## Relay and mint display

The CLI should make important runtime defaults visible:

```sh
acorn set --show-mint
acorn set --show-public-relays
```

These commands are safe to run without a sensitive-material prompt because they
do not display wallet recovery secrets.

## Replication contract

`acorn replicate` copies this wallet's signed events from a source relay to a
target relay:

```sh
acorn replicate --target new-relay.example.com
```

The command must show the source and target relay and ask for confirmation
before publishing, unless `--yes` is supplied.

Expected verified style:

```text
Replication status: OK
Source: wss://relay.getsafebox.app
Target: wss://new-relay.example.com
Events: 42
Target readback verified: True
Kinds:
- 0: 1
- 37375: 36
- 7375: 5
```

The command may support JSON output:

```sh
acorn replicate --target new-relay.example.com --yes --json
```

The operator runbook is documented in
[Relay Migration Runbook](./RELAY-MIGRATION-RUNBOOK.md).

Reaching the source query limit or failing target readback produces
`Replication status: PARTIAL`; it must not be presented as complete success.

## Relay-backed record commands

Record point operations accept an explicit relay pool:

```sh
acorn put "Field Notes" "text" --relays ws://local:8735,wss://backup.example
acorn get "Field Notes" --relays ws://local:8735,wss://backup.example
acorn delete "Field Notes" --relays ws://local:8735,wss://backup.example
```

`ws://` is retained for explicitly supplied local test relays. Ordinary
production configuration should use `wss://`.

`put` reports success only after the new event is canonical and readable on
each selected relay. `delete` reports a NIP-09 deletion request and advisory,
not a guaranteed erase. It requires interactive confirmation before loading
the wallet and publishing the request. `--yes` (or `-y`) bypasses confirmation
for deliberate automation. `--delete-blob` additionally requests cleanup of
an associated encrypted blob and is named explicitly in the confirmation.

## Deposit contract

`acorn deposit <amount>` should:

1. show the effective mint;
2. show the quote and invoice;
3. print a QR code;
4. wait for the user to press Enter after payment;
5. poll for confirmation;
6. print a useful success summary.

Expected success style:

```text
Deposit confirmed.
Amount: 21 sats
Mint: https://mint.getsafebox.app
Balance: 32582 sats in 16 proofs
```

The command should not print `None`, debug type information, or the full BOLT11
invoice as the final success message.

## Error behavior

Errors should be actionable.

Example zap lookup failure:

```text
Zap failed: no event; searched relays: wss://relay.damus.io, wss://relay.primal.net
```

Example deposit timeout:

```text
Error: Deposit was not confirmed before timeout.
```

## Import warning behavior

Normal CLI usage should suppress noisy import-time OQS warnings when the import
still succeeds.

For debugging, users may opt into import warnings:

```sh
ACORN_SHOW_IMPORT_WARNINGS=1 acorn --help
```

## Compatibility expectations

The CLI may evolve, but the following behaviors should remain stable once
downstream applications depend on them:

- `acorn --help` loads without requiring Safebox;
- `acorn info --json` emits machine-readable identity info;
- `acorn balance --json` emits balance and proof count;
- `acorn get <label> --json` emits a single record;
- `acorn get_user_records --labels --json` emits labels without payloads;
- sensitive recovery output requires confirmation.
