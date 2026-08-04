# Acorn Lightning-Address Gateway Design

## Status

This document describes the target provider interface. Its first end-to-end
slice is now implemented in Safebox Web; the full reliability and registration
model remains a design proposal.

As an initial application-boundary milestone, Safebox Web now includes an
optional standalone **service Acorn worker**. Exactly one worker process creates
or recovers this provider-owned wallet and retains minimum recovery state in an
owner-only persistent file across routine restarts. The FastAPI web tier does
not load the provider key or proof state and can therefore run multiple web
workers. Sweeping and burning are an explicit wallet-retirement operation, not
normal process-shutdown behavior.

Safebox Web now also implements the first durable LNURL-pay slice: handle
resolution, queued invoice creation, settlement checking, and gift-wrapped
ecash delivery. Delivery exceptions stop in a manual-review state rather than
risk an automatic duplicate payment. Invoice cleanup, idempotent delivery
acknowledgement, retry, refund, and complete restart reconciliation remain to be
implemented. The service Acorn must not accept meaningful third-party funds
until those obligations are durable and tested.

The two-container deployment has also been verified with a real Lightning
payment: the web process created the durable request, the singleton provider
Acorn accepted settlement, and the worker delivered gift-wrapped ecash to the
registered recipient. This is evidence that the boundary works, not a claim of
production readiness.

## Summary

An Acorn should be able to register its component public key with a Lightning
address provider without surrendering its private key or moving its durable
wallet state into the provider's application.

The provider gives the Acorn a conventional Lightning address. Registration
binds that address to:

- the Acorn component's public key;
- one or more relays where the component can receive private delivery events;
- the ecash mints and protocol versions the component is willing to accept; and
- a signed registration version that can later be updated or revoked.

When a Lightning payment settles, the provider converts the amount into ecash
and delivers it to the registered public key as a NIP-59 gift wrap: relay-visible
kind `1059`, containing an encrypted Acorn kind `7378` transfer. The receiving
Acorn accepts and refreshes the token, adds the resulting proofs to canonical
kind `7375` wallet state, and writes kind `7377` transaction history.

To a payer, this remains an ordinary Lightning-address payment. To the
recipient, it becomes a user-controlled ecash record delivered through Acorn's
normal protocol boundary.

## Design goals

The design should:

- give an Acorn conventional Lightning reachability while it is offline;
- prove control of the registered component key by challenge and
  response;
- keep the `nsec` entirely outside the provider;
- avoid requiring the provider to store the recipient's Acorn wallet state;
- use the existing gift-wrapped kind `7378` transfer and receive path;
- let the recipient change relays without changing its component key;
- make settlement, conversion, publication, and acceptance distinct states;
- make retries idempotent and safe across process crashes;
- disclose the provider's temporary custody and delivery obligations; and
- support gradual migration from the current Safebox-specific payment path.

The first version is not intended to create a decentralized Lightning-address
standard, remove all trust from the provider, or solve portable names across
unrelated provider domains.

## Key and address model

An Acorn wallet is a component with its own cryptographic keypair. The public
key is the stable protocol identifier used by this design. Control of the
corresponding private key provides continuity and authority over the
component's funds, records, registration, and delivery instructions. The key
is not, by itself, the identity of a person or organization.

Registration proves only that the requester controls the private key for the
submitted public key and authorizes a precise registration operation. It does
not establish a civil identity, prove a legal name, or prove control of an
unrelated email address.

The Lightning address is a provider-assigned route and one possible identity
signal. NIP-05, a kind `0` profile, credentials, relationships, or other
external context may provide additional signals. The provider proves only the
registered mapping and key authorization; each counterparty determines what
identity meaning to assign to those signals.

## Actors and trust boundaries

### Receiving Acorn

The recipient controls its `nsec`, selects its delivery relays, states its mint
policy, registers the mapping, and later accepts incoming ecash. The Acorn may
run on the user's device or inside an execution environment operated by a
trusted provider.

### Lightning-address gateway

