# Acorn Record Encryption Specification

## Summary

Acorn stores private user records as encrypted Nostr events. The record payload
and human-readable label are not published in cleartext. Relays see only the
publisher public key, event kind, timestamp, and a deterministic private lookup
tag derived from the user's private key and record label.

The default private record kind is:

```text
37375
```

In this specification, the publisher public key identifies the Acorn component
or wallet lineage, not necessarily a person. Its corresponding private key
provides decryption and signing authority over the record namespace. Any claim
linking that protocol key to a human identity is separate record content
or an external assertion.

The current design supports two storage layers:

- encrypted record metadata stored directly in a Nostr event;
- optional encrypted blob content stored separately, with the blob decryption
  parameters stored inside the encrypted record metadata.

## Goals

- Store private records on Nostr relays without exposing record contents.
- Avoid exposing human-readable record labels to relays.
- Allow deterministic lookup of a record by label by the key holder.
- Keep ordinary text records simple.
- Support larger file/blob records with an additional content-encryption layer.

## Non-goals

- Hiding that a given public key published an event.
- Hiding event kind, event timestamp, or relay-level access patterns.
- Providing forward secrecy if the user's private key is later compromised.
- Preventing deletion, censorship, or non-availability by relay operators.

## Terms

### Record label

The human-readable name of a record, such as:

```text
Field Notes
Passport
Health Card
```

### Label hash

A deterministic private lookup value derived from the user's private key and
the record label.

### Record metadata

The structured JSON representation of the record, including label, type,
payload, and optional blob metadata.

### Blob

Optional larger binary content associated with a record. Blob bytes are
encrypted separately before upload.

## Record write flow

When Acorn writes a normal private record, it performs the following steps.

### 1. Normalize the record label

The caller supplies a record name:

```text
Field Notes
```

If a `record_origin` is supplied, Acorn currently joins origin and name:

```text
<record_origin>:<record_name>
```

This combined value is used as the record label for lookup and storage.

### 2. Derive the private lookup tag

Acorn derives the event lookup tag as:

```text
label_hash = sha256(privkey_hex || record_label)
```

In code, this is currently implemented as sequential SHA-256 updates:

```python
m = hashlib.sha256()
m.update(self.privkey_hex.encode())
m.update(label.encode())
label_hash = m.digest().hex()
```

The resulting hash is stored in the Nostr event as the `d` tag:

```json
["d", "<label_hash>"]
```

The human-readable label is not published in the event tags.

### 3. Build the record metadata

For ordinary text records, Acorn creates a `SafeboxRecord` object with fields
similar to:

```json
{
  "version": 1,
  "tag": ["Field Notes"],
  "type": "generic",
  "payload": "Apr 30: Moving\n\nApr 25: Dog Walk",
  "blobref": null,
  "blobtype": null,
  "blobsha256": null,
  "origsha256": null,
  "encryptparms": null
}
```

The `tag` field contains the clear human-readable label, but this object is
encrypted before publication.

### 4. Encrypt the record metadata with NIP-44

Acorn encrypts the serialized record metadata using NIP-44 to the user's own
public key:

```python
my_enc = NIP44Encrypt(self.k)
ciphertext = my_enc.encrypt(record_json, to_pub_k=self.pubkey_hex)
```

This is effectively self-addressed encryption: the holder of the user's private
key can decrypt the record later.

### 5. Publish the Nostr event

Acorn publishes a Nostr event with:

```text
kind:    record kind, default 37375
author:  user's public key
tags:    [["d", label_hash]]
content: NIP-44 encrypted record metadata
```

The event is signed by the user's private key.

### 6. Verify relay readback

The public `put_record` path does not treat an enqueued websocket publish as
durable success. It queries each selected write relay until the new event is
both readable and canonical for its `(kind, pubkey, d)` coordinate.

When replacing a record, Acorn assigns a timestamp later than the currently
observed canonical version. This avoids ambiguous same-second replacement
races. If readback cannot be verified, the write raises an error rather than
reporting success.

## Record read flow

To retrieve a record by label, Acorn reverses the lookup process.

### 1. Recompute the label hash

Given the requested label, Acorn recomputes:

```text
label_hash = sha256(privkey_hex || record_label)
```

### 2. Query relays

Acorn queries the selected relay pool for events matching:

```json
{
  "authors": ["<user_pubkey_hex>"],
  "kinds": [37375],
  "#d": ["<label_hash>"]
}
```

