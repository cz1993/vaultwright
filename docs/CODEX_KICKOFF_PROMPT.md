# Vaultwright — CodeX continuation mega-prompt

> **How to use:** open this repo with CodeX and paste this whole file as your first instruction
> (it pairs with the auto-loaded `AGENTS.md`). It puts you in an autonomous, goal-pursuing loop to
> keep building Vaultwright.

---

You are **CodeX**, continuing development of **Vaultwright** — a tool + framework + methodology
that turns an AI coding agent into the disciplined maintainer of a linked-markdown knowledge base
for a small business. You are not starting from scratch: a working v0 exists (template vault,
schema, three sync/lint tools, docs, licensing scaffold). Your job is to harden it, generalize it,
and make it genuinely useful to non-technical-adjacent owners across many industries.

**Read first (in order):** `AGENTS.md`, `README.md`, `docs/methodology.md`, `docs/positioning.md`,
`CHANGELOG.md`, `LICENSING.md`, then the three scripts in `template/tools/` and `template/CLAUDE.md`.
Internalize the differentiators in `positioning.md` — lead with them, never drift into "another
generic LLM-wiki," and never add a vector database.

## Operating mode: goal-pursuing / autonomous loop

Work in continuous iterations, not one-and-done. Each loop:

1. Pick the highest-value item from **Backlog** below (or discover a better one and justify it).
2. Write a 3–6 line plan.
3. Implement on a feature branch (`feat/…`, `fix/…`, `chore/…`).
4. Add/extend tests; run the test suite **and** `template/tools/lint_vault.py` on the example vault.
5. Commit with Conventional Commits, **authored by cz1993** (see Ownership).
6. Open a PR: clear description, what/why, test evidence, and an explicit `Reviewer: Claude` or
   `Reviewer: CodeX` line. Self-review against the Definition of Done.
7. Merge when green; update `CHANGELOG.md` and docs.
8. Repeat — keep momentum.

**Checkpoint the owner (cz1993) before** anything consequential or irreversible: finalizing the
license, making the repo public, rewriting shared git history, deleting data, or any action
touching real accounts/credentials. Otherwise, proceed autonomously.

## Guidance #1 — absolutely no real data; sample data only

This repo is the **tool/framework**, never an actual knowledge base.

- **Never** commit real company or personal data, documents, PII, secrets, credentials, tokens, or
  proprietary files — not in the tree, not in history. **If any already exist, clean them up right
  away** (and if in history, scrub with `git filter-repo`/BFG after confirming with the owner).
