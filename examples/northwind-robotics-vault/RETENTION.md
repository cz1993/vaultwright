---
title: RETENTION
type: policy
status: active
domain: governance
created: 2026-01-01
updated: 2026-01-01
owner: you
tags: [governance, retention]
related: ["[[CLAUDE]]", "[[INDEX]]"]
---

# Document Retention Policy

> **Starting template — not legal advice.** Adjust the windows to your jurisdiction, industry, and
> contractual obligations. Defaults below are common North-American small-business norms; confirm
> with your accountant / lawyer.

| Category | Suggested retention | Notes |
| --- | --- | --- |
| Receipts, invoices, financial statements | 6–7 years | Tax-authority norm (e.g. CRA/IRS) |
| Tax filings & working papers | 6–7 years | |
| Signed contracts, NDAs, MSAs, SOWs | 7 years after termination | Surviving clauses may extend |
| Client deliverables | 5 years after engagement close | Or per contract |
| Client communications of record | 5 years | Email exports, decisions, sign-offs |
| Marketing — published | Indefinite | Brand history |
| Marketing — drafts | 1 year | Then archive & prune |
| Grant applications (submitted/awarded) | 7 years | Audit evidence |
| Vendor records | 7 years | |
| Internal runbooks/reports | While relevant | Archive when stale |
| `_tmp/` | 30 days | Auto-prunable |

## Archival process

1. Identify documents past their active window.
2. Move to `_archive/<original-category>/YYYY/` (do not delete).
3. Set the note's `status:` to `archived`.
4. Never delete from `_archive/` without explicit human approval.

## Privacy & sensitivity

- **PII** stays in designated private areas (e.g. `30_customers/<account>/private/` or
  `70_people/private/`); never in market/public-facing trees.
- **Secrets/credentials never live in the vault** — OS keychain or a secrets manager only.
