# Stroma Runtime Migration Milestone — September 2026

## Outcome

Safebox Acorn now uses Stroma as its Nostr wire-format and relay library. The
runtime no longer imports or declares Monstr. Keys, events, NIP-19 entities,
NIP-44 encryption, NIP-59 gift wrapping, and finite relay operations pass
through the smaller Stroma boundary.

This is a source, dependency-lock, and non-live-test milestone. Acorn is pinned
to Stroma commit `84336a9c6f73aedcafd834e6c4fd7523808fe747`, and the lock file resolves that
exact revision. Production deployment remains conditional on passing the
configured live relay suite.

## What prompted the change

The Safebox Web service Acorn worker repeatedly stopped progressing after
logging that its wallet had initialized. A direct diagnostic from the same
container loaded the wallet record in about 0.4 seconds and proof events in
about 0.6 seconds. That evidence separated wallet state and relay performance
from the process-lifecycle problem.

The historical relay client could create long-lived background tasks without a
default operation deadline, and its context exit did not provide a strong
shutdown boundary. Integration tests had accumulated special cleanup fixtures
that searched the event loop for client tasks and cancelled them. Those
fixtures were evidence that application code was compensating for a library
lifecycle that it did not own cleanly.

## New boundary

Stroma treats Nostr as Acorn's signed, encrypted, relay-backed wire format. It
does not own wallet meaning or application state.

- Relay queries open a connection, wait for EOSE within a bounded timeout, and
  close the connection.
- Relay publication waits for an explicit acknowledgement and closes the
  connection.
- A relay pool merges and deduplicates finite query results.
- Context-managed pool publication waits for its publish tasks and exposes
  failures before the context returns.
- Connectivity checks use bounded probes.
- Constructing an Acorn does not create a persistent relay client.
- Long-lived social-client subscriptions are outside the initial Acorn/Stroma
  boundary. Current wallet, record, and incoming-funds paths use finite queries.

Acorn keeps its application policies, including relay selection, canonical
read-after-write verification, zero-jitter gift wrapping, transfer kinds,
receipt checkpoints, and wallet records.

## Compatibility surface

Stroma exposes a deliberately narrow `Client` and `ClientPool` adapter for the
finite operations Acorn already performs. This is a migration surface, not a
commitment to reproduce the full historical client API.

Acorn retains a small policy adapter for its historical gift-wrap class name
and extended NIP-44 class name while their implementations use Stroma
primitives. This keeps stored data and tested application behavior stable while
removing the external Monstr dependency.

## Verification

At the time of this milestone:

- Stroma's unit suite passes;
- Acorn's complete non-live suite passes using the locked Stroma package;
- obsolete Monstr task-draining fixtures have been removed; and
- searches of Acorn runtime code, tests, and dependency declarations contain no
  Monstr imports or dependency declaration.

The remaining release gates are live interoperability checks for existing gift
wraps, new gift wraps, relay acknowledgements, canonical read-after-write, and
clean process shutdown.

## Deployment discipline

The repositories must be advanced in dependency order:

1. Commit and publish the tested Stroma revision.
2. Pin Safebox Acorn to that Stroma tag or commit.
3. Regenerate Acorn's lock file and run Acorn tests.
4. Update Safebox Web or another consumer to the tested Acorn revision and run
   its integration tests.

An editable local Stroma checkout is appropriate for development but is not a
deployment pin. A consumer must not resolve an older Git revision that lacks
the Acorn compatibility surface.

## Architectural lesson

An encrypted relay-backed system still needs strict local lifecycle ownership.
Statelessness does not make unbounded connections harmless. Each finite read or
write should have a deadline, an explicit completion condition, and a clean
shutdown path. The absence of locally persisted wallet state strengthens the
need for predictable relay operations; it does not weaken it.

## Related documents

- [Acorn Component Boundary](ACORN-COMPONENT-BOUNDARY.md)
- [Incoming Funds Reliability and Scaling](INCOMING-FUNDS-RELIABILITY-AND-SCALING.md)
- [Load Boundaries and Read Models](LOAD-BOUNDARIES-AND-READ-MODELS.md)
- [Relay Migration and Incoming Funds Design Correction](RELAY-MIGRATION-AND-INCOMING-FUNDS-DESIGN-CORRECTION-2026-09.md)