The gateway operates the public Lightning address, produces invoices, detects
settlement, obtains ecash, and publishes a gift-wrapped transfer. It stores the
registration mapping and operational payment state, but never needs the
recipient's `nsec` or durable Acorn proof state.

### Lightning payer and node

The payer uses the existing Lightning-address and LNURL-pay flow. The gateway's
Lightning infrastructure receives and confirms the payment.

### Mint

The mint issues the bearer ecash delivered to the Acorn and later refreshes it
for the recipient. Mint selection is a material trust and interoperability
decision and must be made explicit.

### Relays

Relays provide asynchronous availability for the encrypted delivery envelope.
They are not asked to understand the token or payment state. Successful relay
publication is not the same as recipient acceptance.

## Standards used

The public payment surface should remain compatible with
[LUD-16](https://github.com/lnurl/luds/blob/luds/16.md), which maps an
email-like Lightning address to `/.well-known/lnurlp/<name>`, and the
[LUD-06](https://github.com/lnurl/luds/blob/luds/06.md) LNURL-pay flow.

The registration API should use
[NIP-98](https://github.com/nostr-protocol/nips/blob/master/98.md) HTTP
authentication unless implementation experience reveals a concrete limitation.
A NIP-98 kind `27235` event binds a signature to an absolute URL and HTTP
method, and can bind a write request to the SHA-256 hash of its body through the
`payload` tag.

NIP-98 authenticates the HTTP request. The provider challenge carried in the
hashed request body supplies single-use freshness and binds the request to the
particular address registration. No new public Nostr registration kind is
required for the first implementation.

Ecash delivery follows [Acorn Ecash Transfer Kind 7378](ECASH-TRANSFER-KIND-7378-DESIGN.md):

```text
relay-visible event: kind 1059 NIP-59 gift wrap
encrypted inner event: kind 7378 Acorn ecash transfer
accepted proof state: kind 7375
transaction history: kind 7377
```

## Registration protocol

### 1. Request a challenge

The Acorn proposes a provider-local address and its public key:

```http
POST /v1/acorn/registrations/challenge
Content-Type: application/json
```

```json
{
  "address": "alice@example.com",
  "npub": "npub1..."
}
```

The provider returns a cryptographically random, single-use challenge:

```json
{
  "version": 1,
  "challenge_id": "018f...",
  "nonce": "base64url-random-value",
  "provider_origin": "https://example.com",
  "address": "alice@example.com",
  "registration_url": "https://example.com/v1/acorn/registrations",
  "issued_at": 1785700000,
  "expires_at": 1785700300
}
```

The provider must bind the challenge to the normalized address, proposed
public key, provider origin, expiry, and intended action. Challenges must be
short-lived and single use.

### 2. Submit the signed registration

The Acorn submits the registration body to the exact `registration_url` and
authorizes it with a NIP-98 `Authorization: Nostr ...` header signed by the
registered key:

```json
{
  "version": 1,
  "action": "register",
  "challenge_id": "018f...",
  "nonce": "base64url-random-value",
  "provider_origin": "https://example.com",
  "address": "alice@example.com",
  "npub": "npub1...",
  "delivery": {
    "protocol": "acorn-ecash-transfer",
    "version": 1,
    "relays": [
      "wss://relay-one.example",
      "wss://relay-two.example"
    ]
  },
  "mint_policy": {
    "accepted_mints": ["https://mint.example"],
    "unit": "sat"
  },
  "issued_at": 1785700000,
  "expires_at": 1785700300
}
```

The NIP-98 event must include the exact absolute request URL, the `POST`
method, and the SHA-256 hash of the exact transmitted body. The provider must
reject the request if the event public key does not equal the normalized public
key in the body.

### 3. Verify and activate

The provider verifies, in order:

1. the NIP-98 signature and event id;
2. kind `27235`, exact URL, exact method, and payload hash;
3. a narrow acceptable `created_at` window;
4. the challenge id, nonce, provider origin, address, public key, and expiry;
5. that the challenge is unused;
6. address availability or authority to update the existing registration;
7. relay normalization and policy limits;
8. protocol-version and mint-policy compatibility.

The provider then consumes the challenge and stores an immutable registration
version. A response should include the normalized mapping, registration id,
version, state, and activation time. It must never echo or request an `nsec`.

## Registration data model

At minimum, a registration should contain:

- registration id and monotonically increasing version;
- normalized Lightning address and provider origin;
- recipient hex public key and display `npub`;
- ordered, normalized delivery relays;
- delivery protocol and version;
- accepted mint policy and unit;
- state: `pending`, `active`, `suspended`, or `revoked`;
- created, updated, and activated timestamps; and
- hashes or identifiers of the authorizing request and challenge.

The provider should not expose the address-to-`npub` mapping publicly unless
that disclosure is part of an explicit product policy. Lightning address
resolution needs to be public; the underlying component mapping does not.

Relay URLs should follow Acorn's existing normalization rules. Missing schemes
become `wss://`; an explicit `ws://` scheme is preserved for deliberate local
or private deployments. Public providers should normally require TLS relays.

## Update, rotation, and revocation

The currently registered key may sign requests to:

- replace or reorder delivery relays;
- change accepted mints or delivery protocol versions;
- suspend delivery;
- reactivate a suspended address; or
- revoke the registration.

Each change creates a new registration version and consumes a new provider
challenge. Payment processing must record the exact registration version used
for a delivery.

Key rotation should require a handoff authorized by the old key and accepted by
the new key. If the old key has been lost, cryptographic continuity cannot be
proven. Any provider-assisted recovery policy is a separate, weaker trust path
and must be conspicuous. A provider must not silently turn email access or an
ordinary account password into authority over an Acorn registration.

## Payment and delivery flow

1. A payer resolves the address through the standard LUD-16 endpoint.
2. The provider returns an LNURL-pay response and creates a Lightning invoice.
3. The payer pays the invoice.
4. The provider confirms settlement and creates one durable payment record,
   uniquely keyed by payment hash.
5. The provider calculates fees and the exact net whole-satoshi amount to be
   delivered.
6. The provider obtains a Cashu token from a mint allowed by the active
   registration.
7. Before publication, the provider durably stores an encrypted delivery
   outbox record containing the token and the exact serialized event to retry.
8. The provider creates an inner kind `7378` transfer addressed to the
   registered public key and wraps it in a NIP-59 kind `1059` event.
9. The provider publishes the same serialized gift-wrap event to the registered
   relay set and records relay acknowledgements and readback results.
10. The receiving Acorn queries its relays, unwraps the transfer, verifies that
    it is the intended recipient, accepts and refreshes the token at the mint,
    writes kind `7375` proof state, and writes kind `7377` transaction history.
11. A future acknowledgement protocol may let the Acorn explicitly report
    acceptance. Until then, `published` must not be presented as `accepted`.

The recipient can be offline during steps 1 through 9. This asynchronous
boundary is the principal advantage of relay delivery.

## Payment state machine

The provider should persist explicit states rather than infer success from log
messages:

```text
invoice_issued
    -> lightning_settled
    -> ecash_provisioning
    -> ecash_ready
    -> publishing
    -> published
    -> accepted               (when acknowledgement exists)

Any in-progress state
    -> delivery_uncertain
    -> retrying | manual_review | refunded
```

`lightning_settled` is the economic commitment point. From that point until
recipient acceptance or a valid refund, the provider owes value to the
recipient. A relay acknowledgement satisfies neither that obligation nor proof
of acceptance.

External mint operations and local database transactions cannot be made truly
atomic. The implementation therefore needs a recovery journal around ecash
issuance and must be able to reconcile a crash at every boundary. Acorn's
current token-issuance API should not be placed directly in a payment callback
without this durable orchestration layer.

## Idempotency and duplicate handling

The Lightning payment hash must be the provider's unique idempotency key. The
provider must never issue two independent bearer tokens for the same settled
payment merely because a callback, worker, or publish attempt was retried.

Once a delivery event is created, retries should republish the exact serialized
event with the same event id. Creating a fresh gift wrap on every retry produces
different event ids and complicates recipient deduplication.

The inner payload should include a stable provider payment id and payment hash
or a privacy-preserving derivative suitable for recipient deduplication. The
receiving Acorn should record both the outer event id and stable transfer id.
Repeated delivery of the same token must not create repeated transaction-history
credits. Mint refresh provides a final bearer-token double-spend check, but the
application must still make its own history and cursor updates idempotent.

## Amounts, fees, and mint policy

The first implementation should deliver whole satoshis because Acorn's current
wallet accounting is sat-denominated. The LNURL endpoint must enforce a minimum
and amount policy that does not create an unexplained millisatoshi remainder.

The provider must disclose:

- Lightning amount received;
- provider fee;
- mint or issuance fee;
- net ecash amount delivered;
- mint used; and
- unit.

The provider must not select an arbitrary mint after registration. A recipient
may accept one named mint, a provider-operated mint, or an explicit allowlist.
An empty or incompatible policy should stop invoice creation rather than accept
Lightning that cannot be delivered.

When the gateway uses an external mint, it needs prefunded mint liquidity or a
reliable way to acquire tokens after settlement. The Lightning receipt and the
mint issuance are separate economic operations. That liquidity and conversion
risk belongs to the gateway and should be reflected in its operational design.

## Acknowledgement and unclaimed payments

An acknowledgement is not required for the initial delivery experiment, but
the absence of one limits what the provider can know. A mint may report that a
token was spent, but that does not cryptographically prove which Acorn accepted
it.

A later acknowledgement should be encrypted, reference the stable transfer id
and delivery event, and be signed by the registered recipient key. The event
kind and retention policy should be specified separately after operational
experience; this document does not reserve one prematurely.

The provider must define an unclaimed-payment policy before production use:

- how long it retries publication;
- how it reacts when every registered relay is unavailable or unsuitable;
- whether and how an expired payment can be refunded;
- what happens when issued ecash remains unaccepted; and
- when manual intervention is required.

## Privacy properties

Gift wrapping prevents a relay observer from directly identifying the Acorn
sender key used by the gateway. It does not make the complete system anonymous.

The gateway knows the Lightning address, registered public key, relay set,
invoice, settlement, amount, and delivery mint. A relay can observe a kind
`1059` event addressed to the recipient and can observe timing. The mint sees
issuance and refresh operations according to Cashu's privacy properties. Logs,
metrics, and traces must avoid token contents, `nsec` values, NIP-98
authorization events, and sensitive registration payloads.

## Security requirements

The implementation must address:

- high-entropy, single-use, short-lived registration challenges;
- exact provider-origin, address, URL, HTTP-method, body-hash, and public-key
  binding;
- replay rejection even across multiple provider workers;
- strict signature, timestamp, URL, relay, mint, and amount validation;
- rate limits for challenge creation, registration, and invoice creation;
- authorization of every update, suspension, rotation, and revocation;
- encrypted-at-rest storage for bearer tokens in the delivery outbox;
- narrow access to the gateway's own signing and mint credentials;
- payment-hash idempotency and duplicate-recipient protection;
- safe reconciliation after crashes and ambiguous external responses;
- relay suitability checks before accepting Lightning for a registration;
- bounded retries and circuit breakers for relays and mints; and
- auditable state transitions that do not contain secret material.

The provider is temporarily trusted with value after Lightning settlement. The
architecture removes the need to entrust it with the recipient's private key or
permanent wallet state; it does not eliminate its settlement, liquidity,
availability, or honesty risk. Production operation may also carry legal and
compliance obligations that must be assessed separately.

## Relationship to current Safebox behavior

The current Acorn payment implementation supports a legacy Safebox-specific
discovery path. A Lightning-address endpoint can advertise `safebox`, and a
`/.well-known/safebox.json/<name>` lookup can return a public key and relays.
Acorn may then send ecash using the older kind `21401` secure-transmittal path
instead of paying a Lightning invoice.

That interoperability path has practical value and should remain available
during migration, but it is not the target gateway protocol described here.
The target path uses a provider-held registration, standard Lightning
settlement, and the current Acorn kind `1059`/`7378` delivery model.

A migration adapter may support both protocols, but each payment must select
exactly one delivery path. It must never issue the same value through both
legacy kind `21401` and gift-wrapped kind `7378` as a fallback. Registration
should advertise the supported protocol and version so the choice is explicit.

## Failure behavior

- If registration verification fails, no mapping is activated.
- If the registration is suspended, revoked, incompatible, or has no suitable
  relay and mint combination, the provider should not issue an invoice.
- If Lightning has not settled, no ecash should be issued.
- If Lightning settles but ecash issuance is ambiguous, the payment enters
  reconciliation; blindly issuing again is prohibited.
- If ecash exists but publication fails, the encrypted outbox retains the exact
  event and retries it.
- If publication succeeds but readback fails, the state is
  `delivery_uncertain`, not failed and not accepted.
- If a recipient receives a duplicate, it must not credit history twice.
- If a mint rejects refresh, the recipient preserves diagnostic state without
  exposing the token and the provider retains a support path keyed by the
  stable payment id.

## Testing contract

### Deterministic tests

The registration implementation needs tests for:

- valid challenge and registration;
- wrong signer, address, origin, URL, method, body hash, or public key;
- expired, reused, missing, or concurrently consumed challenges;
- normalized addresses, relay URLs, and mint URLs;
- unauthorized updates and revocations;
- old-key/new-key rotation handoff;
- registration-version selection during payment creation; and
- accidental secret material in responses and logs.

The payment orchestration needs deterministic failure injection at every state
transition, including process restart, repeated callbacks, mint timeouts,
ambiguous mint responses, relay timeouts, partial relay success, and repeated
recipient processing.

### Live integration tests

Live tests should use a funded source wallet and disposable recipient Acorns.
At one sat, where supported, they should prove:

1. registration by signed challenge response;
2. LNURL address resolution and invoice settlement;
3. one durable provider payment record;
4. one gift-wrapped kind `1059` event containing inner kind `7378`;
5. recipient acceptance and proof refresh;
6. kind `7375` balance increase and kind `7377` credit history;
7. source/provider accounting that balances exactly;
8. retry without duplicate issue, balance, or history;
9. offline recipient recovery after delayed receipt; and
10. safe cleanup or refund of an intentionally failed delivery.

Relay suitability remains a prerequisite. The existing Acorn relay suite
should qualify the relay before any value-bearing gateway test proceeds.

## Implementation sequence

1. Freeze request schemas, canonicalization rules, state transitions, and test
   vectors in Acorn documentation.
2. Implement registration challenge and NIP-98 verification without accepting
   payments.
3. Add registration update, revocation, relay qualification, and audit records.
4. Implement a simulated-settlement adapter and durable encrypted delivery
   outbox.
5. Add small-value live settlement against a test or tightly bounded provider
   environment.
6. Add explicit recipient acknowledgement and unclaimed-payment operations if
   experience shows they are required.
7. Add a compatibility adapter and migration plan for legacy Safebox kind
   `21401` recipients.

## Open questions

- Should Acorn standardize the registration HTTP schemas, or initially treat
  them as a Safebox provider contract?
- Should the recipient publish accepted mint preferences in a private Acorn
  record as well as the provider registration?
- What acknowledgement event and retention policy provide useful assurance
  without creating unnecessary metadata?
- How long should the provider retain encrypted, unaccepted ecash?
- What refund mechanism is possible when the original Lightning payer is no
  longer reachable?
- Can a Lightning address be ported between providers, or is only the Acorn
  component key and authority portable?
- Should a provider publish a machine-readable capability document describing
  registration versions, fees, mints, and delivery protocols?

## Architectural outcome

This design gives an Acorn a public payment edge without turning the provider
into the permanent owner of the wallet. The provider supplies reachability,
Lightning settlement, and a temporary delivery bridge. The Acorn retains its
own key, relay-backed state, records, and accepted funds.

It is a concrete example of the key-code-data separation behind Acorn: the
provider can run code and expose a service, relays can hold encrypted tenant
data, and a mint can issue value, while authority remains with the Acorn
component key.
