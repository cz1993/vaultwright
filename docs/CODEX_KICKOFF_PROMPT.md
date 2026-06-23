# Vaultwright — CodeX continuation mega-prompt

> **How to use:** open this repo with CodeX and paste this whole file as your first instruction
> (it pairs with the auto-loaded `AGENTS.md`). It puts you in an autonomous, goal-pursuing loop to
> keep building Vaultwright.

---

You are **CodeX**, continuing development of **Vaultwright** — a technical-alpha document
governance tool for turning existing business document collections into governed, inspectable
knowledge workspaces without modifying original records. You are not starting from scratch: a
working v0 exists (template vault, schema, sync/lint tools, docs, licensing scaffold). Your job is
to narrow, harden, and validate the first promise before broadening the roadmap.

**Read first (in order):** `AGENTS.md`, `README.md`, `docs/PRODUCT.md`,
`docs/VAULTWRIGHT_WHITEPAPER_2026-06-23.md`,
`docs/adr/0001-profile-driven-v1-architecture.md`, `docs/V1_FINISH_LINE.md`,
`docs/SYNC_SPEC.md`, `docs/SECURITY_MODEL.md`, `docs/VAULTWRIGHT_WHITEPAPER.md`,
`docs/methodology.md`, `docs/positioning.md`, `CHANGELOG.md`, `LICENSING.md`, then the scripts in
`template/tools/` and `template/CLAUDE.md`.
Internalize the differentiators in `positioning.md` — lead with them, never drift into "another
generic LLM-wiki," and do not add a vector database as a substitute for provenance, mirrors, and
managed lifecycle state.

## Operating mode: goal-pursuing / autonomous loop

Work in continuous iterations, not one-and-done. Each loop:

1. Pick the highest-value item from **Backlog** below (or discover a better one and justify it).
2. Write a 3–6 line plan.
3. Implement on a feature branch (`feat/…`, `fix/…`, `chore/…`).
4. Add/extend tests; run the test suite, `PYTHONPATH=src python3.11 template/tools/lint_vault.py`
   or installed `vaultwright lint`, and example-vault regeneration/lint in a temporary copy.
5. Commit with Conventional Commits, **authored by cz1993** (see Ownership).
6. Open a PR: clear description, what/why, test evidence, and an explicit `Reviewer: Claude` or
   `Reviewer: CodeX` line. Self-review against the Definition of Done.
7. Merge when green; update `CHANGELOG.md` and docs.
8. Repeat — keep momentum.

**Checkpoint the owner (cz1993) before** anything consequential or irreversible: finalizing the
license, making the repo public, rewriting shared git history, deleting data, or any action
touching real accounts/credentials. Otherwise, proceed autonomously.

## Current v1 architecture checkpoint - 2026-06-23

The active product direction is now the profile-driven v1 architecture in
`docs/VAULTWRIGHT_WHITEPAPER_2026-06-23.md`. Treat
`docs/adr/0001-profile-driven-v1-architecture.md` and `docs/V1_FINISH_LINE.md` as the convergence
gate before choosing work.

The execution rule is simple: do not add standalone feature tracks. Every change must advance a
listed finish-line requirement, replace a weaker implementation, or preserve existing behavior
while preparing a required migration. New ideas that do not map to the matrix go to the post-v1
backlog.

**Stage 0 requirements**
- Product statement, six-layer architecture, v1 profiles, v1 non-goals, and command-surface stop
  rule are tracked in docs.
- Every open v1 work item maps to a finish-line requirement.
- New standalone report commands are frozen unless they replace existing behavior or close a
  matrix item.

**Next execution order**
1. Keep safety gates green: no-data scan, template-copy sync, pytest, example lint, CI.
2. Start Stage 1 by moving runtime behavior from copied vault-local scripts into package-owned
   modules under `src/vaultwright/`, leaving compatibility shims only where needed.
3. Define the versioned profile contract before adding research/software profiles.
4. Convert hard-coded business taxonomy assumptions into `business-operations` profile data.
5. Preserve current lifecycle, catalog, review, recovery, safety, and benchmark behavior while
   refactoring.

## Historical review checkpoint - 2026-06-17

Professional review found a strong product thesis, but the repo is still pre-release. Treat this
section as historical context; do not let it override the 2026-06-23 v1 finish-line matrix.

