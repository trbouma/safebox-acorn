# The lifecycle of an Acorn

An Acorn combines a controlling key with encrypted relay-backed records and,
when used for payments, mint-backed proofs. Attachments can live on Blossom
servers. A key backup alone does not recreate records or files that no longer
exist on their storage services.

## 1. Create an identity and record its bootstrap information

Select a home relay you intend to use and a mint suitable for your deployment:

```bash
acorn --config /secure/path/personal.yml init \
  --homerelay wss://relay.example.com \
  --mint https://mint.example.com
```

The `.example.com` addresses in this manual are placeholders; replace them with
your actual services. Initialization generates a recovery phrase by default;
`--words 24` requests 24 words instead of 12. Follow the confirmation and backup
prompts. Do not use `--force` to bypass an existing-account warning casually.

Keep the exact recovery phrase or nsec, the home relay, and the derivation mode
in a secure offline backup. Imported nsecs do not necessarily have a recoverable
seed phrase. `--entropy` is an advanced initialization path for externally
generated entropy, not a way to invent a memorable password.

To deliberately display recovery material later:

```bash
acorn set --show-recovery
```

This exposes secrets on the terminal after confirmation. Do not run it in a
recorded or shared terminal session. The examples from here use the selected
default account; include `--config` consistently if using another account.

## 2. Configure discovery and inspect the account

```bash
acorn info
acorn set
acorn inbox-relays
acorn balance --mints
```

To publish an inbox announcement, supply the externally reachable relays on
which the account can receive private messages and payment transfers:

```bash
acorn inbox-relays wss://inbox.example.com \
  --publish-relay wss://discovery.example.com
```

This publishes a signed kind 10050 event. It does not provision a relay or
register a NIP-05 address. Avoid advertising local-only service names to remote
senders. Public profile publication is separate (`publish_kind0`); an owner
metadata update (`setowner`) does not rotate or transfer the private key.

## 3. Fund and inspect cash

```bash
acorn deposit 100 --mint https://mint.example.com
```

The CLI prints an invoice and quote identifier. Pay the invoice, then press
Enter as instructed. This CLI path checks the quote for approximately one minute
after that prompt; it is not Safebox Web's background monitoring flow.

If confirmation times out, retain the quote, amount, and mint. Do not pay a
second invoice merely because the first was slow. To claim an existing paid
quote without creating another invoice:

```bash
acorn claim-deposit QUOTE_ID 100 --mint https://mint.example.com
acorn balance --verify
acorn txhistory
```

Relay-visible balances are not proof that every mint is currently reachable or
every proof spendable. An inconclusive check is a reason to investigate, not to
delete proofs. A single Lightning payment may be limited by one mint/keyset and
fees even when the total displayed balance is larger.

## 4. Receive transfers and Clear credits

Preview before processing incoming cash:

```bash
acorn receive-ecash --preview
acorn receive-ecash
acorn pending-transfers
```

Receiving cash and finishing mint confirmation are distinct stages. Pending
receipts are not necessarily spendable balance. If mint confirmation is delayed,
keep the receipt and investigate relay/mint availability.

Clear credits have an explicit discovery and acceptance sequence:

```bash
acorn receive-clear --preview
acorn receive-clear
acorn clear accept EVENT_ID
acorn clear balances
acorn clear history
```

Use the full event identifier reported for the pending transfer. Clear units are
not interchangeable with sats or with other Clear units. The issuing mint must
be reachable from the environment doing the acceptance.

## 5. Pay, communicate, and store records

These commands can send value or messages; replace recipients deliberately:

```bash
acorn pay 21 alice@example.com
acorn ecash-transfer 21 alice@example.com --comment "Example payment"
acorn dm alice@example.com "Hello"
```

For an offline token, `issue_token AMOUNT` produces bearer value; it is not just
a balance preview. `accept_token TOKEN` redeems a token. Prefer the dedicated
`ecash-transfer` flow over the older generic `send` path for Acorn transfers.

Store a private record with an explicit nonreserved label:

```bash
acorn put travel-note "Example record"
acorn put travel-document "Example attachment" --file ./document.pdf
acorn get_user_records --labels
acorn get travel-note
```

Private records are encrypted; referenced files use the configured Blossom
storage. Do not assume `put` is append-only: reusing a record label addresses
the same logical record. `get_blob` currently fetches the file but prints only
its media type; it is not a file-export command. The text in these examples is
not secret because command arguments can appear in shell history.

## 6. Maintain availability without changing identity

```bash
acorn replicate --target wss://backup-relay.example.com
```

Replication copies the same signed events to another relay. Inspect the report,
requested kinds, and query limit; do not assume every historical event or event
kind is included. It does not copy Blossom files and is not a funds transfer.
Only switch the configured home relay after checking the copied state:

```bash
acorn set --home wss://backup-relay.example.com
```

Keep more than one usable recovery path. Neither replication nor a deletion
request guarantees how long an independent relay retains data.

## 7. Recover the same identity

Use a new local config path when testing recovery so the working account is not
accidentally replaced:

```bash
acorn --config /secure/path/recovered.yml recover \
  --homerelay wss://relay.example.com
```

Enter the phrase at the hidden prompt. Use `--legacy` only if the account was
created with Acorn's legacy derivation. Recovery must find the original account
on the relay; a different derivation produces a different identity. This flow
does not support an additional BIP39 passphrase.

With an nsec rather than a phrase, set the bootstrap information using the hidden
key prompt, then inspect the resulting account:

```bash
acorn --config /secure/path/recovered.yml set --import-nsec \
  --home wss://relay.example.com
acorn --config /secure/path/recovered.yml balance --verify
```

