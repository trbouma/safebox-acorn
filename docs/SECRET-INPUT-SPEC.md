# Acorn Secret Input Specification

## Summary

Acorn must not accept seed phrases, Nostr private keys, or externally generated
entropy as command-line values or environment variables. Those channels can be
retained by shell history, process inspection, diagnostics, CI systems, and
crash reports.

The command line supports two deliberate secret-input paths:

- a hidden prompt for interactive use; and
- an owner-only regular file, or stdin, for controlled automation.

This rule applies to recovery material entering the CLI. Python applications
may still pass private-key material directly to the Acorn API, because an
embeddable component must receive keys from an application-controlled secret
store, hardware boundary, or execution environment.

## Interactive input

The supported interactive commands are:

```sh
acorn init --import-nsec
acorn set --import-nsec
acorn recover --homerelay relay.example.com
acorn receive-ecash --receive-key
```

Each command reads the secret from a hidden prompt. Recovery phrases and
transient or initialization keys are entered once. BIP39 validates the recovery
phrase checksum, while the nsec parser validates imported key syntax. Only
`acorn set --import-nsec` requires double entry because it replaces the active
component keypair. Secret values must not appear in ordinary output, debug
logs, tracebacks, or the process argument list.

Ordinary `acorn init` does not ask for a private key. It generates a new key and
recoverable phrase. `acorn init --entropy` retains its separate hidden,
confirmed entropy prompt.

## File and stdin input

Named secret files must be regular files readable only by their owner:

```sh
chmod 600 /secure/path/recovery.txt
acorn recover --seed-file /secure/path/recovery.txt \
  --homerelay relay.example.com
```

Private-key file options follow the same rule:

```sh
acorn init --nsec-file /secure/path/wallet.nsec
acorn set --nsec-file /secure/path/wallet.nsec
acorn receive-ecash --receive-nsec-file /secure/path/receiver.nsec
```

Acorn rejects named secret files with any group or world permission bits. The
caller remains responsible for directory permissions, backups, filesystem
encryption, deletion policy, and protection from privileged processes.

Use `-` to read a secret from stdin without putting it in process arguments:

```sh
password-manager read acorn-seed | acorn recover --seed-file - --yes \
  --homerelay relay.example.com
```

Recovery from stdin requires `--yes`, because the input stream cannot also be
used to answer an interactive confirmation. Avoid `echo`, which can expose a
secret in shell history; use a secret manager or another protected producer.

## Test configuration

Live tests load the funded source wallet from `ACORN_SOURCE_CONFIG`, defaulting
to `~/.acorn/config.yml`. They do not accept `ACORN_SOURCE_NSEC` or
`ACORN_RECEIVE_NSEC`. Disposable wallet keys live in gitignored, permission-
restricted config files under `.acorn-test/`.

This keeps real private keys out of `.env`, CI variable listings, inherited
process environments, and test diagnostics.

## Output is a separate trust boundary

`acorn set --show-recovery` and `acorn init --json --include-recovery` can
explicitly display recovery material. They are export operations, not secret
input paths, and their output must be protected independently. Ordinary command
output remains redacted.

## Security invariants

- No recovery secret is a positional argument or option value.
- No supported test environment variable contains an `nsec` or seed phrase.
- Hidden prompts do not echo input; replacement through `set --import-nsec`
  additionally requires confirmation by repeated entry.
- Named secret files must be regular files with mode `0600`.
- `-` reads from stdin; it never means a filename.
- Imported private keys are validated before configuration is written.
- Transient receive keys are never persisted by `receive-ecash`.
