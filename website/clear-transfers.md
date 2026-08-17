---
title: Clear Transfers
description: How Acorn keeps organization-issued Clear balances separate from cash.
---

# Clear transfers

Acorn can now receive private transfers of organization-issued Clear Mint Units
without treating them as sats or adding them to the wallet's Cash Balance.

This gives one wallet two deliberately different value models:

```text
Cash Balance
  -> sat-denominated
  -> used for payments
  -> finalized through ordinary Cashu mints

Clear Balances
  -> one balance per exact mint and CMU
  -> used for transfers of issuer-defined credits
  -> recognized under the issuer's program policy
```

## One wallet, several issuers

An Acorn may receive food credits from one organization, service units from
another, and event credits from a third. Each remains identified by its mint
URL and canonical `cmu-<keyset-id>`.

Friendly names help people understand a balance. They do not combine it with
another issuer's units or change which mint validates its proofs.

## Private delivery

A Clear treasury sends to a NIP-05 address. The transfer travels as an
encrypted NIP-59 gift wrap:

```text
kind 1059 gift wrap
  -> kind 7379 Clear transfer
  -> Acorn pending Clear journal
```

Acorn decrypts the transfer, validates its mint, amount, unit, and keysets, and
stores it separately from kind `7378` cash transfers.

## Pending is honest

Receipt from the relay proves that encrypted bearer material arrived for the
Acorn. It does not yet prove that the recipient has refreshed and durably
stored new spendable proofs.

Acorn therefore keeps the transfer pending. The user may retain it for later
acceptance or delete it. Deletion removes the bearer token and leaves a minimal
tombstone so the same relay event does not return.

## The milestone and the boundary

The working product-family flow now reaches from Clear issuance to Acorn
receipt and Safebox Web display. The next stage is atomic acceptance into
encrypted kind `7380` proof state, kind `7381` transfer history, and onward
spending.

This is experimental software. Use test units only until acceptance recovery,
spending, security review, and release hardening are complete.

[Read the technical milestone](https://github.com/trbouma/safebox-acorn/blob/main/docs/CLEAR-TRANSFER-WALLET-MILESTONE-2026-08-17.md){ .md-button .md-button--primary }
[How Acorn works](how-acorn-works.md){ .md-button }
[Project status](project-status.md){ .md-button }

