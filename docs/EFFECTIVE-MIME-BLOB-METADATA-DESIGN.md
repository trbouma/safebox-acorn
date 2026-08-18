# Effective MIME Blob Metadata Design

Status: Draft  
Scope: Acorn private record blob metadata and original-record transfer metadata

## Summary

Acorn should support caller-declared effective MIME types for encrypted record
blobs while keeping ordinary blob storage automatic and Blossom servers
unopinionated.

The motivating example is Apple Wallet `.pkpass`. A PKPASS artifact is a signed
ZIP package. Byte sniffing commonly identifies it as `application/zip`, but the
artifact MIME that clients need in order to install it into Wallet is:

```text
application/vnd.apple.pkpass
```

Acorn should therefore distinguish:

- the MIME type Acorn returns to clients after decrypting the blob; and
- the MIME type inferred from the plaintext bytes by a detector.

## Design Goals

- Keep Blossom completely unopinionated.
- Preserve ordinary blob behavior when callers do not specify a MIME type.
- Allow callers to declare an authoritative artifact MIME when byte sniffing is
  too generic or container-oriented.
- Preserve backward compatibility with existing `blobtype` and
  `origmimetype` metadata.
- Treat encrypted blob bytes as opaque at the Blossom boundary.
- Never unzip, normalize, rewrite, or re-sign domain-specific container
  formats such as PKPASS.

## Non-Goals

- Teaching Blossom about domain MIME types.
- Making Acorn inspect archive contents.
- Validating whether a PKPASS package is a valid Apple Wallet pass.
- Replacing existing `blobtype` consumers in one step.

## Terminology

### Effective MIME

`effective_mime` is the authoritative plaintext artifact MIME type Acorn uses
when returning decrypted blob bytes to callers.

For example:

```text
application/pdf
image/png
application/vnd.apple.pkpass
```

### Detected MIME

`detected_mime` is the optional MIME type inferred from plaintext bytes by
Acorn's detector.

For PKPASS, this may be:

```text
application/zip
```

### Effective MIME Source

`effective_mime_source` records how `effective_mime` was chosen.

Allowed values for new blob-backed records:

| Value | Meaning |
| --- | --- |
| `declared` | Caller supplied a MIME override and Acorn accepted it. |
| `detected` | Caller did not supply a MIME override; Acorn detected the MIME from plaintext bytes. |
| `default` | Caller did not supply a MIME override and detection failed; Acorn used `application/octet-stream`. |

## Metadata Fields

New blob-backed records SHOULD store:

```json
{
  "effective_mime": "application/vnd.apple.pkpass",
  "effective_mime_source": "declared",
  "detected_mime": "application/zip"
}
```

Field meanings:

| Field | Required for new blob records | Meaning |
| --- | --- | --- |
| `effective_mime` | Yes | Authoritative MIME returned after decryption. |
| `effective_mime_source` | Yes | `declared`, `detected`, or `default`. |
| `detected_mime` | No | Detector result, when detection succeeds. |

Compatibility field:

| Field | Compatibility role |
| --- | --- |
| `blobtype` | Legacy alias for `effective_mime`. New records SHOULD keep it populated until downstream clients migrate. |

## Write Semantics

Acorn should extend blob-capable write APIs with an optional MIME parameter.

Suggested Python API:

```python
await acorn.put_record(
    record_name="Example Pass",
    record_value={"filename": "Example.pkpass"},
    record_type="blob",
    blob_data=pkpass_bytes,
    blob_type="application/vnd.apple.pkpass",
)
```

The name `blob_type` is acceptable as the public argument for compatibility
with existing vocabulary, but internally it should populate `effective_mime`.

### Caller Declares MIME

If `blob_type` is supplied and non-empty:

1. Normalize the supplied value to a safe MIME token:
   - strip parameters after `;`
   - trim whitespace
   - lowercase
2. Detect the MIME from plaintext bytes when possible.
3. Store:
   - `effective_mime = <declared MIME>`
   - `effective_mime_source = "declared"`
   - `detected_mime = <detected MIME>` when available
   - `blobtype = effective_mime` for compatibility
4. Encrypt plaintext bytes.
5. Upload encrypted bytes to Blossom as opaque data.

PKPASS example:

```json
{
  "blobtype": "application/vnd.apple.pkpass",
  "effective_mime": "application/vnd.apple.pkpass",
  "effective_mime_source": "declared",
  "detected_mime": "application/zip"
}
```

### Caller Does Not Declare MIME

If `blob_type` is omitted, empty, or `None`:

1. Detect the MIME from plaintext bytes.
2. If detection succeeds, store:
   - `effective_mime = <detected MIME>`
   - `effective_mime_source = "detected"`
   - `detected_mime = <detected MIME>`
   - `blobtype = effective_mime`
3. If detection fails, store:
   - `effective_mime = "application/octet-stream"`
   - `effective_mime_source = "default"`
   - `blobtype = effective_mime`

PNG example:

```json
{
  "blobtype": "image/png",
  "effective_mime": "image/png",
  "effective_mime_source": "detected",
  "detected_mime": "image/png"
}
```

Unknown binary example:

