# AGENTS.md — rules for any agent working on the Vaultwright **codebase**

> This governs development of Vaultwright itself (CodeX, Claude, etc.). It is **not** the schema
> for a user's vault — that lives in `template/CLAUDE.md`. Read `docs/CODEX_KICKOFF_PROMPT.md` for
> the current mission, and `README.md` + `docs/` for context.

## What this repo is

Vaultwright is the **tool + framework + methodology** for an AI-maintained, linked-markdown
knowledge base. **This repo never contains a real knowledge base.** It contains code, docs,
templates, tests, and *sample* data only.

## Ownership (non-negotiable)

- This is **cz1993's personal-interest project** — deliberately separate from any company/work
  repositories. Do not attribute anything to a company.
- **All commits and PRs are authored by `cz1993`.** Configure git:
  `user.name = cz1993`, `user.email = 56002317+cz1993@users.noreply.github.com`.
- **Reviewers** may be **Claude** or **CodeX** — name the reviewer explicitly in each PR
  (e.g. a `Reviewer: Claude` / `Reviewer: CodeX` line). The owner (cz1993) authors and merges.

## The no-data rule (critical, zero tolerance)

- **Never** commit real company or personal data, documents, PII, secrets, credentials, API keys,
  tokens, or proprietary files — not in the tree, not in history, ever.
- If you find any such file already present, **remove it immediately**; if it reached git history,
  stop and scrub it (git filter-repo / BFG) **after confirming with the owner**, then force-push.
- Keep the safeguards working: `.gitignore` data/secret patterns, the CI "no-data" scan, and the
  pre-commit hook. Treat a tripped guard as a release blocker.
- **Sample data is allowed and encouraged** — but only (a) synthetic/fictional data you generate,
  or (b) genuinely public, permissively-licensed (CC0 / public-domain / CC-BY / MIT) files with
  documented provenance + license. See the kickoff prompt's "Sample-data hunt."

## Protect the differentiators

Lead with these; they are why Vaultwright exists (see `docs/positioning.md`):
the **mirror layer** (Office + GitHub → refreshed markdown mirrors), **governance**
(PII/retention/secrets-out), **anti-proliferation** (consolidate > create), and **linking-first**
retrieval. Do **not** drift back into "another generic LLM-wiki," and do **not** add a vector DB.

## Tech + quality bar

- Python 3 (stdlib + PyYAML + markitdown) and POSIX shell. No heavy frameworks; keep deps minimal.
- Cross-platform (macOS + Linux). Scripts must stay **idempotent**.
- Every change: run `template/tools/lint_vault.py` against the example vault, run the test suite,
  update `CHANGELOG.md` and the relevant docs. Green CI before merge.
- Design for users from **many industries**, not one — keep taxonomy/entities/retention
  configurable and the copy jargon-free.
