# Protected Record Profile Design Note

## Status

**Profile proposed; key-material scaffold implemented.**

This document describes an optional high-assurance record profile for Acorn.
Acorn now implements generation, external-entropy derivation, and validation
of the independent RPK. Protected-record encryption is not implemented. The
record format, recovery encoding, encryption API, and migration procedure still
require test vectors and security review before implementation.

## Summary

Acorn's current blob design encrypts each blob with an independent random
AES-256-GCM key. That key is stored inside the corresponding NIP-44-encrypted
private record. The blob ciphertext is independently quantum-resistant under
currently known attacks, but a future compromise of the secp256k1/NIP-44
envelope could reveal the AES key.

The protected record profile introduces a second secret that is generated and
recovered independently from the Acorn `nsec`:

```text
Record Protection Key (RPK)
```

The RPK protects per-record keys. It is not published to a relay, uploaded to a
blob server, derived from the `nsec`, or stored in ordinary Acorn relay state.
Opening protected records requires both the normal Acorn authority and the RPK.

This design is intended for records whose confidentiality must survive:

- later compromise of the Acorn `nsec` alone;
- collection and later decryption of retained NIP-44 events;
- compromise or disclosure of a Blossom ciphertext without its key; and
- future quantum attacks against the current secp256k1/NIP-44 envelope.

It does not protect plaintext from a compromised execution environment while
the record is actively open.

The primary threat addressed by this profile is **harvest now, decrypt later**:
an adversary collects Nostr events and encrypted blobs today, retains them for
years, and later obtains the `nsec` or uses a future cryptanalytic capability
against secp256k1 and NIP-44. The independent RPK is intended to keep the inner
record and its blob key confidential in that scenario.

The profile does not claim cryptographic availability. An attacker controlling
the `nsec`, a relay, a Blossom server, or a network path may still suppress,
replace, or delete data. Availability is addressed separately through security
boundaries, replication, provider diversity, and offline recovery copies.

## Motivation

The current design separates large ciphertext from its key-bearing metadata,
but the long-term confidentiality of both ultimately depends on the Acorn
private key. That is appropriate for the normal record profile and provides a
simple recovery model.

Some records justify a stronger boundary. A medical record, legal archive,
private credential, or long-lived personal document may need protection even
if the public-key envelope used for routing and interoperability is broken in
the future. An independent symmetric recovery secret can preserve that boundary
without replacing the current Nostr protocol layer immediately.

The additional protection is optional because it creates an additional
recovery obligation. Loss of the RPK means permanent loss of protected records.

## Goals

- Generate a 256-bit protection secret independently from the Acorn key.
- Keep that secret out of relays, blob servers, logs, URLs, command arguments,
  and ordinary local Acorn configuration.
- Require the RPK in addition to ordinary Acorn authority to decrypt protected
  records.
- Encrypt sensitive record metadata as well as blob contents.
- Preserve independent random encryption keys for individual records and blobs.
- Support future RPK rotation without re-encrypting every large blob.
- Allow an application to hold the RPK only for an authenticated working
  session.
- Define an explicit, separately backed-up recovery artifact.
- Preserve compatibility with existing standard records.
- Retain algorithm and format agility for later hybrid or post-quantum profiles.
- Preserve protected-record confidentiality against collection now followed by
  future compromise of the classical `nsec` envelope.

## Non-goals

- Protecting plaintext from a compromised process while it is being used.
- Removing trust from a hosted execution provider or reverse proxy.
- Making Nostr signatures or event authorship post-quantum secure.
- Hiding all timing, size, author, network, relay, or Blossom metadata.
- Recovering protected data after the RPK and all its backups are lost.
- Treating a browser cookie as the durable recovery copy of the RPK.
- Replacing the existing standard record profile for ordinary data.
- Guaranteeing availability from a relay, Blossom server, network, or hosted
  execution provider.
- Shipping experimental post-quantum algorithms without independent review and
  interoperability tests.

## Terminology

### Record Protection Key (RPK)

A random 32-byte symmetric root secret generated independently from the Acorn
`nsec` and mnemonic. The RPK acts as a key-encryption key; it should not encrypt
large user data directly.

### Record Encryption Key (REK)

