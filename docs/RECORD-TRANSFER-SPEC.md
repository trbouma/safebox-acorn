# Acorn Record Transfer Specification

## Status

Version 1 is implemented as an initial interoperable format. It supports a
short-lived encrypted copy of one Acorn record, optional inclusion of its
Original Record, Base64URL QR transport, receiver-side import, and best-effort
deletion after successful storage.

## Purpose

Record transfer lets one Acorn hand a record to another without giving the
recipient access to the sender's relay state, record-protection key, `nsec`, or
permanent Blossom objects. The QR code is a narrowly scoped bearer capability
for one temporary encrypted package.

Safebox Web supplies the confirmation and scanning interface. Acorn owns the
portable descriptor, encryption, validation, import, and cleanup behavior.

## User flow

1. The sender selects **Share** and confirms creation of a temporary copy.
2. Acorn reads the record and, when present, decrypts its Original Record.
3. Acorn creates and uploads one opaque encrypted transfer envelope.
4. Safebox Web renders the Base64URL descriptor as a QR code.
5. A receiving Safebox scans and recognizes the descriptor.
6. The receiver reviews the proposed label and explicitly confirms import.
7. Acorn retrieves, hashes, decrypts, and validates the envelope.
8. Acorn stores the record using the receiver's normal record and blob
   protection.
9. Only after storage succeeds does Acorn request deletion of the temporary
   transfer blob.

## Descriptor

The URI form is:

```text
acorn:record-transfer:<base64url(compact-json)>
```

The compact JSON object contains:

| Field | Meaning |
| --- | --- |
| `v` | Format version; currently `1` |
| `u` | HTTPS or HTTP URL of the opaque transfer blob |
| `h` | Base64URL SHA-256 digest of the ciphertext |
| `s` | Base64URL 32-byte transfer secret |
| `e` | Unix expiry timestamp |

Padding is omitted from Base64URL values. The descriptor is designed to remain
well below 500 characters for reliable screen-to-camera scanning. The record
and Original Record are never placed in the QR code.

## Encryption

The transfer secret is 32 bytes from the operating system CSPRNG. It is not the
AES-GCM nonce. Two domain-separated values are derived using HKDF-SHA-256:

```text
encryption_key = HKDF-SHA-256(
    transfer_secret,
    info="acorn/record-transfer/encryption-key/v1"
)

blossom_authority = HKDF-SHA-256(
    transfer_secret,
    info="acorn/record-transfer/blossom-authority/v1"
)
```

The record envelope is encrypted with AES-256-GCM using a separately generated
96-bit nonce and the versioned associated-data string:

```text
acorn/record-transfer/envelope/v1
```

The transfer-scoped Blossom authority signs upload and deletion requests. It
does not derive or reveal either Acorn's permanent key.

## Envelope

The encrypted CBOR envelope contains:

- version;
- suggested record label;
- record type;
- JSON-serializable payload; and
- optionally, the Original Record bytes, media type, and plaintext SHA-256.

Original Record bytes remain binary inside CBOR, avoiding the roughly one-third
size expansion that Base64 would impose on PDFs and images. Base64URL is used
only for the compact QR descriptor. The outer descriptor hash authenticates the
retrieved ciphertext before decryption; AES-GCM authenticates the envelope; and
the inner Original Record hash detects unexpected plaintext changes before the
receiver stores it.

## Import and deletion ordering

The required ordering is:

```text
retrieve -> verify ciphertext -> decrypt -> validate -> store -> verify storage
-> request transfer deletion
```

The temporary object must not be deleted merely because its QR code was
scanned. A scan does not prove that download, decryption, or receiver storage
completed. If storage fails, Acorn leaves the temporary object available for a
retry until the descriptor expires.

Deletion is best-effort. A Blossom server may retain caches, replicas, logs, or
backups after accepting a deletion request. Expiry prevents conforming Acorn
clients from accepting the descriptor after its deadline; it does not itself
prove physical erasure of ciphertext. Operators should provide garbage
collection for expired temporary objects.

## Security and trust model

The descriptor is a bearer secret. Anyone who obtains it before expiry can
download and decrypt the transfer and can derive its transfer-scoped deletion
authority. Users should display or transmit it only to the intended recipient.

The descriptor never contains:

- a sender or receiver `nsec`;
- a mnemonic or record-protection key;
- plaintext record content;
- permanent Blossom credentials; or
- authority over any other record.

Safebox Web restricts server-side retrieval to operator-approved Blossom
origins. This prevents an arbitrary scanned descriptor from turning the web
application into a general server-side request-forgery mechanism. Independent
Safebox operators must intentionally share or allow a compatible transfer
server before exchanging records.

The Blossom operator observes ciphertext size, hash, upload, retrieval,
deletion, timing, and transfer-scoped authorization. It cannot decrypt the
package without the QR descriptor. The web execution environment temporarily
sees the descriptor and plaintext while performing sender or receiver actions,
consistent with the established Safebox Web trust boundary.

## Current limitations

- The default transfer lifetime is one hour in Safebox Web.
- Sharing status is established by successful receiver storage and the
  subsequent deletion request; there is no sender-visible acknowledgement
  event yet.
- Expired-object garbage collection depends on the transfer-server operator.
- Label collisions are rejected by Safebox Web rather than silently replacing
  an existing receiving record.
- Share-server federation and explicit cross-operator allowlists require
  deployment configuration before broad interoperability testing.
