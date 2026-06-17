# tools/ — mirror & lint scripts

These keep your knowledge base current and healthy. See `../CLAUDE.md` §6 for the mirror pattern.

| Script | Purpose |
| --- | --- |
| `sync_office_md.py` | markdown **mirror** beside every `.docx/.pptx/.xlsx` (Microsoft markitdown), refreshed on content change |
| `sync_github_repos.py` | markdown **mirror** under `projects/` for each repo in `repos.yml` (README + docs + metadata), refreshed on HEAD change |
| `lint_vault.py` | health check — frontmatter, broken wikilinks, orphans, mirror gaps |
| `sync_all.sh` | run both syncs + the linter (for a cron/launchd job) |

## Install

```bash
pip install -r tools/requirements.txt        # markitdown + pyyaml
```

## Office mirrors

```bash
python3 tools/sync_office_md.py              # sync the whole vault
python3 tools/sync_office_md.py --dry-run    # preview
python3 tools/sync_office_md.py --force       # rebuild all
python3 tools/sync_office_md.py --include-pdf # also mirror text-based PDFs
```

Edit the **original** Office file, never a mirror's body below the
`%% AUTO-GENERATED BELOW — DO NOT EDIT %%` sentinel. Curate notes only in the `## Notes` region.
If a hand-authored `<name>.md` already exists, the script writes `<name>.mirror.md` instead.

## GitHub repo mirrors

```bash
cp tools/repos.example.yml tools/repos.yml    # then edit to list your repos
python3 tools/sync_github_repos.py            # sync all repos
python3 tools/sync_github_repos.py --force     # rebuild even if unchanged
```

**Auth — read-only is enough, and never in the vault.** Either `gh auth login` (the script reads
`gh auth token` + git's credential helper), or export a fine-grained PAT with **Contents: read** +
**Metadata: read**:

```bash
export GH_TOKEN=github_pat_xxx      # shell profile / keychain, NOT the vault
```

Without auth it writes a "pending sync" stub and leaves existing content untouched.

## Keep it fresh (unattended)

```bash
bash tools/sync_all.sh
```

```cron
0 7 * * * cd "$HOME/your-vault" && bash tools/sync_all.sh >> _tmp/sync.log 2>&1
```

## Notes & limits

- Legacy `.doc` and scanned/image PDFs extract poorly — convert to `.docx`, or rely on Obsidian's
  native PDF preview. For high-fidelity PDF text, consider swapping markitdown for `docling`.
- Repo **content** comes via `git`; repo **metadata** (topics, languages, issues) needs
  `api.github.com` reachability. If only git is reachable, mirrors still get README/docs/commits.
- Spreadsheets are captured as text for search; the `.xlsx` stays the tool of record for live numbers.
