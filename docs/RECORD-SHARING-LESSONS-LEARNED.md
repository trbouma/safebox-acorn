# Record Sharing Lessons Learned

## Status and purpose

This note records what Acorn learned from the previous major Safebox record-
sharing iteration and how those lessons shaped the current transfer model. It
is an architectural retrospective, not a compatibility specification or a
criticism of the earlier work. That implementation proved that private records
could be exchanged and exposed the coordination costs that should not become
part of the Acorn kernel.

The resulting principle is simple:

> Sharing one record should require authority over one temporary encrypted
> object, not a live relationship between two wallets.

The normative current format is defined in the
[Acorn Record Transfer Specification](RECORD-TRANSFER-SPEC.md).

## What the earlier iteration explored

The previous Safebox application combined several ideas into an interactive
record-transmittal workflow:

- custom authorization and embedding descriptors;
- sender and recipient keys, nonces, scopes, event kinds, and relay lists;
- a relay-mediated request and response handshake;
- WebSocket connections for status and request notification;
- polling and `since` filters, including fallbacks for clock skew and eventual
  relay consistency;
- recipient-specific encryption and experimental KEM handling;
- application routes that coordinated discovery, authorization, transmission,
  receipt, and presentation; and
- browser state that had to remain synchronized with relay and server state.

Each mechanism addressed a real concern. Together, however, they made a simple
user intent—“let this other Safebox acquire this record”—depend on several
distributed systems being available and correctly synchronized at the same
time.

## Challenges revealed by that model

### Live coordination became part of the protocol

The sender, recipient, application servers, relay infrastructure, and browser
connections participated in a multi-step conversation. A delayed relay event,
closed WebSocket, mobile background transition, reverse-proxy problem, clock
difference, or page reload could interrupt the flow without clearly identifying
which steps had completed.

The protocol consequently needed reconnection, replay protection, time-window
selection, stale-message filtering, and status recovery. Those are appropriate
concerns for a general messaging system, but they are disproportionate for
transferring one bounded record.

### Discovery, authorization, encryption, and delivery were coupled

The earlier flow needed to know who the recipient was, where to contact them,
which relay and event kind to use, how to correlate the response, and which
cryptographic profile applied. This coupled identity resolution and presence
with the mechanics of transferring bytes.

It also made experimentation difficult: changing a descriptor, relay policy,
KEM profile, or recipient interaction affected several other layers.

### Failure states multiplied

The system could fail before discovery, during authorization, after the sender
published, before the recipient observed the event, during decryption, or after
storage. A generic “failed” result could not safely say whether the record had
been delivered, and automatic retries risked duplicate or conflicting work.

### Application concerns leaked into the component

WebSocket lifetimes, route state, QR presentation, notifications, and
application-specific record types began to shape the underlying transfer
mechanism. This made the code harder to reuse outside that particular Safebox
application and obscured the boundary between Acorn and its host.

### Testing required too many moving parts

Meaningful end-to-end tests needed two active participants plus functioning
relays, timing behavior, browser coordination, and multiple cryptographic
paths. Unit tests could cover pieces but struggled to express the overall
invariant: the receiver must either store the complete record or store nothing.

## The simpler Acorn model

The current design treats sharing as a temporary encrypted package represented
by a compact bearer descriptor.

```text
sender record
    -> encrypted temporary package
    -> opaque Blossom object
    -> Base64URL QR descriptor
    -> receiver retrieves and verifies
    -> receiver stores under its own Acorn protection
    -> temporary object deletion
```

The descriptor carries only what is required to retrieve and process that one
package:

- a temporary object URL;
- the ciphertext SHA-256 digest;
- a random transfer secret;
- a format version; and
- an acceptance expiry.

Domain-separated keys derived from the random secret provide both AES-256-GCM
encryption and a transfer-scoped Blossom deletion authority. Neither Acorn's
permanent `nsec` nor its record-protection key is delegated.

## How the new model addresses the challenges

### Asynchronous by construction

The wallets do not need to be online together. The sender creates a package and
the recipient retrieves it later. There is no request/response rendezvous,
WebSocket dependency, presence signal, polling loop, or shared application
session.

### Self-contained capability

