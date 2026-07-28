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

The command:

```sh
acorn set --minimal
```

rewrites compatible expanded configs to the minimal form.

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
acorn balance --json
acorn get "Field Notes" --json
acorn get_user_records --labels --json
```

JSON output should avoid extra human text, debug lines, or incidental prints.

## Raw output

Some commands may expose `--raw` for debugging internal objects. Raw output is
not considered a stable machine contract. Prefer `--json` for scripts.

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

Commands that display recovery secrets must require explicit confirmation.

The recovery display command is:

```sh
acorn set --show-recovery
```

It must prompt:

```text
Sensitive recovery material will be displayed. Continue? [y/N]:
```

If confirmed, it may display:

```text
home_relay: ...
seed_phrase: ...
nsec: ...
```

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

Expected success style:

```text
Replicated wallet events.
Source: wss://relay.getsafebox.app
Target: wss://new-relay.example.com
Events: 42
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
