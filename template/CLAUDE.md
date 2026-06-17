# CLAUDE.md — Knowledge Base Schema

This is the **schema layer** of a Vaultwright knowledge base: the operating manual that turns an
LLM agent into a disciplined wiki maintainer rather than a generic chatbot. Read this first in any
session that touches these documents. It is for both humans and the agent. (Agents that look for
`AGENTS.md` are pointed here.)

> Pattern: Karpathy's "LLM wiki" — the LLM incrementally **builds and maintains** a persistent,
> interlinked markdown wiki that sits between you and the raw sources, instead of re-deriving
> knowledge on every query. *Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase.*

---

## 1. The three layers

| Layer | What it is | Who owns it | Mutability |
| --- | --- | --- | --- |
| **Raw sources** | the real artifacts: contracts, signed PDFs, decks, statements, repos, the originating `.docx/.pptx/.xlsx` | human / external | the agent **reads but never alters** them — source of truth |
| **Wiki** | markdown notes that summarize, connect, add metadata: MOCs, entity pages, knowledge notes, and the auto-generated **mirrors** of binaries/repos | agent writes; human curates | freely regenerated and cross-linked |
| **Schema** | this file — conventions + workflows | human + agent co-evolve | edit deliberately |

**Core principle: markdown is the connective tissue; binaries are leaves.** Every binary or repo
that matters gets a markdown companion so it becomes linkable, taggable, searchable, and visible in
the graph — without converting or replacing the original.

---

## 2. Folder map

```
finance/      receipts, invoices, statements, ledger, tax, payroll
legal/        contracts, NDAs, policies, incorporation, playbook
clients/      per-client folders (discovery, proposals, deliverables, comms)
projects/     internal & joint projects + GitHub repo mirrors (see §6)
marketing/    brand, content, social, campaigns
funding/      grants, programs, supporting evidence
hr/           contractor & employee agreements, policies
operations/   runbooks, reports, vendor records
company/      business plan, owner bio, company-wide records
_templates/   Obsidian note templates (§7)
_meta/        conventions reference
tools/        the mirror & lint scripts
_archive/     retired-but-retained (see RETENTION.md)
_tmp/         scratch; anything >30 days is prunable
```

Adapt these to your business. Folders organize *where* a file lives; **links** capture *how things
relate.*

---

## 3. Frontmatter — the metadata contract

Every markdown note carries YAML frontmatter. This is the highest-leverage convention: it powers
Obsidian **Properties** and **Bases** so the index (`Documents.base`) is generated dynamically and
never drifts.

**Required on every note:**

```yaml
---
title: Human-readable title
type: note            # vocabulary below
status: active        # vocabulary below
domain: clients       # top-level folder this belongs to
created: 2026-01-01
updated: 2026-01-01
---
```

**Recommended:** `owner`, `tags` (themes, nested with `/`), `related` (wikilinks), and entity
links like `client: "[[Acme Corp]]"`, `vendor: "[[Some Vendor]]"`, `program: "[[Some Program]]"`.

**`type`:** `moc` (hub) · `entity` (a noun — client, person, vendor, program, product) · `note` ·
`guide` (how-to/runbook) · `policy` · `record` (dated report/meeting/decision) · `source-mirror`
(auto mirror of a binary — never hand-edit the body) · `source-ref` (companion for a non-mirrored
binary, e.g. a PDF) · `repo-mirror` (auto mirror of a GitHub repo — never hand-edit the body).

**`status`:** `draft` · `active` · `in-review` · `sent` · `signed` · `submitted` · `awarded` ·
`superseded` · `archived`.

---

## 4. Linking — defeat the silos

1. **Wikilink generously.** An unresolved `[[link]]` is a to-do, not an error.
2. **Maps of Content (MOCs).** Each cluster gets a hub note (`type: moc`) linking its members with
   one-line context; hubs link up to `INDEX.md` and across to related hubs.