Do not operate both recovered and original clients as independent spenders of
the same proofs. Coordinate writers and retain recovery journals.

## 8. Migrate private records to a new identity

First initialize the destination as a separate account and retain its recovery
material. Then, while the CLI is configured for the **source**, preview:

```bash
acorn records copy --destination-relay wss://new-relay.example.com \
  --destination-blossom https://new-blossom.example.com --dry-run
```

Enter the destination nsec, hexadecimal private key, or recovery phrase at the
hidden prompt. The command verifies an existing signed, decryptable destination
configuration (`wallet`, or `wallet_config` when `wallet` is absent), then shows
both public identities. Repeat without `--dry-run` to
copy after confirmation.

If source file locations are missing or out of date, supply one or more explicit
source servers. Stroma's `BlossomPool` races these candidates first, before
trying discovered or stored locations:

```bash
acorn records copy --destination-relay wss://new-relay.example.com \
  --source-blossom https://source-blossom.example.com \
  --source-blossom https://older-blossom.example.com \
  --destination-blossom https://new-blossom.example.com
```

The pool verifies ciphertext digests and confirms destination storage; Acorn
also decrypts the readback and verifies the original content. The pool defaults
to public HTTPS origins and a 25 MiB encrypted-file limit. Private-network HTTPS
servers require `--allow-private-blossom` for trusted deployments. HTTP and URL
paths are not supported by this command.

Downloads must match the source record's ciphertext digest. The first verified
response wins and remaining requests are cancelled. A missing file or digest
mismatch does not prevent another candidate from succeeding; no match means no destination record is
published. Options apply only to this command and do not change saved settings.
Source download errors identify hostnames, not private paths or credentials.

- Copies labeled user records in kind 37375; excludes funds, configuration,
  locks, payment queues, and recovery state. Other record kinds are not included.
- Does not load proofs or run payment recovery, so it can rescue records from an
  account whose financial state is stuck.
- Re-encrypts records to the new identity and regenerates private lookup tags.
- With a destination Blossom server, decrypts and verifies source files, encrypts
  them with fresh AES-256-GCM keys/nonces, then downloads and verifies the new
  files before publishing their records. Plaintext stays in memory.
- Without that option, records with attachments are skipped. Missing files,
  unsupported encryption, unreadable records, and conflicts are reported.
- Preserves signed payloads and plaintext content, not the old ciphertext
  identifiers. Embedded references to old ciphertext are not rewritten, and
  credential holder/issuer authority does not change.
- Leaves the source untouched. Retries recognize verified fresh-key copies;
  existing records are never overwritten, including old copies using old file
  keys. Pause destination writers because relay writes are not atomic.

Review every skipped or failed item and inspect the destination from its own
account. Queries stop on a 10,000-event saturation limit; a relay can still omit
records. This is not an exhaustive archive guarantee. A partial attempt can
leave an uploaded file or an unverified record; rerun the preview before retrying.

Results appear as each record completes. On failure, the next line identifies
the stage and a sanitized reason, for example a source-download HTTP 404, a
missing plaintext digest (`origsha256`), or a destination-upload HTTP 403.
Share the stage/reason lines for diagnosis; do not share private keys, recovery
phrases, raw record JSON, or attachment encryption parameters. Reporting does
not weaken verification or automatically discard an uncertain destination copy.

Moving funds, updating public identity, and changing address registration are
separate operations. New keys cannot revoke access to plaintext or old file keys
someone already obtained.

### Migrating away from a legacy wallet

If a new wallet works but an older wallet cannot finalize incoming payments,
that suggests an account-specific problem; it does not establish the cause.
Possible causes include old operational state, configuration differences, or
another client writing under the same identity. An actively running legacy
client is different from simply having old user records.

Stop legacy workers and clients for the old identity before investigating its
payment state. Keep its private key and recovery records available; do not delete
uncertain payment state merely to make an error disappear. Use `records copy`
to move eligible user records and attachments to a separately initialized wallet,
without transferring the old payment queues, proofs, locks, or recovery journals.
Pause other destination writers while copying, inspect copied records and files
in the new account, and review all skipped or failed results before retiring the
old account. Any remaining funds require separate recovery or transfer.

## 9. Investigate problems before destructive intervention

| Situation | First step | Avoid |
|---|---|---|
| Mint unavailable or verification inconclusive | Restore connectivity; inspect `check-proofs` | Deleting unknown/pending proofs |
| Outgoing Lightning payment unresolved | Inspect `reconcile-payments` | Blindly paying again |
| Proofs conclusively spent | Review `reconcile-proofs` | Treating a timeout as proof of spending |
| Incoming cash awaits confirmation | Inspect `pending-transfers` and mint availability | Using broad relay deletion as a reset |
| Legacy account cannot load normally | Preview `records copy` | Burning the source before rescuing records |
| Wallet appears busy | Stop competing writers and inspect `checklock` | Assuming `releaselock` can unlock another process |

`repair-proofs`, `discard-incompatible-proofs`, and `abandon-transfer` are
operator interventions, not routine cleanup. Abandoning a receipt accepts
possible loss and does not prove the transfer was invalid. Consult the
[command-specific cautions](commands.md) before using them.

## 10. Retire only after verification

Confirm records and attachments are available under the intended account,
resolve outstanding payments, move remaining value deliberately, and keep the
necessary audit/recovery material before considering `burn`.

`delete` requests deletion of a selected record; `--delete-blob` additionally
requests deletion of its file. `deletekind` is much broader. `burn` requests
deletion of selected wallet events and normally removes the local config; its
funds-sweep options are described in the reference. It is not guaranteed secure
erasure of relay backups, third-party copies, or every Blossom object. Do not
delete a shared source file merely because one account has been migrated.
