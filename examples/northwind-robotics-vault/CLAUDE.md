# CLAUDE.md — Knowledge Base Schema

This is the **schema layer** of a Vaultwright knowledge base: the operating manual that turns an
LLM agent into a disciplined wiki maintainer rather than a generic chatbot. Read this first in any
session that touches these documents. It is for both humans and the agent. (Agents that look for
`AGENTS.md` are pointed here.)

> Pattern: Karpathy's "LLM wiki" — the LLM incrementally **builds and maintains** a persistent,
> interlinked markdown wiki that sits between you and the raw sources, instead of re-deriving
> knowledge on every query. *Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase.*

---

## 1. The four layers

| Layer | What it is | Who owns it | Mutability |
| --- | --- | --- | --- |
| **Raw sources** | the real artifacts: contracts, signed PDFs, decks, statements, repos, the originating `.docx/.pptx/.xlsx` | human / external | the agent **reads but never alters** them — source of truth |
| **Generated mirrors** | markdown mirrors of Office sources and optional PDF text mirrors under `_mirrors/`, plus repo mirrors under `80_sources/repos/` | agent writes; human annotations live in curated notes or `_meta/mirror-annotations/` sidecars | regenerated from source |
| **Wiki** | markdown notes that summarize, connect, and add metadata: MOCs, entity pages, decisions, guides, and indexes | agent writes; human curates | freely edited and cross-linked |
| **Schema** | this file — conventions + workflows | human + agent co-evolve | edit deliberately |

**Core principle: markdown is the connective tissue; binaries are leaves.** Every binary or repo
that matters gets a markdown companion so it becomes linkable, taggable, searchable, and visible in
the graph — without converting or replacing the original.

---

## 2. Function-based file plan

```
00_inbox/       unprocessed files, imports, triage notes
10_governance/  company identity, ownership, legal, policy, compliance, risk
20_market/      market research, positioning, brand, campaigns, partnerships
30_customers/   accounts/clients, sales, discovery, proposals, support records
40_delivery/    products/services, projects, implementations, delivery playbooks
50_operations/  internal process, vendors, procurement, IT, security, facilities
60_finance/     accounting, tax, payroll, budgets, funding, banking, reporting
70_people/      hiring, employees, contractors, onboarding, training
80_sources/     repo mirrors, public datasets, source inventories
_mirrors/     generated Office markdown mirrors and optional PDF text mirrors, preserving canonical source paths
_templates/   Obsidian note templates (§7)
_meta/        conventions reference, mirror config, manifests, and sync audit log
tools/        the mirror & lint scripts
_archive/     retired-but-retained (see RETENTION.md)
_tmp/         scratch; anything >30 days is prunable
```

