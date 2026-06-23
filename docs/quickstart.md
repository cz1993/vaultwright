# Quickstart

Aimed at a technical founder/owner who knows git. ~15 minutes.

## Prerequisites

- [Obsidian](https://obsidian.md) (free) — optional reference human UI.
- Python 3.11+ and `git`.
- An AI coding agent that reads a `CLAUDE.md` / `AGENTS.md`: Claude Code, OpenAI Codex, etc.
- Optional: GitHub CLI (`gh`) if you'll mirror private repos.

## 1. Create your vault

```bash
git clone <this-repo> vaultwright && cd vaultwright
bash scripts/init.sh ~/my-business-vault
```

`init.sh` copies `template/` into `~/my-business-vault` (the schema, templates, tools, Bases view,
and the business-operations starter folders). It refuses to overwrite a non-empty target.

Alternatively, from a source checkout, the package CLI can scaffold and validate the same profile
contract:

```bash
python3.11 -m pip install -e .
vaultwright profile list
vaultwright init --profile business-operations ~/my-business-vault
vaultwright --root ~/my-business-vault profile validate
vaultwright --root ~/my-business-vault profile diff 0.1.0
vaultwright --root ~/my-business-vault profile migrate --plan
```

`business-operations` is currently the only packaged profile. The v1 finish line tracks
research-learning, software-project, and blank profiles, but the CLI intentionally rejects them
until their profile contracts and fixtures exist.

## 2. Open it in Obsidian

"Open folder as vault" → `~/my-business-vault`. Enable the core plugins **Properties**, **Bases**,
and **Graph** (Settings → Core plugins). Open `Documents.base` to see the auto-generated index.

Obsidian is useful for people, but it is not the correctness boundary. The key artifact is the
filesystem of markdown mirrors, manifests, and curated notes that your agent can inspect directly.

## 3. Point your agent at it

Open the vault with your agent (e.g. run Claude Code / Codex in the folder). It reads `CLAUDE.md`
first — that's the operating manual. Try: *"Read CLAUDE.md, then ingest the file I just added to
`60_finance/` following the schema."*

## 4. Mirror your binaries and repos

```bash
cd ~/my-business-vault
python3.11 -m pip install -r tools/requirements.txt  # markitdown + pyyaml

cp tools/repos.example.yml tools/repos.yml      # then edit to list your repos
gh auth login                                   # read-only is enough (or export GH_TOKEN)

python3.11 tools/vaultwright.py doctor          # check dependencies and vault structure
python3.11 tools/vaultwright.py sandbox --source-root /path/to/original-documents # copied-vault preflight
python3.11 tools/vaultwright.py plan            # inspect source inventory and proposed mirrors
python3.11 tools/vaultwright.py sync            # mirrors -> _mirrors/ and 80_sources/repos/
python3.11 tools/vaultwright.py status          # review manifest-backed lifecycle state
python3.11 tools/vaultwright.py catalog         # write CATALOG.md inventory gateway
python3.11 tools/vaultwright.py catalog --html  # write CATALOG.html visual inventory gateway
python3.11 tools/vaultwright.py m365            # Microsoft 365/Copilot handoff readiness
python3.11 tools/vaultwright.py review --json   # summarize metadata-only review decisions
python3.11 tools/vaultwright.py overlap         # calibrate overlap thresholds without note bodies
python3.11 tools/vaultwright.py conversion --guide # read-only conversion spot-check and guide
python3.11 tools/vaultwright.py conversion --init-results # private quality result scaffold
python3.11 tools/vaultwright.py conversion --results _meta/conversion-quality-results.yml --require-reviewed # after filling scaffold
python3.11 tools/vaultwright.py migration       # dry-run report for legacy/unknown folders
python3.11 tools/vaultwright.py migration --worksheet # Markdown cleanup checklist
python3.11 tools/vaultwright.py migration --runbook # legacy folder move protocol
python3.11 tools/vaultwright.py migration --normalize-frontmatter-domains --worksheet # domain cleanup checklist
python3.11 tools/vaultwright.py recovery --worksheet # manifest recovery checklist
python3.11 tools/vaultwright.py pilot           # aggregate pilot evidence, no source content
python3.11 tools/vaultwright.py pilot --worksheet # redacted Markdown private-pilot summary
python3.11 tools/vaultwright.py benchmark       # validate benchmark tasks, if configured

python3.11 tools/vaultwright.py lint            # health check
```

## 5. Keep it fresh (unattended)

`tools/sync_all.sh` runs both syncs + the linter. Schedule it daily on the machine that holds the
vault:

If the vault should keep text-based PDF mirrors fresh too, set `office_mirrors.include_pdf: true`
in `_meta/mirror-config.yml`; `sync_all.sh` will honor that setting.

```cron
0 7 * * * cd "$HOME/my-business-vault" && bash tools/sync_all.sh >> _tmp/sync.log 2>&1
```

## Daily use

- **New document?** Drop the original in the right folder and ask the agent to *ingest* it — it
  will mirror binaries under `_mirrors/`, create or **extend** a note, link it from the relevant
  hub/entity, and log it.
- **A question?** Ask the agent; it reads `INDEX.md` / the MOCs first and answers with citations.
- **Need a non-Obsidian gateway?** Regenerate `CATALOG.md` with `tools/vaultwright.py catalog`,
  or `CATALOG.html` with `tools/vaultwright.py catalog --html`; both list source paths, mirrors,
  lifecycle states, and inventory stats without copying content. The HTML gateway adds static
  aggregate charts for quick review.
- **Reviewed an artifact?** Record the decision with
  `tools/vaultwright.py review --artifact CATALOG.html --status approved --reviewer <name>`.
  The ledger stores hashes and short metadata notes only, then reports approvals as stale if the
  reviewed artifact changes.
- **Housekeeping?** Ask it to *lint* — or just run `tools/lint_vault.py`.
- **Remember:** prefer consolidating into existing notes over creating new ones. See
  `docs/methodology.md` §4.
- **Agent-readiness pilot?** Use `docs/AGENT_READINESS_BENCHMARK.md` and
  `tools/vaultwright.py benchmark --init-tasks` to create a private task scaffold after sync, then
  `tools/vaultwright.py benchmark --worksheet` to run the comparison, then
  `tools/vaultwright.py benchmark --init-results` and
  `tools/vaultwright.py benchmark --results _meta/agent-readiness-results.yml` to compare raw-source,
  document-chat, and Vaultwright-markdown performance on the same questions. Add
  `--require-citations` and `--require-prompt-safety` when pilot results must prove source-backed
  answers and prompt-injection handling.
- **Microsoft 365 handoff?** Use `docs/MICROSOFT_365_HANDOFF.md` and
  `tools/vaultwright.py m365` to check whether the generated mirror/catalog layer is ready for a
  governed SharePoint, OneDrive, Copilot Studio, or connector review.
