# Relay Suitability Ledger

Acorn uses Nostr relays as user-selectable infrastructure for
wallet bootstrap state, private records, gift-wrapped ecash transfers, and
relay-backed recovery. Not every public relay is suitable for this role.

This ledger records observed live-test results so relay compatibility can be
tracked over time.

## Two suitability assessments

These tests answer different questions. Neither replaces the other.

| Assessment | Question | Preferred environment | Passing evidence |
| --- | --- | --- | --- |
| Implementation suitability | Does this relay implementation support the operations safebox-acorn requires? | A deployment under the tester's control, such as Spurline or strfry, with access to configuration and logs. | The implementation live suite completes the required capabilities; failures and skipped checks are reviewed. |
| User suitability | Does this particular service deployment support a safebox-acorn user at realistic interaction timings? | The service endpoint under its ordinary user access, authentication, retention and rate-limit policies. | The paced first-time-user journey completes wallet creation, payment receipt, payment sending, and record creation, editing and deletion with verified results. |

The implementation suite exercises protocol behavior and lifecycle operations
in quick succession. It is not a model of normal user pacing. The user journey
spaces actions and verification reads to approximate reading and typing time;
it is not a throughput or multi-user load test. A public service that throttles
the implementation suite may still support an individual user, but that must be
tested rather than inferred.

Implementation suitability covers:

- wallet bootstrap state can be written and read back;
- private records can be put, read, listed, and deleted;
- kind `1059` gift-wrapped ecash transfers carrying inner Acorn kind `7378`
  payloads can be published and received;
- disposable wallet burn can sweep remaining funds back to the source wallet;
- relay behaviour is reliable enough to pass within the configured live-test
  timeout.

Record the actual suite version and capabilities exercised, including token
round-trip, entropy recovery and Blossom integration where applicable. A
historical pass with fewer capabilities is not automatically a pass of the
current suite. Missing required checks are incomplete, not passed. A documented
non-applicable mint-specific maintenance check (for example, zero-input-fee
per-proof repair) need not invalidate the relay assessment when the required
funded transfer and token round-trip checks passed.

### Service certification rule

For this project's suitability matrix, a service is **certified as tested only
when both assessments pass**, with recorded evidence applicable to that
deployment and configuration. This is a project testing designation, not an
independent security audit or external accreditation.

- Implementation pass alone: implementation-compatible as tested; not certified.
- User pass alone: user-suitable as tested; not certified.
- Both pass: certified as tested for the recorded deployment/configuration.
- Either missing, failed, skipped in a required area, or inconclusive: not certified.

A controlled implementation test may supply the implementation evidence for a
service only when its implementation version and relevant configuration match
the deployment being assessed. Record that relationship explicitly; a pass on
one Spurline or strfry installation does not certify all installations of that
implementation. User suitability must be tested against the actual service
under normal user policies, not a temporary rate-limit exemption.

Record dates, Acorn and relay revisions, relevant deployment policies, mint and
Blossom dependencies, pacing/timeouts, and the full pass/fail/skip summaries for
both assessments. Material changes require reassessment. HTTP 429 makes a run
incomplete/rate-limited; it does not by itself prove protocol incompatibility.
Keep earlier evidence, but do not treat an incomplete current reassessment as
a current certification pass.

Suitability is an observed test result, not a permanent guarantee. Relay
operators can change policies, retention windows, accepted event kinds, rate
limits, authentication requirements, or infrastructure at any time.

### Timestamp compatibility

Verified Acorn record replacements must be newer than the previous event.
Acorn now waits for wall-clock time to advance instead of creating a future-dated
replacement. Preflight and timestamp waiting share the configured verification
timeout budget (with a 0.5-second minimum); canonical readback retains its own
bounded verification window. A record too far in the future fails before a new
event is published. Existing events are not deleted or rewritten to bypass this.

A relay rejection such as `invalid: created_at too late` is distinct from rate
limiting. Check client/server clock synchronization and the relay's timestamp
policy. This change prevents Acorn's deliberate timestamp advancement, but does
not correct clock skew between hosts. Preserve pending payment recovery records
and investigate the rejected event before repeating funded tests.

