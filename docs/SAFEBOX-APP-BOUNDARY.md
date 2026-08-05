# Safebox App Boundary

Safebox should be rebuilt as a product application on top of the Acorn kernel,
not inside the Acorn component itself.

This note sketches the intended boundary so the future web app can be built
cleanly without re-coupling product/UI concerns back into `safebox-acorn`.

## Repository boundary

Recommended split:

```text
safebox-acorn
  installable kernel / protocol component

safebox-app
  web application depending on safebox-acorn
```

Acorn should stay small, reusable, testable, and protocol-first. Safebox should
own user experience, product workflows, web sessions, deployment defaults, and
support surfaces.

## Boundaries that guide Safebox Web

The repository split is only the first boundary. Safebox Web development is
guided by four related boundaries:

| Boundary | Owns | Must not become |
| --- | --- | --- |
| **Browser / hypermedia** | Following links, submitting forms, presenting complete HTML, and optional progress feedback | A second wallet runtime, workflow engine, or browser-side store of Acorn state |
| **Safebox Web application** | HTTP routes, CSRF, encrypted sessions, input validation, product language, HTML representations, NIP-05 service, and durable provider jobs | A reimplementation of keys, proofs, record encryption, relay semantics, or mint behavior |
| **Acorn component** | Key operations, relay-backed wallet state, private-record encryption, proof handling, mint operations, transfers, recovery, and protocol invariants | A web framework, product workflow, public service directory, or deployment platform |
| **Infrastructure and operators** | TLS termination, reverse-proxy assertions, process execution, databases, relay availability, mint service, backup, and monitoring | An invisible or universal trust assumption |

This produces a deliberate request path:

```text
browser link or form
        -> Safebox Web validates the HTTP request and reconstructs Acorn
        -> Acorn performs the wallet, fund, record, mint, or relay operation
        -> Safebox Web renders complete HTML or redirects to a resource
        -> browser presents the result
```

The browser is a hypermedia client, not a distributed copy of the application.
Safebox Web should not require browser-side JavaScript to retrieve records,
calculate balances, coordinate payments, or decide workflow outcomes. Small
scripts may progressively enhance presentation—for example, displaying a wait
message and disabling a submitted button—only when ordinary links and forms
remain fully functional without them.

This boundary is also a security control. Keeping the browser thin reduces the
number of places that can hold private keys, proofs, decrypted records, and
ambiguous transaction state. It does not make the web operator blind: Safebox
Web still decrypts the HTTP-only session cookie and holds the operational
`nsec` and plaintext request data in server memory while invoking Acorn. The
execution-provider trust described below therefore remains explicit.

Application-owned services are not forced into Acorn merely because they use
Acorn. A NIP-05 directory, LNURL endpoint, provider-payment queue, and singleton
service wallet are Safebox service concerns. They should communicate with
Acorn through its public component API and durable application boundaries.
Conversely, private-record encryption, proof refresh, transaction journalling,
and relay readback verification stay in Acorn even when initiated by an HTML
form.

### Boundary test for web features

For each Safebox Web feature, ask:

1. Can the browser complete it through links and forms without JavaScript?
2. Does FastAPI own HTTP validation, sessions, CSRF, and representation?
3. Does Acorn remain authoritative for keys, funds, records, and protocol
   mutations?
4. Is durable product or provider state stored in the application rather than
   hidden in a browser or Acorn internals?
5. Are operator, proxy, relay, and mint trust assumptions visible?

A feature that crosses one of these boundaries should trigger an explicit
design review rather than an incidental implementation shortcut.

## Safebox as a trusted operator

The trusted operator is whoever provides the execution environment or running
code for an Acorn instance. That may be the user, a household, a community, an
employer, a hosted service, an appliance, or a product such as Safebox.

Safebox may operate Acorn as a private component for a user. In this model,
Safebox is not merely a web UI over a local library; it can provide a managed
execution and service surface around Acorn:

- web presence and browser UX;
- hosted onboarding and recovery flows;
- Lightning address support;
- default relay and mint configuration;
- monitoring and operational support;
- appliance, jail, or hosted deployment defaults;
- compatibility with the standalone Acorn CLI and package.

This is a valid model, especially for users who want safeguarded,
user-controlled keys, funds and records without becoming infrastructure
operators. The app should
make the trust boundary clear. An operator-run Acorn component can improve
availability and usability, but it should not remove the user's practical exit
path.

Safebox should therefore preserve:

- recovery export with explicit confirmation;
- compatibility with relay-backed Acorn state;
- the ability to replicate or migrate to another relay;
- clear display of the effective home relay, public relays, and home mint;
- eventual support for stronger key custody boundaries, such as local hardware,
  HSM-like devices, or constrained signing environments.

### Execution provider and Lightning-address gateway

The provider that runs Acorn code and the provider that supplies a Lightning
address are distinct trust roles, even when Safebox performs both.

An execution provider can observe component keys and plaintext while Acorn is
running. A Lightning-address gateway does not need the recipient's `nsec`, but
it receives Lightning, controls settlement and mint liquidity, and temporarily
owes ecash delivery to the registered component. It also holds the mapping from
the public address to the Acorn public key, delivery relays, and accepted-mint
policy.

Safebox should expose these roles separately in configuration, user messaging,
logs, and operational controls. Combining them may improve usability, but must
not obscure which party can observe secrets and which party can delay, lose,
or misdirect funds in transit.

The future registration and delivery model is documented in
[Acorn Lightning-Address Gateway Design](ACORN-LIGHTNING-ADDRESS-GATEWAY-DESIGN.md).

