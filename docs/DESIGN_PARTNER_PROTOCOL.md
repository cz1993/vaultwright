# Design Partner Protocol

## Purpose

Vaultwright is not validated until external operators use it on real client-shaped corpora. This
protocol keeps validation concrete, comparable, and honest.

Use `docs/PILOT_WORKSHEET.md` as the working artifact for each pilot. Attach aggregate output from
`tools/vaultwright.py pilot --json` to the private pilot record, not to this public repository.

## Target Participants

Recruit small consulting, advisory, implementation, compliance, or operations teams that handle
document-heavy onboarding or review work. Avoid broad consumer testing until this wedge is proven.

## Corpus Requirements

Each pilot should use a copied, permission-cleared corpus:

- 50 to 2,000 source files;
- mixed Office files, PDFs, markdown/text, spreadsheets, decks, and optional repositories;
- no files the participant is unwilling to process locally;
- no secrets committed to Git;
- one engagement or protected boundary per vault.

## Evaluation Steps

1. Baseline interview: current process, pain points, tools, security constraints.
2. Non-destructive inventory: run `tools/vaultwright.py plan`.
3. First sync: run `tools/vaultwright.py sync` and capture manifests/audit logs.
4. Conversion review: run `tools/vaultwright.py conversion` and spot-check high/medium-priority
   mirrors before relying on generated content.
5. Review exceptions: unsupported, stale, missing, unreachable, conflicted, or manual-modification
   states.
6. Catalog review: run `tools/vaultwright.py catalog`, `tools/vaultwright.py catalog --html`, and
   `tools/vaultwright.py m365` if the participant expects Microsoft 365 handoff.
7. Record artifact review decisions with `tools/vaultwright.py review` after spot-checking
   selected mirrors, catalogs, and handoff reports.
8. Curate the first hubs and entity pages.
9. Answer a fixed set of operational questions with citations.
10. Capture aggregate evidence: run `tools/vaultwright.py pilot --json` and
   `tools/vaultwright.py pilot --worksheet`, then store the outputs with the private pilot
   worksheet.
11. Modify or move selected sources, rerun status/sync, and verify lifecycle reporting.
12. One-week follow-up: determine whether the participant returned to the vault.

## Required Metrics

Record:

- source file count and total size;
- supported, unsupported, skipped, errored, and warning counts;
- first-sync duration;
- second-sync idempotency result;
- conversion exceptions by file type;
- manual correction count and time;
- provenance spot-check pass/fail rate;
- stale or missing source detection after changes;
- reviewed-artifact counts and stale-review counts from `_meta/review-ledger.jsonl`;
- time to answer fixed operational questions before and after Vaultwright;
- operator confidence score;
- support time required.

## Evidence Artifacts

Keep pilot evidence outside this public repository unless it is fully synthetic or public-domain.
For each pilot, maintain an anonymized summary:

- corpus shape, not source contents;
- command transcript with sensitive paths redacted;
- aggregate metrics;
- review-ledger summary, not source or mirror bodies;
- issues found;
- product changes made;
- participant quote only with written permission.

`tools/vaultwright.py pilot --json` is designed for machine-readable aggregate evidence.
`tools/vaultwright.py pilot --worksheet` prints a redacted Markdown summary for private pilot
records. Both report aggregate counts only, including review-ledger approval/stale-review counts,
and must not be treated as permission to commit pilot evidence to this repository.

## Success Standard

A credible v0.1 needs at least three independent external users and multiple corpora. Passing tests
and public examples are engineering evidence; they do not replace this validation.