A fresh random 32-byte data-encryption key used to encrypt one protected inner
record envelope with AES-256-GCM.

### Blob Encryption Key (BEK)

A fresh random 32-byte data-encryption key used to encrypt one blob with
AES-256-GCM. The protected inner record contains the BEK and blob metadata.

### Outer envelope

The NIP-44-encrypted, signed Nostr event used for transport, compatibility,
addressability, and present-day access control.

### Inner envelope

The record metadata encrypted with the REK. It contains the human-readable
label, payload, and any BEK and blob metadata.

### Wrapped record key

The REK protected by the RPK using a reviewed AES-256 key-wrapping method. NIST
SP 800-38F defines AES Key Wrap and AES Key Wrap with Padding for protecting the
confidentiality and integrity of cryptographic keys.

## Security architecture

```text
                         independently backed up
                                  RPK
                                   |
                                   | AES-256 key wrap
                                   v
Acorn nsec ---> NIP-44 ---> wrapped REK + encrypted inner envelope
     |                             |
     | signs event                 | REK / AES-256-GCM
     v                             v
kind 37375 event             protected record metadata
                                   |
                                   | contains independently generated BEK
                                   v
                             AES-256-GCM blob
                                   |
                                   v
                              Blossom server
```

The outer event remains useful for Nostr interoperability, routing, signatures,
replication, and current clients. The inner envelope is the durable
confidentiality boundary for protected data.

This separation deliberately assigns different responsibilities:

| Concern | Primary mechanism |
| --- | --- |
| Long-term content confidentiality | Independent RPK, wrapped record keys, and AES-256-GCM |
| Content authenticity after retrieval | AES-GCM authentication and protected hashes |
| Current protocol authority and event signing | Acorn `nsec` and Nostr signatures |
| Resistance to unauthorized collection and deletion | Network isolation and access controls independent of the `nsec` |
| Continuity after infrastructure loss | Replication, reciprocal resilience, and encrypted offline backups |

The RPK can preserve confidentiality after an `nsec` compromise. It cannot
restore a deleted event, compel a provider to serve a blob, or prevent a holder
of the signing key from creating protocol-valid deletion or replacement events.

Breaking or decrypting the outer NIP-44 layer must reveal only:

- the protected-record profile and format version;
- a non-secret RPK identifier, if the final format requires one;
- the wrapped REK;
- the inner ciphertext, nonce, and integrity metadata; and
- non-sensitive fields explicitly approved for outer-envelope routing.

It must not reveal the record label, payload, BEK, plaintext hash, private MIME
metadata, or Blossom reference unless a field is deliberately classified as
outer metadata during format review.

## Proposed cryptographic hierarchy

For every protected record:

1. Generate a fresh random 32-byte REK.
2. Build the complete protected inner record, including any blob key and
   metadata.
3. Encrypt the inner record with AES-256-GCM under the REK and a fresh 12-byte
   nonce.
4. Wrap the REK under the RPK using an approved AES-256 key-wrapping profile.
5. Store only the wrapped REK and encrypted inner envelope inside NIP-44.
6. Sign and publish the outer event with the normal Acorn key.

For every protected blob:

1. Generate a fresh random 32-byte BEK and 12-byte nonce.
2. Encrypt the blob with AES-256-GCM.
3. Upload only the ciphertext to the configured Blossom server.
4. Put the BEK, nonce, hashes, MIME type, and blob reference inside the inner
   protected record.

The RPK must not be used directly as a record or blob data-encryption key. This
hierarchy limits key reuse and allows RPK rotation by rewrapping REKs rather
than downloading and re-encrypting large blobs.

The blob encryption itself does not change from the current Acorn design. The
protected profile changes where and how the existing BEK and blob metadata are
protected. Once the key-bearing record is protected by the RPK hierarchy, the
existing independently encrypted AES-256-GCM blob does not require another
content-encryption layer.

The initial design should prefer a fully specified key-wrapping construction,
not an ad hoc combination of encryption and authentication. The final choice
between AES Key Wrap and AES Key Wrap with Padding must be recorded in the
versioned profile and accompanied by fixed test vectors.

## Protected lookup namespace

