# tools/ — mirror & lint scripts

These keep your knowledge base current and healthy. See `../CLAUDE.md` §6 for the mirror pattern.

| Script | Purpose |
| --- | --- |
| `sync_office_md.py` | markdown **mirror** under `_mirrors/` for every `.docx/.pptx/.xlsx` (Microsoft markitdown), refreshed on content change |
| `sync_github_repos.py` | markdown **mirror** under `80_sources/repos/` for each repo in `repos.yml` (README + docs + metadata), refreshed on HEAD change |
| `vaultwright.py` | thin operator wrapper: `plan`, `sync`, `status`, `conversion`, `migration`, `pilot`, `recovery`, `sandbox`, `lint`, `benchmark`, `doctor`, and repo-root `init` |
| `lint_vault.py` | health check — frontmatter, broken wikilinks, orphans, overlap warnings, mirror gaps, configured repo mirror gaps, stale generated mirrors |
| `benchmark_tasks.py` | validates `_meta/agent-readiness-tasks.yml` task packs and optional aggregate result packs |
| `conversion_report.py` | prints a read-only conversion spot-check report from the source manifest |
| `migration_report.py` | prints a read-only migration report for legacy or unknown top-level folders |
| `pilot_report.py` | prints a read-only aggregate pilot evidence report without source content |
| `recovery_report.py` | prints a read-only recovery checklist from source/repo manifest lifecycle states |
| `sandbox_report.py` | prints a read-only copied-vault readiness report before a pilot sync |
| `sync_all.sh` | run both syncs + the linter (for a cron/launchd job) |