## Current results

Last updated: 2026-10-12

The matrix combines implementation (relay) suitability and user suitability.
Yakihonne (`wss://nostr-01.yakihonne.com/`) has both required passes recorded
and is certified as tested on 2026-10-12 under this project's two-assessment
rule. Island Bitcoin has a recorded paced user-journey pass, but no implementation
suitability result is recorded for it here. “Not yet recorded” does not mean a
test failed.

**A user-suitability pass alone does not establish overall relay suitability or
certification. Relay implementation suitability must also pass**, with evidence
applicable to the same deployment/configuration. Even both passes establish
suitability only as tested, not a permanent service guarantee.

The older results below are historical observations, not continuous health
checks. On October 12, nos.lol's retest was incomplete due to HTTP 429 rate
limiting during wallet-lock and bootstrap reads. The funding event was retrieved,
but the funded burn check did not complete. Its earlier successful result is
retained; this retest does not establish permanent protocol incompatibility.

The preferred relay suitability signal is a post-`1059` test result. Earlier
results gathered while Acorn used kind `7378` as the relay-visible outer
gift-wrap kind should be retested where possible. New results should validate
standard kind `1059` gift wraps carrying inner Acorn kind `7378` transfer
payloads.

| Deployment | Implementation suitability | User suitability | Certification | Implementation evidence | Observed time | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `wss://nostr-01.yakihonne.com/` | Passed as tested (2026-10-12) | Passed as tested (2026-10-12) | Certified as tested (2026-10-12) | Passed burn-sweep-transfer, disposable-token-round-trip, external-entropy-bootstrap-recovery-burn, gift-wrapped-ecash-transfer, grove-blob-put-get, private-record-put-get-list-delete | Implementation summary ~425.8s (612.97s pytest total); user journey ~481.8s (483.12s pytest total) | Supplied implementation result: 7 passed, 1 skipped, 576 deselected. Token round-trip passed; the skipped per-proof swap/repair checks require a zero-input-fee mint. Two user-journey balance-snapshot timeouts did not prevent subsequent balance verification. See evidence scope below. |
| `wss://relay.notoshi.win/` | Not yet recorded | Inconclusive (2026-10-12): connection closed before query completion | Not certified | Not yet recorded | ~91.5s journey; 92.65s pytest total | Wallet-configuration query closed before EOSE during creation; no funding sent. No empty-result assumption or protocol-incompatibility finding. |
| `wss://relay.trustroots.org/` | Not yet recorded | Access/policy blocked as tested (2026-10-12): publication rejected, status 403 | Not certified | Not yet recorded | ~32.4s journey; 33.52s pytest total | Wallet creation stopped before funding. Authentication/allowlist/event restrictions are possible causes, not established by the supplied output. |
| `wss://relay.islandbitcoin.com/` | Not yet recorded | Passed as tested; latest user-reported retry with 15s record-query timeout (2026-10-12) | Not certified — relay implementation pass required | Not yet recorded | Initial pass ~463.6s; latest retry duration not supplied | Preserve initial pass, intervening 5s query timeout, and successful 15s retry separately below. Does not establish overall relay suitability. |
| `wss://spurline.safebox.dev` | Passed as tested (2026-10-12) | Not yet recorded | Not certified | Passed burn-sweep-transfer, disposable-token-round-trip, external-entropy-bootstrap-recovery-burn, gift-wrapped-ecash-transfer, grove-blob-put-get, private-record-put-get-list-delete | ~97.4s | User-reported run: 7 passed, 1 skipped; legacy per-proof swap/repair requires a zero-input-fee mint. |
| `ws://127.0.0.1:8080` | Historical pass | Not yet recorded | Not certified | Passed external-entropy-bootstrap-recovery-burn, private-record-put-get-list-delete | ~11.1s | Spurline local relay tested in third-party scenario. Funded ecash capabilities were tested separately in controlled mode. |
| `wss://purplerelay.com/` | Historical pass | Not yet recorded | Not certified | Passed burn-sweep-transfer, gift-wrapped-ecash-transfer, private-record-put-get-list-delete | ~48.7s | Real third-party relay. Passed core Acorn capabilities. |
| `wss://relay.mostr.pub/` | Historical pass | Not yet recorded | Not certified | Passed burn-sweep-transfer, gift-wrapped-ecash-transfer, private-record-put-get-list-delete | ~49.4s | Real third-party relay. Passed core Acorn capabilities. |
| `wss://relay.openetr.org` | Historical pass | Not yet recorded | Not certified | Passed third-party scenario live test matrix | ~55s | Independently deployed relay controlled by the project operator. |
| `ws://beelink:8735` | Historical pass | Not yet recorded | Not certified | Passed controlled live test matrix | ~58s to ~60s | Local controlled relay used for development. |
| `wss://nostr.oxtr.dev` | Historical pass | Not yet recorded | Not certified | Passed burn-sweep-transfer, gift-wrapped-ecash-transfer, private-record-put-get-list-delete | ~61.3s | Real third-party relay. Passed core Acorn capabilities. |
| `wss://nos.lol` | Historical pass; latest retest inconclusive (rate-limited) | Not yet recorded | Not certified | Earlier pass: burn-sweep-transfer, gift-wrapped-ecash-transfer, private-record-put-get-list-delete. 2026-10-12: suitability not fully reassessed due to HTTP 429. | Earlier pass ~62.1s; latest relay summary ~27.3s | Preserve earlier pass. Latest user-reported run: 1 failed, 4 passed, 3 skipped; transfer retrieved, lock/bootstrap reads rate-limited. |
| `wss://relay.primal.net` | Historical pass | Not yet recorded | Not certified | Passed third-party scenario live test matrix | ~99s | Real third-party relay. Passed core Acorn capabilities, but slower than `relay.openetr.org` in the observed run. |
| `wss://espelho.girino.org` | Historical pass | Not yet recorded | Not certified | Passed burn-sweep-transfer, gift-wrapped-ecash-transfer, private-record-put-get-list-delete | ~108.8s | Real third-party relay. Passed core Acorn capabilities. |
| `wss://nostr.openhoofd.nl` | Historical pass | Not yet recorded | Not certified | Passed third-party scenario live test matrix | ~114s | Real third-party relay. Passed burn sweep, gift-wrapped ecash transfer, and private record lifecycle. |
| `wss://custom.fiatjaf.com` | Failed/incomplete as tested | Not yet recorded | Not certified | wallet-bootstrap-readback: wallet bootstrap state was not readable after initialization | ~0.0s | Failed the basic Acorn home-relay bootstrap readback requirement. |
| `wss://dwebcamp.nos.social` | Failed/incomplete as tested | Not yet recorded | Not certified | wallet-bootstrap-readback: wallet bootstrap state was not readable after initialization | ~0.0s | Failed the basic Acorn home-relay bootstrap readback requirement. |
| `wss://nostrrelay.win` | Failed/incomplete as tested | Not yet recorded | Not certified | wallet-bootstrap-readback: wallet bootstrap state was not readable after initialization | ~0.0s | Failed the basic Acorn home-relay bootstrap readback requirement. |
| `wss://relay.damus.io` | Failed/incomplete as tested | Inconclusive (2026-10-12): HTTP 503 during wallet bootstrap readback | Not certified | Historical implementation run: failed/skipped relay compatibility checks | Implementation ~55s; user journey ~37s (~38s pytest total) | User-reported paced run stopped before funding; no payment sent by this journey. HTTP 503 does not establish protocol incompatibility. Earlier implementation evidence is retained separately. |
| `wss://relay.magiccity.live` | Failed/incomplete as tested | Not yet recorded | Not certified | Timed out during wallet bootstrap initialization | ~257s for mixed controlled/third-party run | Did not complete Acorn disposable wallet initialization within the configured timeout. |