The current lookup tag is derived from the `nsec` and record label. A future
quantum compromise of the Acorn key would therefore permit label guessing even
if the inner content remained encrypted.

Protected records should use a separate lookup namespace derived from the RPK,
for example:

```text
protected_d_tag = HMAC-SHA256(
    key = derived_lookup_key,
    data = normalized_record_label
)
```

The lookup key should be domain-separated from the key-wrapping key using a
reviewed KDF and fixed context labels. Exact normalization, KDF inputs, and tag
encoding must be specified before implementation. Changing existing lookup
rules silently is prohibited; protected records require an explicit profile
and version.

An observer can still correlate replacements using the same protected `d` tag
and can still see the event author. The RPK-derived tag prevents an `nsec`
compromise alone from enabling offline label guesses.

## Blossom authorization and blob correlation

The current Acorn implementation authorizes a Blossom upload with the Acorn
`nsec`. Blossom-compatible APIs may support listing blobs by author public key,
and a server can retain the authorization event and operational logs. Hiding a
blob reference inside the protected record therefore does not guarantee that
an attacker cannot identify the broader set of blobs associated with the Acorn
public key.

With the current authorization arrangement, an attacker holding the `nsec` may
be able to:

- enumerate blobs attributed to the Acorn public key, depending on server
  policy;
- obtain their ciphertext hashes and public descriptors;
- authorize deletion of known blobs; and
- delete all candidate blobs without knowing which protected label refers to
  each one.

The attacker would still lack the RPK and therefore could not map a protected
label to a blob through the inner record or decrypt the blob. This preserves
confidentiality but not availability.

A hardened protected-blob profile may use a random Blossom authorization key
that is separate from the Acorn `nsec`, preferably one key per blob:

```text
Acorn nsec
    signs the Nostr record

random per-blob Blossom authorization key
    authorizes blob upload and deletion
    is stored only inside the RPK-protected inner record
```

This reduces public-key correlation and prevents an `nsec`-only attacker from
authorizing deletion through the protected blob's upload identity. It does not
hide timing, source address, or operational correlation from the Blossom
operator, and it does not force that operator to retain the object.

Per-blob authorization is a defense-in-depth option, not the source of the
quantum-resistance claim. Its lifecycle, server compatibility, recovery,
replication, and deletion behavior require separate tests before it can become
mandatory for the protected profile.

## Proposed outer and inner formats

The following structures are illustrative, not final serialization formats.

Outer record before NIP-44 encryption:

```json
{
  "version": 2,
  "profile": "acorn-protected-record-v1",
  "key_id": "<non-secret RPK identifier>",
  "wrap_alg": "A256KW",
  "wrapped_record_key": "<encoded wrapped REK>",
  "inner_alg": "AES-256-GCM",
  "inner_nonce": "<encoded 12-byte nonce>",
  "inner_ciphertext": "<encoded authenticated ciphertext>"
}
```

Protected inner record:

```json
{
  "version": 1,
  "label": "Medical Archive",
  "type": "protected-blob",
  "payload": {
    "description": "Private medical records"
  },
  "blob": {
    "alg": "AES-256-GCM",
    "key": "<encoded BEK>",
    "nonce": "<encoded 12-byte nonce>",
    "reference": "<Blossom reference>",
    "ciphertext_sha256": "<hash>",
    "plaintext_sha256": "<hash>",
    "media_type": "application/pdf"
  }
}
```

The final design must define canonical serialization, binary encoding, maximum
sizes, required fields, and failure behavior. Unknown versions, algorithms, or
critical fields must fail closed.

## Creation and backup ceremony

Protected records should be an explicit opt-in capability. During creation of
a new Acorn, the user may choose to enable protected records. Existing Acorns
should be able to enable the profile later without changing their `nsec`.

When enabled:

1. Acorn generates 32 random bytes using the operating system cryptographic
   random source, or accepts exactly 32 bytes of high-quality entropy from an
   explicitly selected external source.
2. Acorn derives the RPK with HKDF-SHA256 and the domain-separation context
   `safebox-acorn/record-protection-key/v1`. The input entropy is never reused
   directly as the RPK.
