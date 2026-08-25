# Interrupted Swap Recovery Milestone — 2026-08-25

## Summary

Live Safebox Web operation exposed a bearer-proof reliability gap at the exact
boundary between a successful Cashu swap and receipt of its HTTP response. Two
incoming transfers reached the recipient as gift-wrapped relay events, but a
timeout interrupted the mint swap used to refresh their proofs. The mint had
already spent the inputs. Acorn had not retained the random output secrets and
blinding factors needed to reconstruct the replacement proofs.

The subsequent retry correctly encountered `proofs already spent`, but the old
implementation could only classify the receipts as terminal errors. The value
remained accounted for at the operator's Lightning node, but the intended
recipient could not complete those two ecash transfers.

Acorn now establishes a durable recovery invariant before every incoming-token
swap: **the mint never receives bearer inputs until the encrypted recovery
material for the exact prepared outputs has been published to and verified on
the wallet's home relay.**

## Observation

The incident sequence was:

1. Safebox Web discovered two incoming transfer events.
2. Acorn combined their proofs into one mint swap.
3. The mint accepted the inputs and generated replacement signatures.
4. The client experienced an HTTP read timeout before receiving the response.
5. A later attempt presented the same inputs again.
6. The mint correctly reported that those proofs were already spent.
7. Without the original output secrets and blinding factors, Acorn could not
   reconstruct the replacement proofs.

The same logs also showed repeated HTTP `429` responses during invoice
settlement checks. Settlement polling was occurring quickly enough to add
avoidable load and increase the likelihood of poor behavior during network or
mint congestion. Rate limiting did not itself spend the proofs, but it was part
of the operational conditions surrounding the failure.

## Root cause

A Cashu swap is atomic at the mint but not across the network boundary between
the mint and wallet. Once `/v1/swap` accepts the inputs, those inputs are spent.
The replacement proofs exist only after the wallet receives blind signatures
and unblinds them using the output secrets and blinding factors it created.

Previously, that recovery material existed only in process memory. A lost HTTP
response or process interruption therefore created this unsafe state:

```text
inputs spent at mint
        +
replacement signatures not received by wallet
        +
output recovery material lost
        =
replacement value cannot be reconstructed
```

Retrying with newly generated outputs cannot repair the operation. The mint
sees already-spent inputs, while NUT-09 restoration requires the original
blinded outputs.

## Corrective invariant

The corrected incoming-token swap lifecycle is:

```text
prepare exact blinded outputs
        |
        v
encrypt recovery material to the Acorn itself
        |
        v
publish and verify pending_swaps on the home relay
        |
        v
submit /v1/swap exactly once
        |
        +---- response received ----> unblind replacements
        |
        +---- response interrupted --> POST /v1/restore with same outputs
                                             |
                                             v
                                      unblind replacements
        |
        v
publish and verify replacement proof state
        |
        v
retire pending swap intent
```

The encrypted `pending_swaps` record contains:

- a random intent identifier;
- the normalized mint and unit;
- a non-secret fingerprint of the input set;
- the exact blinded outputs;
- each output secret and blinding factor; and
- the expected output amount and keyset.

It does not create an application-local wallet journal. The record is encrypted
as an ordinary Acorn private record and stored on the relay under the same
key-controlled state model as other Acorn recovery information.

## Recovery behavior

When the immediate swap response is lost, Acorn retains the intent and calls
the mint's NUT-09 `/v1/restore` endpoint with the original blinded outputs. If
the signatures are available, Acorn validates their keysets and denominations,
reconstructs the replacement proofs, and continues normal relay persistence.

A later retry with the same inputs performs restoration rather than another
swap submission. A different swap is refused while an unresolved intent exists.
If restoration is unavailable or incomplete, Acorn raises
`AmbiguousSwapError`, preserves the recovery record, and leaves the operation
pending for later review. It does not misclassify the condition as an ordinary
double-spend merely because the original inputs are now spent.

The intent is removed only after the replacement Cash proof events or Clear
proof event have been verified on the relay. If cleanup itself fails, the
replacement proofs remain authoritative and the stale intent can be retired
later.

## Safebox Web operational change

The singleton service Acorn worker now limits mint settlement-status checks to
one request every four seconds across the queue. An unpaid quote is not eligible
for another check for five seconds. This prevents several queued invoices or an
eager client from collectively driving the mint beyond its request limit.

The durable provider-payment row remains the authoritative job state. The
throttle is only ephemeral scheduling state inside the singleton worker; it is
not wallet state and does not violate the relay-backed Acorn boundary.

## Verification evidence

Deterministic failure injection now covers the critical sequence:

1. prepare and retain the swap intent;
2. submit `/v1/swap` once;
3. simulate a lost response;
4. simulate process-level retry with the retained intent;
5. recover the signatures through `/v1/restore`;
6. verify that `/v1/swap` was not submitted a second time; and
7. verify the recovered proof amount.

Additional tests verify that the recovery record requests canonical relay
verification and that it is not retired when replacement proof publication
fails.

Verification results after implementation:

- Safebox Acorn: **295 non-live tests passed, 8 live tests deselected**.
- Safebox Web: **381 tests passed**.
- `https://mint.safebox.dev` advertised NUT-09 support when checked on
  August 25, 2026.

## Boundaries and residual risk

This change cannot reconstruct the two transfers that exposed the defect. Their
original output secrets and blinding factors were never persisted, so the data
required by NUT-09 does not exist.

NUT-09 is optional. If a mint does not implement restoration, Acorn can retain
an ambiguous intent but cannot compel the mint to reproduce its signatures.
Mint capability testing therefore remains part of interoperability assessment.

This milestone addresses incoming-token proof refreshes used by Cash and Clear
receipt acceptance. It does not complete the separate outgoing bearer-token
outbox and acknowledged-delivery design. It also cannot guarantee availability
when both the mint and relay are unreachable.

## Lessons

- A successful server-side atomic operation does not make its network response
  reliable.
- Bearer-input idempotency requires retaining the exact prepared outputs, not
  merely recognizing the original inputs.
- Recovery state must be durable before the irreversible boundary.
- A report of `already spent` after a timeout can be evidence of a completed
  operation, not evidence of theft or malformed input.
- Rate-limit headroom is part of reliability engineering.
- Failure injection at each interruption boundary reveals defects that ordinary
  success-path testing cannot.

## Related documents

- [Proof State and Relay Consistency](PROOF-STATE-RELAY-CONSISTENCY.md)
- [Lightning Melt Recovery](LIGHTNING-MELT-RECOVERY.md)
- [Fund-Safety Hardening and Interoperability Milestone](FUND-SAFETY-HARDENING-MILESTONE-2026-08-13.md)
- [Mint-Fee Interoperability Milestone](MINT-FEE-INTEROPERABILITY-MILESTONE-2026-08-24.md)
- [Roadmap to Releasability](ROADMAP-TO-RELEASABILITY.md)
- [Security Policy and Residual Risks](../SECURITY.md)
- [Safebox Web Lightning Handle Payments](https://github.com/trbouma/safebox-web/blob/main/docs/LIGHTNING-HANDLE-PAYMENTS.md)