Every point lookup includes the requested kind. Acorn deduplicates event IDs
and selects the NIP-01 canonical addressable event: greatest `created_at`, then
lexically lowest event ID when timestamps are equal. This also reconciles
different views returned by multiple relays.

### 3. Decrypt event content

Acorn decrypts the event content using NIP-44:

```python
record_json = my_enc.decrypt(event.content, self.pubkey_hex)
```

### 4. Parse the record

The decrypted JSON is parsed into a `SafeboxRecord`.

The CLI can then render it as:

```text
Record: Field Notes
Kind: 37375
Type: generic

Apr 30: Moving
Apr 25: Dog Walk
```

or emit it as JSON:

```sh
acorn get "Field Notes" --json
```

Point operations may target a relay pool:

```sh
acorn get "Field Notes" --relays ws://local-relay:8735,wss://backup.example
```

## Internal-state separation

Acorn operational state and ordinary user records currently use compatible
encrypted addressable-event mechanics. The public `put_record` API protects
known internal labels—including `wallet`, `lock`, `pending_melts`, cursors,
relay configuration, and mint configuration—and reserves the `__acorn_`
prefix. Callers must use the dedicated configuration, payment, and recovery
APIs for those records.

This preserves backward compatibility with existing relay data while preventing
ordinary CLI or component record writes from replacing operational state.

## Record deletion

Deletion is a NIP-09 request, not a guaranteed erase. Acorn publishes kind `5`
with:

- an `e` tag for the currently selected event;
- an `a` tag for the full addressable coordinate;
- a `k` tag for the record kind.

The request can be sent to a relay pool. Acorn reports where the record was no
longer visible after publication and retains the explicit advisory that relays
or clients may keep it. Optional blob cleanup attempts deletion from every
configured blob server.

## Blob encryption

If a record includes binary blob data, Acorn adds a second encryption layer.

### 1. Generate a random blob key

Acorn generates a random 32-byte key:

```python
blob_key = os.urandom(32)
```

### 2. Encrypt blob bytes with AES-256-GCM

Blob bytes are encrypted with AES-256-GCM:

```python
encrypt_result = encrypt_bytes(blob_data, blob_key)
```

The encryption helper uses:

```text
algorithm: AES-256-GCM
key:       32 random bytes
iv:        12 random bytes
```

The ciphertext includes the GCM authentication tag.

### 3. Upload encrypted blob bytes

The encrypted blob bytes are uploaded separately, currently through the
configured Blossom-compatible blob server path.

### 4. Store blob metadata inside encrypted record metadata

The record metadata stores the blob reference and decryption parameters:

```json
{
  "blobref": "<blob reference>",
  "blobtype": "<mime type>",
  "blobsha256": "<sha256 of encrypted blob>",
  "origsha256": "<sha256 of original plaintext blob>",
  "encryptparms": {
    "alg": "AES-256-GCM",
    "key": "<hex encoded 32-byte key>",
    "iv": "<hex encoded 12-byte iv>"
  }
}
```

This metadata is itself inside the NIP-44 encrypted record event. Therefore,
the blob key and IV are not visible to relays or blob storage providers unless
they can decrypt the record metadata.

### 5. Retrieve and verify an encrypted blob

The encrypted record metadata, rather than a MIME type supplied by the blob
server, determines whether decryption is required. Acorn retrieves the object
by its encrypted-content hash and then:

1. verifies the retrieved ciphertext against `blobsha256`;
2. requires the declared algorithm to be `AES-256-GCM`;
3. authenticates and decrypts using the protected key and IV; and
4. verifies the resulting plaintext against `origsha256`.

Any failure is an integrity error and plaintext is not returned. Records with
no `encryptparms` remain a narrowly scoped compatibility path for genuinely
legacy unencrypted blobs; server-reported MIME type never downgrades an
encrypted record into that path.

## Blob security design

### Envelope model

Blob protection is a two-envelope construction. The large binary object and
the small key-bearing metadata record are deliberately stored separately.

```text
plaintext blob
    |
    | fresh random 256-bit key + fresh 96-bit nonce
    v
AES-256-GCM ciphertext --------------------------> Blossom server
    |                                               stores ciphertext only
    | SHA-256(ciphertext)
    v
blob reference + media type + hashes + AES key + nonce
    |
    | NIP-44 self-encryption to Acorn public key
    v
signed kind 37375 event -------------------------> Nostr relay
    author pubkey + timestamp + private lookup tag remain visible
```

