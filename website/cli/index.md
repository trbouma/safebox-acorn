# Acorn CLI manual

The `acorn` CLI controls an Acorn from a terminal. It is separate from
Safebox Web: web pages, background workers, and web-only operator commands are
not part of this command reference.

Start with the [Acorn lifecycle](lifecycle.md), or use the
[complete command reference](commands.md) for arguments and options. The
reference covers every registered command, including the `clear` and `records`
subcommands and older experimental commands.

## Install and inspect

From a checkout of the safebox-acorn repository:

```bash
poetry install
poetry run acorn --help
```

Examples below assume `acorn` is on your active environment's path. Otherwise,
prefix them with `poetry run`. Python 3.11–3.13 is supported by the package.
Pin a reviewed release or commit when installing for production.

Help does not create a wallet or run the selected command:

```bash
acorn --help
acorn init --help
acorn records copy --help
```

## Select the account before the command

```bash
acorn --config /secure/path/personal.yml balance
acorn --config /secure/path/testing.yml get_user_records --labels
```

`--config` is a global option and goes before the command. Its default is
`~/.acorn/config.yml`, or the path selected by `ACORN_CONFIG`. An account's local
configuration contains sensitive bootstrap material, including its private key
and home relay. Keep separate config files for separate identities. Do not paste
their contents into issue reports.

`acorn set` shows configuration with the private key redacted. `--verbose` / `-v`
enables debug logging; inspect logs for private metadata before sharing them.
File permissions are hardened to `0600` and the default account directory to
`0700`; filesystem protection is not encryption against a compromised host.

## Choose the right operation

| Task | Commands |
|---|---|
| Create or recover an identity | `init`, `recover`, `set --import-nsec` |
| Inspect balances and payments | `balance`, `check-proofs`, `txhistory`, `pending-transfers` |
| Fund or pay | `deposit`, `claim-deposit`, `pay`, `ecash-transfer`, `mint-transfer` |
| Work with Clear credits | `receive-clear`, `clear balances`, `clear accept`, `clear history` |
| Store and inspect private records | `put`, `get`, `get_user_records`, `get_blob` |
| Move records to a new identity | `records copy` |
| Copy signed events to another relay, keeping the identity | `replicate` |
| Discover inboxes and send messages | `inbox-relays`, `dm` |
| Reconcile interrupted financial operations | `reconcile-payments`, `reconcile-proofs` |
| Delete data or retire an account | `delete`, `deletekind`, `burn` |

## Safety and output conventions

- **A private key or recovery phrase belongs in a hidden prompt.** `init`,
  `set`, `recover`, and `records copy` provide secret-input paths. Where supported,
  a secret file must have restricted permissions. Never put a seed phrase in a
  positional argument, even if an older diagnostic message suggests that syntax.
- **Tokens are bearer value.** `accept_token` takes a token argument and
  `issue_token` prints a token. Shell history, terminal capture, and automation
  logs can expose them. The same caution applies to private text passed as a
  record or message argument.
- **There is no universal dry-run switch.** `records copy --dry-run` and the
  receive commands' `--preview` options have specific meanings. Do not assume
  adding `--dry-run` makes another command safe.
- **Inspection is not a blanket no-write guarantee.** Several older CLI
  commands call `load_data` before their main action. Wallet loading can perform
  recovery or maintenance. A proof check itself does not repair proofs, but do
  not treat the entire CLI invocation as an isolated offline audit. Record copy
  deliberately avoids wallet loading and payment recovery.
- **Confirmation is command-specific.** Not every payment or publication
  command asks a second question. Review amount, recipient, account, and relay
  before invoking it. `--yes`, `--force`, and loss-acknowledgment options are not
  interchangeable.
- **JSON is available only where listed.** Use `--json` when a command supports
  it; do not parse human-readable tables. Some legacy paths print errors rather
  than setting a nonzero exit status, so inspect returned status fields as well.

## Reading the reference

`[OPTIONS]` denotes flags. Uppercase names such as `EVENT_ID` are placeholders;
square brackets in usage text indicate syntactically optional arguments, not
necessarily a useful or safe default. Supply explicit amounts, recipients, and
record labels. Both hyphenated and underscored command names are intentional:
use their exact spelling.

The [reference](commands.md) contains operational notes followed by the current
Click help for each command. A coverage test checks that registered commands and
their option names are represented. Installed versions may differ: use their
local `--help` as the final syntax check.

See also [recovery and continuity](../recovery-and-continuity.md) and
[deployment and trust](../deployment-and-trust.md).
