# Acorn CLI and Safebox Web App Interoperability

Acorn should be usable as a standalone CLI component and as the protocol engine
behind a Safebox-style web application. A wallet created by one surface should
be recoverable by the other when the same recovery/bootstrap material is used.

This document captures the current manual acceptance scenario for proving that
the Acorn CLI and the Safebox web app can observe and operate on the same
relay-backed wallet state.

## What this validates

This scenario validates that Acorn state is not trapped inside one interface.
The CLI and web app should share the same protocol-level wallet identity,
relay-backed records, Cashu proof state, and transaction history.

The source wallet should be treated as the funding and recovery anchor. It
should remain clean enough to recover in the Safebox web app and inspect by
hand. Most mutation-heavy live checks should use disposable wallets that can be
created, funded, burned, and removed during the test run.

The current acceptance flow confirms:

- a wallet can be created from the Acorn CLI;
- the same wallet can be recovered in the Safebox web app;
- deposits made from the CLI are visible after web-app recovery;
- live pytest ecash transfers update the source wallet;
- disposable-wallet burn sweeps return funds to the source wallet;
- transaction history is rendered consistently enough for the web app to show
  deposits, debits, credits, and burn sweep details.

## Milestone: external NIP-05 ecash delivery through Safebox Web

In August 2026, the standalone
[Safebox Web application](https://github.com/trbouma/safebox-web) completed a
manual end-to-end external-recipient test:

1. the Acorn live test resolved an external NIP-05 address to its component
   public key and advertised home relay;
2. the funded source Acorn issued ecash and published a NIP-59 gift-wrapped
   kind `7378` transfer to that relay;
3. the recipient attached its Acorn to Safebox Web through the encrypted,
   authenticated browser session;
4. the user selected **Check and receive ecash** on the transaction-history
   page;
5. Safebox Web invoked Acorn's `sweep_ecash_transfers()` method on the
   request-scoped component;
6. Acorn unwrapped the transfer, accepted and refreshed the proofs through the
   issuing mint, persisted the resulting kind `7375` proof state, and wrote the
   kind `7377` credit history; and
7. Safebox Web displayed both the received funds and the resulting transaction.

This milestone formalizes the application boundary. Acorn owns recipient
resolution, transfer encryption, relay queries, mint interaction, proof-state
mutation, and transaction journalling. Safebox Web owns the user-controlled
browser session, CSRF protection, progress and error presentation, and the
explicit user action that invokes the mutation. The web application does not
reimplement proof handling or maintain a separate wallet-state database.

The result also demonstrates that the sender and recipient need not use the
same application surface. A CLI-driven source Acorn can send to a NIP-05
address whose recipient later accepts the transfer through Safebox Web, while
both sides remain anchored in Acorn's relay-backed protocol state.

This is milestone evidence, not a complete fund-safety claim. It does not yet
close the durable receive-journal, interrupted-operation recovery, concurrent
writer, or independent security-review gates in the releasability roadmap.

## Acceptance scenario

Use this as a manual interoperability check after changes to Acorn recovery,
proof handling, ecash transfer, transaction history, or the Safebox web app's
wallet recovery path.

1. Create or initialize a source wallet with the Acorn CLI.

   ```sh
   acorn init
   ```

   Record the recovery/bootstrap material in a secure location:

   ```sh
   acorn set --show-recovery
   ```

2. Deposit a small amount of sats into the source wallet.

   ```sh
   acorn deposit 21
   acorn balance
   ```

3. Configure the live test harness to use the source wallet and disposable test
   wallets.

   The source wallet normally uses the default profile:

   ```env
   ACORN_SOURCE_CONFIG=~/.acorn/config.yml
   ```

   Disposable test wallets should use explicit config files and a test relay:

   ```env
   ACORN_TEST_WALLET_CONFIG=./.acorn-test/test-wallet.yml
   ACORN_TEST_CREATE_WALLET=true
   ACORN_TEST_BURN_AFTER=true
   ACORN_TEST_RELAY=ws://beelink:7777
   ```

   In normal use, do not set `ACORN_TEST_MINT`; disposable wallets inherit the
   source wallet's relay-backed home mint. Set `ACORN_TEST_MINT` only when you
   intentionally want to override that behavior for a specific mint test.

   Testing lanes:

   - Source wallet: funds the suite, receives sweep-backs, and funds the
     separate opt-in external interoperability tests.
   - Disposable wallets: carry most test mutations, including private record
     lifecycle and burn-wallet flows.
   - Separate opt-in tests: cover NIP-05 recipient resolution and real
     lightning-address payments.

   The normal source-wallet ecash transfer test is deliberately narrow. The
   source wallet funds the transfer, sends to its own npub through the active
   relay scenario, receives the gift-wrapped transfer, refreshes proofs, and
   writes transaction history to the same source wallet. This proves
   source-wallet/web-app interoperability without moving the rest of the test
   suite away from disposable wallets.

   Override rules:

   | Variable | Default behavior | Set only when |
   | --- | --- | --- |
   | `ACORN_SOURCE_CONFIG` | Uses `~/.acorn/config.yml` as the funded source wallet. | You want a different source wallet config file. |
   | `ACORN_TEST_MINT` | Disposable wallets inherit the source wallet's relay-backed mint. | You are intentionally testing a different mint. |
   | `ACORN_TEST_TRANSFER_RELAY` | Uses the active relay scenario. | You want transfers published to a relay different from the scenario relay. |
   | `ACORN_NIP05_RECIPIENT` | NIP-05 tests are skipped. | You intentionally want the source wallet to send ecash to an external NIP-05 wallet and will verify receipt separately. |
   | `ACORN_LIGHTNING_ADDRESS` | Lightning payment tests are skipped. | You intentionally want to spend sats in the separate lightning-address test. |

   Before running tests, it is useful to check for exported shell variables that
   can override `.env`:

   ```sh
   env | grep '^ACORN_'
   ```

   Keep NIP-05 and lightning-address tests separate from the default
   interoperability flow. They exercise different behavior:

   - The NIP-05 test resolves an external recipient, uses its advertised relay
     hints, publishes a gift-wrapped transfer, and verifies the source debit.
     Because the test does not hold the external recipient's private key,
     successful receipt must be confirmed separately in that wallet.
   - Lightning-address tests prove mint melt/payment behavior and spend real
     sats.
   - The default source-wallet ecash transfer proves Acorn's core
     gift-wrapped transfer, receive, proof refresh, and web-app-visible
     transaction history.
   - Disposable-wallet tests protect the source wallet from noisy record and
     burn lifecycle churn.

   Source wallet versus disposable wallets:

   Use the source wallet when the test is proving interoperability or real
   payment behavior. Use disposable wallets when the test is proving relay
   suitability or record/proof lifecycle behavior.

   The source wallet is the wallet a user can recover in the Safebox web app.
   It is therefore the right place to test behavior where web-app-visible
   continuity matters:

   - initial deposit visibility;
   - source-wallet gift-wrapped ecash self-transfer;
   - source-wallet ecash transfer to an external NIP-05 recipient;
   - source-wallet lightning-address payment;
   - source-wallet transaction history rendering.

   These tests answer: can one funded Acorn wallet operate across CLI, relay,
   mint, and web-app surfaces without losing the user's recoverable state?

   Disposable wallets are better for relay suitability and churn-heavy lifecycle
   tests:

   - wallet bootstrap/readback on a candidate relay;
   - private record put/get/list/delete;
   - burn-wallet flows;
   - relay deletion advisory behavior;
   - repeated third-party relay compatibility checks.

   These tests answer: can a relay support Acorn's event patterns reliably
   enough without polluting the long-lived source wallet?

   In short:

   ```text
   Source wallet       -> interoperability and real payment behavior
   Disposable wallets  -> relay suitability and lifecycle churn
   ```

4. Run the live test flow.

   ```sh
   poetry run pytest -m live -rs
   ```

   A healthy run should show the live ecash transfer, record lifecycle, and burn
   wallet tests passing or intentionally skipping with a clear reason.

5. Recover the same wallet in the Safebox web app using the CLI wallet's
   recovery/bootstrap material.

6. Verify the web app can display the resulting balance and transaction
   history.

## Expected transaction pattern

The exact timestamps, event IDs, balances, and sender prefixes will vary. The
important point is that the web app can render the CLI-originated wallet state
and show the same lifecycle of funds.

Expected entries include:

- a credit for the initial deposit, such as `acorn deposit`;
- debits for pytest ecash transfer funding;
- credits for incoming burn sweeps, such as
  `ecash transfer received from ...: acorn wallet burn sweep`;
- balances that reflect the transfer and sweep lifecycle.

Example pattern:

```text
C  21 sats  acorn deposit
D   1 sat   pytest burn test funding
C   1 sat   ecash transfer received from ...: acorn wallet burn sweep
D   1 sat   pytest live gift-wrapped transfer
C   1 sat   ecash transfer received from ...: pytest live gift-wrapped transfer
```

## Fixes validated by this scenario

The live interoperability run exposed real protocol-component bugs, not merely
test harness issues. The current acceptance scenario should remain in place
because it exercises the boundary between:

- relay-backed wallet state;
- mint-facing Cashu proof operations;
- NIP-59 gift-wrapped ecash transfer events;
- kind `7375` proof state;
- kind `7377` transaction history;
- Safebox web app recovery and display.

### Mint-safe proof serialization

Acorn originally sent proofs to mint APIs using broad model serialization. That
included wallet-local/default fields such as an empty `witness` value. Some
mints tolerated this, but stricter mints rejected the request with errors such
as:

```text
witness data not allowed without a spending condition
```

Mint-facing swap and melt calls must send Cashu proof payloads using the
minimal proof shape:

```json
{
  "id": "...",
  "amount": 1,
  "secret": "...",
  "C": "..."
}
```

Optional fields such as `witness` should appear only when they are actually
required by a spending condition. Wallet-local fields must not be sent to mint
APIs.

### Receive identity must match storage identity

The tests also exposed a subtle identity mismatch. A gift-wrapped ecash transfer
is addressed to a receive key, but accepted proofs are stored by the wallet that
runs `sweep_ecash_transfers()`. The receive key and the storage wallet must be
aligned unless the caller is deliberately using a transient receive key and
understands where the accepted proofs will be written.

For the normal source-wallet interoperability flow:

- send to the source wallet npub;
- receive with the source wallet;
- verify the resulting credit in source wallet kind `7377` history.

For disposable burn-wallet tests:

- fund the disposable wallet using the disposable wallet receive key;
- burn/sweep remaining funds back to the source wallet;
- verify source-wallet debit and sweep-back credit history.

### Non-addressed gift wraps should be skipped cleanly

Relay queries can return events that are not decryptable with the active receive
key, especially when tests are repeated against the same relay. Acorn should not
treat this as a fatal wallet failure. Non-addressed gift wraps should be
reported as skipped/failed receive candidates, while valid addressed transfers
continue to be processed.

This makes the live tests more useful: a failure should explain whether the
event was not addressed to the receive key, could not be decrypted, or failed at
mint acceptance.

### Web-app-visible transaction history is part of acceptance

The test flow now checks more than balances. It also verifies that source-wallet
transaction history is readable after:

- source wallet debit for gift-wrapped transfer;
- source wallet debit for disposable burn-wallet funding;
- source wallet credit for burn sweep-back.

The final manual check is recovery in the Safebox web app. Seeing entries such
as the following confirms that CLI-originated Acorn state is web-app visible:

```text
D 1 sat  pytest live gift-wrapped transfer
C 1 sat  ecash transfer received from ...: pytest live gift-wrapped transfer
D 1 sat  pytest burn test funding
C 1 sat  ecash transfer received from ...: acorn wallet burn sweep
```

## Why this matters

This is stronger than a CLI smoke test. It proves that Acorn is behaving like a
user-controlled protocol component rather than a feature trapped inside one
application boundary.

The concept became more concrete once the same flows were exercised against
both a third-party relay and a third-party Cashu mint not controlled by the
Safebox project. That combination matters: the relay validates that Acorn state
can live on replaceable Nostr infrastructure, while the mint validates that
Cashu proofs can move through independently operated value infrastructure.

Together, those tests show that Acorn is not merely abstracting Safebox's
current backend. It is carrying user-controlled identity, encrypted records,
wallet proofs, recovery context, and transaction history across independently
operated protocol services.

The same user-controlled recovery material can move between:

- the installable Acorn Python package;
- the `acorn` CLI;
- live relay and mint infrastructure;
- the Safebox web app.

That makes Acorn easier to harden independently. Safebox can then consume Acorn
as a reusable component while still preserving the user's ability to recover,
replicate, migrate, and operate their wallet through other compatible surfaces.

This is the practical test for Acorn as a user-controlled protocol component:

```text
Can the user keep operating when the app, relay, mint, or deployment operator
changes?
```

The answer is increasingly yes, provided the chosen relay and mint satisfy the
required protocol behavior. That is why relay suitability testing, mint
compatibility testing, recovery checks, and web-app-visible transaction history
are all part of the same hardening effort.

## Notes and cautions

- Use small amounts for live tests.
- Do not commit real `nsec` values or `.env` files.
- Prefer disposable test-wallet config files for integration tests.
- Treat `acorn set --show-recovery` output as highly sensitive.
- Relay deletion requests are advisory; do not assume a burn operation erases
  data from every relay implementation.
