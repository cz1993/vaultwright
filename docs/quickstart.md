# Quickstart

Aimed at a technical founder/owner who knows git. ~15 minutes.

## Prerequisites

- [Obsidian](https://obsidian.md) (free) — the human UI.
- Python 3.11+ and `git`.
- An AI coding agent that reads a `CLAUDE.md` / `AGENTS.md`: Claude Code, OpenAI Codex, etc.
- Optional: GitHub CLI (`gh`) if you'll mirror private repos.

## 1. Create your vault

```bash
git clone <this-repo> vaultwright && cd vaultwright
bash scripts/init.sh ~/my-business-vault
```

`init.sh` copies `template/` into `~/my-business-vault` (the schema, templates, tools, Bases view,
and the function-based starter folders). It refuses to overwrite a non-empty target.

## 2. Open it in Obsidian

"Open folder as vault" → `~/my-business-vault`. Enable the core plugins **Properties**, **Bases**,
and **Graph** (Settings → Core plugins). Open `Documents.base` to see the auto-generated index.

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
python3.11 tools/vaultwright.py plan            # inspect source inventory and proposed mirrors
python3.11 tools/vaultwright.py sync            # mirrors -> _mirrors/ and 80_sources/repos/
python3.11 tools/vaultwright.py status          # review manifest-backed lifecycle state

python3.11 tools/vaultwright.py lint            # health check
```

## 5. Keep it fresh (unattended)

`tools/sync_all.sh` runs both syncs + the linter. Schedule it daily on the machine that holds the
vault:

```cron
0 7 * * * cd "$HOME/my-business-vault" && bash tools/sync_all.sh >> _tmp/sync.log 2>&1
```

## Daily use

- **New document?** Drop the original in the right folder and ask the agent to *ingest* it — it
  will mirror binaries under `_mirrors/`, create or **extend** a note, link it from the relevant
  hub/entity, and log it.
- **A question?** Ask the agent; it reads `INDEX.md` / the MOCs first and answers with citations.
- **Housekeeping?** Ask it to *lint* — or just run `tools/lint_vault.py`.
- **Remember:** prefer consolidating into existing notes over creating new ones. See
  `docs/methodology.md` §4.
