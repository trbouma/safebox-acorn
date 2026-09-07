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
  "blob_service_npubs": ["npub1grove..."],
  "blobref": "https://legacy.example/<ciphertext-sha256>"
}
```

`blob_service_npubs` is ordered, deduplicated, and validated as NIP-19 public
keys. `blobref` remains an advisory migration hint. Version 1 records continue
to load with an empty provider list.

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

## Current Operations

On upload, Acorn asks the configured Blossom server for JSON service metadata.
When it reports a valid `service_identity` of type `blossom`, Acorn stores the
derived Grove `npub` with the attachment. Failure to discover an identity does
not break older or third-party Blossom servers; the record remains on the
legacy compatibility path.

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

The Mainstay integration now supplies the first two former steps: Mainstay
publishes a read-only context manifest, Safebox Web consumes it, and Acorn
idempotently stores the internal Grove hint in the wallet's private
`context_endpoints` record.