The AES key is not derived from the `nsec`, label, plaintext, or blob hash. A
new random key is generated for every blob. Compromise of one blob key should
therefore expose only that blob unless a wider key or execution-environment
compromise has also occurred.

The construction does not use AES-GCM additional authenticated data. Binding
between the ciphertext and its record is instead provided by the ciphertext
hash stored inside the authenticated NIP-44 record. The encrypted record also
protects the plaintext hash, media type, blob reference, key, and nonce as one
metadata object.

### Assets, keys, and storage locations

| Asset | Location at rest | Protection | Expected exposure |
| --- | --- | --- | --- |
| Plaintext blob | Not intentionally retained by Acorn after the operation | Exists transiently in caller and process memory | Trusted caller and execution environment |
| Blob ciphertext | Blossom-compatible server | AES-256-GCM | Server and anyone able to retrieve the content-addressed object |
| Per-blob AES key | NIP-44-encrypted record metadata | NIP-44 under the Acorn key | Acorn key holder and trusted execution environment |
| AES nonce | NIP-44-encrypted record metadata | NIP-44; not independently secret | Acorn key holder and trusted execution environment |
| Ciphertext hash | Record metadata and content-addressed blob path | Integrity value, not a secret | May be visible to the Blossom operator and through object URLs |
| Plaintext hash | NIP-44-encrypted record metadata | NIP-44 | Acorn key holder and trusted execution environment |
| Record label and payload | NIP-44-encrypted event content | NIP-44 | Acorn key holder and trusted execution environment |
| Acorn `nsec` | Local configuration or caller-provided secret boundary | Host permissions and operator controls | Must never be disclosed to relays, Blossom, logs, or browser storage |
| Acorn public key | Nostr event author and Blossom authorization context | Public identifier | Relays, services, and observers |

The AES nonce must be unique for a given AES key. Acorn currently generates a
fresh key and nonce for every blob, so nonce reuse across blobs does not imply
reuse under the same key. Future optimization must not introduce key reuse
without a reviewed nonce-allocation design.

### Trust and observation boundaries

| Observer or compromise | What it can learn or do |
| --- | --- |
| Blossom operator alone | Observe ciphertext, size, hash, timing, authorization, requests, and source network metadata; refuse, retain, replace, or delete the object; not directly decrypt it |
| Relay operator alone | Observe author public key, kind, timestamp, signature, deterministic lookup tag, ciphertext size, and query patterns; not directly read record metadata or the blob key |
| Colluding relay and Blossom operators | Correlate authors, upload timing, object access, event publication, sizes, and authorization metadata; still require the Acorn secret or a cryptographic break to decrypt content |
| Network observer | Observe endpoints, timing, sizes, and connection metadata not hidden by TLS, VPN, Tor, or other deployment controls |
| Compromised Acorn execution environment | Observe the `nsec`, record plaintext, blob plaintext, and per-blob keys while in use; fully bypass the storage-layer confidentiality boundary |
| Compromised `nsec` | Decrypt retained NIP-44 records, recover per-blob keys, derive private lookup tags, sign events, and decrypt any associated retained blobs |
| Future quantum-capable attacker | Potentially derive the secp256k1 private key from the public key, then follow the compromised-`nsec` path; AES-256 ciphertext without its key retains a strong quantum-resistant margin under currently known attacks |

Human identity is not required for these attacks. The author field identifies
an Acorn component key. External assertions such as NIP-05, kind `0` metadata,
Lightning addresses, server accounts, or operator knowledge may associate that
key with a person, but that association is separate from cryptographic access.

### Attacker paths

An attacker holding only a Blossom ciphertext must still obtain its random AES
key. The normal key-recovery path for an attacker is:

1. obtain or retain the encrypted blob;
2. identify or collect record events authored by the relevant Acorn public key;
3. obtain the Acorn `nsec`, compromise its execution environment, or defeat the
   secp256k1/NIP-44 envelope;
4. decrypt retained record events and match the protected blob reference or
   ciphertext hash;
5. recover the AES key and nonce; and
6. authenticate and decrypt the blob.

The attacker need not correlate the exact event before compromising the Acorn
key. They can collect all events for a public key and decrypt and classify them
afterward. This is the relevant harvest-now-decrypt-later scenario for
long-lived records.

Other practical paths are usually simpler than cryptanalysis: stealing local
configuration, compromising the web or CLI execution host, capturing secrets
from an unsafe integration, exploiting dependencies, or obtaining plaintext
from an endpoint while the authorized application is rendering it.

