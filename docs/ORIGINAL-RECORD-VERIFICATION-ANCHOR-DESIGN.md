# Original Record Verification Anchor Design

Status: Draft  
Scope: Acorn Original Record digests, effective MIME, and external verification

## Summary

An Acorn Original Record can act as a verification anchor for higher-level
control and provenance systems.

Acorn stores the exact original bytes, encrypts them before Blossom upload, and
records integrity metadata for the plaintext artifact. The resulting plaintext
digest, such as `origsha256`, is the artifact's **Uniform Digest Anchor (UDA)**.
Applications may
render the artifact according to `effective_mime`, but verification binds to
the unchanged bytes.

This creates a layered model:

```text
exact bytes -> Uniform Digest Anchor -> control evidence -> verifier policy
```

The digest gives external systems such as OpenETR a precise object identity
without requiring Acorn, Blossom, or Safebox Web to understand every possible
document, credential, ticket, pass, or media format.

## Motivating Example: PKPASS

An Apple Wallet `.pkpass` is a signed ZIP package. Safebox Web can preview it by
reading `pass.json`, rendering package images, and generating declared QR or
Aztec barcode symbols.

Those preview steps must not define the object being verified. They are
representations.

The verification anchor is the digest of the exact PKPASS package bytes:

```text
origsha256 = sha256(original_pkpass_bytes)
```

That distinction matters because a PKPASS contains multiple useful layers:

| Layer | Example | Owner of concern |
| --- | --- | --- |
| Bytes | the exact `.pkpass` package | Acorn Original Record |
| Artifact type | `application/vnd.apple.pkpass` | Acorn effective MIME metadata |
| Representation | pass fields, logo, Aztec or QR symbol | Application renderer |
| Wallet behavior | install, trust, pass signature handling | Wallet software |
| Control evidence | origin, transfer, presentation, termination | OpenETR or another control layer |
| Verifier conclusion | accepted, rejected, warning, policy result | Verifier policy |

The same model applies to PDFs, images, credentials, bills of lading, tickets,
or any other exact artifact that can be hashed.

## Design Principle

The Original Record's Uniform Digest Anchor is a byte-level identity, not a
rendering decision.

Applications may have many representations for the same bytes:

- a thumbnail;
- a PDF canvas;
- a Wallet pass preview;
- extracted text;
- a barcode symbol generated from metadata; or
- a generic download page.

None of those representations should replace the original digest as the
verification target. A verifier should hash the exact artifact bytes it is
being asked to verify and compare that digest to signed evidence.

## Separation of Interests

Deep verification works by keeping concerns separate and then composing them.

| Concern | Question | Evidence |
| --- | --- | --- |
| Integrity | Are these the exact bytes? | plaintext digest such as `origsha256` |
| Classification | What kind of artifact should an app show? | `effective_mime` |
| Storage | Where are bytes available? | encrypted Blossom object and Acorn metadata |
| Control | Who originated, controls, transferred, or terminated it? | signed control events |
| Recognition | Who are these keys or organizations to this verifier? | NIP-05, profiles, registries, trust lists, policies |
| Validity | What conclusion should be reached now? | verifier policy over the evidence |

Acorn should own the first three concerns for private records. External
protocols and applications should own the remaining concerns through explicit
interfaces.

## OpenETR Compatibility

OpenETR-style control can attach directly to an Acorn Original Record digest.

For an encrypted blob attachment:

- the encrypted Blossom digest identifies stored ciphertext, not the controlled
  object;
- the Acorn event id identifies encrypted record metadata, not the artifact;
- the Original Record plaintext digest identifies the artifact; and
- OpenETR origin and control events should bind to that plaintext digest.

This means an application can issue or verify control evidence without
rewriting the artifact. The OpenETR component can receive the exact bytes or a
complete digest from the application boundary, construct or verify signed
events, and return a policy result.

Acorn does not need to become an OpenETR implementation. It needs to preserve
the original bytes, expose the digest, and keep enough metadata for applications
to offer the right workflow.

## Effective MIME Role

`effective_mime` helps applications choose how to represent a verified artifact.

It does not define the artifact identity and it does not prove the content is
safe. For example:

```json
{
  "effective_mime": "application/vnd.apple.pkpass",
  "effective_mime_source": "declared",
  "detected_mime": "application/zip",
  "origsha256": "..."
}
```

The digest answers "which exact artifact?" The effective MIME answers "which
viewer should the application consider?" A verifier should not substitute the
MIME type, filename, label, or parsed fields for the digest.

## Security Considerations

Digest anchoring improves integrity, but it does not answer every trust
question by itself.

- A matching digest proves byte equality, not truth.
- A valid signature proves key authorization, not civil identity.
- A recognized issuer may still issue a false, expired, revoked, or irrelevant
  record.
- A rendered preview may omit fields that matter to a domain-specific verifier.
- A declared MIME may be wrong or malicious.

Applications should therefore treat deep verification as layered evidence:
hashes, signatures, control history, identity recognition, domain policy, and
human-readable presentation each do a different job.

## Implementation Notes

Acorn should continue to:

- hash the exact plaintext Original Record bytes before encryption;
- preserve the exact bytes during storage, retrieval, sharing, and
  presentation;
- keep `origsha256` distinct from encrypted blob hashes;
- expose `effective_mime` for application rendering;
- avoid domain-specific parsing in generic blob storage; and
- let applications pass exact bytes or complete digests to external verifier
  components.

Future APIs may expose a structured Original Record metadata object so
applications do not need to infer digest, MIME, and storage fields from record
payload conventions.