**Strengths to preserve**
- The core positioning is clear: mirror layer, governance, anti-proliferation, and linking-first
  retrieval.
- `scripts/init.sh` can create a fresh vault, and the generated template vault lints cleanly.
- The implementation is still small enough to harden without architectural churn.

**Release blockers to fix before feature work**
- `template/tools/sync_all.sh` must fail reliably when a required sync fails; cron/launchd cannot
  receive a false success.
- A fresh vault without `tools/repos.yml` must skip GitHub repo sync cleanly, while an explicitly
  supplied missing config should fail.
- `template/tools/repos.example.yml` must not contain an active placeholder repo that resolves to a
  real third-party GitHub repository.
- The no-data guard must exist as code and be used by CI and a pre-commit hook.
- Add a focused pytest suite and GitHub Actions CI for the core scripts.
- Align docs with implemented behavior: do not claim duplicate/overlap linting until it exists.
- Continue license readiness: the full AGPL text is vendored, project-specific notices live in
  `NOTICE`, and source headers use SPDX; CLA vs DCO, trademark clearance, and commercial terms still
  require owner/counsel decisions before outside contributions or enterprise licensing.

**Priority execution plan**
1. Create a P0 feature branch and configure local git identity as `cz1993`.
2. Run a no-data scan over tracked files before edits.
3. Fix `sync_all.sh`, `sync_github_repos.py`, and `repos.example.yml` so fresh-vault automation is
   deterministic and safe.
4. Add `scripts/no_data_scan.py`, `.githooks/pre-commit`, GitHub Actions CI, and pytest coverage for
   the fixed behaviors.
5. Update README/template docs and `CHANGELOG.md` so release claims match shipped behavior.
6. Run: no-data scan, `python3.11 scripts/sync_template_copies.py --check`,
   `python3.11 -m py_compile`, shell syntax checks, `python3.11 -m pytest`, and
   `PYTHONPATH=src python3.11 template/tools/lint_vault.py` or installed `vaultwright lint`.
7. Commit with Conventional Commits as `cz1993`, open a PR with `Reviewer: CodeX`, and continue to
   the next P0 item.

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
- **Use it to build public-document showcase vaults** under `examples/<name>-vault/`. The primary
  direction is familiar government/public-service material because dense public guidance is a
  pain point most users understand. Fictional business examples are still useful for repo mirrors
  and private-business workflows, but should not be the only showcase.
- Generated Office mirrors and optional PDF text mirrors should live under
  `_mirrors/<canonical-source-path>.md` by default, not beside originals. Raw folders must stay
  clean; use `--mirror-mode sibling` only for legacy compatibility.
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

## Guidance #3 — narrow before broadening

Vaultwright should eventually serve owners beyond consulting, but the next development sequence is
not broad industry expansion. Prove the narrow promise first:

- Define product, sync, and security contracts before adding more capabilities.
- Make `plan`/`status` lifecycle behavior first-class before broader CLI polish.
- Extend the initial Office/repo manifests before migration automation.
- Use external design-partner evidence before designing industry presets.
- The current starter file plan is function-based (`00_inbox`, `10_governance`, `20_market`,
  `30_customers`, `40_delivery`, `50_operations`, `60_finance`, `70_people`, `80_sources`) and
  documented in `docs/information-architecture.md` plus `_meta/domain-map.yml`. Preserve this
  configurable function-first approach unless the owner explicitly requests an industry-specific
  preset.

## Backlog (prioritized — refine as you learn)

**P0 — foundations & safety**
- **Product contract specs:** keep `docs/PRODUCT.md`, `docs/SYNC_SPEC.md`, and
  `docs/SECURITY_MODEL.md` current; do not implement features that contradict them.
- **Mirror lifecycle correctness:** extend the initial Office/repo manifests and stable IDs into
  complete lifecycle states, rename / move / delete / stale / conflict handling, recovery tests,
  and source-byte integrity tests.