### Network edge and proxy authority

The network that makes Safebox reachable and the reverse proxy that asserts
public HTTPS are also separate roles. A VPN can authenticate and encrypt the
private path between a proxy machine and a Safebox machine. It does not mean
that every VPN peer should be trusted to provide forwarded transport headers.

Safebox deployment configuration should distinguish:

- the bind address and port, which determine network reachability;
- VPN or firewall policy, which restricts connections;
- the reverse proxy address, which is authorized to supply
  `X-Forwarded-Proto`, host, and client metadata; and
- the public TLS hostname presented to the browser.

Binding the application to `0.0.0.0` can be appropriate when a reverse proxy
runs on another private machine. It must not be interpreted as trusting every
reachable caller. Forwarded headers should still be accepted only from the
designated proxy, and direct internal HTTP should remain an expected rejection.

## What the app consumes from Acorn

The web app should call Acorn for wallet and record primitives rather than
reimplementing them.

Core Acorn capabilities to consume:

- initialize or recover wallet from recovery material;
- show balance and proof count;
- deposit funds;
- pay or issue ecash tokens;
- send ecash transfers;
- receive ecash transfers;
- show transaction history;
- put, get, list, and delete private records;
- issue private records to holders;
- create grant/request flows where still in scope;
- configure home relay, public relay preferences, and home mint;
- replicate wallet events to another relay;
- burn disposable wallets and sweep remaining funds;
- display recovery material with explicit confirmation.

## Event-kind model the app must respect

The app should treat the Acorn event-kind model as a contract:

| Kind | Meaning |
| --- | --- |
| `1059` | Relay-visible NIP-59 gift-wrap envelope for private ecash delivery. |
| `7378` | Inner Acorn ecash-transfer application kind. |
| `7375` | Durable spendable wallet proof state. |
| `7377` | Transaction history. |
| `37375` | Default encrypted private records. |

The app should not treat relay-visible transfer events as wallet balance. A
received ecash transfer becomes balance only after Acorn accepts the token
through the mint, refreshes proofs, and persists the updated proof state as kind
`7375`.

## What stays out of Acorn

The following should belong to the web app or a domain-specific layer, not the
Acorn kernel:

- web framework routes and templates;
- session cookies and browser authentication UX;
- branding and product copy;
- admin dashboards;
- support workflows;
- product-specific onboarding;
- deployment-specific reverse proxy configuration;
- public LNURL-pay and Lightning-address HTTP endpoints;
- the provider's address-registration directory and challenge service;
- provider Lightning settlement, mint liquidity, delivery outbox, refund, and
  unclaimed-payment operations;
- healthcare, trade, identity, or other domain schemas beyond generic record
  primitives.

Acorn may provide generic private records, issue/present mechanics, signed
registration clients, and gift-wrapped delivery primitives. Domain
applications and provider services should define their public HTTP surface,
operational custody, schema, and workflow semantics.

## Recovery and sensitive material

The web app should preserve the same recovery discipline as the CLI:

- never display `nsec` or seed material without explicit confirmation;
- make recovery material easy to back up when a wallet is created;
- make imported/recovered wallets obvious to the user;
- avoid storing transient receive keys supplied for `receive-ecash`;
- distinguish local browser/session state from durable Acorn relay-backed
  wallet state.

## Testing contract

The app should have acceptance tests that mirror the Acorn kernel tests:

```text
create/recover wallet
deposit
send gift-wrapped ecash
receive ecash
verify 7375 proof-state update
verify 7377 transaction-history update
put/get/list/delete private record
recover same wallet in another surface
```

The Acorn live relay suitability suite should remain in `safebox-acorn`. The
web app should consume its results rather than duplicate the relay-compatibility
matrix.

## Migration approach

The existing Safebox web app should be treated as a reference implementation
and migration source, not as the new foundation.

A clean rebuild should proceed by:

1. depending on `safebox-acorn`;
2. implementing minimal wallet init/recover;
3. adding balance and transaction history;
4. adding deposit/pay/ecash transfer/receive;
5. adding private record CRUD;
6. adding issued private record workflows;
7. adding relay/mint configuration and recovery UX;
8. hardening deployment, tests, and support flows.

This keeps the app focused on product polish while Acorn remains the
user-controlled protocol component.

## Working stateless integration pattern

The first independently implemented Safebox Web slice now demonstrates a
browser-held encrypted bootstrap session, request-scoped Acorn reconstruction,
relay-backed balance loading, record-label listing, and individual record
retrieval without a wallet database or server-side session store.

The boundary has since been extended through an end-to-end external NIP-05
ecash milestone. Safebox Web provides the authenticated, CSRF-protected user
action to check for incoming transfers, while the request-scoped Acorn performs
gift-wrap decryption, mint acceptance and proof refresh, kind `7375`
persistence, and kind `7377` transaction journalling. The updated balance and
credit history are then rendered by the web application. This keeps protocol
and fund-state authority inside Acorn while allowing Safebox Web to concentrate
on session handling and user experience.

The detailed contract, security boundaries, browser-origin lesson, residual
risks, and resulting Acorn API recommendations are documented in
[Stateless Web Integration for Acorn](STATELESS-WEB-INTEGRATION.md).

The corresponding implementation contract in the application repository is
[Safebox Web Hypermedia Architecture](https://github.com/trbouma/safebox-web/blob/main/docs/HYPERMEDIA-ARCHITECTURE.md).