### User-suitability results

This list records only the paced first-time-user assessment, not a list of
certified or fully suitable relays. The combined matrix above remains the place
to check whether **both** assessments have passed.

| Deployment | Date | User suitability | Timing | Evidence and qualifications | Overall suitability / certification |
| --- | --- | --- | --- | --- | --- |
| `wss://nostr-01.yakihonne.com/` | 2026-10-12 | Passed as tested | 30s action pauses; 5s verification pauses; ~481.8s journey (483.12s pytest total) | Supplied output: 1 passed, all six user stages verified. Received 31 sats net from 32; returned 7 sats net from 8; 22 sats retained. Two balance-snapshot refresh timeouts; subsequent balance checks passed. | Certified as tested (2026-10-12): separate implementation suite also passed, with the documented mint-specific maintenance skip. |
| `wss://relay.notoshi.win/` | 2026-10-12 | Inconclusive — connection closed | ~91.5s journey (92.65s pytest total) | Supplied traceback: connection closed before EOSE while querying kind 17375 wallet configuration during creation. No payment sent; the incomplete response was not treated as an empty wallet. | Not established / not certified: user journey incomplete; no implementation pass recorded. |
| `wss://relay.trustroots.org/` | 2026-10-12 | Access/policy blocked | ~32.4s journey (33.52s pytest total) | Supplied traceback: wallet publication explicitly rejected with status 403. No payment sent. Exact access policy is unknown. | Not established / not certified: user journey blocked; no implementation pass recorded. |
| `wss://relay.islandbitcoin.com/` | 2026-10-12 | Passed as tested | 30s action pauses; 5s verification pauses; ~463.6s journey (464.98s pytest total) | User-reported `1 passed`. Wallet creation, receiving, sending, record creation, editing and deletion all verified. Received 31 sats net from 32; returned 7 sats net from 8; 22 sats retained. One balance-snapshot refresh timed out, but subsequent balance verification passed. | Not established / not certified: relay implementation-suitability pass still required. |
| `wss://relay.islandbitcoin.com/` (subsequent run) | 2026-10-12 | Inconclusive — timeout | Internal record-query timeout 5s; ~250.7s journey (251.87s pytest total) | Supplied traceback: funding and receipt completed, then the lock-record preflight query timed out at “send payment back”, before return-token issuance. Received funds remained in the retained wallet. | Not established / not certified; earlier pass retained as historical evidence. |
| `wss://relay.islandbitcoin.com/` (latest retry) | 2026-10-12 | Passed — user-reported | Record-query timeout 15s; command retains default 30s action pauses, 5s verification pauses and 120s step timeout; elapsed time not supplied | Tester reported “everything passed this time around” after the 15s retry command. Full retry output, exact fee/balance results and revisions were not supplied. | Not established / not certified: relay implementation-suitability pass still required. |
| `wss://relay.damus.io/` | 2026-10-12 | Inconclusive | ~37s journey (~38s pytest total); stopped at bootstrap readback | User-reported `1 failed`. HTTP 503 before funding; no payment sent. Service unavailability is not proof of protocol incompatibility. | Not established / not certified: no completed user pass and earlier implementation checks failed or were incomplete. |