- **Thin operator CLI:** `tools/vaultwright.py plan`, `sync`, `status`, `catalog`, `conversion`,
  `m365`, `review`, `overlap`, `migration`, `pilot`, `recovery`, `sandbox`, `lint`,
  `benchmark`, and `doctor` exist; keep them thin. The source-installable
  `vaultwright` console entry point now owns `plan`, `sync`, `status`, `doctor`, `catalog`, `lint`,
  `conversion`, `m365`, `recovery`, and `review` through the package while remaining legacy operator commands delegate to the same
  vault-local wrapper during migration. `plan` must remain
  non-destructive; keep improving its sensitive-file risks, duplicate warnings, and
  conversion-quality estimates before writing. `conversion`, `m365`, `migration`, `pilot`, and `recovery` must
  remain read-only operator reports. `review` may append metadata-only decisions to
  `_meta/review-ledger.jsonl`, but must not copy source text, mirror bodies, answer text, secrets,
  or client identifiers. `catalog` writes generated path-and-metadata-only
  `CATALOG.md` and `CATALOG.html` gateways; neither may copy source document text. HTML catalog
  charts must stay aggregate-only and deterministic.
  `overlap` must remain a read-only calibration report that prints paths and scores but not note
  bodies, shared terms, source text, or reviewer notes. `sandbox` must remain a read-only copied-vault preflight that
  verifies the pilot workspace is separate from the original source collection and does not print
  source paths or document bodies.
- **Fresh-vault automation reliability:** `sync_all.sh` fails on required sync failures, missing
  default `repos.yml` skips cleanly, explicit missing configs fail, and sample repo config cannot
  accidentally mirror undocumented third-party content.
- The **no-data** safeguards: `.gitignore` hardening, pre-commit hook, CI scan (see Guidance #1).
- **Test suite** (pytest) for the three tools — idempotency, sentinel/curation preservation,
  frontmatter merge, lint rules, repo-mirror stub vs populated — with fixtures. **GitHub Actions CI.**
- Keep licensing metadata current: `LICENSE` must remain the verbatim AGPL-3.0 text, project
  notices stay in `NOTICE`, source files keep `SPDX-License-Identifier: AGPL-3.0-or-later`, and
  CLA vs DCO/commercial terms remain owner-counsel decisions.

**P1 — differentiators**
- **Mirror robustness:** optional **docling** backend for high-fidelity PDF; richer manifest audit
  trails; conflict-safe curation; cleaner `.xlsx` rendering (drop the `NaN`/`Unnamed` noise).
- **Anti-proliferation:** improve the warning-level near-duplicate / overlap detection and add
  better consolidation suggestions in `lint_vault.py`; keep it human-gated.
- **Repo mirror:** large-repo handling, rate-limit/backoff, and groundwork for **typed links**.

**P2 — DX & adoption**
- Continue shrinking the **`vaultwright` CLI** by moving remaining report runtimes from the existing
  wrapper into the package; keep doctor checks for Obsidian config, `gh` auth, backup posture, and
  recovery readiness package-owned.
- **Industry starter profiles** only after design-partner evidence shows reusable patterns.
- **Docs site** (MkDocs or Quartz); quickstart polish; screenshots/GIFs.
- **Typed links** (`supports` / `contradicts` / `supersedes` / `depends-on`) across schema, linter,
  and a Bases view.

## Definition of done (every change)

- Tests pass in CI; `lint_vault.py` is clean on the template + example vault, including zero
  orphan curated notes and zero overlap warnings after example regeneration.
- Template-derived copies are current: `python3.11 scripts/sync_template_copies.py --check` passes
  after any edit to `template/` or `template/tools/`.
- Scripts remain **idempotent** and cross-platform (macOS + Linux); no new heavy dependencies.
- No real data/secrets added; no-data guard green.
- `CHANGELOG.md` + relevant docs updated; commit authored by cz1993; PR reviewed (Claude/CodeX).

## Anti-patterns (don't)

- Don't reframe Vaultwright as a generic personal-PKM / LLM-wiki — lead with the differentiators.
- Don't add a vector database as a substitute for lifecycle correctness, and don't add a hosted
  SaaS into this repo.
- Don't bloat dependencies, assume a single industry, commit data/secrets, or rewrite shared
  history without owner approval.

## Start here (first session)

1. Read the files listed above; run the **no-data scan** and confirm the tree is clean.
2. Confirm **tests + CI + the no-data guard** remain green.
3. Map the next change to `docs/V1_FINISH_LINE.md` before editing code or docs.
4. Work Stage 1 package/profile convergence before adding broad examples, index work, Explorer UI,
   or more report commands.
5. Check the remaining licensing decisions in `LICENSING.md`; do not accept outside contributions
   until the owner decides CLA vs DCO with counsel.
6. Open PRs, request review (Claude/CodeX), iterate. Keep going.
