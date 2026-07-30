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

The current acceptance flow confirms:

- a wallet can be created from the Acorn CLI;
- the same wallet can be recovered in the Safebox web app;
- deposits made from the CLI are visible after web-app recovery;
- live pytest ecash transfers update the source wallet;
- disposable-wallet burn sweeps return funds to the source wallet;
- transaction history is rendered consistently enough for the web app to show
  deposits, debits, credits, and burn sweep details.

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

   Similarly, do not set `ACORN_RECEIVE_NSEC` for the normal source-wallet
   interoperability flow. If it is unset, the live tests receive using the
   source wallet nsec and ignore any ambient `ACORN_RECIPIENT_NIP05`. Set both
   `ACORN_RECEIVE_NSEC` and `ACORN_RECIPIENT_NIP05` only when you intentionally
   want to test a different receive identity.

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

- leave `ACORN_RECEIVE_NSEC` unset;
- ignore ambient `ACORN_RECIPIENT_NIP05`;
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
sovereign protocol component rather than a feature trapped inside one
application boundary.

The same user-controlled recovery material can move between:

- the installable Acorn Python package;
- the `acorn` CLI;
- live relay and mint infrastructure;
- the Safebox web app.

That makes Acorn easier to harden independently. Safebox can then consume Acorn
as a reusable component while still preserving the user's ability to recover,
replicate, migrate, and operate their wallet through other compatible surfaces.

## Notes and cautions

- Use small amounts for live tests.
- Do not commit real `nsec` values or `.env` files.
- Prefer disposable test-wallet config files for integration tests.
- Treat `acorn set --show-recovery` output as highly sensitive.
- Relay deletion requests are advisory; do not assume a burn operation erases
  data from every relay implementation.