3. Acorn presents an independently labelled RPK recovery artifact.
4. The user is told that it is separate from the wallet mnemonic and cannot be
   reconstructed from the `nsec`.
5. The user confirms that the recovery artifact has been copied before Acorn
   permits creation of protected records.
6. Acorn does not publish or persist the RPK in ordinary configuration.

The initial implementation exposes these Acorn-owned primitives:

```python
from acorn import (
    generate_record_protection_key,
    record_protection_key_from_entropy,
    validate_record_protection_key,
)
```

Both creation paths return a canonical 64-character lowercase hexadecimal
working key. This representation is an internal API and session transport
format; it is not the final user-facing recovery artifact. The protected-record
encryption profile remains disabled until its format and recovery ceremony are
implemented and tested.

The recovery artifact should provide versioning and checksum protection. One
candidate is a separately labelled 24-word phrase encoding the original 256
bits plus checksum. If BIP39 encoding is used, the words represent the RPK
entropy directly; they must not be passed through the Acorn wallet's SLIP-10
derivation path or described as the wallet mnemonic. A checksummed textual or
QR representation may also be provided after usability and transcription
testing.

The final user-facing terminology should be unmistakable:

```text
Acorn wallet recovery phrase       -> recovers the Acorn signing key
Protected-record recovery phrase   -> recovers the independent RPK
```

## Recovery

Complete recovery of protected records requires:

1. the Acorn `nsec` or its valid offline mnemonic;
2. the home relay or sufficient replicated relay information; and
3. the independent RPK recovery artifact.

The RPK must be accepted through a hidden, confirmation-aware input channel.
It must not be accepted as a command-line argument, URL parameter, ordinary
environment variable, or logged request field.

Recovery should verify the key against an existing protected record or a
non-secret key identifier before declaring success. If no protected records
exist, Acorn can validate only the artifact's syntax and checksum. It must not
claim that an unverified RPK is correct.

Loss of the RPK is intentionally unrecoverable. A support operator, relay,
Blossom server, and Safebox provider must not possess a hidden recovery copy.

## Safebox Web session handling

Cookie storage is an integration choice, not an Acorn core responsibility.
Acorn should accept the RPK as an explicit transient API dependency and should
not know whether it came from a cookie, hidden prompt, hardware device, or
another trusted secret broker.

Safebox Web may include the RPK in its authenticated encrypted session cookie
after the user supplies it. The cookie copy must be:

- protected by the application's authenticated session encryption;
- `Secure`, `HttpOnly`, and appropriately `SameSite` scoped;
- absent from URLs, HTML, JavaScript, logs, and the application database;
- cleared on logout; and
- treated as an expiring working copy, never the recovery backup.

The server necessarily decrypts the cookie and holds the RPK in process memory
while processing a protected record. Therefore, placing the `nsec` and RPK in
the same encrypted cookie provides independent cryptographic recovery factors,
but it does not provide runtime isolation between them.

A malicious or compromised Safebox execution environment can capture both
secrets. A trusted reverse proxy can also replace or redirect the application
and must remain part of the disclosed execution trust boundary.

## Availability, isolation, and reciprocal resilience

Encryption cannot guarantee availability. A valid RPK does not help if every
copy of an event or blob has been destroyed or made unreachable. The protected
profile must therefore describe availability as an operational property rather
than a cryptographic one.

For especially sensitive deployments, relays and Blossom servers may be placed
behind firewalls, VPNs, private networks, or application gateways that an
internet attacker cannot directly reach. Those controls can reduce:

- passive harvesting of long-lived ciphertext;
- public enumeration of author events or blobs;
- deletion attempts made with a compromised `nsec` from outside the boundary;
- traffic and access-pattern observation; and
- opportunistic denial-of-service attacks.

Infrastructure access controls should be independent from the Acorn `nsec`
where practical. Compromise of the protocol key should not automatically grant
VPN membership, firewall access, administrative credentials, or storage-host
control.

Private infrastructure is still not a single-copy strategy. Natural hazards,
hardware failure, operator error, compromise from inside the boundary, and
loss of an entire site remain possible. Continuity should combine:

