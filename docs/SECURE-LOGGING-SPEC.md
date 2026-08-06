# Secure Logging Specification

## Purpose

Acorn logs operational state without logging the user-controlled funds,
records, or root key material being operated on. This applies at every logging
level, including DEBUG, and to exception and test output.

Debug logging is not a protected storage channel. Logs are commonly copied to
terminals, service managers, support bundles, CI systems, backups, and external
observability platforms. A value that is unsafe to disclose must never be made
safe merely by assigning it a lower log level.

## Prohibited log content

Acorn must never log:

- `nsec` values, raw private keys, RPKs, protected-record recovery phrases,
  external entropy, or wallet seed phrases;
- Cashu tokens, complete `Proof` objects, proof secrets, blinding factors, or
  full spend/keep proof collections;
- complete mint request bodies or response objects that may contain quotes,
  invoices, preimages, change proofs, or other capabilities;
- Lightning invoices or payment preimages;
- decrypted wallet metadata or record payloads;
- private record labels or stable private label hashes;
- direct-message or secure-transmittal plaintext;
- complete gift wraps, zap requests, serialized events, or event content;
- passwords, authentication headers, access tokens, or future HSM credentials;
  or
- secret values embedded in exception messages.

This prohibition applies even when the value is encrypted before publication.
Logging the plaintext immediately before encryption remains disclosure.

## Permitted operational fields

Logs may include the smallest metadata needed to diagnose an operation:

- operation and status names;
- counts of proofs, events, tags, relays, or records;
- aggregate satoshi amounts and fee reserves;
- mint domains and relay URLs when operationally necessary;
- keyset identifiers;
- event IDs for already published events;
- event kinds;
- payload byte lengths;
- boolean state such as `paid`, `verified`, or `has_blob`; and
- exception classes and sanitized error descriptions.

Public identifiers such as `npub`, NIP-05 names, payment addresses, event IDs,
relay URLs, and record timing can still be privacy-sensitive. They should be
logged only when they materially help diagnose the operation and should not be
combined with private content.

## Proof logging

Cashu proofs are bearer assets. Logging a complete proof or its `secret` can
turn a diagnostic artifact into a spendable-value disclosure. Proof operations
therefore log summaries such as:

```text
op=pay_multi status=proof_selection spend_count=2 spend_amount=21 keep_count=3 keep_amount=42
```

They must not log the proof objects used to calculate those values.

## Payment logging

Payment operations may log the requested amount, fee reserve, mint domain,
keyset, and final status. They must not log the Bolt11 invoice, mint quote
identifier, melt request body, preimage, or full mint response.

Transaction history is wallet data rather than diagnostic logging. Its user
comment and payment details remain encrypted wallet records and must not be
duplicated into process logs.

## Record and messaging logging

Private record operations log the event kind and operation status. They do not
log the label, deterministic label hash, decrypted record, blob encryption key,
or payload.

Messaging operations may log message byte length and relay count. They do not
log message plaintext. Gift-wrapped and NIP-44 encrypted content is subject to
the same rule before and after encryption.

## Exceptions

Code should prefer structured, sanitized exceptions. An upstream HTTP or
parsing exception may contain a response body or user data, so callers should
avoid blindly logging arbitrary objects or request payloads. Where practical,
log the exception class, HTTP status, operation, and remote endpoint rather
than an unreviewed body.

## Verification

`tests/unit/test_sensitive_logging.py` enforces known prohibited logging
patterns and confirms that wallet initialization does not log its `nsec` or raw
private key at DEBUG. New wallet, payment, record, and messaging features must
extend this coverage when they introduce another class of sensitive value.

Live tests may show progress using public relay names, operation names, counts,
amounts, and disposable event IDs. They must not print source-wallet keys,
disposable keys, proof secrets, seed phrases, entropy, invoices, or tokens.