`lint_vault.py` reads `_meta/lint-config.yml` for warning-level overlap thresholds. Overlap
warnings include human-gated consolidation suggestions and prefer the note with more inbound links
when that signal is available. Keep the template defaults until copied pilot vaults show too many
false positives or false negatives, then record any threshold changes in the private pilot
worksheet.

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
python3.11 tools/vaultwright.py conversion --guide
python3.11 tools/vaultwright.py migration
python3.11 tools/vaultwright.py pilot
python3.11 tools/vaultwright.py recovery
python3.11 tools/vaultwright.py sandbox --source-root /path/to/original-documents
python3.11 tools/vaultwright.py lint
python3.11 tools/vaultwright.py benchmark
python3.11 tools/vaultwright.py doctor
```

`doctor` is read-only. It checks required files and copied tools, Python dependencies, source/repo
manifest lifecycle counts, sync audit presence, recovery action counts, git backup posture, and
GitHub auth posture. It also reports optional Obsidian config/plugin posture and `.gitignore` backup
guard coverage. A fresh vault may warn that manifests, audit logs, repo config, git history, or
Obsidian UI config are not generated yet; those warnings are preflight context, not sync failures.

`conversion` is read-only. It reads `_meta/source-manifest.json` and turns lifecycle states,
format risks, warnings, errors, and source/mirror existence into a prioritized spot-check list. It
does not claim a quantitative quality score; operators still review high-risk formats, tables,
slides, PDFs, source links, and generated-region boundaries before relying on mirrors.
Use `--guide` to append a manifest-aware operator checklist; see
`docs/CONVERSION_REVIEW_GUIDE.md` in the source repository for the durable review protocol.

`migration` is read-only. It scans top-level folders, reports old aliases from
`_meta/domain-map.yml` such as `marketing/`, `legal/`, `clients/`, or `hr/`, and flags unknown
folders that need human classification before any manual move. Non-reserved hidden or
underscore-prefixed folders are reported too, because they may contain staged imports or legacy
source material.

`pilot` is read-only. It summarizes aggregate pilot evidence from manifests, audit events,
conversion priorities, recovery action counts, benchmark tasks, and optional benchmark result
scores without printing source paths, source text, mirror text, answer text, reviewer notes, or
repository document bodies. Use `--json` to attach the aggregate metrics to an anonymized
design-partner worksheet. Use `--worksheet` to print a redacted Markdown summary that can be pasted
into a private pilot record without source paths or document content.

`recovery` is also read-only. It reads `_meta/source-manifest.json`, `_meta/repo-manifest.json`, and
the latest matching `_meta/sync-audit.jsonl` events, then prints only records that need operator
action, such as missing sources, manual generated-region edits, conflicts, unreachable repos,
missing mirrors, stale atomic temp files from interrupted writes, or error states.
For moved sources and mirror-root conflicts, it also prints the previous generated mirror path that
must be reviewed before regeneration.

`sandbox` is read-only. Run it from a duplicated pilot vault before the first sync:

```bash
python3.11 tools/vaultwright.py sandbox --source-root /path/to/original-documents
python3.11 tools/vaultwright.py sandbox --source-root /path/to/original-documents --json
```

It checks required Vaultwright files/tools, verifies the copied vault is not the same path as the
original source collection, counts Office/PDF source candidates, reports whether generated mirrors
are isolated under `_mirrors/`, summarizes manifests/audit/recovery readiness, and checks basic git
backup posture. It does not print source paths, document text, mirror text, or repo document bodies.

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
If a managed source frontmatter field such as `source`, `source_manifest`, or `source_format`
drifts from the manifest/source, plan/status reports `stale` and normal sync rewrites the managed
field without requiring `--force`.
If a source moves and the generated mirror path changes, sync reports `source_moved` while the
previous generated mirror still exists. Preserve, move, archive, or remove the old mirror before
generating the new path.
If the configured mirror root or mode changes, sync reports `conflict` while the previous generated
mirror still exists. Review and archive/remove the old mirror before generating the new path.

The Office plan also reports warning counts for:

- sensitive-looking source paths or filenames;
- duplicate source bytes;
- format-specific conversion-quality risks for spreadsheets, decks, PDFs, and legacy `.doc` files.

For `.xlsx` mirrors, sync applies a conservative readability cleanup to extracted markdown tables:
obvious `NaN` placeholders become blank cells, and empty `Unnamed:*` columns are removed. The
workbook remains the source of truth for formulas, hidden sheets, and live calculations.

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
Each configured repo must resolve to a unique generated note path. Duplicate `note:` values under
the same `settings.notes_dir` are rejected before sync writes anything, because one generated note
cannot safely represent two repo identities.

Successful repo syncs maintain `_meta/repo-manifest.json`. Office and repo syncs append
machine-readable events to `_meta/sync-audit.jsonl`. These generated metadata files explain what
changed, which source or repo identity was involved, the generated note path, the lifecycle state
after sync, and structured warnings/errors. They do not embed README or documentation bodies.
`tools/lint_vault.py` treats an explicit repo entry in `tools/repos.yml` as a source contract: the
expected `repo-mirror` note must exist under the configured notes directory and must carry the
generated sentinel plus manifest metadata. A fresh vault with no `tools/repos.yml` still skips repo
sync and lint checks cleanly.
Lint also treats repo frontmatter as managed evidence: if a generated mirror's `repo` or commit
metadata drifts from `_meta/repo-manifest.json`, rerun repo sync before relying on the mirror.
Repo plan/status also reports managed `repo` frontmatter identity drift as stale, and a normal sync
rewrites the managed field from the configured/resolved repo identity without requiring `--force`.
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

If a private pilot records comparison scores in `_meta/agent-readiness-results.yml`, summarize the
aggregate results with:

```bash
python3.11 tools/vaultwright.py benchmark --results _meta/agent-readiness-results.yml
python3.11 tools/vaultwright.py benchmark --results _meta/agent-readiness-results.yml --require-results
python3.11 tools/vaultwright.py benchmark --results _meta/agent-readiness-results.yml --require-citations
python3.11 tools/vaultwright.py benchmark --results _meta/agent-readiness-results.yml --json
```

Result packs score each task across `raw_source_folder`, `document_chat_transcript`, and
`vaultwright_markdown`. The report prints per-mode scores, correction counts, privacy/provenance
violation counts, citation counts, and uncited scored-result counts, but it does not print answer
text or reviewer notes. Use `--require-citations` when scored pilot results must cite at least one
declared source or generated mirror path. Result packs are ignored and scanner-blocked in the
public repository by default; keep them in private pilot workspaces unless an anonymized aggregate
has been reviewed separately.

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