- more than one relay and blob copy;
- independently administered or geographically separated infrastructure;
- verified replication and periodic restore exercises;
- encrypted offline backups containing ciphertext and required metadata;
- monitoring for missing, replaced, or unexpectedly deleted objects; and
- a documented recovery process requiring the RPK.

This is consistent with Acorn's reciprocal-resilience model: trusted parties or
communities can preserve independently encrypted copies for one another without
receiving the keys needed to read them.

## CLI, device, and hardware handling

The CLI should request the RPK through a hidden prompt and retain it only for
the active process unless the user deliberately selects an approved secret
store. It must not add the RPK to the default YAML configuration.

Future integrations may obtain the RPK or perform unwrapping through:

- an operating-system keychain;
- a hardware security module;
- a hardware token or secure element;
- a local agent with narrowly scoped access; or
- a user-supplied recovery artifact for one session.

Hardware-backed unwrapping is preferable to exporting the raw RPK, but it
requires a separate provider interface, recovery policy, and failure model.

## Rotation and multiple protectors

RPK rotation requires the old RPK. For each protected record, Acorn should:

1. unwrap the REK with the old RPK;
2. wrap the same REK with the new RPK;
3. publish and verify the replacement protected record;
4. retain the old wrapping until new-record readback is confirmed; and
5. retire the old RPK only after every selected record is migrated and audited.

Because blob content remains encrypted under its BEK, rotation should not
require downloading or re-uploading the blob.

A later format may support multiple wrapping slots so the same REK can be
opened by a user recovery key, a hardware-backed key, or another explicitly
authorized protector. Multiple protectors materially broaden the attack and
revocation surface and are out of scope for the first implementation.

## Threat analysis

| Event | Standard record | Protected record |
| --- | --- | --- |
| Blossom ciphertext disclosed | Blob remains encrypted without its key-bearing record | Blob remains encrypted without the protected inner record and RPK |
| Relay record disclosed | NIP-44 protects metadata | NIP-44 plus the RPK-wrapped inner envelope protect metadata |
| `nsec` compromised offline | Attacker can decrypt metadata and recover blob keys | Attacker can reach only the wrapped REK and inner ciphertext without the RPK |
| Future secp256k1 quantum break | Equivalent to `nsec` compromise for retained events | Protected inner content remains encrypted without the RPK under currently known attacks |
| RPK compromised without `nsec` | RPK does not exist | Attacker may derive protected lookup tags but cannot decrypt the NIP-44 outer envelope; if its decrypted contents are obtained through another path, the attacker can unwrap the REK and decrypt the inner record |
| Active Acorn host compromised while unlocked | Plaintext and keys may be captured | Plaintext, `nsec`, RPK, REKs, and BEKs may be captured |
| RPK lost | Not applicable | Protected records become permanently unavailable |
| Event deleted or censored | Availability may be lost | Availability may be lost; the RPK does not provide replication |

The protected profile is successful when an attacker can identify, retain, or
even delete ciphertext without learning the protected content. Preventing or
recovering from deletion requires the separate availability controls described
above.

The RPK is an additional confidentiality boundary, not a complete second
authentication system. Event signing and relay authorization continue to use
the Acorn key in the first profile.

## Failure semantics

| Failure | Required behavior |
| --- | --- |
| RPK generation or secure-random failure | Abort protected-profile creation |
| Backup confirmation not completed | Do not enable protected-record creation |
| Invalid recovery checksum or format | Reject before attempting record access |
| RPK cannot unwrap a record key | Return a generic protected-record key error; return no inner plaintext |
| Inner GCM authentication or hash fails | Fail closed and return no record or blob key |
| Process exits after receiving RPK | Discard the working copy; require it again unless an approved session or hardware store remains valid |
| RPK rotation is interrupted | Preserve the old RPK and wrapping until every replacement has verified readback |
| Cookie expires or is cleared | Require the user to supply the RPK again; do not imply record loss |
| User loses every RPK backup | Report permanent protected-record recovery failure; no provider bypass exists |

## Deletion and cryptographic erasure

Protected records use the same advisory NIP-09 and Blossom deletion mechanisms
as standard records. Provider acceptance does not prove that mirrors, logs,
backups, or retained ciphertext have been physically erased.

