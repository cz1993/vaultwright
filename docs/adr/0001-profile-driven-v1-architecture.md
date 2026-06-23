# ADR 0001: Profile-Driven V1 Architecture

**Status:** Accepted
**Date:** 2026-06-23
**Decision source:** `docs/VAULTWRIGHT_WHITEPAPER_2026-06-23.md`
**Owner:** cz1993

## Context

Vaultwright started as a business-operations vault template with copied vault-local tools. The
current repository now has manifests, lifecycle contracts, sync audit events, conversion review,
recovery, migration, overlap calibration, review ledger, benchmark scaffolds, catalogs, Microsoft
365 handoff guidance, package tests, CI, and no-data safeguards.

That progress creates a risk: adding profiles, Obsidian skills, indexing, Explorer UI, and more
reports as separate tracks would increase tool sprawl and make v1 harder to finish. The product
needs a stable architecture gate before more feature work.

## Decision

Vaultwright v1 will converge on this product statement:

> Vaultwright turns heterogeneous source collections into governed, profile-driven knowledge
> workspaces that humans and AI agents can inspect, navigate, cite, and refresh without replacing
> the original records.

The shorter product line is:

> Compile source collections into governed knowledge workspaces.

The target architecture has six layers:

| Layer | Responsibility | Authority |
| --- | --- | --- |
| Sources | Original files, repositories, exports, and external records | Authoritative |
| Mirrors | Machine-generated Markdown and extraction metadata | Derived |
| Curated knowledge | Human-reviewed notes, syntheses, entities, and decisions | Human-governed |
| Profile | Domain vocabulary, schemas, templates, views, skills, and benchmarks | Versioned contract |
| Evidence index | Full-text and graph index for retrieval and context assembly | Disposable derived cache |
| Presentation | Obsidian, catalogs, Canvas, Explorer, MCP, and exported context packs | Derived interfaces |

Vaultwright v1 will support exactly three maintained content profiles plus a minimal blank starter:

- `business-operations` - the current consulting and implementation wedge.
- `research-learning` - source-backed reading, literature, concept, question, synthesis, course,
  and project work.
- `software-project` - repositories, architecture, ADRs, runbooks, APIs, releases, incidents, and
  engineering documentation.
- `blank` - minimal advanced-user starter with inbox, sources, mirrors, metadata, templates, and
  views.

The core must become profile-driven. Business-specific folders, note types, required fields,
statuses, and views belong in a profile contract, not hard-coded in core behavior.

Runtime code should converge into the installed `src/vaultwright/` package. Vault-local tools may
remain compatibility shims during the migration, but vaults should not permanently contain an
independent application copy.

Generated mirrors should become fully machine-owned for v1. Existing above-sentinel human notes
must be preserved by migration into curated notes or source-ID-keyed sidecars before mirrors become
disposable generated artifacts.

New feature work must map to the finish-line matrix in `docs/V1_FINISH_LINE.md`. Standalone report
commands are frozen unless they replace an existing command, close a listed v1 requirement, or are
explicitly recorded as a migration shim. New non-gating ideas move to the post-v1 backlog.

## V1 Non-Goals

These are not v1 requirements:

- hosted SaaS;
- multi-user real-time collaboration;
- enterprise administration console;
- Obsidian plugin;
- public profile marketplace;
- mobile application;
- automatic OCR and high-fidelity layout extraction for every format;
- vector embeddings by default;
- autonomous note deletion or consolidation;
- email and mailbox ingestion;
- broad connector catalog;
- desktop application shell;
- automatic enterprise permission or retention enforcement.

## Consequences

- Stage 0 is complete only when this ADR, the v1 non-goals, and the finish-line matrix are tracked.
- Stage 1 must prioritize kernel/package convergence and profile schemas before new UI or index
  work.
- Stage 2 must introduce official profiles from a shared core package, not copied template forks.
- Stage 4 is a binding gate. If the evidence index improves measured task outcomes, v1 includes
  Explorer work. If it does not, v1 Core ships without the index and Explorer as release blockers.
- Any new command, schema, example, skill, or UI artifact must cite the finish-line requirement it
  advances.