Entries distinguish supplied test output from a verbal success report. The initial Island Bitcoin output
identifies `https://mint.safebox.dev` as the mint, but does not identify the relay
implementation/version, Acorn commit or complete service policy configuration.
Capture those details for certification review; do not infer them from a
successful user journey. Retain performance warnings alongside passing results.

#### Yakihonne: two-assessment evidence and scope

The tester supplied a complete paced user-journey log and a separate
implementation-suite summary for the same endpoint. The implementation run
reported all six listed capabilities passing, with `7 passed, 1 skipped, 576
deselected`. The skip explicitly followed a successful token round-trip and
concerned additional per-proof swap/repair tests requiring a zero-input-fee mint;
it is not an untested required relay capability under the rule above.

The supplied implementation command selected this endpoint in the `third-party`
scenario, used `ACORN_TEST_AMOUNT=10`, set
`ACORN_RECORD_QUERY_ATTEMPT_TIMEOUT_SECONDS=15`, and excluded the paced journey
file. The pasted summary does not independently show effective environment
values. The user log confirms 30-second action pauses, 5-second read pauses and
`https://mint.safebox.dev`; it does not show its internal query timeout.

“Certified as tested” records these two observed passes for this endpoint, not
all Yakihonne relays, an independent security accreditation, or a guarantee of
future availability. Acorn/relay revisions and the complete deployment policy
configuration were not supplied; the evidence does not establish reproducibility
across versions or configuration changes. Retain the two non-fatal snapshot
timeout warnings as performance observations and reassess after material changes.

