# Methodology

Vaultwright is mostly *discipline*, encoded so an agent follows it. This is the why behind the
schema in `template/CLAUDE.md`.

## 1. Three layers

- **Raw sources** — the real artifacts (contracts, decks, statements, receipts, repos, the
  originating Office files). Immutable: the agent reads them, never rewrites them. Source of truth.
- **Wiki** — markdown notes that summarize, connect, and add metadata: Maps of Content (MOCs),
  entity pages, knowledge notes, and the auto-generated **mirrors** of binaries/repos. The agent
  writes this; you curate.
- **Schema** — `CLAUDE.md`: the conventions and the ingest/query/lint workflows. It's what makes
  the agent a disciplined maintainer instead of a generic chatbot. You and the agent co-evolve it.

## 2. Markdown is the connective tissue; binaries are leaves

You don't convert or replace your real files. Every binary that matters gets a markdown
**companion/mirror** so it becomes linkable, taggable, searchable, and visible in the graph — while
the original stays the editable source of truth.

- **Office files** → `source-mirror` notes via markitdown, refreshed on content change.
- **GitHub repos** → `repo-mirror` notes (README + docs + metadata), refreshed when HEAD changes.
- **PDFs** → embed natively in Obsidian; a light `source-ref` companion when useful.
- Each mirror has a **curated region** (preserved across syncs) and an **auto region** below a
  sentinel line (regenerated). Edit the original, never the auto region.

This is Vaultwright's core technical idea and its main differentiator — see `positioning.md`.

## 3. Linking-first (the retrieval engine)

Folders say *where* a file lives; **links say how things relate** — and links are what make
retrieval work without a vector database at small scale.

- **Wikilink generously.** An unresolved `[[link]]` is a to-do, not an error — it marks a page
  worth creating.
- **Maps of Content (MOCs).** Every cluster gets a hub note that links its members with one-line
  context. Hubs link up to `INDEX.md` and across to related hubs.
- **Entity pages.** Recurring nouns (each client, vendor, program, person, product) get a page;
  everything about them links to it, so the graph clusters naturally.
- **The index maintains itself.** `Documents.base` reads note frontmatter (Obsidian Bases) and
  generates always-current tables, so a hand-maintained index can't drift.
- **Future: typed links.** Plain `[[links]]` can't say *why* two notes relate. A roadmap item is
  typed relations (`supports` / `contradicts` / `supersedes` / `depends-on`) so the graph carries
  meaning.

The test: ≤3 clicks from `INDEX.md` to anything, and no orphan notes.

## 4. Anti-proliferation — the discipline that makes it usable

> **When everything is documented, nothing is.** A knowledge base dies from *too many* notes faster
> than from too few.

So Vaultwright optimizes for *fewer, better-connected, current* notes:

1. **Consolidate before you create.** Before writing a new note, the agent searches for an existing
   one to extend. One canonical note per concept.
2. **Incremental update > new file.** New information usually edits an existing note (and bumps
   `updated:`), it doesn't spawn a sibling.
3. **Archive, don't accrete.** Superseded material moves to `_archive/` per `RETENTION.md`; the live
   set stays small.
4. **Human-gated promotion.** Agent-drafted notes start as `draft`; a human promotes them to
   `active`. (LLMs hallucinate; the vault must not silently fill with unverified notes.)
5. **The linter enforces it.** `lint_vault.py` flags orphans, stale mirrors, and — on the roadmap —
   near-duplicate/overlapping notes that should be merged.

Most agent-wiki projects happily spawn notes. Disciplined restraint is a deliberate edge.

## 5. The agent's operating loop

- **Ingest** — file the original; mirror it if binary/repo; create or *extend* a knowledge note;
  wikilink it from its MOC and entity pages; log one line.
- **Query** — read `INDEX.md` / the relevant MOC first, follow links, answer with citations to note
  paths; file reusable answers back as notes so work compounds.
- **Lint** — periodically check frontmatter, links, orphans, stale mirrors, duplicates; fix
  mechanically where safe, flag judgment calls.
- **Log** — append one greppable line per change to `log.md`.

## 6. Governance (because this is business data)

- **PII** stays in designated private areas, never in shared/marketing trees.
- **Secrets never live in the vault** — OS keychain / environment only.
- **Retention** windows and the archival process live in `RETENTION.md`.
- Auth for repo/Office sync is read-only and kept out of the vault.