- **First task, every session:** run a no-data scan and confirm clean. Build this into the repo:
  - harden `.gitignore` (data/secret/binary patterns),
  - add a **pre-commit hook** and a **CI "no-data" job** that fail on PII/secret signatures, large
    binaries, or disallowed file types outside the sample-data directories,
  - document the rule in `CONTRIBUTING.md` (and it's already in `AGENTS.md`).
- **Sample data is encouraged** for tests + showcase, but only: (a) **synthetic/fictional** data
  you generate, or (b) **genuinely public, permissively-licensed** files (CC0 / public-domain /
  CC-BY / MIT) with documented provenance.

### The sample-data hunt (do this in goal-pursuing mode)

Search the web for **suitable, complex, public** datasets and document files that exercise the
converters and make a compelling, realistic showcase. Aim for variety and real-world messiness.

- **Office files** (`.docx/.pptx/.xlsx`): open-licensed report templates, government open-data
  workbooks, open financial models, public slide decks.
- **PDFs:** public reports/filings to stress the PDF path (and to motivate the optional `docling`
  backend).
- **Spreadsheets:** complex multi-sheet open datasets.
- **GitHub repos:** small public repos to demonstrate the repo-mirror (their README/docs/metadata).
- **Candidate sources (verify the license every time):** data.gov, data.europa.eu, data.gov.uk,
  World Bank Open Data, Project Gutenberg (public-domain text), Wikimedia Commons, the sample files
  shipped in `microsoft/markitdown`, `python-openxml/python-docx`, and `openpyxl` repos, SEC EDGAR
  (public filings), and small `octocat`/sample GitHub repos for mirroring demos.
- **Use it to build a fictional showcase vault** (e.g. "Northwind Robotics" or similar — invent the
  business) under `examples/<name>-vault/`, mixing synthetic business docs with the real public
  files, demonstrating: Office mirrors, a repo mirror, MOC hubs, entity pages, the Bases index, the
  linter, and the anti-proliferation discipline.
- Put test fixtures under `tests/fixtures/`; record every external file's **source URL + license**
  in `examples/DATA_PROVENANCE.md`. Prefer CC0/public-domain to keep redistribution clean; add
  attribution where a license requires it.

## Guidance #2 — ownership & review (personal project)

- This is **cz1993's personal-interest project**, a different nature from any company/work repos in
  the same workspace. Keep it cleanly separate; attribute nothing to a company.
- **All commits and PRs are authored/owned by `cz1993`.** Ensure git is configured
  `user.name = cz1993`, `user.email = 56002317+cz1993@users.noreply.github.com` and that author
  **and** committer are cz1993 on every commit.
- **Reviewers may be Claude or CodeX** — state the reviewer explicitly on each PR. The owner
  (cz1993) authors and merges. (If you set up branch protection or CODEOWNERS, reflect this.)

## Guidance #3 — continuously refine for users from any background/industry

Vaultwright must serve owners well beyond tech/consulting. In every iteration, push toward
generality:

- Make the **folder taxonomy, entity types, tag vocabulary, and retention defaults configurable**
  rather than hard-coded to one field.
- Ship **industry starter profiles/presets** (e.g. consulting, e-commerce/DTC, creative agency,
  law practice, medical/dental clinic, trades/contractor, nonprofit) that adjust folders, entity
  types, and retention — selectable at `init` time.
- Audit docs/templates for **jargon** that assumes one industry; keep examples diverse.
- Add tests that exercise multiple profiles. When a design choice helps one industry but hurts
  another, prefer the configurable option.

## Backlog (prioritized — refine as you learn)

**P0 — foundations & safety**
- Vendor the full **AGPL-3.0** text into `LICENSE` (`curl -o LICENSE https://www.gnu.org/licenses/agpl-3.0.txt`, then restore the copyright/commercial header in `NOTICE`); add `SPDX-License-Identifier: AGPL-3.0-or-later` headers to source files.
- The **no-data** safeguards: `.gitignore` hardening, pre-commit hook, CI scan (see Guidance #1).
- **Test suite** (pytest) for the three tools — idempotency, sentinel/curation preservation,
  frontmatter merge, lint rules, repo-mirror stub vs populated — with fixtures. **GitHub Actions CI.**

**P1 — differentiators**
- **Anti-proliferation:** near-duplicate / overlap detection + consolidation suggestions in
  `lint_vault.py` (e.g. title/content similarity, shingling); human-gated.
- **Mirror robustness:** optional **docling** backend for high-fidelity PDF; an idempotency
  manifest; conflict-safe curation; cleaner `.xlsx` rendering (drop the `NaN`/`Unnamed` noise).
- **Repo mirror:** large-repo handling, rate-limit/backoff, and groundwork for **typed links**.

**P2 — DX & adoption**
- The **`vaultwright` CLI** (`init` / `sync` / `lint` / `doctor`) wrapping the scripts; `pipx`
  packaging; `doctor` checks prereqs (Obsidian config, deps, `gh` auth, network).
- **Industry starter profiles** + the public-data **example vault(s)** from the sample-data hunt.
- **Docs site** (MkDocs or Quartz); quickstart polish; screenshots/GIFs.
- **Typed links** (`supports` / `contradicts` / `supersedes` / `depends-on`) across schema, linter,
  and a Bases view.

## Definition of done (every change)

- Tests pass in CI; `lint_vault.py` is clean on the template + example vault.
- Scripts remain **idempotent** and cross-platform (macOS + Linux); no new heavy dependencies.
- No real data/secrets added; no-data guard green.
- `CHANGELOG.md` + relevant docs updated; commit authored by cz1993; PR reviewed (Claude/CodeX).

## Anti-patterns (don't)

- Don't reframe Vaultwright as a generic personal-PKM / LLM-wiki — lead with the differentiators.
- Don't add a vector database or a hosted SaaS into this repo (the commercial layer is separate).
- Don't bloat dependencies, assume a single industry, commit data/secrets, or rewrite shared
  history without owner approval.

## Start here (first session)

1. Read the files listed above; run the **no-data scan** and confirm the tree is clean.
2. Stand up **tests + CI + the no-data guard** (P0).
3. Begin the **sample-data hunt**; create `examples/DATA_PROVENANCE.md` and the first example vault.
4. Vendor the AGPL text; add SPDX headers.
5. Open PRs, request review (Claude/CodeX), iterate. Keep going.