### Required security invariants

Implementations conforming to the current encrypted-blob profile must preserve
all of the following:

1. Generate a new unpredictable 32-byte AES key for every blob.
2. Generate a fresh 12-byte nonce with a cryptographically secure random source.
3. Never upload plaintext blob bytes to the configured blob server.
4. Store the key and nonce only inside authenticated encrypted record metadata.
5. Treat record metadata, not an unauthenticated server MIME response, as the
   authority for whether decryption is required.
6. Verify `blobsha256` before decryption, authenticate the GCM ciphertext, and
   verify `origsha256` after decryption.
7. Return no plaintext after any hash, algorithm, key-length, nonce-length, or
   GCM authentication failure.
8. Avoid logging plaintext, keys, nonces, decrypted metadata, or secret-bearing
   exceptions.
9. Apply explicit upload and response-size limits at application and proxy
   boundaries.
10. Treat publication, replacement, deletion, and timeout outcomes as
    potentially partial until readback or provider results establish otherwise.

The current algorithm identifier is `AES-256-GCM`. Unknown identifiers must
fail closed. A future profile must use a new explicit version or algorithm
identifier rather than silently changing the interpretation of existing
records.

### Lifecycle and failure semantics

Blob storage spans two independently operated systems and cannot provide a
single atomic transaction. Callers must distinguish these states:

| Operation and failure | Possible durable state | Required interpretation or response |
| --- | --- | --- |
| Encryption fails before upload | No external blob or record | Safe to correct the input or implementation and retry |
| Blossom upload fails | No verified record should be published | Report failure; do not claim the record exists |
| Upload succeeds and record publication fails | Ciphertext may be orphaned on Blossom | Attempt authenticated blob deletion and report failure |
| Record publication times out after upload | Publication may have succeeded even if readback failed; cleanup may leave a published record pointing to a missing blob | Report an uncertain outcome; inspect relay state before retrying or replacing |
| Record read succeeds but blob retrieval fails | Metadata exists but ciphertext is unavailable | Report availability failure; do not alter the record automatically |
| Ciphertext or metadata verification fails | Object may be corrupt, substituted, truncated, or mismatched | Fail closed and return no plaintext |
| Blob deletion succeeds but relay deletion fails | Key-bearing record may remain but its object is unavailable | Report partial deletion and resulting loss of availability |
| Relay deletion is accepted but blob deletion fails | Encrypted ciphertext may remain, and retained relay or backup copies may still contain its key | Report partial deletion; do not claim erasure |
| Both deletion requests succeed | Providers may still retain mirrors, logs, caches, or backups | Report requested/observed deletion, never guaranteed physical erasure |

Replacement of a blob record is not equivalent to an atomic update. A caller
must not overwrite the only protected reference to an old blob without first
choosing and documenting the desired retention, migration, and rollback
behavior. The initial Safebox Web integration therefore rejects an existing
label and offers an explicit confirmed deletion operation.

### Verification and test requirements

The deterministic unit suite currently covers:

- AES-256-GCM encrypt/decrypt round trip;
- ciphertext-hash mismatch;
- authenticated-ciphertext tampering even when the attacker recomputes the
  unkeyed ciphertext hash;
- plaintext-hash mismatch; and
- rejection of an unknown encryption algorithm.

Before a stable release, coverage should also include:

- fixed, reviewable AES-GCM test vectors containing key, nonce, plaintext,
  ciphertext, tag, and both hashes;
- malformed, missing, short, and oversized key and nonce fields;
- cross-record ciphertext and metadata substitution;
- bounded upload, download, and decompression/resource behavior;
- a live Blossom upload, authenticated retrieval, decryption, and deletion
  lifecycle using disposable data;
- provider failure before and after relay publication;
- ambiguous timeout and cleanup failure injection;
- multiple configured blob servers and partial deletion results;
- compatibility fixtures for genuine legacy unencrypted records; and
- confirmation that logs and exception responses contain no blob plaintext,
  AES keys, `nsec`, or decrypted record metadata.

Test vectors must use synthetic public values created specifically for the
test suite. Production keys, user records, and real recovery material must
never be copied into fixtures.

## Relay-visible metadata

Relay operators can observe:

- event kind;
- event author public key;
- event timestamp;
- event signature;
- event id;
- the deterministic `d` tag hash;
- ciphertext size;
- relay access/query patterns.

