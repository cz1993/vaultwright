# Agent-Readiness Benchmark

Vaultwright's future claim is not just that people can browse a cleaner knowledge base. The claim
to prove is stronger:

> AI agents should answer, reconcile, update, and audit operational knowledge more reliably from
> Vaultwright-generated markdown than from raw source folders or one-off document-chat transcripts.

This document defines the benchmark shape for design partners. It is intentionally conservative:
until these tasks are measured, "agent-ready markdown substrate" is a thesis, not a proven product
claim.

## Comparison Modes

Run the same task set against three modes:

1. **Raw source folder** - originals only, such as Office files, PDFs, spreadsheets, decks, repos,
   and loose notes.
2. **Document-chat transcript** - a chat or RAG session over the same source collection, with no
   durable markdown mirrors or manifest-backed refresh state.
3. **Vaultwright markdown** - generated mirrors, manifests, source-linked hubs, entity pages, and
   linted conventions.

Do not mix evidence between modes during scoring.

## Task Families

Use fixed tasks that reflect real operator and agent work:

| Family | Example task | What good looks like |
| --- | --- | --- |
| Answer | "What steps are required before GST/HST registration?" | Correct answer with source-backed citations and caveats |
| Reconcile | "Which documents disagree about eligibility or dates?" | Finds conflicts and points to specific files/sections |
| Update | "A source changed; what notes or hubs must be refreshed?" | Identifies stale mirrors/notes without rewriting originals |
| Audit | "Show evidence for this recommendation." | Produces traceable source path, mirror path, and manifest context |
| Consolidate | "Where should this new fact live?" | Extends an existing note when appropriate instead of spawning duplicates |

## Metrics

Track both outcome quality and operating cost:

- answer correctness;
- citation/source-path accuracy;
- missed caveats or unsupported claims;
- stale-source detection;
- duplicate-note avoidance;
- manual reviewer correction count;
- time to acceptable answer;
- token/tool-call count if available;
- operator confidence score;
- privacy/provenance violations.

## Scoring

Use a simple 0-2 score for each task:

- `0` - wrong, uncited, unsafe, or not actionable;
- `1` - partially correct but missing caveats, citations, or update/audit evidence;
- `2` - correct, source-backed, and operationally useful.

Vaultwright should not claim agent-readiness superiority unless the markdown mode improves total
score, reduces correction effort, or improves auditability across multiple corpora.

## Required Evidence

For each benchmark run, keep:

- corpus description and file counts;
- supported/unsupported source counts;
- task prompts;
- final agent answers;
- cited source and mirror paths;
- reviewer corrections;
- timing and token/tool-call notes where available;
- lint and sync status output;
- no-data confirmation that no private corpus evidence is committed to this repository.

## Result Pack

Task packs define what to run. Result packs summarize what happened after an agent or operator runs
those tasks in each comparison mode. Keep result packs in the private pilot vault or an anonymized
review packet; do not commit confidential answers, client names, source text, mirror text, or
reviewer notes to this public repository.

The public Vaultwright repository ignores and rejects committed `_meta/agent-readiness-results.yml`
files by default. Store them in private pilot workspaces, then copy only aggregate numbers into a
review packet after no-data review.

Default local path:

```text
_meta/agent-readiness-results.yml
```

Minimal schema:

```yaml
schema_version: 1
corpus: government-services-vault
results:
  - task_id: answer-gst-readiness
    mode: vaultwright_markdown
    score: 2
    reviewer_corrections: 0
    elapsed_seconds: 95
    cited_source_paths:
      - 60_finance/tax/gst-hst-readiness.docx
    cited_generated_mirror_paths:
      - _mirrors/60_finance/tax/gst-hst-readiness.md
    privacy_or_provenance_violation: false
```

Rules enforced by the validator:

- `task_id` must exist in the task pack;
- `mode` must be one of `raw_source_folder`, `document_chat_transcript`, or
  `vaultwright_markdown`;
- `score` must be `0`, `1`, or `2`;
- reviewer corrections must be a non-negative integer;
- elapsed seconds, when present, must be finite and non-negative;
- citation paths must be relative vault paths;
- cited paths must exist in the current vault copy;
- cited paths must be declared on the referenced task;
- source citations must not point into `_mirrors/`;
- generated mirror citations must point into `_mirrors/`;
- unsupported top-level or per-result fields are rejected so answer text and reviewer notes are not
  stored in result packs;
- `--require-results` fails unless every task has a score for every comparison mode.

Validate and summarize results with:

```bash
python3.11 tools/vaultwright.py benchmark --results _meta/agent-readiness-results.yml
python3.11 tools/vaultwright.py benchmark --results _meta/agent-readiness-results.yml --require-results
python3.11 tools/vaultwright.py benchmark --results _meta/agent-readiness-results.yml --json
```

The human-readable report prints aggregate per-mode scores, correction counts, and privacy/
provenance violation counts. It does not print answer text, reviewer notes, source text, mirror
text, or document bodies.

## Example Task Pack

The public government-services demo includes a starter task pack at
`examples/government-services-vault/_meta/agent-readiness-tasks.yml`. It is not a completed
benchmark result; it is a source-linked prompt set for exercising the protocol against synthetic
business-registration, GST/HST, funding/support, update, audit, and consolidation tasks.

The task pack deliberately references both committed source files and generated mirror paths. The
mirror paths should exist only after running sync in a temporary or local working copy, not in the
committed example tree.

Validate a configured task pack with:

```bash
python3.11 tools/vaultwright.py benchmark
python3.11 tools/vaultwright.py benchmark --require-generated  # after sync
```

No public result pack is committed for the example. Completing one requires running the comparison
protocol and reviewing the answers.

## Guardrails

- Never benchmark with confidential client data inside this public repo.
- Keep one client or engagement per vault.
- Treat generated markdown as a working layer, not final authority.
- Require citations to source-backed notes or original source paths.
- Do not let an agent delete, move, or consolidate records without explicit review.

## Current Status

No external benchmark has been completed yet. The government-services and Northwind examples are
useful for smoke tests and demo tasks, but they are not proof that Vaultwright improves real agent
performance on client-shaped corpora.