#### Island Bitcoin: 15-second query-timeout retry

The successful retry used this command in the safebox-acorn repository:

```sh
ACORN_RECORD_QUERY_ATTEMPT_TIMEOUT_SECONDS=15 \
ACORN_SOURCE_CONFIG="$HOME/.acorn/test-source-new.yml" \
ACORN_TEST_WALLET_CONFIG="./.acorn-test/user-wallet.yml" \
ACORN_THIRD_PARTY_RELAY=wss://relay.islandbitcoin.com/ \
ACORN_RELAY_SCENARIO=third-party \
ACORN_RUN_USER_JOURNEY=1 \
poetry run pytest -m live -rs -s tests/integration/test_user_journey_live.py
```

`ACORN_RECORD_QUERY_ATTEMPT_TIMEOUT_SECONDS` controls an internal record-query
attempt budget (5 seconds by default). It is separate from the 5-second pause
before verification reads and the 120-second overall journey-step timeout.
Increasing the step timeout alone would not extend this internal query budget.
The command changes the budget for this run only; the default remains unchanged.

The observed sequence supports a user-suitability pass with the 15-second
setting, not a conclusion that the larger timeout caused success or guarantees
future reliability. Network and service conditions may differ between runs.
It does not establish relay implementation suitability or certification.

Each run creates a new disposable wallet and spends real mint fees. A retry
does not resume or reclaim the previous wallet's funds. Keep the printed
configuration files and inspect unfinished operations before retrying. Timeout
reporting now follows wrapped exception causes, so a preflight `TimeoutError`
wrapped by token issuance is still reported as “operation timed out”, with the
failed stage and funding warning intact; this adds no automatic retries.

## Test commands

### Implementation suitability

Prefer deployments you control. Run the implementation suite with the paced
journey explicitly excluded, even if its opt-in variable is set:

```sh
poetry run pytest -m live -rs -s --ignore=tests/integration/test_user_journey_live.py
```

To test only a third-party relay, set:

```env
ACORN_THIRD_PARTY_RELAY=wss://relay.example.com
ACORN_RELAY_SCENARIO=third-party
ACORN_TEST_AMOUNT=10
```

Then run:

```sh
poetry run pytest -m live -rs -s --ignore=tests/integration/test_user_journey_live.py
```

The `third-party` scenario name selects the endpoint; it does not mean the
deployment must be outside the tester's control.

Funded ecash tests default to 10 sats and verify the net credit after mint fees.
An existing environment value of 1 overrides this default and can produce a token
whose entire value is consumed by an input fee. Keep extra source funds for fees.
The legacy per-proof refresh checks require a zero-input-fee mint and are skipped
otherwise; inspect skipped capabilities before treating a relay as fully tested.

The output should emit suitability lines such as:

```text
SUITABLE relay capability (... capability=burn-sweep-transfer ...)
SUITABLE relay capability (... capability=gift-wrapped-ecash-transfer ...)
SUITABLE relay capability (... capability=private-record-put-get-list-delete ...)
```

or diagnostic lines such as:

```text
UNSUITABLE relay capability (... capability=wallet-bootstrap-readback ...)
UNSUITABLE relay capability (... capability=burn-sweep-transfer ...)
```

At the end of the pytest run, Acorn also prints a legacy single-run suitability
summary and ledger row:

