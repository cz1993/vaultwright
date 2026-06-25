# Product Contract

## Product Direction

Vaultwright turns heterogeneous source collections into governed, profile-driven knowledge
workspaces that humans and AI agents can inspect, navigate, cite, and refresh without replacing the
original records. The canonical v1 direction now adds journaled changed-file materialization:
after an initial baseline, normal steady-state refresh should process event-identified candidate
sources, while full sync remains the recovery and verification path.

The first paid workflow remains consulting and implementation work, but the v1 architecture is no
longer a single business-operations folder template. The accepted v1 direction is documented in
[`docs/adr/0001-profile-driven-v1-architecture.md`](adr/0001-profile-driven-v1-architecture.md)
and the release gates are tracked in [`docs/V1_FINISH_LINE.md`](V1_FINISH_LINE.md).

## First Buyer

Vaultwright's first buyer is a small consulting, advisory, or implementation team that handles
document-heavy client onboarding, operational audits, funding-readiness work, compliance reviews,
or recurring operating-system cleanup.

The first buyer is not "all small businesses." Owner-operators may benefit later, but consulting
teams are the better wedge because they already understand engagement boundaries, provenance,
source preservation, repeatable delivery, and client trust.

## First Workflow

The first workflow is:

1. Point Vaultwright at an existing client document collection.
2. Produce a non-destructive inventory and sync plan.
3. Generate mirrors for supported files without modifying originals.
4. Run a read-only conversion spot-check report for unsupported, stale, conflicted, risky, or
   potentially low-quality conversions.
5. Generate Markdown/HTML catalog gateways for operator, reviewer, and agent orientation.
6. If the customer uses Microsoft 365, run a read-only Microsoft 365/Copilot handoff readiness
   report before moving derived content into approved tenant boundaries.
7. Record metadata-only human review decisions against generated mirrors, catalogs, and handoff
   reports so approvals are tied to artifact hashes.
8. Create a small number of curated hubs and entity pages.
9. Refresh the workspace over time with auditable sync/status output.
10. After Stage 1B, use journaled changed-file materialization for normal steady-state refresh and
    full sync for recovery, reconciliation, and verification.

## Supported Corpus Range

Initial target corpus:

- 50 to 2,000 source files.
- Office files, PDFs, markdown, plain text, spreadsheets, decks, and small repositories.
- Single-client or single-engagement workspace.
- Local filesystem source; cloud-synced folders are acceptable only when files are pinned locally.

Out of scope for the first release:

- Multi-tenant hosted storage.
- Enterprise DMS replacement.
- Unbounded network crawls.
- Bulk email/mailbox ingestion.
- Fully automated legal, tax, accounting, or compliance conclusions.

## Expected Outcome

A successful first workflow produces:

- original files unchanged;
- full sync available as baseline and recovery mode;
- future journaled changed-file materialization state kept local and derived, never authoritative;
- generated mirrors under `_mirrors/`;
- repo mirrors under the active profile's `repo_notes_dir` (`80_sources/repos/` in the packaged
  business-operations profile);
- generated `CATALOG.md` and `CATALOG.html` inventory gateways;
- source/repo manifests, audit events, and lifecycle status reports;
- a Microsoft 365 handoff readiness report when the target workflow involves SharePoint, OneDrive,
  Copilot Studio, Dataverse, or Copilot connectors;
- a review ledger that records reviewer/status decisions without copying source or mirror bodies;
- aggregate pilot evidence reports that avoid source or mirror content;
- curated hubs for the highest-value document clusters;
- an agent-readable markdown substrate with source links, frontmatter, headings, manifests, and
  refresh boundaries;
- explicit warnings for unsupported or risky inputs;
- a repeatable refresh procedure.

## Non-Goals

- Not a generic personal PKM or Zettelkasten app.
- Not a hosted SaaS in this open-core repository.
- Not a vector-RAG chatbot over documents.
- Not a filesystem watcher that treats events as authoritative truth.
- Not a public profile marketplace for v1.
- Not an Obsidian plugin for v1.
- Not a desktop application shell for v1.
- Not a guarantee that conversion output fully represents every table, image, formula, scan, or
  comment.
- Not an autonomous agent that silently rewrites human-maintained business knowledge.
- Not a verifier of Microsoft 365 tenant permissions, sensitivity labels, retention, or Copilot
  indexing behavior.

## Role of Obsidian

Obsidian is the reference human interface because it provides local markdown browsing, links,
properties, graph views, and Bases. Vaultwright correctness must not depend on Obsidian sync,
community plugins, or a specific team-deployment model.

## Role of AI

AI may assist with:

- reading generated markdown mirrors as the first operational substrate;
- summarizing generated mirrors;
- proposing curated notes;
- suggesting links and consolidation;
- drafting review checklists;
- answering questions with citations to source-backed notes.

AI must not silently:

- modify original source files;
- delete, move, or consolidate records;
- overwrite human-curated notes;
- make uncited factual claims in durable notes;
- cross client boundaries.

## Agent-Readiness Validation

Vaultwright's long-term value depends on whether agents perform better against governed markdown
than against raw folders or one-off document-chat transcripts. The benchmark protocol in
`docs/AGENT_READINESS_BENCHMARK.md` defines the evidence needed before this claim is treated as
more than a thesis.
