# Mint-Fee Interoperability Milestone — 2026-08-24

## Summary

Testing Acorn against a second Cashu mint exposed an important interoperability
defect that had remained hidden while development used a mint configured with
zero proof-input fees. Acorn prepared the correct Lightning amount and
Lightning fee reserve, but did not include every NUT-02 `input_fee_ppk` charge
incurred across the complete payment path.

The independently configured mint correctly rejected a 21-sat payment because
the submitted proofs totalled 21 sats while 22 sats were required: 21 sats for
the invoice and 1 sat for mint proof-input fees. The Lightning node was never
asked to make the payment.

Acorn now calculates both mint-fee layers before submitting a melt, preserves
definitive mint rejection details, and leaves the wallet's proofs safely
available when a request is rejected. A live 21-sat payment subsequently
completed through the fee-charging mint with 2 sats in reported fees.

## What independent-mint testing revealed

The original development mint accepted the earlier calculation because its
active keyset did not charge an input fee. That environment validated the
basic payment path but could not exercise fee-aware interoperability.

The second mint advertised a nonzero `input_fee_ppk`. Its logs showed:

```text
not enough inputs provided for melt. Provided: 21, needed: 22
```

This demonstrated that the failure was not Lightning routing. Direct payments
from the mint's Lightning node succeeded, while the rejected Acorn attempt did
not appear in the node's payment history. The mint had rejected the Cashu melt
before Lightning submission.

The test exposed two distinct mint input-fee layers:

1. The wallet's existing proofs are consumed in a preparatory swap that creates
   exact payment and change proofs. Those inputs may incur a mint fee.
2. The newly prepared payment proofs are consumed by the melt itself. Those
   inputs may incur another mint fee.

Lightning routing fees and mint input fees are separate. A correct payment
plan must cover all of them without treating the nominal invoice amount as the
required proof total.

## Corrective behavior

Acorn now:

- reads the active keyset's `input_fee_ppk` before preparing a payment;
- selects enough existing proofs to cover the preparatory swap input fee;
- constructs enough melt proofs to cover the invoice, Lightning fee reserve,
  and final melt input fee;
- handles binary-denomination boundaries where adding one sat changes the
  number of proofs and therefore the fee calculation;
- applies the same accounting to Lightning-address payments, direct invoices,
  and mint-to-mint transfers;
- reports the combined fee actually borne by the wallet; and
- treats an HTTP 4xx melt response as a definitive pre-submission rejection,
  preserving the mint's response instead of replacing it with a misleading
  `UNPAID` result from the unchanged quote.

Ambiguous transport failures and server errors still require quote-state
reconciliation. A definitive request rejection does not.

## Live evidence

After the fix, the previously failing payment path was repeated:

```text
Payment of 21 sats with fee 2 sats to trbouma@acorn.safebox.dev successful!
```

The successful run exercised Acorn against a mint with nonzero proof-input
fees and completed the Cashu-to-Lightning-to-Safebox path. The 2-sat result
included the applicable mint fee accounting rather than assuming that only
the invoice amount needed to be supplied.

This is strong interoperability evidence, not a universal mint certification.
Different implementations may vary in keysets, fee schedules, Lightning
backends, quote behavior, and failure responses. Continued testing across
independently configured mints remains a release requirement.

## Why this milestone matters

This defect was not revealed by more repetitions against the original mint.
It emerged because Acorn was exercised against infrastructure with materially
different—but valid—protocol settings. The finding reinforces a core release
principle:

> A component is not interoperable merely because it works repeatedly with one
> familiar deployment.

Independent relay and mint testing is therefore part of correctness work, not
only deployment validation. It reveals implicit assumptions about fees,
timeouts, event behavior, and protocol options before those assumptions become
embedded in a release.

## Verification

The deterministic suite includes coverage for:

- zero and nonzero `input_fee_ppk`;
- proof-denomination boundaries;
- preparatory swap input fees;
- final melt input fees;
- insufficient balance after fees;
- full-amount mint transfers; and
- preservation of HTTP 4xx mint rejection details.

Following the change, the non-live suite passed with 277 tests and the payment
was then verified live using a small amount.

## Related documents

- [Lightning Melt Recovery](LIGHTNING-MELT-RECOVERY.md)
- [Fund-Safety Hardening and Interoperability Milestone](FUND-SAFETY-HARDENING-MILESTONE-2026-08-13.md)
- [Roadmap to Releasability](ROADMAP-TO-RELEASABILITY.md)
- [CLI Contract](CLI-CONTRACT.md)
- [Security Policy and Residual Risks](../SECURITY.md)