The QR descriptor carries the routing, integrity, decryption, expiry, and
cleanup material needed for one transfer. A receiving Acorn does not need the
sender's relay configuration, wallet state, or private keys.

### One clear atomicity rule

The receiver follows a strict order:

```text
retrieve -> verify -> decrypt -> validate -> store -> verify storage -> delete
```

Failure before verified storage leaves the temporary object available for a
retry. Cleanup happens only after the receiver owns a complete local copy.

### Independent cleanup safeguards

Recipient cleanup and sender revocation are complementary:

- after successful import, the recipient requests deletion;
- while presenting the QR code, the sender may select **Stop Sharing**;
- conforming clients reject an expired descriptor; and
- the storage operator may garbage-collect retained temporary ciphertext.

Safebox Web warns the sender before navigating away from the active sharing
page. The warning is a convenience safeguard, not a deletion guarantee.
Browser lifecycle events are deliberately not treated as protocol state.

If the sender revokes before acquisition, the recipient receives a clean
“transfer unavailable” outcome and stores no partial record. If the recipient
already imported the record, later sender revocation cannot and should not
delete the recipient's independent copy.

### Cleaner component boundary

Acorn owns:

- envelope encoding and authenticated encryption;
- descriptor parsing and validation;
- transfer-scoped authority derivation;
- temporary-object upload, retrieval, and deletion;
- receiver-side store-before-delete ordering; and
- application-neutral structured outcomes.

The host application owns:

- the Share and Stop Sharing confirmations;
- QR rendering and camera acquisition;
- progress, warning, and result representations;
- accepted transfer-server policy; and
- user-facing recovery from uncertain outcomes.

The browser never implements the transfer cryptography or becomes the source
of truth for delivery.

### Smaller and more deterministic tests

The kernel can test descriptor round trips, tamper rejection, expiry,
encryption, storage ordering, sender revocation, and server allowlisting with a
fake Blossom boundary. The web application can separately test confirmation,
CSRF protection, scanner routing, navigation warnings, and graceful errors.
Live interoperability remains important, but core correctness no longer
depends on a live two-party test harness.

## Deliberate tradeoffs and residual risks

The simpler model does not eliminate every problem.

- The descriptor is a bearer secret. Anyone who copies it before expiry can
  decrypt the package or request its deletion.
- The initial format does not restrict acquisition to a named recipient.
- There is no sender-visible acknowledgement that identifies who imported the
  record.
- Navigating away without Stop Sharing can leave opaque ciphertext behind if
  the recipient never imports it and the operator does not garbage-collect it.
- Descriptor expiry is enforced by conforming clients; it does not physically
  erase a Blossom object.
- Deletion is best-effort because storage operators may retain caches, replicas,
  logs, or backups.
- Availability still depends on the selected transfer server during the
  sharing window.

These limitations are explicit and bounded. The temporary object remains
authenticated ciphertext, its deletion key controls no other object, and its
failure states do not silently mutate either permanent wallet.

## Why recipient-specific transfer is not in version 1

A future profile could encrypt the package to a named recipient or require a
recipient signature before release. That may be useful when forwarding must be
restricted or receipt must be attributable. It would also reintroduce key
discovery, recipient resolution, compatibility negotiation, and more complex
failure states.

Version 1 therefore establishes the portable bearer transfer first. Any
recipient-bound profile should be layered on top only when a concrete use case
justifies the additional ceremony, and it must preserve the store-before-delete
invariant.

## Lessons to retain

1. Prefer a bounded capability over a live distributed conversation.
2. Keep permanent wallet authority out of temporary sharing credentials.
3. Make each destructive action explicit and independently recoverable.
4. Treat browser lifecycle signals as hints, never durable protocol facts.
5. Separate successful receiver storage from best-effort transport cleanup.
6. Report unavailable, expired, imported, revoked, and cleanup-unconfirmed as
   different states.
7. Keep protocol mechanics in Acorn and interaction mechanics in the host.
8. Add complexity only after the minimal interoperable path has demonstrated
   the need for it.

The earlier Safebox iteration was valuable because it made these lessons
concrete. The current design is not a rejection of secure transmittal; it is a
distillation of that work into a smaller component contract that can be tested,
embedded, and evolved without reproducing an entire application protocol.
