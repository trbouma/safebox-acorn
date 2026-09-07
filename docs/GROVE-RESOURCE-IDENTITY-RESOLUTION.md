# Grove Resource Identity Resolution

Status: Initial resolver implemented

## Purpose

Safebox records historically stored a Blossom URL in `blobref`. That made the
location appear to be the attachment's identity and coupled durable records to
one DNS name or network context.

Acorn now separates the immutable resource, the services retaining it, and the
routes used to reach those services:

```text
ciphertext SHA-256
    -> one or more Grove service npubs
    -> service and active-context endpoint records
    -> HTTP, HTTPS, or later FIPS transport
```

The ciphertext SHA-256 in `blobsha256` is the stable resource identity. It can
be checked before decryption. `origsha256` separately verifies the recovered
plaintext and must remain private with the record's encryption parameters.

A Grove `npub` is a stable storage-provider identity. It is not the identity of
the bytes and does not imply that the provider will retain them forever. One
blob may name several Grove services when replicas exist.

## Record Schema

New `SafeboxRecord` documents use version 2 and add:

```json
{
  "version": 2,
  "blobsha256": "<ciphertext-sha256>",
  "blob_service_npubs": ["npub1grove..."]
}
```

`blob_service_npubs` is ordered, deduplicated, and validated as NIP-19 public
keys. New identity-aware records omit `blobref`; the provider `npub`, resolved
base endpoint, and `blobsha256` reconstruct the standard Blossom request.
`blobref` is stored only when the upload server does not report a valid service
identity, and remains an advisory migration hint on older records. Version 1
records continue to load with an empty provider list.

## Endpoint Resolution

Grove uses the existing encrypted relay-backed service records:

- `service_endpoints` maps a Grove `npub` to external HTTPS routes;
- `context_endpoints` maps a Grove `npub` and active context `npub` to internal,
  local, or external routes.

Endpoints advertise `blossom.read`, `blossom.write`, or `blossom.delete`.
Resolution rejects revoked, rejected, expired, capability-incompatible, and
wrong-context entries. A global descriptor cannot introduce an internal or
local URL; those routes require a matching active context.

FIPS-native endpoints remain in the generic endpoint schema but are not chosen
until the Blossom client has a FIPS transport adapter.

## Resolution Procedure

Resolution has two stages: establishing the active deployment context and
selecting a route for one attachment operation.

### Establish the active context

An application hosting an Acorn may supply a context identity such as a
Mainstay installation `npub`. Mainstay does this by publishing a read-only
context manifest containing its installation `npub`, Grove's service `npub`,
and Grove's scoped endpoints. Safebox Web validates the public identities,
sets the Acorn's active context, and asks Acorn to install or refresh each hint
in the private `context_endpoints` record.

Installing a hint is idempotent. Acorn preserves unrelated hints and does not
publish a replacement record when the context, service, endpoint, source, and
state are unchanged. A changed endpoint replaces the hint with an incremented
sequence number. A locally supplied Mainstay hint remains a `candidate` until
signed evidence supports promotion to `verified`.

### Select routes for an operation

For `blossom.read`, `blossom.write`, or `blossom.delete`, Acorn performs the
following procedure:

1. Read the ordered Grove identities from `blob_service_npubs`.
2. Load the private `service_endpoints` and `context_endpoints` records.
3. From `service_endpoints`, retain services that identify a requested Grove
   `npub`, have type `blossom` or `grove`, are not revoked or expired, and
   support the requested capability. Retain only their external HTTPS routes.
4. From `context_endpoints`, retain hints that identify a requested Grove
   `npub`, match the active context `npub`, are not rejected or expired, and
   support the requested capability. HTTP and HTTPS routes are eligible here
   because the context qualifies internal and local addresses.
5. Rank eligible routes by verification state, then scope, then numeric
   priority. Verified evidence ranks before provisional or candidate evidence;
   within the same evidence class, scope order is `internal`, `local`, then
   `external`.
6. Remove duplicate normalized URLs while retaining the first-ranked route.
7. Attempt the resulting routes in order.

A verified external route can therefore rank ahead of a candidate internal
hint. An internal route wins over an external route when their evidence class
is equivalent. This prevents locality alone from outranking stronger identity
evidence.

### Compatibility fallback

After identity-based candidates, Acorn may consider the server extracted from
the advisory `blobref` and the configured Blossom server list. If the record
contains `blob_service_npubs`, Acorn queries each fallback server's service
metadata and retains it only when the reported Grove `npub` matches one of the
record's providers. An arbitrary server cannot satisfy an identity-bearing
record merely because it returns bytes at the expected path.

Version 1 records without provider identities continue to use the legacy
location path. This preserves existing records while version 2 records gain
identity-qualified fallback behavior.

### Verify the resource

Endpoint resolution answers where to request a blob; it does not establish
that the returned bytes are correct. Acorn verifies the downloaded ciphertext
against `blobsha256` before decryption, authenticates the encrypted content,
and verifies the recovered plaintext against `origsha256`. Route identity and
content integrity remain separate checks.

## Current Operations

On upload, Acorn asks the configured Blossom server for JSON service metadata.
When it reports a valid `service_identity` of type `blossom`, Acorn stores the
derived Grove `npub` with the attachment and omits the returned upload URL.
Failure to discover an identity does not break older or third-party Blossom
servers; Acorn stores their returned URL in `blobref` and the record remains on
the legacy compatibility path.

Reads, explicit deletion, and replacement cleanup resolve provider identities
before using the advisory URL or configured server list. If a fallback server
does not report one of the record's provider identities, Acorn skips it.
Every retrieved encrypted attachment is still checked against `blobsha256`
before decryption and against `origsha256` afterward.

## Migration

No bulk rewrite is required. Existing version 1 records continue to work from
their hash, `blobref`, and configured Blossom servers. A later record write or
explicit migration can add provider identities after the endpoint has been
identified.

Mainstay can seed and refresh context-qualified Grove endpoints, but Acorn owns
the durable relay-backed records. Moving an Acorn between contexts changes
eligible routes without changing the blob hash or Grove service identity.

## Next Steps

1. Add signed Grove endpoint descriptors and promote verified external routes.
2. Add explicit replica registration and removal without changing blob hashes.
3. Add a FIPS transport adapter for Blossom operations.

The Mainstay integration now supplies the active context and initial Grove
hint: Mainstay publishes a read-only context manifest, Safebox Web consumes it,
and Acorn idempotently stores the internal route in the wallet's private
`context_endpoints` record.
