# tools/ — mirror & lint scripts

These keep your knowledge base current and healthy. See `../CLAUDE.md` §6 for the mirror pattern.

| Script | Purpose |
| --- | --- |
| `sync_office_md.py` | markdown **mirror** under `_mirrors/` for every `.docx/.pptx/.xlsx` (Microsoft markitdown), refreshed on content change |
| `sync_github_repos.py` | markdown **mirror** under `80_sources/repos/` for each repo in `repos.yml` (README + docs + metadata), refreshed on HEAD change |
| `vaultwright.py` | thin operator wrapper: `plan`, `sync`, `status`, `recovery`, `lint`, `benchmark`, `doctor`, and repo-root `init` |
| `lint_vault.py` | health check — frontmatter, broken wikilinks, orphans, overlap warnings, mirror gaps |
| `benchmark_tasks.py` | validates `_meta/agent-readiness-tasks.yml` benchmark packs and referenced source/mirror paths |
| `recovery_report.py` | prints a read-only recovery checklist from source/repo manifest lifecycle states |
| `sync_all.sh` | run both syncs + the linter (for a cron/launchd job) |

## Install

```bash
python3.11 --version                         # use Python 3.11+
python3.11 -m pip install -r tools/requirements.txt  # markitdown + pyyaml
```

## Office mirrors

For the operator workflow, prefer:

```bash
python3.11 tools/vaultwright.py plan
python3.11 tools/vaultwright.py sync
python3.11 tools/vaultwright.py status
python3.11 tools/vaultwright.py recovery
python3.11 tools/vaultwright.py lint
python3.11 tools/vaultwright.py benchmark
python3.11 tools/vaultwright.py doctor
```

`doctor` is read-only. It checks required files and copied tools, Python dependencies, source/repo
manifest lifecycle counts, sync audit presence, recovery action counts, git backup posture, and
GitHub auth posture. A fresh vault may warn that manifests, audit logs, or repo config are not
generated yet; those warnings are preflight context, not sync failures.

`recovery` is also read-only. It reads `_meta/source-manifest.json`, `_meta/repo-manifest.json`, and
the latest matching `_meta/sync-audit.jsonl` events, then prints only records that need operator
action, such as missing sources, manual generated-region edits, conflicts, unreachable repos,
missing mirrors, stale atomic temp files from interrupted writes, or error states.
For moved sources and mirror-root conflicts, it also prints the previous generated mirror path that
must be reviewed before regeneration.

```bash
python3.11 tools/sync_office_md.py              # sync the whole vault
python3.11 tools/sync_office_md.py --plan       # non-mutating inventory + proposed actions
python3.11 tools/sync_office_md.py --status     # report manifest-backed lifecycle state
python3.11 tools/sync_office_md.py --dry-run    # preview sync output without writes
python3.11 tools/sync_office_md.py --force       # rebuild all
python3.11 tools/sync_office_md.py --include-pdf # also mirror text-based PDFs
python3.11 tools/sync_office_md.py --mirror-mode sibling # legacy sibling layout
```

Edit the **original** Office file, never a mirror's body below the
`%% AUTO-GENERATED BELOW — DO NOT EDIT %%` sentinel. Curate notes only in the `## Notes` region.
By default mirrors are written to `_mirrors/<canonical-source-path>.md`, so source folders stay
clean even when old folder aliases are still present. Configure `_meta/mirror-config.yml` or pass
`--mirror-mode sibling` only for legacy vaults.

Successful syncs also maintain `_meta/source-manifest.json`. The manifest records a stable source
ID, source hash/size, mirror path, converter/config version, lifecycle state, warnings, and last
successful sync time. `--plan` never writes mirrors or the manifest; `--status` reads the manifest
and current source tree to surface clean, planned, unsupported, missing, stale, conflicted, and
manual-modification states. Plan/status output also prints `next actions` for lifecycle states that
need review, sync, source recovery, or conflict resolution.
Each sync attempt also appends `_meta/sync-audit.jsonl` with the source ID, generated mirror path,
status, lifecycle state, and structured warnings/errors. The audit log is diagnostic metadata only;
it does not embed original document text.
If conversion fails, sync records an `error` state and leaves the previous mirror untouched; fix the
converter/source issue and rerun sync to recover.
If writing the mirror fails, sync records an `error` state and keeps the previous mirror; fix the
filesystem issue and rerun sync to recover.
If a source file changes while conversion is running, sync records an error and leaves the previous
mirror untouched so generated markdown is not tied to stale source-hash metadata.
If a source moves and the generated mirror path changes, sync reports `source_moved` while the
previous generated mirror still exists. Preserve, move, archive, or remove the old mirror before
generating the new path.
If the configured mirror root or mode changes, sync reports `conflict` while the previous generated
mirror still exists. Review and archive/remove the old mirror before generating the new path.

The Office plan also reports warning counts for:

- sensitive-looking source paths or filenames;
- duplicate source bytes;
- format-specific conversion-quality risks for spreadsheets, decks, PDFs, and legacy `.doc` files.

## GitHub repo mirrors

```bash
cp tools/repos.example.yml tools/repos.yml    # then edit to list your repos
python3.11 tools/sync_github_repos.py --plan     # non-mutating repo mirror plan
python3.11 tools/sync_github_repos.py            # sync all repos
python3.11 tools/sync_github_repos.py --status   # repo manifest lifecycle report
python3.11 tools/sync_github_repos.py --force     # rebuild even if unchanged
```

**Auth — read-only is enough, and never in the vault.** Either `gh auth login` (the script reads
`gh auth token` + git's credential helper), or export a fine-grained PAT with **Contents: read** +
**Metadata: read**:

```bash
export GH_TOKEN=github_pat_xxx      # shell profile / keychain, NOT the vault
```

Without auth it writes a "pending sync" stub and leaves existing content untouched.
If `tools/repos.yml` is missing, the sync skips cleanly; copy `tools/repos.example.yml` only when
you are ready to list repos.
For deterministic examples or tests, a repo entry may use `local_path:` to mirror a local fixture
directory instead of calling GitHub.

Successful repo syncs maintain `_meta/repo-manifest.json`. Office and repo syncs append
machine-readable events to `_meta/sync-audit.jsonl`. These generated metadata files explain what
changed, which source or repo identity was involved, the generated note path, the lifecycle state
after sync, and structured warnings/errors. They do not embed README or documentation bodies.
Repo plan/status output also prints `next actions` for changed, unreachable, conflicted, manually
modified, and errored repo mirrors.
If writing a repo mirror note fails, sync records an `error` state and keeps the previous note; fix
the filesystem issue and rerun sync to recover.

## Agent-readiness benchmark tasks

If `_meta/agent-readiness-tasks.yml` exists, validate it with:

```bash
python3.11 tools/vaultwright.py benchmark
python3.11 tools/vaultwright.py benchmark --require-generated  # after running sync
```

The first command allows generated mirror paths to be planned but not present yet. The
`--require-generated` variant is for synced working copies and fails when a referenced mirror path
does not exist.

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