3. **Entity pages.** Recurring nouns (each client, vendor, program, person, product) get a page;
   everything about them links to it, so the graph clusters naturally.
4. **`related:`** frontmatter for structural links that don't appear in prose.

Test: ≤3 clicks from `INDEX.md` to anything; no orphan notes.

---

## 5. Anti-proliferation — fewer, better, current notes

> **When everything is documented, nothing is.** A KB dies from *too many* notes faster than too few.

This is a first-class rule, not a preference:

1. **Consolidate before you create.** Before writing a new note, search for an existing one to
   extend. One canonical note per concept.
2. **Incremental update > new file.** New info usually edits an existing note (bump `updated:`),
   not spawns a sibling.
3. **Archive, don't accrete.** Superseded material moves to `_archive/` per `RETENTION.md`.
4. **Human-gated promotion.** Agent-drafted notes start `status: draft`; a human promotes to
   `active`. Don't let the vault fill with unverified notes.
5. **The linter helps.** `tools/lint_vault.py` flags orphans, stale mirrors, and duplicate/overlap
   candidates to merge.

---

## 6. Office, binary & repo files — the mirror pattern

Originals stay the editable source of truth; scripts generate markdown **mirrors** that refresh
when the original changes.

- **Office** (`.docx/.pptx/.xlsx`): `tools/sync_office_md.py` (Microsoft markitdown) writes a sibling
  `<name>.md` (`type: source-mirror`) with managed frontmatter (hash, timestamps), a curated
  **`## Notes`** region (preserved), and an auto extraction below the sentinel
  `%% AUTO-GENERATED BELOW — DO NOT EDIT %%`.
- **GitHub repos**: `tools/sync_github_repos.py` (config `tools/repos.yml`) writes `projects/<name>.md`
  (`type: repo-mirror`) with the README, `/docs`, top-level markdown, and metadata — refreshed when
  the repo's HEAD changes.
- **PDFs** embed natively in Obsidian (`![[file.pdf#page=2]]`); use a light `source-ref` companion
  when useful.
- **Rules:** edit the original, never a mirror's auto region. Curate only above the sentinel.
  Mirror generation is idempotent (hash/HEAD-based). Sync auth is **read-only and never stored in
  the vault** (§9).

---

## 7. Templates

`_templates/` holds note skeletons for Obsidian's Templates core plugin: `base-note` ·
`client-hub` (moc) · `entity` · `guide` · `decision-record` · `daily-log` · `source-ref`. Each
ships correct frontmatter so new notes are born compliant.

---

## 8. Workflows (the agent's loop)

**Ingest** — a new document arrives: file the original (§2); if binary/repo, run the mirror sync;
**check for an existing note to extend before creating one** (§5); add frontmatter + a short
summary; wikilink it from its MOC and entity pages; append one line to `log.md`.

**Query** — read `INDEX.md` / the relevant MOC first, follow links, answer with **citations to note
paths**; file reusable answers back as notes so work compounds.

**Lint** — periodically check missing/invalid frontmatter, broken wikilinks, orphans, stale mirrors,
duplicate/overlapping notes, status drift; fix mechanically where safe, flag judgment calls.

**Log** — `log.md` is append-only and greppable: `## [YYYY-MM-DD] <op> | <what>`.

---

## 9. Guardrails

- **No deletes or renames without explicit human approval.** Agents may create, draft, file, link,
  and add metadata freely — but prefer consolidation (§5).
- **Never hand-edit a `source-mirror`/`repo-mirror` body** below the sentinel.
- **Secrets never live in the vault** (OS keychain / env only).
- **PII** stays in designated private areas; never in shared/marketing trees.
- Follow **`RETENTION.md`** for archival windows and the `_archive/` process.
- The index is generated from frontmatter (Bases) — keep frontmatter correct.

---

*This schema co-evolves. When a convention stops serving the work, change it here first, then
propagate.*