Destroying every copy of the RPK can make retained protected ciphertext
computationally inaccessible, but Acorn must not call this guaranteed erasure:

- an RPK may have been copied or captured;
- plaintext may exist elsewhere;
- an unlocked execution environment may have retained keys;
- individual REKs or BEKs may have been exported; and
- implementation defects or future cryptanalysis may alter assumptions.

Deletion results and key-destruction claims must therefore remain separate.

## Compatibility and migration

Standard records continue to use the existing version `1` format. Protected
records use an explicit new profile and must never be mistaken for legacy
unencrypted blobs or ordinary NIP-44-only records.

Migration from a standard record requires:

1. a valid RPK and confirmed backup;
2. successful decryption of the standard record;
3. creation, publication, and readback verification of the protected version;
4. explicit user confirmation before deletion of the standard version and any
   old blob; and
5. reporting of partial relay or Blossom cleanup.

Migration must not overwrite the only usable copy before the protected version
has been verified.

## Proposed component boundary

Illustrative APIs might eventually resemble:

```python
acorn.enable_protected_records(record_protection_key=rpk)

await acorn.put_record(
    record_name="Medical Archive",
    record_value=metadata,
    blob_data=document,
    protection_profile="protected-v1",
    record_protection_key=rpk,
)

record = await acorn.get_record_safebox(
    record_name="Medical Archive",
    record_protection_key=rpk,
)
```

These names are illustrative. The final API must make secret lifetime explicit,
avoid retaining the RPK on a long-lived object unnecessarily, and prevent a
caller from silently downgrading a protected record to the standard profile.

## Testing and review gates

Implementation must not begin with only a round-trip test. The profile requires:

- deterministic test vectors for KDF, lookup tag, key wrap, inner encryption,
  and blob encryption;
- independent verification of those vectors outside the primary code path;
- wrong-RPK, corrupted-wrap, corrupted-inner-ciphertext, substituted-record,
  and substituted-blob tests;
- confirmation that `nsec` compromise alone cannot decrypt protected fixtures;
- recovery tests using the exact exported recovery representation;
- cookie expiry, logout, session rotation, and multi-worker web tests;
- interrupted RPK rotation and migration failure injection;
- logging and exception-output regression tests;
- resource limits and malformed-envelope fuzzing;
- live relay and Blossom lifecycle tests using disposable records; and
- author-listing and deletion tests for any per-blob Blossom authorization
  profile;
- private-network deployment tests confirming that possession of the `nsec`
  alone does not cross the infrastructure access boundary;
- review of cryptographic construction and user recovery behavior before a
  stable release claim.

The project must continue to describe the profile as proposed until the format,
test vectors, implementation, recovery ceremony, and compatibility behavior
have all passed review.

## Open design decisions

1. Final name and user-facing terminology for the RPK.
2. Recovery encoding: 24-word phrase, checksummed textual key, QR form, or a
   carefully specified combination.
3. Exact KDF and domain-separation labels for wrapping and lookup keys.
4. AES Key Wrap versus AES Key Wrap with Padding for the version `1` profile.
5. Canonical binary and JSON encodings.
6. Whether a non-secret key identifier is required and how it is derived.
7. Exact protected-label normalization and event-kind strategy.
8. Whether protected records can be listed without attempting to decrypt every
   candidate event.
9. RPK caching duration for CLI, web, device, and hardware integrations.
10. Rotation, multiple-protector, escrow, and organizational recovery policy.
11. Whether independent per-blob Blossom authorization is mandatory or an
    optional hardened deployment profile.
12. Minimum replication, backup, and restore evidence required before the UI
    describes a protected record as resilient.

## References

- [Acorn Record Encryption Specification](RECORD-ENCRYPTION-SPEC.md)
- [Acorn Security](../SECURITY.md)
- [Recovery Specification](RECOVERY-SPEC.md)
- [Secret Input Specification](SECRET-INPUT-SPEC.md)
- [Stateless Web Integration](STATELESS-WEB-INTEGRATION.md)
- [NIST SP 800-38F: Methods for Key Wrapping](https://csrc.nist.gov/pubs/sp/800/38/f/final)
- [NIST SP 800-57 Part 1 Rev. 5: Recommendation for Key Management](https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final)
