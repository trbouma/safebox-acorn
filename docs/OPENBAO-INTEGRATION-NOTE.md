# OpenBao Integration Note for Hosted Acorns

## Status and purpose

This note defines how an application or trusted provider may use OpenBao to
protect secrets used with Safebox Acorn without making OpenBao a dependency of
the Acorn package or changing Acorn's user-controlled model.

It is an integration boundary and security note. It does not claim that Acorn
contains an OpenBao client, that a current deployment uses OpenBao, or that
placing a secret in OpenBao makes the surrounding execution environment
trustless.

The core rule is:

> Acorn accepts cryptographic authority from its caller. How a trusted
> execution environment obtains and protects that authority is an application
> and deployment concern.

OpenBao may therefore protect provider-managed Acorn secrets. Acorn itself
should remain independently installable and unaware of OpenBao paths, tokens,
policies, leases, agents, or storage topology.

## Relationship between Acorn and OpenBao

Acorn and OpenBao address different layers:

| Layer | Principal responsibility |
| --- | --- |
| Acorn | Exercise key authority over relay-backed funds and records using interoperable protocols |
| Consuming application | Authenticate users, obtain authorized key material, construct Acorn instances, and present workflows |
| OpenBao | Protect and audit secrets controlled by the application operator |
| Execution environment | Run the application and Acorn code while handling authorized plaintext in memory |
| Relay and mint infrastructure | Provide event availability and bearer-proof issuance and settlement |

OpenBao can improve operator-side secret storage, access separation,
versioning, and audit evidence. It does not replace Acorn's relay-backed data
model, Cashu proof state, recovery specifications, or cryptographic event
formats.

## Integration boundary

```text
OpenBao or another secret source
              |
              | provider-authorized secret delivery
              v
consuming application / execution environment
              |
              | nsec and explicit configuration
              v
        Acorn public API
              |
              +------------> relays
              +------------> mints
              `------------> blob servers
```

The application resolves the secret before constructing or invoking Acorn:

```python
service_nsec = secret_source.read("service-acorn-nsec")

wallet = Acorn(
    nsec=service_nsec,
    home_relay=home_relay,
    relays=[home_relay],
)
```

`secret_source` is application code. It may read a protected file rendered by
OpenBao Agent, an operating-system key store, an HSM adapter, a prompt, or a
test fixture. Acorn should not need to know which mechanism supplied the
value.

This preserves dependency direction:

```text
application -> Acorn
application -> OpenBao integration