```json
{
  "blobtype": "application/octet-stream",
  "effective_mime": "application/octet-stream",
  "effective_mime_source": "default"
}
```

## Read Semantics

Record blob retrieval should return `effective_mime` and plaintext bytes:

```python
mime, data = await acorn.get_record_blobdata(...)
```

Resolution order:

1. `effective_mime`, if present.
2. `blobtype`, for legacy records.
3. MIME detected from decrypted plaintext bytes.
4. `application/octet-stream`.

Existing callers that already consume the first tuple value as a MIME type
continue to work.

## Original Record Transfer Semantics

Original-record transfer metadata should preserve the effective MIME.

Current transfer metadata includes:

```text
origmimetype
blobmimetype
```

Compatibility behavior:

- `origmimetype` SHOULD be populated from `effective_mime`.
- `blobmimetype` SHOULD continue to describe the encrypted transfer blob when
  useful, but it MUST NOT override the plaintext artifact MIME.

Future transfer metadata MAY add:

```json
{
  "effective_mime": "application/vnd.apple.pkpass",
  "effective_mime_source": "declared",
  "detected_mime": "application/zip"
}
```

Transfer ingest should re-store the received blob using the transferred
effective MIME. It should not reclassify PKPASS as ZIP merely because the
decrypted bytes are ZIP-shaped.

## Blossom Boundary

Blossom remains byte storage.

Because Acorn encrypts blob bytes before upload, Blossom usually sees only
ciphertext. Its storage MIME can remain:

```text
application/octet-stream
```

Blossom MUST NOT be required to:

- know PKPASS-specific MIME types;
- inspect encrypted or plaintext artifact contents;
- preserve artifact MIME metadata;
- choose client-facing download headers.

Acorn owns artifact metadata. Applications own presentation and download
headers based on Acorn's returned `effective_mime`.

## Duplicate Original Uploads

If two Acorn users upload the same plaintext original blob, Acorn should treat
the uploads as independent private attachments.

For each upload, Acorn generates fresh encryption material before sending bytes
to Blossom. As a result:

- `origsha256` is the same for identical plaintext bytes.
- encrypted bytes are different because the key and nonce are fresh.
- `blobsha256` is different because it hashes encrypted bytes.
- Blossom stores separate opaque blobs and cannot infer that the plaintext
  originals were identical.

This intentionally avoids cross-user deduplication at the Blossom layer.
`origsha256` remains useful for Acorn-side integrity verification after
decryption, but it is stored in encrypted record metadata rather than exposed as
the Blossom storage key.

## Validation

Acorn should accept declared MIME values only when they are syntactically
reasonable media types. A conservative first pass:

- split at `;` and keep only the media type;
- require one `/`;
- require non-empty type and subtype;
- lowercase ASCII;
- reject control characters and whitespace inside the final token.

Acorn should not maintain a fixed allowlist at this layer. Domain applications
may enforce their own policy.

## Security Considerations

Declared MIME is metadata, not validation.

Callers can lie about MIME type. Applications MUST continue to make their own
inline rendering decisions from a narrow allowlist. For example, Safebox Web
may inline only images and PDFs while returning all other MIME types as
attachments.

For PKPASS:

- Acorn MUST digest and encrypt the exact package bytes.
- Acorn MUST NOT unzip or normalize the package before computing hashes.
- Acorn MUST NOT validate Apple signatures as part of generic blob storage.
- Wallet-install behavior belongs to the client/application layer.

## Backward Compatibility

Old records may have only `blobtype`.

For those records:

- treat `blobtype` as the effective MIME if present;
- otherwise fall back to sniffing decrypted plaintext;
- if sniffing fails, use `application/octet-stream`.

New records should write both `effective_mime` and `blobtype` during the
migration period.

## Implementation Plan

1. Extend `SafeboxRecord` with:
   - `effective_mime: str | None`
   - `effective_mime_source: str | None`
   - `detected_mime: str | None`
2. Add a helper to normalize and resolve blob MIME metadata.
3. Extend `Acorn.put_record(...)` with optional `blob_type: str | None = None`.
4. In the blob write path:
   - compute detected MIME from plaintext bytes;
   - resolve effective MIME;
   - store new metadata fields;
   - keep `blobtype = effective_mime`.
5. In `get_record_blobdata(...)`, return the resolved effective MIME.
6. In original-record transfer creation, set `origmimetype` from effective
   MIME, not from fresh sniffing alone.
7. In transfer ingest, preserve the transferred effective MIME when re-storing.
8. Add tests:
   - PNG/PDF with no override use detected MIME.
   - unknown bytes use default MIME.
   - PKPASS with override returns `application/vnd.apple.pkpass` while
     retaining `detected_mime = application/zip` when detected.
   - legacy records with only `blobtype` still retrieve correctly.
   - Blossom mock only sees encrypted opaque bytes and does not need artifact
     MIME knowledge.

## Open Questions

- Should `effective_mime_source` be an enum in the Pydantic model or a plain
  string with validation helper?
- Should Acorn expose a structured blob metadata object in addition to the
  existing `(mime, bytes)` tuple?
- Should `OriginalRecordTransfer` gain explicit effective MIME fields now, or
  should `origmimetype` remain the transfer compatibility field until the next
  transfer metadata version?
