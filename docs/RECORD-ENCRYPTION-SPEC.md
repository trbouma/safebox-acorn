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

### Quantum-safe cryptography

The current private record format relies on Nostr-compatible classical key
material and NIP-44 encryption for record metadata. Blob content is encrypted
with AES-256-GCM using random symmetric keys.

This should not be described as fully quantum-safe.

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
- `acorn/models.py`
  - `SafeboxRecord`
  - `EncryptionParms`
  - `EncryptionResult`

## Compatibility notes

Some model and method names still use `SafeboxRecord` or `safebox` terminology.
These names are currently part of the transition from Safebox to the standalone
Acorn component and should not be renamed casually if they affect stored record
shape or compatibility with existing clients.
