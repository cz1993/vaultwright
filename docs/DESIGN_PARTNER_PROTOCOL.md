# Design Partner Protocol

## Purpose

Vaultwright is not validated until external operators use it on real client-shaped corpora. This
protocol keeps validation concrete, comparable, and honest.

## Target Participants

Recruit small consulting, advisory, implementation, compliance, or operations teams that handle
document-heavy onboarding or review work. Avoid broad consumer testing until this wedge is proven.

## Corpus Requirements

Each pilot should use a copied, permission-cleared corpus:

- 50 to 2,000 source files;
- mixed Office files, PDFs, markdown/text, spreadsheets, decks, and optional repositories;
- no files the participant is unwilling to process locally;
- no secrets committed to Git;
- one engagement or client boundary per vault.

## Evaluation Steps

1. Baseline interview: current process, pain points, tools, security constraints.
2. Non-destructive inventory: run `tools/vaultwright.py plan`.
3. First sync: run `tools/vaultwright.py sync` and capture manifests/audit logs.
4. Review exceptions: unsupported, stale, missing, unreachable, conflicted, or manual-modification
   states.
5. Curate the first hubs and entity pages.
6. Answer a fixed set of operational questions with citations.
7. Modify or move selected sources, rerun status/sync, and verify lifecycle reporting.
8. One-week follow-up: determine whether the participant returned to the vault.

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
- time to answer fixed operational questions before and after Vaultwright;
- operator confidence score;
- support time required.

## Evidence Artifacts

Keep pilot evidence outside this public repository unless it is fully synthetic or public-domain.
For each pilot, maintain an anonymized summary:

- corpus shape, not source contents;
- command transcript with sensitive paths redacted;
- aggregate metrics;
- issues found;
- product changes made;
- participant quote only with written permission.

## Success Standard

A credible v0.1 needs at least three independent external users and multiple corpora. Passing tests
and public examples are engineering evidence; they do not replace this validation.