Acorn -X-> application
Acorn -X-> OpenBao
```

## Supported usage models

### Independent user Acorn

A locally operated Acorn may continue to use its CLI configuration, direct
secret input, external entropy, or recovery mnemonic. OpenBao is not required.
Installing Acorn must not install an OpenBao SDK, require a running OpenBao
server, or change ordinary CLI behavior.

### Temporary web-connected Acorn

In the Safebox Web model, a user supplies an `nsec` or Safebox Acorn mnemonic
and the web application places the resulting operational key in an encrypted,
authenticated browser session. OpenBao may protect the web application's
cookie-encryption master key.

That does not mean the user `nsec` should be copied into OpenBao. The
application still receives the user key in plaintext and necessarily holds it
in memory while processing the request. OpenBao improves custody of the
operator's cookie key; it does not remove the need to trust the running web
code, host, proxy path, and operator.

### Provider-operated service Acorn

A provider may run a persistent Acorn to accept Lightning payments, issue
invoices, and deliver ecash to other Acorns. This component has its own
`nsec`, funds, relay history, and operational continuity.

OpenBao is a suitable place for the provider to store that service `nsec` at
rest. A narrowly authorized process may receive the key at startup through a
protected file or equivalent delivery channel. The application then passes
the key to Acorn through its normal API.

The service key remains plaintext in authorized process memory while Acorn
signs, decrypts, or spends. OpenBao protects storage and delivery; it does not
create a confidential-computing boundary.

### Explicit custodial deployment

A provider could choose to store individual users' Acorn keys in OpenBao, but
that would be a materially different custodial product. It must not be treated
as a transparent implementation detail.

Such a design would require separate documentation and consent covering:

- who can authorize OpenBao to release a user key;
- operator and administrator access;
- user recovery and export;
- account closure and verified deletion;
- legal access and compelled disclosure;
- backup, replication, and retention;
- incident notification; and
- whether the provider can act as the Acorn without the user present.

This mode is outside the default Acorn and Safebox Web architecture.

## Secret classification

| Material | Default owner | OpenBao suitability | Notes |
| --- | --- | --- | --- |
| User Acorn `nsec` | User/controller | No, by default | Central storage changes the trust and custody model |
| Safebox Acorn mnemonic | User/controller | No, by default | Offline recovery material should remain under separate user custody |
| Record Protection Key or mnemonic | User/controller | No, by default | Central co-storage weakens its intended separation from the Acorn key |
| Provider service Acorn `nsec` | Trusted provider | Yes | Deliver only to the singleton provider-wallet process |
| Web cookie-encryption key | Trusted provider | Yes | This is an application secret, not an Acorn secret |
| Database credentials | Trusted provider | Yes | Prefer short-lived dynamic credentials when supported operationally |
| Cashu proofs | Acorn/controller | Not as ordinary secrets | They are live bearer state with protocol-specific persistence and concurrency rules |
| Private records and blobs | Acorn/controller | No normal need | Their protocol formats already define encryption and relay/blob storage |
| Relay and mint URLs | Acorn/controller or application | Usually no | Configuration integrity matters, but the values are not normally confidential |

OpenBao should not become a parallel wallet database. Moving proofs or record
state outside Acorn's documented event and recovery model would introduce
split-brain state and bypass its consistency rules.

## Application-facing secret delivery

OpenBao Agent can authenticate to OpenBao, renew its token, and render a KV
secret to a local file. This pattern is preferable to giving Acorn an OpenBao
token or teaching Acorn how to authenticate to an operator's infrastructure.

The consuming application should:

1. receive the secret through a process-specific protected file;
2. validate its type and encoding without logging the value;
3. pass the value directly to Acorn;
4. avoid copying it into application databases or general configuration
   records;
5. fail closed when required provider authority is unavailable; and
6. define when the temporary file is removed and how the process is restarted
   after rotation.

File-reading behavior should be implemented by the application or a small
generic configuration utility, not in Acorn's wallet logic. If Acorn later
provides a generic helper, it must remain secret-manager-neutral and accept a
path or callback without importing an OpenBao-specific client.

## Least-privilege separation

Each hosted process should have its own OpenBao identity and policy. In the
Safebox Web example:

- the web process may read the cookie-encryption key but not the service Acorn
  `nsec`;
- the singleton provider worker may read the service Acorn `nsec` but not the
  web cookie key;
- the reverse proxy may read neither;
- ordinary Acorn CLI processes receive no provider OpenBao identity; and
- application identities cannot write secrets or administer policies.

This separation limits accidental exposure and produces useful audit evidence.
It does not protect secrets from a host administrator or attacker who can read
both process memory and secret-delivery files.

## Nostr keys and the Transit limitation

Acorn uses `secp256k1` keys for Nostr signatures and NIP-44 operations. The
currently documented OpenBao Transit asymmetric signing types include Ed25519,
NIST P-256/P-384/P-521, and RSA, but not `secp256k1`.

OpenBao Transit therefore cannot presently replace an Acorn `nsec` with a
non-exportable Transit key while preserving Acorn's Nostr behavior. Storing
the `nsec` in OpenBao KV still requires releasing it to the authorized process.

Even if a future signer supports `secp256k1`, Acorn needs more than a signature
operation. It also derives public identifiers, performs NIP-44 key agreement
and decryption, and executes recovery-related behavior. A future external-key
design would need a general cryptographic-provider interface covering every
required operation, with compatibility vectors and failure semantics. It
should be HSM- and service-neutral rather than designed specifically around
OpenBao.

## Rotation semantics

### Provider Acorn key

An Acorn `nsec` is authority and continuity, not merely a replaceable API
password. Rotating it changes the component public key and can affect:

- funds and spendable proof state;
- Nostr event authorship and encrypted records;
- relay queries and replication;
- NIP-05 and Lightning-address mappings;
- counterparties that recognize the previous key; and
- recovery material and operational history.

OpenBao versioning can preserve old secret versions, but it cannot define the
protocol migration. Provider-key rotation must use an Acorn-aware procedure to
sweep funds, move required records, update mappings, communicate continuity,
and decide when the former key is destroyed.

### Cookie-encryption key

The cookie key belongs to Safebox Web rather than Acorn. Immediate replacement
can invalidate all connected Acorn sessions. The application needs a bounded
key-ring and key-version design before routine rotation can preserve active
sessions.

### User key

User-key recovery or migration remains controlled by the Acorn recovery and
replication specifications. An operator's OpenBao rotation policy must not
silently rotate user authority.

## Availability and failure behavior

OpenBao becomes an availability dependency for any process that requires a
secret from it at startup. The integration should specify:

- whether a running process continues after OpenBao becomes unavailable;
- how long an agent may use or renew cached authorization;
- whether rendered files reside only in memory;
- how a sealed or unavailable OpenBao instance affects restart;
- how operators distinguish missing authority from a new-wallet condition;
- how backups and restores are tested; and
- which alerts require service shutdown or incident response.

A missing service key must never cause Acorn or its application to generate a
new key automatically. Generation is appropriate only for an explicit new
wallet ceremony. Silent regeneration could abandon funds, records, mappings,
and recognized authority.

Acorn operations already depend on relays and mints. OpenBao adds a different
provider-side dependency; it must not be confused with relay replication or
wallet recovery.

## Logging and audit boundary

Acorn's secure-logging rules continue to apply. The consuming application must
not log:

- OpenBao tokens or AppRole secret IDs;
- returned `nsec` values;
- mnemonics or record-protection material;
- rendered secret-file contents;
- Cashu proofs or tokens; or
- plaintext private records.

OpenBao audit logging should record the client identity, path, operation,
decision, and secret version without raw secret values. Application logs and
OpenBao audit logs should use correlation identifiers that do not contain
wallet secrets or sensitive event content.

## Package and API requirements

The Acorn package should preserve the following properties:

- no mandatory OpenBao dependency or SDK;
- no OpenBao-specific configuration in the core wallet schema;
- no default network connection to an OpenBao endpoint;
- no assumption that a secret manager is available;
- no automatic provider-secret persistence;
- no change to record, proof, event, or recovery formats; and
- identical cryptographic behavior regardless of the caller's secret source.

Potential future generic interfaces may include:

- a caller-supplied secret callback;
- a `KeyProvider` protocol covering all Acorn cryptographic operations; or
- explicit zeroization hooks where Python and underlying libraries permit
  meaningful guarantees.

These should be justified by multiple integration targets and independently
reviewed before becoming public APIs.

## Validation plan

A hosted OpenBao integration should demonstrate that:

- Acorn installs and runs without OpenBao;
- the same tests pass when an `nsec` is supplied from an OpenBao-rendered file;
- direct input and secret-manager input derive the same expected `npub`;
- the web and worker roles cannot read each other's secrets;
- denied OpenBao reads are audited without revealing secret material;
- malformed or missing provider secrets fail closed;
- missing secrets never trigger implicit wallet creation;
- secrets do not appear in logs, process arguments, image layers, shared
  persistent volumes, or test artifacts;
- a service worker restart preserves the same `npub` and wallet state;
- a short OpenBao outage has documented behavior;
- seal, unseal, snapshot, restore, and disaster-recovery exercises succeed;
  and
- provider-key rotation is tested as an Acorn migration rather than a simple
  KV overwrite.

Use disposable keys, test relays, test mints, and very small test balances for
all integration and recovery exercises.

## Residual risks

OpenBao integration does not prevent:

- an authorized application from observing the secret it receives;
- a compromised execution environment from reading Acorn keys and plaintext
  while they are in use;
- a privileged host or OpenBao operator from abusing provider authority;
- relay censorship, deletion, stale responses, or traffic analysis;
- mint failure, proof invalidation, or settlement disputes;
- application logic defects; or
- user loss or unsafe handling of offline recovery material.

It reduces secret sprawl and improves operator controls. It does not convert a
hosted Acorn into a hardware wallet, confidential-computing environment, or
trustless service.

## Decision summary

OpenBao is compatible with Acorn when it remains outside the component and is
used by a consuming application to protect operator-managed secrets. The first
appropriate use is the provider service Acorn `nsec`; Safebox Web may also use
OpenBao for its cookie-encryption key under a separate policy.

User recovery secrets remain user-controlled by default. Transit is deferred
because it does not currently provide the complete `secp256k1` signing,
decryption, and derivation interface Acorn requires. Any future external-key
support should be a generic Acorn cryptographic-provider design rather than an
OpenBao-specific dependency.

## References

- [What is OpenBao?](https://openbao.org/docs/what-is-openbao/)
- [OpenBao architecture](https://openbao.org/docs/internals/architecture/)
- [KV version 2 secrets engine](https://openbao.org/docs/secrets/kv/kv-v2/)
- [AppRole authentication](https://openbao.org/docs/auth/approle/)
- [Agent auto-authentication](https://openbao.org/docs/agent-and-proxy/autoauth/)
- [Agent templates](https://openbao.org/docs/agent-and-proxy/agent/template/)
- [Transit secrets engine](https://openbao.org/docs/secrets/transit/)
- [Transit API and supported key types](https://openbao.org/api-docs/secret/transit/)
- [Audit devices](https://openbao.org/docs/2.4.x/audit/)
- [Integrated storage](https://openbao.org/docs/internals/integrated-storage/)
- [Safebox Web OpenBao Integration Note](https://github.com/trbouma/safebox-web/blob/main/docs/OPENBAO-INTEGRATION-NOTE.md)

## Related Acorn documents

- [Acorn Component Boundary](ACORN-COMPONENT-BOUNDARY.md)
- [Safebox App Boundary](SAFEBOX-APP-BOUNDARY.md)
- [Stateless Web Integration](STATELESS-WEB-INTEGRATION.md)
- [Secret Input Specification](SECRET-INPUT-SPEC.md)
- [Secure Logging Specification](SECURE-LOGGING-SPEC.md)
- [Recovery Specification](RECOVERY-SPEC.md)
- [Relay Resilience and Replication](RELAY-RESILIENCE-AND-REPLICATION-DESIGN.md)
- [Roadmap to Releasability](ROADMAP-TO-RELEASABILITY.md)
- [`SECURITY.md`](../SECURITY.md)