This is a **starter file plan**, not a universal org chart. It follows a records-management
principle: classify by the business function the record supports, then use links and metadata for
cross-functional views. Adapt subfolders and `domain-map.yml` to the industry before scaling.

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
domain: customers     # functional domain from _meta/domain-map.yml
created: 2026-01-01
updated: 2026-01-01
---
```

**Recommended:** `owner`, `tags` (themes, nested with `/`), `related` (wikilinks), and entity
links like `account: "[[Acme Corp]]"`, `vendor: "[[Some Vendor]]"`, `program: "[[Some Program]]"`.

**`domain`:** `intake` · `governance` · `market` · `customers` · `delivery` · `operations` ·
`finance` · `people` · `sources`. See `_meta/domain-map.yml` for folder mapping and aliases.

**`type`:** `moc` (hub) · `entity` (a noun — account, person, vendor, program, product) · `note` ·
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
3. **Entity pages.** Recurring nouns (each account, vendor, program, person, product) get a page;
   everything about them links to it, so the graph clusters naturally.
4. **`related:`** frontmatter for structural links that don't appear in prose.

Test: ≤3 clicks from `INDEX.md` to curated knowledge; no orphan curated notes. Generated mirrors
may be leaf artifacts when manifests and source paths preserve provenance.

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
5. **The linter helps.** `tools/lint_vault.py` flags orphans, Office and configured repo mirror
   gaps, stale generated mirrors, and likely duplicate/overlap candidates for human review.

---

## 6. Office, binary & repo files — the mirror pattern

Originals stay the editable source of truth; scripts generate markdown **mirrors** that refresh
when the original changes.

- **Office** (`.docx/.pptx/.xlsx`): `tools/sync_office_md.py` (Microsoft markitdown) writes
  dedicated mirrors under `_mirrors/<canonical-source-path>.md` (`type: source-mirror`) with
  managed frontmatter (hash, timestamps), a machine-owned prelude, and an auto extraction below the
  sentinel `%% AUTO-GENERATED BELOW — DO NOT EDIT %%`. This keeps raw source folders clean while
  making converted content searchable. Run `sync_office_md.py --plan` before writing when reviewing
  a new corpus, and `sync_office_md.py --status` to inspect the `_meta/source-manifest.json`
  lifecycle state.
- **GitHub repos**: `tools/sync_github_repos.py` (config `tools/repos.yml`) writes repo mirrors
  under `80_sources/repos/` by default
  (`type: repo-mirror`) with the README, `/docs`, top-level markdown, and metadata — refreshed when
  the repo's HEAD changes. Repo lifecycle state lives in `_meta/repo-manifest.json`, and lint
  blocks configured repo entries whose expected generated mirror note is missing, unmanaged, or
  duplicated by another configured repo target.
- **PDFs** embed natively in Obsidian (`![[file.pdf#page=2]]`); use a light `source-ref` companion
  when useful, run `sync_office_md.py --include-pdf` for a one-off text mirror, or set
  `office_mirrors.include_pdf: true` in `_meta/mirror-config.yml` for unattended PDF mirror refresh.
- **Rules:** edit the original, never a generated mirror body. Keep durable human notes in regular
  curated notes. If a legacy mirror already contains above-sentinel annotations, run
  `vaultwright migrate annotations --write` before sync refreshes it. Mirror generation is
  idempotent (hash/HEAD-based). The Office and repo manifests record stable IDs, hashes, mirror
  paths, lifecycle state, and warnings. Sync events append to `_meta/sync-audit.jsonl`. Sync auth
  is **read-only and never stored in the vault** (§9).

---

## 7. Templates

`_templates/` holds note skeletons for Obsidian's Templates core plugin: `base-note` ·
`account-hub` (moc) · `entity` · `guide` · `decision-record` · `daily-log` · `source-ref`. Each
ships correct frontmatter so new notes are born compliant.

---

## 8. Workflows (the agent's loop)

**Ingest** — a new document arrives: file the original (§2); if binary/repo, run the mirror sync;
**check for an existing note to extend before creating one** (§5); add frontmatter + a short
summary; wikilink the mirror or source-ref from its MOC and entity pages; append one line to
`log.md`.

**Query** — read `INDEX.md` / the relevant MOC first, follow links, answer with **citations to note
paths**; file reusable answers back as notes so work compounds.

**Lint** — periodically check missing/invalid frontmatter, broken wikilinks, orphans, overlap
candidates, mirror gaps, stale generated mirrors, and status vocabulary; fix mechanically where
safe, flag judgment calls.

**Log** — `log.md` is append-only and greppable: `## [YYYY-MM-DD] <op> | <what>`.

---

## 9. Guardrails

- **No deletes or renames without explicit human approval.** Agents may create, draft, file, link,
  and add metadata freely — but prefer consolidation (§5).
- **Never hand-edit a `source-mirror`/`repo-mirror` body.** Use curated notes or annotation
  sidecars for durable human context.
- **Secrets never live in the vault** (OS keychain / env only).
- **PII** stays in designated private areas; never in market/public-facing trees.
- Follow **`RETENTION.md`** for archival windows and the `_archive/` process.
- The index is generated from frontmatter (Bases) — keep frontmatter correct.

---

*This schema co-evolves. When a convention stops serving the work, change it here first, then
propagate.*