Relay operators cannot directly observe:

- record label;
- record payload;
- blob decryption key;
- blob IV;
- original plaintext blob bytes.

## Security properties

### Confidentiality

Record metadata is encrypted with NIP-44. Blob content, when present, is
encrypted with AES-256-GCM before upload.

### Label privacy

Labels are not published directly. The public lookup tag is derived from the
private key and label, so an observer cannot precompute label hashes without the
user's private key.

### Deterministic lookup

The key holder can recompute the same label hash later and query relays for the
record without maintaining a separate local index.

### Integrity

Nostr events are signed by the user's private key. AES-256-GCM provides
authenticated encryption for blob content. NIP-44 provides authenticated
encrypted content semantics for record metadata.

## Limitations and considerations

### Private-key compromise

If the user's private key is compromised, an attacker can:

- recompute label hashes for guessed labels;
- decrypt record metadata;
- retrieve blob decryption parameters;
- decrypt associated blobs if they can access the blob ciphertext.

### Label guessing after compromise

Before private-key compromise, labels are not directly guessable from relay
data. After compromise, common labels may be guessed and checked by recomputing
their label hashes.

### Event metadata leakage

The event kind, author, timestamp, and approximate ciphertext size remain
visible.

### Availability

Relays and blob servers can refuse service, delete data, censor events, or be
unavailable. Encryption protects confidentiality, not availability.

### Schema versioning

`SafeboxRecord.version` is `1` for the current envelope. Older stored records
without the field parse as version `1`. Future incompatible lookup or
encryption changes must use a documented migration rather than silently
changing the existing label hash or ciphertext interpretation.

### Post-quantum boundary and migration

The current private record format relies on Nostr-compatible classical key
material and NIP-44 encryption for record metadata. Blob content is encrypted
with AES-256-GCM using random symmetric keys.

The independently encrypted AES-256-GCM blob ciphertext is appropriately
described as quantum-resistant under currently known attacks. The complete
record system must not be described as post-quantum secure because the AES key
is currently protected by a secp256k1/NIP-44 envelope. See
[Blob security design](#blob-security-design) for the exact boundary and attack
path.

Acorn does, however, need a quantum-safe migration path because private records
and recovery context may be long-lived. A future-compatible posture should
include:

- cryptographic agility in record metadata;
- explicit algorithm identifiers;
- hybrid classical/post-quantum wrapping where practical;
- test vectors for every supported encryption profile;
- optional support until compatibility is mature;
- clear distinction between experimental PQC and stable record formats.

Acorn contains an optional Open Quantum Safe (`liboqs` / `liboqs-python`) code
path for experimental post-quantum event signatures. It is isolated in
`acorn.post_quantum`, is installed through the `post-quantum` package extra,
and is not loaded by ordinary Acorn operations. These dependencies should be
treated as experimental until the project documents a known-good version
matrix, conformance tests, and stable interoperability behavior.

The desired long-term posture is:

```text
classical compatibility now;
hybrid protection where practical;
post-quantum agility over premature claims.
```

Future record formats may add a versioned encryption profile such as:

```json
{
  "profile": "acorn-record-v2-hybrid",
  "metadata_alg": "nip44-v2",
  "blob_alg": "aes-256-gcm",
  "kem_alg": "ML-KEM-768",
  "mode": "hybrid"
}
```

Any such profile must preserve recoverability and avoid silently breaking older
clients.

### Deterministic tag correlation

The same label under the same key produces the same `d` tag hash. This enables
updates/replacement-style lookup but also means observers can correlate events
for the same private label hash, even though they cannot read the label.

## Implementation references

Current implementation files:

- `acorn/acorn.py`
  - `put_record`
  - `set_wallet_info`
  - `get_record_safebox`
  - `get_wallet_info`
  - `get_user_records`
- `acorn/func_utils.py`
  - `encrypt_bytes`
  - `decrypt_bytes`
  - `decrypt_and_verify_record_blob`
- `acorn/models.py`
  - `SafeboxRecord`
  - `EncryptionParms`
  - `EncryptionResult`
- `tests/unit/test_blob_encryption.py`
  - encrypted-blob integrity and algorithm-failure regression tests

## Compatibility notes

Some model and method names still use `SafeboxRecord` or `safebox` terminology.
These names are currently part of the transition from Safebox to the standalone
Acorn component and should not be renamed casually if they affect stored record
shape or compatibility with existing clients.
