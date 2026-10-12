# Complete CLI command reference

This reference covers every registered command and subcommand in the current
source tree. Read the [manual](index.md) and [lifecycle](lifecycle.md) first for
account selection, secret handling, payment uncertainty, and migration safety.

The usage blocks are snapshots of Click help, not commands to execute in bulk.
Operational notes explain side effects and known limitations that the older help
strings do not always describe accurately. Command names and option spellings
are checked against the CLI by the documentation coverage test. Review this page
whenever changing command behavior or help. No commands were executed against a
live account to generate these help blocks.

## Index

- [`acorn (global options)`](#global-options)
- [`acorn abandon-transfer`](#abandon-transfer)
- [`acorn accept_token`](#accept-token)
- [`acorn acquirelock`](#acquirelock)
- [`acorn balance`](#balance)
- [`acorn burn`](#burn)
- [`acorn check-proofs`](#check-proofs)
- [`acorn checklock`](#checklock)
- [`acorn claim-deposit`](#claim-deposit)
- [`acorn clear`](#clear)
- [`acorn clear accept`](#clear-accept)
- [`acorn clear balances`](#clear-balances)
- [`acorn clear history`](#clear-history)
- [`acorn create_grant`](#create-grant)
- [`acorn create_request`](#create-request)
- [`acorn delete`](#delete)
- [`acorn delete-ecash-transfers`](#delete-ecash-transfers)
- [`acorn deletekind`](#deletekind)
- [`acorn deposit`](#deposit)
- [`acorn discard-incompatible-proofs`](#discard-incompatible-proofs)
- [`acorn dm`](#dm)
- [`acorn ecash-transfer`](#ecash-transfer)
- [`acorn get`](#get)
- [`acorn get_blob`](#get-blob)
- [`acorn get_follow_posts`](#get-follow-posts)
- [`acorn get_latest_posts`](#get-latest-posts)
- [`acorn get_root_entities`](#get-root-entities)
- [`acorn get_social_profile`](#get-social-profile)
- [`acorn get_trusted_entities`](#get-trusted-entities)
- [`acorn get_user_records`](#get-user-records)
- [`acorn get_wot_entities`](#get-wot-entities)
- [`acorn get_wot_scores`](#get-wot-scores)
- [`acorn inbox-relays`](#inbox-relays)
- [`acorn info`](#info)
- [`acorn init`](#init)
- [`acorn issue_record`](#issue-record)
- [`acorn issue_token`](#issue-token)
- [`acorn mint-transfer`](#mint-transfer)
- [`acorn pay`](#pay)
- [`acorn pending-transfers`](#pending-transfers)
- [`acorn profile`](#profile)
- [`acorn proofs`](#proofs)
- [`acorn publish_kind0`](#publish-kind0)
- [`acorn publish_kind1`](#publish-kind1)
- [`acorn put`](#put)
- [`acorn react`](#react)
- [`acorn receive-clear`](#receive-clear)
- [`acorn receive-ecash`](#receive-ecash)
- [`acorn reconcile-payments`](#reconcile-payments)
- [`acorn reconcile-proofs`](#reconcile-proofs)
- [`acorn records`](#records)
- [`acorn records copy`](#records-copy)
- [`acorn recover`](#recover)
- [`acorn releaselock`](#releaselock)
- [`acorn repair-proofs`](#repair-proofs)
- [`acorn replicate`](#replicate)
- [`acorn reply`](#reply)
- [`acorn run`](#run)
- [`acorn send`](#send)
- [`acorn set`](#set)
- [`acorn set_trusted_entities`](#set-trusted-entities)
- [`acorn set_wot_entities`](#set-wot-entities)
- [`acorn setowner`](#setowner)
- [`acorn stx`](#stx)
- [`acorn swap`](#swap)
- [`acorn txhistory`](#txhistory)
- [`acorn zap`](#zap)

## Global options { #global-options }

Global account selection and logging options. Put `--config` before the command. Help is safe to inspect without initializing an account.

```text
Usage: acorn [OPTIONS] COMMAND [ARGS]...

Options:
  --config TEXT  Path to Acorn config file; defaults to ~/.acorn/config.yml or
                 ACORN_CONFIG
  -v, --verbose  Show debug logs.
  --help         Show this message and exit.

Commands:
  abandon-transfer             Abandon one pending incoming cash receipt,...
  accept_token                 Accept cashu token
  acquirelock                  acquire lock
  balance                      show balance
  burn                         Burn this wallet's relay data and remove...
  check-proofs                 Check proof state at each mint without...
  checklock                    acquire lock
  claim-deposit                Claim proofs from an existing paid mint...
  clear                        Inspect spendable Clear balances and history
  create_grant                 create grant from offer
  create_request               create request from grant
  delete                       request deletion of a private wallet record
  delete-ecash-transfers       Delete direct kind 7378 ecash transfer...
  deletekind                   delete kind records
  deposit                      deposit funds into wallet via lightning...
  discard-incompatible-proofs  Discard non-NUT-00 proof state while...
  dm                           Send message to nip05 address or npub
  ecash-transfer               Send funds to another Acorn
  get                          get a private wallet record
  get_blob                     get blob data from private wallet record
  get_follow_posts             Get latest kind 1 posts from your follow list
  get_latest_posts             Get latest kind 1 posts by nip05 and print...
  get_root_entities            get root entities
  get_social_profile           get wot score
  get_trusted_entities         get trusted_entities
  get_user_records             list private wallet records
  get_wot_entities             get wot entities
  get_wot_scores               get wot score
  inbox-relays                 Show or publish external NIP-17 inbox...
  info                         This is the help for the acorn info command.
  init                         initialize a new acorn wallet
  issue_record                 Issue private record
  issue_token                  Issue token amount
  mint-transfer                transfer funds from one mint to another...
  pay                          Payout funds to lightning address
  pending-transfers            List provisional incoming cash receipts...
  profile                      get profile
  proofs                       list proofs
  publish_kind0                Publish NIP-01 kind 0 metadata event
  publish_kind1                Publish NIP-01 kind 1 text note
  put                          write a private record
  react                        Publish NIP-25 reaction (kind 7) to an event
  receive-clear                Store incoming Clear token transfers as...
  receive-ecash                Receive incoming funds transfers into this...
  reconcile-payments           Resume pending Lightning payment...
  reconcile-proofs             Remove only proofs conclusively reported...
  records                      Record-only migration; does not load or...
  recover                      Recover a wallet from a privately entered...
  releaselock                  release lock
  repair-proofs                Prune spent proofs and rewrite wallet...
  replicate                    replicate this wallet's signed events to a...
  reply                        Publish a kind 1 reply to an event
  run                          run as a service
  send                         Send amount to nip05 address or npub
  set                          set local config options
  set_trusted_entities         set trusted_entities
  set_wot_entities             set wot entities npub:tag:relay
  setowner                     get profile
  stx                          Send secure transmitta to nip05 address or...
  swap                         swap proofs for new proofs
  txhistory                    transaction history
  zap                          Zap amount to event or to recipient
```

## acorn abandon-transfer { #abandon-transfer }

Destructive financial intervention: marks one pending incoming cash receipt abandoned, removes its stored token, and retains its event ID to prevent ordinary rediscovery. Requires interactive confirmation and a reason can be supplied. It does not delete wallet proofs or swap-recovery state. Stop other processing of the receipt first; loss is possible.

```text
Usage: acorn abandon-transfer [OPTIONS] EVENT_ID

  Abandon one pending incoming cash receipt, accepting potential loss.

Options:
  --reason TEXT  [default: Owner abandoned test transfer and accepted
                 potential loss.]
  --help         Show this message and exit.
```

## acorn accept_token { #accept-token }

Accepts a Cashu token, including supported cashuA/cashuB encodings. The token is bearer value and this positional argument may appear in process listings or shell history. This changes wallet state.

```text
Usage: acorn accept_token [OPTIONS] TOKEN

  Accept cashu token

Options:
  --help  Show this message and exit.
```

## acorn acquirelock { #acquirelock }

Advanced diagnostic lease acquisition in this CLI process. A lease belongs to its acquiring context; this is not a general cross-process maintenance lock or a recommended way to pause other clients.

```text
Usage: acorn acquirelock [OPTIONS]

  acquire lock

Options:
  --help  Show this message and exit.
```

## acorn balance { #balance }

Shows relay-loaded cash balances, optionally grouped by mint/keyset. `--verify` adds mint proof-state checks and payment-capacity information; it does not request proof repair. The CLI first loads wallet state, which can perform maintenance. Inconclusive verification is not permission to discard funds.

```text
Usage: acorn balance [OPTIONS]

  show balance

Options:
  --json    Emit JSON output.
  --mints   Show balance grouped by mint and keyset.
  --verify  Read-only check of each proof at its mint.
  --help    Show this message and exit.
```

## acorn burn { #burn }

Retirement operation requesting relay-data deletion and normally removing local configuration. Optional sweep/payment flags can move remaining cash first. `--allow-funded` explicitly permits potential loss and `--force` bypasses confirmations. Verify records, attachments, funds, pending operations, event kinds, and relay coverage before using it. It is not comprehensive Blossom deletion or guaranteed secure erasure.

An ecash sweep with `--send-to` reserves mint input fees rather than issuing the
gross balance. It requires a single keyset and stops before deletion if fees
consume the balance, the sweep fails, balance readback fails, or funds remain.
If a transfer was already published when readback fails, inspect that transfer
and the remaining wallet state before retrying; do not assume nothing happened.

```text
Usage: acorn burn [OPTIONS]

  Burn this wallet's relay data and remove local wallet config

Options:
  --send-to TEXT        NIP-05/npub/pubkey recipient for remaining funds
                        before burn
  --send-relay TEXT     Relay to publish the optional funds sweep transfer
  --pay-to TEXT         Lightning address recipient for remaining funds before
                        burn
  --pay-amount INTEGER  Lightning amount in sats; defaults to the maximum
                        amount that fits mint fees
  --relay TEXT          Comma-separated relays to burn from; defaults to home
                        relay
  --kinds TEXT          Comma-separated event kinds to burn; defaults to Acorn
                        wallet/data kinds
  --allow-funded        Burn even if funds remain and no sweep/payment
                        recipient is provided
  --keep-local-config   Do not remove the local Acorn config file after burn
  --limit INTEGER       Maximum events to query for deletion  [default: 1024]
  -f, --force           Bypass confirmation prompts
  --json                Emit JSON output
  --help                Show this message and exit.
```

## acorn check-proofs { #check-proofs }

Checks each proof at its mint; the check itself does not mutate proof state. The CLI loads wallet data first. Do not interpret pending, unknown, unreachable, or rate-limited states as spent.

```text
Usage: acorn check-proofs [OPTIONS]

  Check proof state at each mint without changing the wallet

Options:
  --json  Emit JSON output.
  --help  Show this message and exit.
```

## acorn checklock { #checklock }

Inspects wallet lock state after wallet loading; the short help incorrectly says “acquire lock.” It does not intentionally acquire a new lease.

```text
Usage: acorn checklock [OPTIONS]

  acquire lock

Options:
  --help  Show this message and exit.
```

## acorn claim-deposit { #claim-deposit }

Claims proofs for an existing quote from the specified mint without creating another invoice. Supply the exact quote, amount in sats, and issuing mint.

```text
Usage: acorn claim-deposit [OPTIONS] QUOTE AMOUNT

  Claim proofs from an existing paid mint quote without creating a new
  invoice.

Options:
  -m, --mint TEXT  Mint that issued the quote  [required]
  --help           Show this message and exit.
```

## acorn clear { #clear }

Clear-credit command group. Discovery is handled by `receive-clear`; acceptance and spendable state are handled by these subcommands.

```text
Usage: acorn clear [OPTIONS] COMMAND [ARGS]...

  Inspect spendable Clear balances and history

Options:
  --help  Show this message and exit.

Commands:
  accept    Accept a pending Clear transfer
  balances  Show spendable Clear balances
  history   Show append-only Clear transaction history
```

## acorn clear accept { #clear-accept }

Accepts the pending Clear transfer identified by its full event ID through its issuing mint. Requires access to that mint and writes proof/history state.

```text
Usage: acorn clear accept [OPTIONS] EVENT_ID

  Accept a pending Clear transfer

Options:
  --json  Emit JSON output.
  --help  Show this message and exit.
```

## acorn clear balances { #clear-balances }

Displays spendable Clear balances by their mint/unit context. Pending receipts are not equivalent to spendable Clear proofs.

```text
Usage: acorn clear balances [OPTIONS]

  Show spendable Clear balances

Options:
  --json  Emit JSON output.
  --help  Show this message and exit.
```

## acorn clear history { #clear-history }

Reads append-only Clear history with optional mint, canonical CMU, direction, and operation filters. It is separate from cash `txhistory`.

```text
Usage: acorn clear history [OPTIONS]

  Show append-only Clear transaction history

Options:
  --mint TEXT                     Filter by exact mint URL.
  --unit TEXT                     Filter by canonical CMU.
  --direction [in|out]
  --operation [accept|send|receive|retire|repair]
  --json                          Emit JSON output.
  --help                          Show this message and exit.
```

## acorn create_grant { #create-grant }

Advanced offer-to-grant workflow. Supply offer kind, offer label, and holder identity explicitly. The library expects an odd addressable offer kind; the usual grant kind is offer kind plus one. Can create signed records and move associated attachment representations.

```text
Usage: acorn create_grant [OPTIONS] OFFER_NAME HOLDER

  create grant from offer

Options:
  -o, --offer INTEGER  offer kind
  -g, --grant TEXT     grant kind, if not provided it default to offer_kind+1
  --help               Show this message and exit.
```

## acorn create_request { #create-request }

Advanced request creation from a grant record. Supply the correct grant kind and label. This is an application record workflow, not a Cashu payment-request creation command.

```text
Usage: acorn create_request [OPTIONS] GRANT_NAME

  create request from grant

Options:
  -g, --grant INTEGER  grant kind
  --help               Show this message and exit.
```

## acorn delete { #delete }

Requests deletion of one record, prompting unless `--yes` is supplied. `--delete-blob` additionally requests deletion of its attachment. Check whether another record still depends on the same file. Deletion requests do not guarantee erasure from every relay or backup.

```text
Usage: acorn delete [OPTIONS] [LABEL]

  request deletion of a private wallet record

Options:
  -k, --kind INTEGER
  -o, --origin TEXT
  -r, --relays TEXT   Relays that are used to read posts and profiles.
  --delete-blob       Also request deletion of an associated encrypted blob.
  -y, --yes           Skip the deletion confirmation.
  --json              Emit JSON output.
  --help              Show this message and exit.
```

## acorn delete-ecash-transfers { #delete-ecash-transfers }

Requests deletion of direct kind 7378 transfer events authored by this Acorn, optionally narrowed by recipient and timestamps. It is not the command for clearing incoming provisional receipts or gift-wrapped transfer state.

```text
Usage: acorn delete-ecash-transfers [OPTIONS]

  Delete direct kind 7378 ecash transfer events authored by this Acorn

Options:
  -r, --relay TEXT  Relay to delete transfer events from; defaults to home
                    relay
  --recipient TEXT  Only delete transfers addressed to this nip05, npub, or
                    pubkey
  --since INTEGER   Only match transfer events since this timestamp
  --until INTEGER   Only match transfer events until this timestamp
  --limit INTEGER   Maximum transfer events to query
  -y, --yes         Skip confirmation prompt
  --json            Emit JSON output
  --help            Show this message and exit.
```

## acorn deletekind { #deletekind }

Broad deletion request for records of the selected kind. This older command prompts, but has no per-record preview. Its default kind is 30000; always choose the intended kind explicitly and understand what it contains.

```text
Usage: acorn deletekind [OPTIONS]

  delete kind records

Options:
  -k, --kind INTEGER
  --help              Show this message and exit.
```

## acorn deposit { #deposit }

Creates a Lightning mint quote, prints the invoice and QR, then waits for Enter before polling for about one minute. Keep the quote identifier, amount, and mint if it times out. Do not automatically pay another invoice; use `claim-deposit` for an existing paid quote.

```text
Usage: acorn deposit [OPTIONS] AMOUNT

  deposit funds into wallet via lightning invoice

Options:
  -m, --mint TEXT  deposit mint
  --help           Show this message and exit.
```

## acorn discard-incompatible-proofs { #discard-incompatible-proofs }

Permanent discard of incompatible non-NUT-00 proof state. Requires the exact acknowledged sat amount and records a reason. This is not a fix for a temporarily unavailable mint.

```text
Usage: acorn discard-incompatible-proofs [OPTIONS]

  Discard non-NUT-00 proof state while preserving this Acorn and its records.

Options:
  --confirm-amount INTEGER RANGE  Exact incompatible sat amount acknowledged
                                  for permanent discard.  [x>=1; required]
  --reason TEXT                   Audit note written to transaction history.
                                  [default: NUT-00 development reset]
  --json                          Emit JSON output.
  --help                          Show this message and exit.
```

## acorn dm { #dm }

Sends a private message to a NIP-05 address or npub using recipient inbox discovery unless relays are explicitly overridden. Supply recipient and message; neither encrypted delivery nor a successful publish proves the recipient has read it.

```text
Usage: acorn dm [OPTIONS] [NRECIPIENT] [MESSAGE]

  Send message to nip05 address or npub

Options:
  -r, --relays TEXT  Comma-separated relay override; default: discover
                     recipient inbox.
  --help             Show this message and exit.
```

## acorn ecash-transfer { #ecash-transfer }

Sends funds to another Acorn using the dedicated transfer flow. Gift wrapping is the default; `--direct` deliberately publishes a sender-authored direct event and exposes more metadata. Expiration is a relay hint, not a refund or a guarantee that delivered value becomes unspendable.

```text
Usage: acorn ecash-transfer [OPTIONS] AMOUNT RECIPIENT

  Send funds to another Acorn

Options:
  -r, --relay TEXT            relay to publish the transfer to; defaults to
                              home relay
  -c, --comment TEXT          transfer comment
  --direct                    Publish direct sender-authored NIP-44 event
                              instead of default gift-wrapped event
  --expires-in INTEGER RANGE  Add a NIP-40 expiration tag this many seconds
                              from now  [x>=1]
  --json                      Emit JSON output.
  --help                      Show this message and exit.
```

## acorn get { #get }

Retrieves a private record with optional kind, origin, and relay selection. `--raw` prints the record object; `--json` requests structured output. Output can contain private content and attachment decryption metadata.

```text
Usage: acorn get [OPTIONS] [LABEL]

  get a private wallet record

Options:
  -k, --kind INTEGER
  -o, --origin TEXT
  -r, --relays TEXT   Relays that are used to read posts and profiles.
  --raw               Print the raw record object.
  --json              Emit JSON output.
  --help              Show this message and exit.
```

## acorn get_blob { #get-blob }

Retrieves/decrypts the attachment associated with a private record. The current CLI prints its media type only: it has no output-file option and does not export the file to disk.

```text
Usage: acorn get_blob [OPTIONS] [LABEL]

  get blob data from private wallet record

Options:
  -k, --kind INTEGER
  -o, --origin TEXT
  -r, --relays TEXT   Relays that are used to read posts and profiles.
  --help              Show this message and exit.
```

## acorn get_follow_posts { #get-follow-posts }

Retrieves recent public posts from the account's follow list. This CLI currently has no dedicated follow/unfollow command, even though the library has contact-list APIs.

```text
Usage: acorn get_follow_posts [OPTIONS]

  Get latest kind 1 posts from your follow list

Options:
  -l, --limit INTEGER  maximum number of posts to return
  -r, --relays TEXT    comma-separated relay list to override defaults
  --help               Show this message and exit.
```

## acorn get_latest_posts { #get-latest-posts }

Retrieves recent public kind 1 posts for a NIP-05 identity, bounded by the requested limit and relays.

```text
Usage: acorn get_latest_posts [OPTIONS] NIP05

  Get latest kind 1 posts by nip05 and print post content

Options:
  -l, --limit INTEGER  maximum number of posts to return
  -r, --relays TEXT    comma-separated relay list to override defaults
  --help               Show this message and exit.
```

## acorn get_root_entities { #get-root-entities }

Reads the root-entity trust information used by the account.

```text
Usage: acorn get_root_entities [OPTIONS]

  get root entities

Options:
  --help  Show this message and exit.
```

## acorn get_social_profile { #get-social-profile }

Looks up a public profile, despite its short help saying “get wot score.” Supply an explicit `--relays` value: the current legacy implementation does not initialize its relay list when the option is omitted.

```text
Usage: acorn get_social_profile [OPTIONS] [NPUB]

  get wot score

Options:
  -r, --relays TEXT
  --help             Show this message and exit.
```

## acorn get_trusted_entities { #get-trusted-entities }

Reads the configured trusted-entity list. A listed entity is a policy input, not a universal guarantee about its statements.

```text
Usage: acorn get_trusted_entities [OPTIONS]

  get trusted_entities

Options:
  --help  Show this message and exit.
```

## acorn get_user_records { #get-user-records }

Lists private records, optionally labels only, raw objects, or JSON. `--since` is expressed in hours, unlike the receive commands' timestamp options. Private record content may appear in output.

```text
Usage: acorn get_user_records [OPTIONS]

  list private wallet records

Options:
  -k, --kind INTEGER
  -s, --since TEXT    since in hours
  -r, --relays TEXT   Relays that are used to read posts and profiles.
  --labels            print record labels only
  --raw               print raw record objects
  --json              Emit JSON output.
  --help              Show this message and exit.
```

## acorn get_wot_entities { #get-wot-entities }

Reads the configured Web-of-Trust sources.

```text
Usage: acorn get_wot_entities [OPTIONS]

  get wot entities

Options:
  --help  Show this message and exit.
```

## acorn get_wot_scores { #get-wot-scores }

Queries scores for a supplied public key from configured trust sources, including addressable kind 30382 records. Scores depend on the selected sources and are not intrinsic identity properties.

```text
Usage: acorn get_wot_scores [OPTIONS] [PUBKEY]

  get wot score

Options:
  -r, --relays TEXT
  --help             Show this message and exit.
```

## acorn inbox-relays { #inbox-relays }

Without positional relays, discovers this identity's signed kind 10050 inbox announcement. With relays, publishes a replacement announcement. `--publish-relay` can be repeated. Advertise addresses reachable by intended senders; this does not register a NIP-05 address.

```text
Usage: acorn inbox-relays [OPTIONS] [INBOX_RELAYS]...

  Show or publish external NIP-17 inbox relays for token delivery

Options:
  --publish-relay TEXT  Relay on which to publish or discover the kind 10050
                        record.
  --json                Emit JSON output.
  --help                Show this message and exit.
```

## acorn info { #info }

Displays component/account information; it is not a mint-confirmed balance check. Use `--json` for structured output.

```text
Usage: acorn info [OPTIONS]

  This is the help for the acorn info command.

  Acorn release is: v0.1.0.

  The info function displays general information and confirms that the command
  line interface is working properly.

Options:
  --json  Emit JSON output.
  --help  Show this message and exit.
```

## acorn init { #init }

Creates or initializes an account and writes local bootstrap configuration. Existing-account replacement is sensitive. Use hidden import/entropy prompts rather than command-line secrets; `--include-recovery` deliberately exposes secrets in JSON. Back up the relay and derivation mode as well as the key.

```text
Usage: acorn init [OPTIONS]

  initialize a new acorn wallet

Options:
  --import-nsec         Import an existing nsec through a hidden prompt.
  --nsec-file PATH      Read an existing nsec from a chmod-600 file, or '-'
                        for stdin.
  --entropy             Initialize from externally generated 256-bit entropy
                        entered at a hidden prompt.
  --words 12|24         Generate a 12- or 24-word BIP39 offline mnemonic
                        (default: 12).
  -h, --homerelay TEXT  The home relay is where Acorn wallet and record events
                        are published to and retrieved from. Be sure to use a
                        relay that you trust for availability. Relay operators
                        cannot see your encrypted data but may decide to block
                        your access. Be ready to replicate your data should
                        your home relay become unreliable or adversarial.
  -m, --mint TEXT       home mint
  -k, --keepkey         Keep existing key(nsec).
  -f, --force           Bypass safety confirmations and use defaults for
                        omitted values.
  --json                Emit JSON output.
  --include-recovery    Include the seed phrase and nsec in JSON output.
                        Requires --json.
  --help                Show this message and exit.
```

## acorn issue_record { #issue-record }

Experimental/developer command, not a production issuance workflow. The current handler passes a `tags` keyword not accepted by `issue_private_record`, so it can fail before issuance. It also uses a fixed “test credential” record name. Documented for completeness; use a reviewed application/library issuance flow instead.

```text
Usage: acorn issue_record [OPTIONS] [CONTENT]

  Issue private record

Options:
  -t, --tags TEXT
  -k, --kind INTEGER  kind for record
  --help              Show this message and exit.
```

## acorn issue_token { #issue-token }

Issues a bearer token for the requested amount. It exports spendable value rather than merely displaying a balance. Protect the printed token and do not issue a second token merely because delivery of the first is uncertain.

```text
Usage: acorn issue_token [OPTIONS] [AMOUNT]

  Issue token amount

Options:
  --help  Show this message and exit.
```

## acorn mint-transfer { #mint-transfer }

Moves cash value between mints over Lightning. An explicit amount or `--full-amount` is required by the workflow. Full amount means the largest eligible source keyset minus fees, not necessarily every proof across the wallet. This spends value and can incur fees.

```text
Usage: acorn mint-transfer [OPTIONS] SOURCE_MINT DESTINATION_MINT [AMOUNT]

  transfer funds from one mint to another over Lightning

Options:
  --full-amount  Transfer the largest source-mint keyset amount minus
                 Lightning fees.
  --json         Emit JSON output.
  --help         Show this message and exit.
```

## acorn pay { #pay }

Pays a Lightning address using the selected account. Supply amount and recipient explicitly; do not rely on optional positional defaults. Fees and the available mint/keyset constrain payment capacity. This can send funds immediately.

```text
Usage: acorn pay [OPTIONS] [AMOUNT] [LNADDRESS]

  Payout funds to lightning address

Options:
  -c, --comment TEXT
  --help              Show this message and exit.
```

## acorn pending-transfers { #pending-transfers }

Lists provisional incoming cash receipts without contacting mints or loading wallet proofs. JSON omits bearer tokens. Use the full event ID for a subsequent targeted intervention.

```text
Usage: acorn pending-transfers [OPTIONS]

  List provisional incoming cash receipts without contacting mints.

Options:
  --json  Emit token-free JSON output.
  --help  Show this message and exit.
```

## acorn profile { #profile }

Reads the Acorn profile using the selected wallet name. This older command loads wallet data and calls an ecash receive helper; it is not a guaranteed read-only metadata query. `--force` can create a profile. Its `--name` help currently repeats relay guidance; the option actually selects a profile name.

```text
Usage: acorn profile [OPTIONS]

  get profile

Options:
  -n, --name TEXT  The home relay is where Acorn wallet and record events are
                   published to and retrieved from. Be sure to use a relay
                   that you trust for availability. Relay operators cannot see
                   your encrypted data but may decide to block your access. Be
                   ready to replicate your data should your home relay become
                   unreliable or adversarial.
  -f, --force      Force creation of profile.
  --help           Show this message and exit.
```

## acorn proofs { #proofs }

Displays proof identifiers, amounts, commitment information, keyset groups, and known mints after wallet loading. Treat this as private operational metadata, not a public diagnostic report.

```text
Usage: acorn proofs [OPTIONS]

  list proofs

Options:
  --help  Show this message and exit.
```

## acorn publish_kind0 { #publish-kind0 }

Publishes public Nostr profile metadata. Values, including extra JSON fields, are public; never put recovery material or private record data here.

```text
Usage: acorn publish_kind0 [OPTIONS]

  Publish NIP-01 kind 0 metadata event

Options:
  --name TEXT          profile name
  --about TEXT         short bio
  --picture TEXT       profile picture URL
  --display-name TEXT  display name
  --nip05 TEXT         nip05 identifier
  --banner TEXT        banner URL
  --website TEXT       website URL
  --lud16 TEXT         lightning address
  --extra-json TEXT    extra metadata fields as JSON object
  -r, --relays TEXT    comma-separated relay list override
  --help               Show this message and exit.
```

## acorn publish_kind1 { #publish-kind1 }

Publishes a public text note to the selected relays. It is not an encrypted direct message.

```text
Usage: acorn publish_kind1 [OPTIONS] CONTENT

  Publish NIP-01 kind 1 text note

Options:
  -r, --relays TEXT  comma-separated relay list override
  --help             Show this message and exit.
```

## acorn put { #put }

Writes an encrypted private record, optionally with a file attachment. Supply a nonreserved label and payload explicitly; the legacy default label `default` is reserved and is not a useful example. Reusing a label can replace its record. The CLI loads wallet data before prompting for the write. Private argument text may remain in shell history.

```text
Usage: acorn put [OPTIONS] [LABEL] [LABEL_INFO]

  write a private record

Options:
  -k, --kind INTEGER
  -o, --origin TEXT
  -f, --file TEXT
  -r, --relays TEXT   Relays that are used to read posts and profiles.
  --help              Show this message and exit.
```

## acorn react { #react }

Publishes a public reaction with target-event metadata and optional custom tags. Supplied tags are part of the public event.

```text
Usage: acorn react [OPTIONS] EVENT_ID

  Publish NIP-25 reaction (kind 7) to an event

Options:
  -c, --content TEXT      reaction content, default heart emoji
  --pubkey TEXT           reacted event author pubkey (npub or hex)
  --kind INTEGER          reacted event kind
  --relay-hint TEXT       relay hint for the e/p tags
  --a-tag TEXT            optional addressable event coordinate
  --extra-tags-json TEXT  optional extra tags as JSON array of arrays
  -r, --relays TEXT       comma-separated relay list override
  --help                  Show this message and exit.
```

## acorn receive-clear { #receive-clear }

Discovers Clear transfers and stores pending receipts; discovery alone is not mint acceptance. Use `clear accept EVENT_ID` afterward. `--preview` avoids storing receipts and advancing the cursor; `--no-advance` controls only cursor advancement. A local-only mint may require running acceptance inside its reachable network.

```text
Usage: acorn receive-clear [OPTIONS]

  Store incoming Clear token transfers as pending receipts

Options:
  --since INTEGER            Override the Clear transfer cursor.
  -r, --relay TEXT           Relay to sweep for incoming kind 1059 gift wraps.
  --page-size INTEGER RANGE  Maximum relay events requested per page.
                             [default: 1024; x>=1]
  --max-pages INTEGER RANGE  Maximum relay pages read in one receive
                             operation.  [default: 100; x>=1]
  --receive-key              Prompt privately for a transient receiving nsec;
                             it is not stored.
  --receive-nsec-file PATH   Read a transient receiving nsec from a chmod-600
                             file, or '-' for stdin.
  --event-id TEXT            Receive a specific kind 1059 gift-wrap event id;
                             bypasses recipient tag and cursor query.
  --no-advance               Do not advance the stored Clear receive cursor.
  --preview                  Show pending Clear transfers without storing
                             receipts or advancing the cursor.
  --json                     Emit JSON output.
  --help                     Show this message and exit.
```

## acorn receive-ecash { #receive-ecash }

Discovers incoming cash transfers and, outside preview, processes them into wallet receipt/proof state. `--preview` does not accept proofs or advance the receive cursor. `--no-advance` only controls the cursor; it is not a preview. Transient receiving keys are not stored. Targeted event lookup and pagination are recovery tools; check results before rerunning large sweeps.

```text
Usage: acorn receive-ecash [OPTIONS]

  Receive incoming funds transfers into this Acorn

Options:
  --since INTEGER            Override the incoming funds transfer cursor.
  -r, --relay TEXT           Relay to sweep for incoming kind 1059 gift wraps
                             or direct kind 7378 transfers.
  --page-size INTEGER RANGE  Maximum relay events requested per page.
                             [default: 1024; x>=1]
  --max-pages INTEGER RANGE  Maximum relay pages read in one receive
                             operation.  [default: 100; x>=1]
  --receive-key              Prompt privately for a transient receiving nsec;
                             it is not stored.
  --receive-nsec-file PATH   Read a transient receiving nsec from a chmod-600
                             file, or '-' for stdin.
  --event-id TEXT            Receive a specific kind 1059 gift-wrap or direct
                             kind 7378 event id; bypasses recipient tag and
                             cursor query.
  --no-advance               Do not advance the stored receive cursor.
  --preview                  Show pending incoming funds without accepting
                             proofs or advancing the cursor.
  --json                     Emit JSON output.
  --help                     Show this message and exit.
```

## acorn reconcile-payments { #reconcile-payments }

Resumes reconciliation of pending outgoing Lightning payments. Check status before sending the same payment again; uncertainty does not mean nonpayment.

```text
Usage: acorn reconcile-payments [OPTIONS]

  Resume pending Lightning payment reconciliation

Options:
  --json  Emit JSON output.
  --help  Show this message and exit.
```

## acorn reconcile-proofs { #reconcile-proofs }

Mutates relay proof state by removing only proofs conclusively reported as spent. Preserve uncertain proofs and investigate mint availability instead of forcing removal.

```text
Usage: acorn reconcile-proofs [OPTIONS]

  Remove only proofs conclusively reported as spent by their mints.

Options:
  --json  Emit JSON output.
  --help  Show this message and exit.
```

## acorn records { #records }

Record-only migration command group. Use `records copy --help` for the actual copy operation.

```text
Usage: acorn records [OPTIONS] COMMAND [ARGS]...

  Record-only migration; does not load or transfer funds.

Options:
  --help  Show this message and exit.

Commands:
  copy
```

## acorn records copy { #records-copy }

Copies labeled user records in kind 37375 to a different, already initialized Acorn. Prompts privately for the destination key or phrase, verifies the target configuration, and previews records before confirmation. `--dry-run` writes nothing. Attachments require `--destination-blossom` and are decrypted, verified, and freshly encrypted; otherwise attachment-bearing records are skipped. Conflicts are never overwritten, source state is untouched, and funds/configuration/recovery journals are excluded. See the lifecycle migration section for completeness and retry limitations.

Run this command from the source account. For example, preview a migration
including files stored on current or older Blossom servers:

```bash
acorn records copy \
  --destination-relay wss://spurline.safebox.dev \
  --source-blossom https://grove.safebox.dev \
  --source-blossom https://blossom.getsafebox.app \
  --destination-blossom https://grove.safebox.dev \
  --dry-run
```

Enter the destination private key or recovery phrase at the hidden prompt;
do not put it on the command line. Check both public identities and the preview,
then repeat without `--dry-run` and confirm to copy.

Stroma's `BlossomPool` queries explicit source candidates concurrently, accepts
the first digest-verified response, and cancels remaining requests. If that
group fails, it tries stored/discovered locations. Acorn still verifies decrypted
content and freshly encrypted destination readback before publishing the record.
This is concurrent retrieval, not a race between wallet writers.

Use HTTPS origins without paths, credentials, queries, or fragments. The pool
limits encrypted files to 25 MiB. For a trusted private-network HTTPS deployment,
add `--allow-private-blossom`; plain HTTP remains disabled. These options do not
change saved account configuration. See [the migration lifecycle](lifecycle.md#8-migrate-private-records-to-a-new-identity)
for retry handling and legacy-wallet precautions.

```text
Usage: acorn records copy [OPTIONS]

Options:
  --destination-relay TEXT    Existing destination wallet's home relay.
                              [required]
  --destination-blossom TEXT  Copy attachments to this HTTPS Blossom server.
  --allow-private-blossom     Allow private-network HTTPS Blossom endpoints for
                             a trusted local deployment.
  --source-blossom TEXT       Try this HTTPS source server before stored
                             locations; repeat for multiple servers.
  --legacy                    Use Acorn's legacy recovery-phrase derivation.
  --dry-run                   Verify identities and preview; write nothing.
  --help                      Show this message and exit.
```

## acorn recover { #recover }

Restores bootstrap configuration using a privately entered phrase and the relay holding the account. `--legacy` selects the older derivation; no additional BIP39 passphrase is supported. A seed supplied through stdin requires `--yes`, because stdin cannot also answer confirmation. It loads the recovered wallet; it is not an offline key derivation utility.

```text
Usage: acorn recover [OPTIONS]

  Recover a wallet from a privately entered seed phrase

Options:
  --seed-file PATH      Read the seed phrase from a chmod-600 file, or '-' for
                        stdin
  -h, --homerelay TEXT
  --legacy              Use legacy key derivation (default: False)
  -y, --yes             Skip the recovery confirmation; required with --seed-
                        file '-'
  --help                Show this message and exit.
```

## acorn releaselock { #releaselock }

Attempts release by the current Acorn context. A fresh CLI invocation does not own another process's lease; this is not a force-unlock command. Stop competing writers and allow lease expiry rather than deleting lock state blindly.

```text
Usage: acorn releaselock [OPTIONS]

  release lock

Options:
  --help  Show this message and exit.
```

## acorn repair-proofs { #repair-proofs }

Operator repair that can rewrite proof state. `--refresh` performs irreversible mint swaps and requires `--confirm-refresh`; `--force` permits an empty result when no usable proofs survive. Neither flag makes uncertain funds safe to discard.

```text
Usage: acorn repair-proofs [OPTIONS]

  Prune spent proofs and rewrite wallet proof state

Options:
  -f, --force        Allow repair to clear the wallet if no usable proofs
                     survive
  --refresh          Refresh all proofs even when check-proofs reports clean
                     state.
  --confirm-refresh  Acknowledge that refresh performs irreversible mint
                     swaps.
  --help             Show this message and exit.
```

## acorn replicate { #replicate }

Copies the same signed events to another relay without changing keys or record identifiers. Inspect the event-kind selection and limit. It does not copy Blossom files or automatically switch the home relay; use `records copy` to migrate to a different identity.

```text
Usage: acorn replicate [OPTIONS]

  replicate this wallet's signed events to a target relay

Options:
  -t, --target TEXT    target relay to copy wallet events to  [required]
  -s, --source TEXT    source relay; defaults to home_relay
  -k, --kinds TEXT     comma-separated event kinds; defaults to core Acorn
                       wallet kinds
  -l, --limit INTEGER  maximum events to query from the source relay
  -y, --yes            skip confirmation prompt
  --json               Emit JSON output.
  --help               Show this message and exit.
```

## acorn reply { #reply }

Publishes a public reply to an event. Optional author, kind, relay hint, and tags describe the target; they do not make the reply private.

```text
Usage: acorn reply [OPTIONS] EVENT_ID CONTENT

  Publish a kind 1 reply to an event

Options:
  --pubkey TEXT           target event author pubkey (npub or hex)
  --kind INTEGER          target event kind
  --relay-hint TEXT       relay hint for reply tags
  --extra-tags-json TEXT  optional extra tags as JSON array of arrays
  -r, --relays TEXT       comma-separated relay list override
  --help                  Show this message and exit.
```

## acorn run { #run }

Older service entry point using the supplied relay list. It loads wallet data and starts the library service; it is not Safebox Web's worker, a scheduler, or an LLM agent loop. Treat deployment/supervision as an application-specific concern.

```text
Usage: acorn run [OPTIONS]

  run as a service

Options:
  -r, --relays TEXT
  --help             Show this message and exit.
```

## acorn send { #send }

Older generic token-send path: issues a token and sends it through secure transmittal. Prefer `ecash-transfer` for the dedicated Acorn transfer workflow. Issuance can succeed before delivery fails; investigate before retrying.

```text
Usage: acorn send [OPTIONS] [AMOUNT] [NRECIPIENT]

  Send amount to nip05 address or npub

Options:
  -c, --comment TEXT
  -r, --relays TEXT
  --help              Show this message and exit.
```

## acorn set { #set }

Shows redacted local settings when called without options; options can change local configuration and some relay-backed preferences. `--show-recovery` deliberately displays secrets after confirmation. Changing the key or home relay is not a migration of records or files.

```text
Usage: acorn set [OPTIONS]

  set local config options

Options:
  --import-nsec         Replace the nsec through a hidden, confirmed prompt
  --nsec-file PATH      Read replacement nsec from a chmod-600 file, or '-'
                        for stdin
  -r, --relays TEXT     Relays that are used to read posts and profiles.
  -h, --home TEXT       The home relay is where Acorn wallet and record events
                        are published to and retrieved from. Be sure to use a
                        relay that you trust for availability. Relay operators
                        cannot see your encrypted data but may decide to block
                        your access. Be ready to replicate your data should
                        your home relay become unreliable or adversarial.
  -m, --mints TEXT      The mints that are used by Acorn. The first mint
                        specified in the list is the home mint.
  -x, --xrelays TEXT    set replicate relays
  --public-relays TEXT  store preferred public relays as an encrypted reserved
                        record
  --show-public-relays  show preferred public relays from encrypted reserved
                        record
  --show-mint           show effective home mint from wallet data
  --show-recovery       show recovery information: seed phrase and home relay
  -l, --logging TEXT    set logging level
  --minimal             rewrite config with only nsec and home_relay
  --help                Show this message and exit.
```

## acorn set_trusted_entities { #set-trusted-entities }

Updates the private trusted-entity list. Supply the intended list explicitly rather than the legacy default placeholder; this changes local trust policy records.

```text
Usage: acorn set_trusted_entities [OPTIONS] [TRUSTED_ENTITIES]

  set trusted_entities

Options:
  --help  Show this message and exit.
```

## acorn set_wot_entities { #set-wot-entities }

Updates Web-of-Trust entity configuration using the implementation's `npub:tag:relay` representation. This changes which sources are consulted; validate the supplied identities and endpoints.

```text
Usage: acorn set_wot_entities [OPTIONS] [WOT_ENTITIES]

  set wot entities npub:tag:relay

Options:
  --help  Show this message and exit.
```

## acorn setowner { #setowner }

Updates owner npub and local currency metadata. Despite the short help saying “get profile,” this is a write operation. It does not transfer control of the signing key.

```text
Usage: acorn setowner [OPTIONS]

  get profile

Options:
  -o, --owner TEXT     set owner npub
  -c, --currency TEXT  set local currency
  --help               Show this message and exit.
```

## acorn stx { #stx }

Advanced generic secure-transmittal command with selectable event kind. It is not the same contract as `dm` or a dedicated payment request. The current command echoes message text, and positional content can also appear in shell history.

```text
Usage: acorn stx [OPTIONS] [NRECIPIENT] [MESSAGE]

  Send secure transmitta to nip05 address or npub

Options:
  -r, --relays TEXT
  -k, --kind INTEGER
  --help              Show this message and exit.
```

## acorn swap { #swap }

Swaps proofs for fresh proofs; `--consolidate` requests consolidation. This is a financial state change involving mint operations, not a harmless formatting command.

```text
Usage: acorn swap [OPTIONS]

  swap proofs for new proofs

Options:
  -c, --consolidate  Consolidate proofs
  --help             Show this message and exit.
```

## acorn txhistory { #txhistory }

Reads cash transaction history. This is distinct from `clear history` and from mint proof-state verification.

```text
Usage: acorn txhistory [OPTIONS]

  transaction history

Options:
  --json  Emit JSON output.
  --help  Show this message and exit.
```

## acorn zap { #zap }

Sends a Lightning zap to an event or recipient with an optional comment and relay search overrides. This spends value; inspect recipient resolution and amount.

```text
Usage: acorn zap [OPTIONS] [AMOUNT] EVENT

  Zap amount to event or to recipient

Options:
  -c, --comment TEXT
  -r, --relays TEXT   comma-separated relays to search for the event
  --help              Show this message and exit.
```