```text
Acorn relay suitability summary
Suitable: wss://relay.example.com (third-party, 58.4s)
  Observed: Passed burn-sweep-transfer, gift-wrapped-ecash-transfer, private-record-put-get-list-delete
  Ledger row: | `wss://relay.example.com` | Suitable | Passed ... | ~58.4s |  |
```

This output is capability evidence, **not a certification decision**. Review the
full pytest result, including failures and skips, and map it to the appropriate
assessment column above. The generated row still uses the old five-column
format and should not be pasted unchanged into the two-assessment matrix.

Incomplete user journeys now include the failing stage and distinguish HTTP
5xx service errors, status 401/403 access or policy blocks, HTTP 429 rate limiting,
connections closed before EOSE (end of stored events), interrupted connections,
timeouts and other incomplete
operations/verifications. These are inconclusive user evidence, not automatic
protocol-incompatibility findings. The original exception still fails the test;
reporting does not retry operations or convert a failure into a pass. Failures
before funding explicitly say no payment was sent; once funding may have
started, the summary instead directs the tester to inspect retained transfers.
A dependency such as a mint can also return an HTTP error, so the summary does
not automatically attribute every service error to the relay under test.

Known error categories are recognized through visible exception causes/contexts,
including wrapped errors. Summaries use fixed descriptions rather than copying
arbitrary exception payloads. An access block is not a protocol-incompatibility
finding, and a closed response is never treated as a successful empty query.
The overall result remains inconclusive when the user journey cannot complete;
the reason distinguishes a blocked request from transient unavailability.

For an early connection closure, record the result and, if appropriate, retry
once later. Repeated closure warrants reviewing access policies and query
handling with the operator. Avoid repeated retries against a rejecting or
rate-limiting service. Retain configurations and inspect transfers whenever
funding may have started; these reporting changes add no retries or cleanup.

### User suitability

Run the paced journey separately against the actual deployment:

```sh
ACORN_SOURCE_CONFIG="$HOME/.acorn/test-source-new.yml" \
ACORN_TEST_WALLET_CONFIG="./.acorn-test/user-wallet.yml" \
ACORN_THIRD_PARTY_RELAY=wss://relay.example.com \
ACORN_RELAY_SCENARIO=third-party \
ACORN_RUN_USER_JOURNEY=1 \
poetry run pytest -m live -rs -s tests/integration/test_user_journey_live.py
```

Defaults are 30 seconds between actions and 5 seconds before verification reads,
with a 120-second per-operation timeout. The test receives 32 sats and sends
8 sats back; fund the source with extra mint-fee headroom. The unique test wallet
and remaining funds are retained on success and failure. Inspect its printed
configuration path and unfinished operations before another funded run. Do not
run both suites concurrently or immediately retry a rate-limited run.

See the [README user-journey instructions](../README.md#paced-first-time-user-suitability-test)
for pacing and amount overrides. Record the actual timings with the result;
different settings are not directly comparable.

## How to add a result

When testing a new relay:

1. Set `ACORN_THIRD_PARTY_RELAY` to the relay URL.
2. Set `ACORN_RELAY_SCENARIO=third-party`.
3. Run the implementation suite and record its evidence in the implementation
   column, including required checks that failed or did not run.
4. Run the paced user journey separately and record its evidence in the user
   column, including date, elapsed time and pacing settings.
5. Record deployment/version/configuration provenance for both runs. Update
   certification to “Certified as tested (date)” only when both pass under the
   rule above. Preserve earlier observations when a retest is inconclusive.

Prefer small amounts for live ecash tests. Do not commit real `nsec` values or
`.env` files.

## Interpretation

An implementation pass demonstrates protocol/lifecycle compatibility in the
tested environment. A user pass demonstrates the paced workflow on a particular
deployment. Certification requires both, and does not mean the service is
trusted, permanent, private, secure against all threats, or commercially supported.

An unsuitable result does not necessarily mean the relay is broken. It may mean
the relay is optimized for social Nostr traffic rather than Acorn's relay-backed
wallet and record lifecycle.

The goal of this ledger is practical: identify relays that can support Acorn's
protocol-first user-controlled record model, and make relay choice an explicit,
testable deployment decision.
