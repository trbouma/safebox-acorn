# Stateless Web Integration for Acorn

## Summary

An Acorn-backed web application can provide a useful hosted interface without
maintaining a database of wallets or server-side sessions. The working Safebox
Web prototype demonstrates a narrow pattern:

```text
user recovery input
        |
        v
encrypted browser cookie: nsec + bootstrap relay
        |
        v
request-scoped Acorn component
        |
        v
encrypted relay-backed wallet and record state
```

The application reconstructs an Acorn component for each authenticated
request. It may load encrypted state from the selected relay, use that state in
memory, render a response, and then discard the request-scoped object. It does
not need a wallet database, local Acorn configuration file, or server-side
session store.

This pattern is **stateless at the web application persistence layer**. It is
not trustless and it is not a claim that the server cannot access keys. The
running code decrypts the cookie and necessarily holds the operational `nsec`,
decrypted records, and proofs in process memory while serving a request. The
operator of that execution environment remains a trusted provider.

The initial reference implementation is maintained separately in
[trbouma/safebox-web](https://github.com/trbouma/safebox-web). This document
records the Acorn-facing contract and the lessons that should survive changes
to the web framework or product interface.

## Objectives

The integration should:

- preserve Acorn as the source of wallet and record behavior;
- avoid a server-side wallet database or session table;
- let a user connect an existing Acorn using an `nsec` or offline mnemonic;
- keep the selected bootstrap relay explicit;
- reconstruct Acorn through the web framework's dependency boundary;
- support a small read-only vertical slice before adding mutation;
- prevent ordinary logs, errors, templates, and APIs from exposing secrets;
- require secure transport outside tightly constrained loopback development;
  and
- remain interoperable with the CLI and other Acorn applications.

The first slice does not attempt accounts, password reset, federated login,
multi-device session management, revocation, payment, record mutation, relay
migration, or HSM-backed signing.

## Separation of key, code, and data

The pattern makes Acorn's separation model concrete:

| Layer | Location | Trust and lifecycle |
| --- | --- | --- |
| Operational key | Encrypted browser cookie; plaintext only in request memory | User supplies or derives it; the web operator can access it while code runs. |
| Executing code | Safebox Web process | Trusted to decrypt the cookie, construct Acorn, and avoid leaking secrets. |
| Durable data | User-selected bootstrap relay | Encrypted and signed by Acorn; the relay provides availability but need not see plaintext. |
| Funds | Cashu mint, represented by encrypted relay-backed proofs | Mint remains an independent trust domain; merely displaying balance need not contact it. |
| Public NIP-05 name | Domain DNS, TLS/reverse proxy, and the application operator's directory database | The domain asserts a current name-to-key mapping; it does not independently prove a person's identity or permanent ownership. |

The browser becomes the holder of an encrypted bootstrap capability. The relay
remains the durable data layer. The web process joins them transiently.

### NIP-05 naming trust boundary

An Acorn may cryptographically prove control of its component key to a web
application before claiming a NIP-05 handle. That protects the claim endpoint,
but it does not make the resulting public name self-authenticating. A NIP-05
identifier is trustworthy only to the extent that a relying party trusts:

- the domain registrant and DNS/TLS configuration to direct requests to the
  intended service; and
- the reverse-proxy operator to terminate TLS and route requests to the
  intended application without substituting another backend or response; and
- the application operator, running code, and directory database to return the
  authorized name-to-public-key and relay mapping.

A domain, proxy, or application compromise can reassign a handle or redirect
its relay hints even though the Acorn private key remains safe. Application
controls can restrict which proxy addresses are authorized to supply forwarded
metadata, but they cannot force an authorized proxy to route to the genuine
application. NIP-05 therefore means
“this domain currently asserts that this name maps to this key.” It is not, by
itself, proof of civil identity, a permanent ownership guarantee, or a
substitute for verifying a high-value recipient key through another channel.

This is an inversion of the usual hosted-wallet architecture: the application
does not make its account database the authoritative home of keys, funds,
and records. It reconstructs a component whose continuity comes from its key
and protocol state.

## Authentication inputs

The login flow accepts:

```text
nsec + bootstrap relay
```

or:

```text
offline mnemonic + bootstrap relay
```

An offline mnemonic is validated as BIP39 and passed through Acorn's documented
SLIP-10 secp256k1 derivation contract. The resulting `nsec` becomes the
operational secret. The mnemonic must be discarded after derivation and must
not be placed in the cookie, application configuration, logs, or relay-backed
web-session state.

An imported `nsec` has no reconstructable original mnemonic. The interface
must not imply otherwise. See the [Recovery Specification](RECOVERY-SPEC.md).

The bootstrap relay is normalized before it enters the cookie. A missing
scheme becomes `wss://`. Plain `ws://` should be accepted only for an explicitly
local loopback relay.

## Encrypted browser session

The minimal session payload is:

```json
{
  "version": 1,
  "nsec": "nsec1...",
  "bootstrap_relay": "wss://relay.example.com"
}
```

The payload must be encrypted and authenticated, not merely signed or
Base64-encoded. The reference implementation uses a Fernet token and enforces
a bounded token age. Equivalent implementations may use another reviewed
authenticated-encryption construction.

Production cookies should use:

- the `__Host-` name prefix;
- `Secure`;
- `HttpOnly`;
- `SameSite=Strict`;
- `Path=/`;
- no `Domain` attribute; and
- a bounded `Max-Age`.

The server-held cookie key must be stable across workers and restarts. Changing
it invalidates every existing session. The first implementation has no key
rotation or revocation mechanism; both remain release work.

Cookie encryption does not protect an `nsec` from malicious or compromised web
code. Anyone who obtains both the encryption key and a session cookie can
recover the `nsec`. A stolen decrypted session remains usable until expiry or
cookie destruction because there is no server-side revocation state.

## Request-scoped dependency model

FastAPI dependency injection provides a clean boundary with two levels:

```text
SessionCredentials dependency
    decrypt and validate cookie

Acorn dependency
    construct Acorn(nsec, home_relay, relays=[home_relay])

LoadedAcorn dependency
    await Acorn.load_data() with a bounded timeout
```

Routes declare the narrowest dependency they require. A session-inspection
route does not need relay state. A balance or record route uses the loaded
dependency. Mutating routes should eventually use a separate dependency or
service boundary that makes mutation, locking, and failure recovery obvious.

This separation prevents a seemingly harmless route from loading or mutating
more wallet state than it needs. It also makes tests able to replace the loaded
Acorn dependency with a deterministic fake without using a real `nsec`, relay,
or mint.

## Read-only vertical slice

The proven first slice consists of:

1. connect with an `nsec` or offline mnemonic;
2. reconstruct the component's key authority;
3. load wallet state from the bootstrap relay;
4. display balance;
5. list private record labels; and
6. retrieve and render one selected private record.

The next developer-preview slice adds an explicitly confirmed Lightning-address
payment. It is the first state-changing web operation and therefore uses a
separate mutation dependency rather than silently extending the read-only
loaded-wallet contract.

### Balance

`Acorn.load_data()` queries and decrypts the wallet record and kind `7375`
proof events, deduplicates proofs, and derives balance in memory. In the
current implementation this path does not query a mint, refresh proofs, or
publish relay events. It is therefore suitable for an observational balance
page.

The displayed value is total proof value, not necessarily the amount available
for one Lightning payment. Proofs may span multiple mints and keysets, and mint
fees reduce actual payable capacity. See
[Proof State and Relay Consistency](PROOF-STATE-RELAY-CONSISTENCY.md).

### Record labels

The index uses `Acorn.get_user_record_labels()` and displays only returned
labels. Each label is encoded as a query parameter:

```text
/record?label=Field+Notes
```

A query parameter is preferable to an unescaped path segment because labels
may contain spaces, slashes, Unicode, or punctuation. Display text and link
attributes must still be HTML-escaped.

The current Acorn label helper calls the broader record-list operation, which
decrypts record envelopes and materializes payloads before returning only the
labels. The web page does not display or retain those payloads, but they can
exist transiently in the Acorn process. A narrower Acorn label-index API would
reduce memory exposure and unnecessary work.

### Record retrieval

The detail route calls `Acorn.get_record_safebox(record_name=label)`. String
payloads are rendered as escaped preformatted text. Structured payloads are
serialized as formatted JSON and then escaped. Record content is never treated
as trusted HTML.

Missing records return a generic not-found response. Unexpected exceptions
must not place the requested label, decrypted payload, key, or relay event
content in application logs.

## First mutation: Lightning-address payment

This section describes an outbound, user-initiated payment from the connected
Acorn. It does not make the stateless web application a Lightning-address
provider for incoming payments.

The payment page delegates the complete operation to
`Acorn.pay_multi(amount, lnaddress, comment)`. The web layer does not select
proofs, construct invoices, call a mint, update transaction history, or write
relay events itself.

Before calling Acorn, the web route requires:

- an authenticated loaded Acorn component;
- a valid short-lived CSRF form token;
- an explicit confirmation checkbox;
- a syntactically plausible Lightning address;
- a positive whole-sat amount no greater than displayed total balance; and
- a bounded comment length.

The total-balance precheck is only an early user-facing check. Acorn still
decides whether amount plus mint fee reserve fits one spendable keyset. A
wallet can have enough total value while lacking sufficient capacity in any
single keyset.

Acorn retains responsibility for the safety-critical sequence:

```text
acquire wallet lock
reconcile previous pending melts
resolve Lightning address and invoice
obtain mint quote
checkpoint post-swap proofs
persist pending-melt journal
submit melt
resolve PAID / UNPAID / unknown outcome
update proofs and transaction history
release wallet lock
```

A timeout or exception is not presented as a definite failure. The web
interface instructs the operator not to retry blindly and to run
`acorn reconcile-payments` and inspect transaction history. This preserves the
kernel's ambiguous-payment contract.

The current developer-preview response renders the success result directly
from the POST. Browsers normally warn before resubmitting a refreshed POST, and
the page explicitly says not to refresh. Before pilot use, replace this with a
POST/Redirect/GET result flow and add a durable, wallet-bound idempotency model;
a stateless CSRF token alone does not prevent deliberate or accidental replay
of a previously valid payment submission.

### Inbound Lightning reachability is a separate service

A future inbound service would let an Acorn register its component public key,
delivery relays, and accepted-mint policy with a Lightning-address gateway.
After receiving and settling Lightning, that gateway would obtain ecash and
publish a NIP-59 kind `1059` gift wrap containing an inner kind `7378`
transfer to the registered component.

That gateway cannot remain stateless in the same sense as this web interface.
It needs durable registration versions, payment-hash idempotency, settlement
accounting, an encrypted bearer-token delivery outbox, retry state, and an
unclaimed-payment or refund policy. Those provider records are operational
state; they are not the recipient's Acorn wallet state.

The receiving Acorn still retains its own key and relay-backed wallet data.
The gateway never needs its `nsec`, but it is temporarily responsible for value
between Lightning settlement and recipient acceptance. See
[Acorn Lightning-Address Gateway Design](ACORN-LIGHTNING-ADDRESS-GATEWAY-DESIGN.md).

## Transport boundary

HTTPS is mandatory outside local development. The only plain-HTTP exception in
the reference pattern is direct access to:

```text
http://127.0.0.1:<port>
```

Both the requested hostname and the connected client address should be
loopback. Binding Uvicorn to `0.0.0.0` does not make an insecure remote request
acceptable.

Behind a TLS-terminating reverse proxy, the application must receive a trusted
`https` scheme. Forwarded headers should be accepted only from the explicitly
configured proxy address. Trusting arbitrary `X-Forwarded-Proto` headers lets a
remote client bypass the transport decision.

When the reverse proxy runs on another VPN-connected machine, the application
may need to bind its published container port to `0.0.0.0` so that the proxy can
reach it. This changes reachability, not authority. The VPN and firewall define
who can connect; Uvicorn's forwarded-header allowlist defines which immediate
peer may assert that the original browser request used HTTPS.

A deployment should prove both properties explicitly:

1. a direct HTTP request from the proxy machine without forwarded HTTPS
   metadata receives the application's HTTPS-required response; and
2. the same request with `X-Forwarded-Proto: https` succeeds only when it comes
   from the configured proxy address.

The first independently deployed Safebox Web instance validated this pattern
with Nginx on one Tailscale machine and the Dockerized application on another.
The public `/health` response returned status 200 with HSTS and the expected
security headers, while direct internal HTTP remained rejected. This is a
useful deployment acceptance test rather than merely a troubleshooting step.

Recommended response controls include:

- `Cache-Control: no-store`;
- a restrictive Content Security Policy;
- `frame-ancestors 'none'` and `X-Frame-Options: DENY`;
- `X-Content-Type-Options: nosniff`;
- `Referrer-Policy: no-referrer`; and
- HSTS on HTTPS responses.

## CSRF lesson: `Origin: null`

Initial browser testing rejected a legitimate loopback login because the
browser sent:

```text
Origin: null
```

An opaque `null` origin cannot prove that a request came from the displayed
Safebox page. Simply allowing it would let sandboxed or privacy-modified
cross-site contexts bypass an origin-only CSRF check.

The stateless solution is a short-lived encrypted and authenticated form token:

1. the server places a fresh token in the login or logout form;
2. the form returns it as a hidden field;
3. the server validates its purpose, authenticity, and age; and
4. no token state is stored server-side.

Non-null origins must still match the request's normalized scheme, hostname,
and effective port. A cross-origin request remains rejected even if another
control is present. A `null` or absent Origin is acceptable only when the form
token is valid.

The CSRF token contains no wallet material. A production implementation should
derive independent subkeys for cookie encryption and CSRF protection, support
rotation, and preserve cryptographic domain separation.

## Failure behavior

Relay access is an external operation and must be bounded. The reference
pattern applies a configurable timeout to wallet, label, and record queries.

User-facing failures should distinguish:

- session missing or expired (`401`);
- invalid or expired form token (`403`);
- record not found (`404`);
- relay or application dependency failure (`502`); and
- relay timeout (`504`).

Responses should remain useful without echoing secrets, labels, payloads, raw
relay events, or exception text. Logs should record operation names and safe
error classes rather than secret-bearing local variables or exception
messages.

## Legacy mnemonic retention interaction

The target recovery policy treats the mnemonic as an offline, one-time
bootstrap artifact. Current Acorn wallet metadata may still contain a retained
encrypted mnemonic. Consequently, `load_data()` can bring that legacy phrase
into request memory even though Safebox Web never places a mnemonic in its
cookie.

This is another reason to complete the migration described in the
[Recovery Specification](RECOVERY-SPEC.md#implementation-status-and-migration).
Until then, a hosted Acorn process should be assumed capable of accessing the
retained mnemonic as well as the operational `nsec`.

## Testing contract

The web integration should have deterministic tests for:

- refusal to start without a valid server cookie key;
- automatic local configuration loading without committing `.env`;
- HTTPS enforcement and the exact loopback exception;
- encrypted cookie contents and security attributes;
- cookie expiry, corruption, and unsupported versions;
- `nsec` validation and mnemonic-to-`nsec` compatibility vectors;
- confirmation that the mnemonic is absent from the cookie;
- matching, mismatched, absent, and `null` Origin behavior;
- valid, invalid, expired, and tampered CSRF form tokens;
- request-scoped Acorn construction;
- bounded relay loading and sanitized failures;
- balance display from a fake loaded wallet;
- label URL encoding and HTML escaping;
- payload escaping for both strings and structured JSON;
- payment validation and explicit confirmation without calling a real mint;
- exact delegation of address, amount, and comment to a fake Acorn; and
- sanitized timeout and ambiguous-payment responses that never encourage an
  automatic retry.

These tests require no live relay or mint. A later opt-in interoperability test
may use a disposable Acorn wallet and relay, but the kernel's relay suitability
suite should remain in `safebox-acorn`.

## Acorn API lessons

The prototype identified public API improvements that belong in Acorn:

1. Export mnemonic validation and mnemonic-to-`nsec` derivation through a
   stable public recovery API. The web application currently needs an internal
   helper.
2. Provide an explicitly read-only wallet-load or snapshot operation whose
   non-mutation contract is tested.
3. Provide a narrow record-label operation that does not retain complete
   payload objects longer than required.
4. Return typed, sanitized exceptions that distinguish missing wallet data,
   relay timeout, incompatible relay behavior, and invalid records.
5. Provide an immutable read model for public-key information, balance, mint/keyset capacity,
   and record labels so applications do not depend on mutable Acorn internals.

The web application should consume these APIs rather than copy cryptography,
event filters, label hashing, proof accounting, or record parsing into its own
repository.

## Residual risks and next gates

Before treating browser-initiated payments as pilot-ready or adding record
mutation, address:

- cookie-key rotation and multi-key decryption during migration;
- logout versus true session revocation;
- XSS testing, because same-origin script can exercise authenticated routes
  even when an `HttpOnly` cookie cannot be read directly;
- multiple concurrent requests using the same wallet and stale relay views;
- mutation-specific locking, idempotency, and recovery journals;
- POST/Redirect/GET payment results and wallet-bound replay prevention;
- protection against oversized cookies, forms, records, and relay responses;
- durable transfer outbox behavior before any browser-initiated ecash send;
- a separate provider architecture before offering inbound Lightning-address
  registration or Lightning-to-ecash delivery;
- deployment behind a correctly constrained TLS proxy; and
- eventual hardware-backed or locally mediated signing so the hosted process
  need not receive unrestricted key authority.

The appropriate next product step is not to reproduce the legacy web
application feature by feature. It is to extend this small, tested boundary one
capability at a time while keeping Acorn responsible for protocol behavior and
Safebox responsible for presentation, sessions, deployment, and user consent.
