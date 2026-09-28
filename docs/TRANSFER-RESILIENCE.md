# Transfer resilience: identity, routing, and payment state

This is the shared design and operating guide for Cash/Clear transfer
resilience. Acorn owns proof handling, mint operations, encrypted receipts,
and recovery. Safebox Web owns presentation and bounded job orchestration;
Mainstay owns deployment routes and service configuration.

Companion guides:

- [Safebox Web: transfer status and recovery](https://github.com/trbouma/safebox-web/blob/main/docs/TRANSFER-STATUS-AND-RECOVERY.md)
- [Mainstay: Clear request relay policy](https://github.com/trbouma/mainstay/blob/main/docs/CLEAR-REQUEST-RELAY-POLICY.md)
- [Acorn: token delivery relay routing](TOKEN-DELIVERY-RELAY-ROUTING.md)
- [Acorn: service identity and endpoint records](SERVICE-IDENTITY-AND-ENDPOINT-RECORDS.md)

## Separate three questions

1. **Identity:** which wallet key is the recipient, and which mint, unit, and
   keyset back the credits? An address or relay URL is not the recipient key.
2. **Routing:** where can this sender publish, and where can the receiver read?
   Reachability depends on the process and network making the connection.
3. **Payment state:** were proofs exported, delivered, discovered, accepted by
   the mint, and durably recorded? Success at one stage does not prove the next.

Changing a relay route does not change recipient identity. Conversely, do not
rewrite a token's mint URL merely because two URLs appear to expose the same
service: mint compatibility and accepted routes must be established separately.

## Route scope

| Scope | Example | Boundary |
| --- | --- | --- |
| Internal deployment | `ws://spurline:8080`, `http://clear:3339` | Names belong to one container network. Another deployment can resolve the same name to a different service. |
| Local-only | localhost, LAN/private IP, local DNS | Reachable only from the relevant host or network; localhost refers to the calling process's host/container. |
| External | public mint and inbox URLs | Intended for cross-network access; DNS, TLS, authentication, firewall, and service availability still matter. |

URL classification is a routing hint, not proof of connectivity. An internal
and external endpoint may reach the same service, or different services. A
public lookup returning no event does not establish its absence on an internal
relay or behind authenticated access.

NIP-05 transfers resolve recipient identity and discover inbox routes. NUT-18
request payments use the identity and relay hints embedded in the request.
These paths can therefore choose different routes. Public requests use the
wallet's signed inbox list (or a public home relay when no list exists);
internal request encoding requires explicit caller opt-in. Generic discovery
relays are not automatically recipient inboxes.

## Evidence at each stage

These are conceptual stages, not one database enum shared by every payment flow.

| Stage | Evidence | What it does not prove |
| --- | --- | --- |
| Prepared | Valid request, suitable balance/keyset, fee calculation | No payment has been sent. |
| Exported | Bearer proofs produced from the sender's balance | Delivery can still fail. |
| Delivered | Relay publication acknowledged | Receiver discovery or mint acceptance is not established. |
| Discovered / pending | Receiver decodes a transfer and can present or journal it | A preview may not yet be journaled; neither makes proofs spendable. |
| Accepted | Mint refresh succeeds and resulting proof state is persisted | The request's success indicator still needs matching durable receipt/history evidence. |
| Confirmed in UI | Matching accepted receipt and incoming history | It is not inferred solely from sender success or an HTTP status code. |

Direct Clear transfers carry kind `7379`; NUT-18 Clear payments carry kind `14`.
Both use encrypted kind `1059` gift wraps. Outer recipient metadata establishes
the addressee, not the decrypted request ID, amount, or validity of proofs.

## Safety and recovery rules

- Probe selected delivery relays before exporting value, then require relay
  acknowledgement. A successful probe cannot guarantee subsequent delivery.
- Preserve the request's advertised receive routes for monitoring and targeted
  discovery, alongside local access to the home relay.
- Treat pending encrypted receipts and durable proof/history records as recovery
  evidence. Web job rows coordinate work; they are not the wallet balance.
- Use wallet locks and job leases to coordinate mutation. A repeated acceptance
  should recover or return an existing result where durable evidence permits it;
  do not promise exactly-once delivery across network failures.
- After an ambiguous swap or delivery outcome, inspect the existing operation.
  Do not issue another token or repeat the payment just because confirmation is
  absent. Unspent, spent, pending, and unknown proof states require different handling.
- cashuB-to-cashuA fallback is local encoding of the same proofs, never a reason
  to repeat issuance or a mint swap. See [Web format compatibility](https://github.com/trbouma/safebox-web/blob/main/docs/CASHU-TOKEN-FORMATS.md).
- Operator intervention must be explicit and scoped. Closing or hiding a
  diagnostic entry is not proof of acceptance, recovery, or reversal of value.

## Diagnostic sequence

1. Match one exact request/payment pair: request ID, amount, unit, mint, and
   recipient key. Do not compare successive tests as if they were one payment.
2. Take the sender's event ID and query the exact advertised relay from the
   relevant network. Compare its `p` recipient tag with the request's key.
3. If correctly addressed and present, inspect receiver discovery: relay set,
   cursor/time filters, decryption, inner kind, payload validation, and scan
   failures. Do not infer a routing problem from an empty UI alone.
4. If pending, inspect acceptance and mint accessibility. If accepted but the
   request remains unconfirmed, inspect request matching and durable history.
5. Report identifiers, stages, and sanitized error categories. Never request
   or log nsecs, bearer tokens/proofs, or encrypted browser authorization tickets
   as routine diagnostic output.

## Current limits and follow-up work

Clear discovery currently stops a scan on some malformed-transfer failures;
an older bad message can hide later valid messages. The Web pending preview and
request monitor do not surface all returned scan failure details. This has been
reproduced locally, but must not be assumed to explain an individual missing
payment without event-specific evidence. This guide does not claim that defect
is fixed.

Bounded request monitors are not permanent subscriptions or durable scheduled
jobs. Process restarts, expired authorization, and finite monitoring windows
require explicit resumption. Relay acknowledgement also does not guarantee
indefinite retention. Test deployed routing, retention, and recovery separately
from mocked unit tests.
