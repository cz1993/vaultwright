# Product Contract

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
5. Create a small number of curated hubs and entity pages.
6. Refresh the workspace over time with auditable sync/status output.

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
- generated mirrors under `_mirrors/`;
- repo mirrors under `80_sources/repos/`;
- source/repo manifests, audit events, and lifecycle status reports;
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
- Not a guarantee that conversion output fully represents every table, image, formula, scan, or
  comment.
- Not an autonomous agent that silently rewrites human-maintained business knowledge.

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
