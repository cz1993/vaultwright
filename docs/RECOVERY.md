# Recovery Guide

## Purpose

Vaultwright must be recoverable because it works near authoritative business records. Recovery
procedures preserve the core promise: source files stay untouched, generated mirrors can be
regenerated, and human-curated notes can be restored from versioned backups.

## What To Back Up

Back up the whole vault before first sync and before bulk changes:

- original source folders;
- curated markdown notes;
- `_meta/source-manifest.json`;
- `_meta/repo-manifest.json`;
- `_meta/sync-audit.jsonl`;
- `log.md`;
- `tools/repos.yml`;
- `.obsidian/` settings only if the operator intentionally versions them.

Do not back up secrets into the vault. Keep tokens in the OS keychain or environment.

## Regenerate Generated Mirrors

Generated mirrors can be deleted and rebuilt from sources:

```bash
rm -rf _mirrors
rm -f 80_sources/repos/*.md
python3.11 tools/vaultwright.py plan
python3.11 tools/vaultwright.py sync
python3.11 tools/vaultwright.py status
python3.11 tools/vaultwright.py lint
```

Review the plan before sync if the source tree changed, especially after folder renames or cloud
sync conflicts.

## Recover From Interrupted Sync

Mirror writes are atomic, so an interrupted sync should preserve either the prior complete mirror or
the new complete mirror. After interruption:

```bash
python3.11 tools/vaultwright.py status
python3.11 tools/vaultwright.py recovery
python3.11 tools/vaultwright.py sync
python3.11 tools/vaultwright.py lint
```

If `_meta/source-manifest.json`, `_meta/repo-manifest.json`, or `_meta/sync-audit.jsonl` is missing,
restore it from backup when possible. If no backup exists, rerun status/sync to rebuild manifests
from the current sources and mirrors, then review all `planned`, `stale`, `source_missing`,
`unreachable`, and `manual_modification` states.

Important limitation: without the old manifest, Vaultwright cannot prove whether an existing
generated region is pristine. Existing Office and repo mirrors without a manifest-generated baseline
are treated as review-required, and `--force` will not accept them as clean. If the sentinel boundary
is valid, preserve curated notes above it and regenerate from the original source. If the sentinel is
missing or altered, restore the mirror from backup or remove the untrusted mirror after preserving
any known-curated notes elsewhere, then regenerate from the source.

## Recovery Report

Use the read-only recovery report before changing files:

```bash
python3.11 tools/vaultwright.py recovery
python3.11 tools/vaultwright.py recovery --json
```

The report reads `_meta/source-manifest.json` and `_meta/repo-manifest.json`, then lists only records
that need operator action. It does not move, delete, regenerate, or archive anything. Treat it as a
triage checklist for:

- `source_missing`, `source_moved`, `manual_modification`, `conflict`, and `error` Office records;
- missing generated mirror paths;
- `unreachable`, `repo_changed`, `manual_modification`, `conflict`, and `error` repo records;
- missing repo mirror notes.

For Office `conflict` records caused by a mirror-root or mirror-mode change, archive or remove the
previous generated mirror after review. Vaultwright will not write the new mirror path while the
old generated mirror still exists, because that would leave two generated notes claiming the same
source.

For Office `source_moved` records with `previous_mirror_path`, preserve any curated notes in the
old mirror, then move, archive, or remove that previous generated mirror. Vaultwright will not
write the new mirror path while the old generated mirror still exists.

If a manifest is missing, restore it from backup when possible. Without manifest evidence,
Vaultwright cannot safely prove whether an existing generated region is pristine.

## Recover From Bad Generated Output

If extraction quality is poor or a converter update produces worse markdown:

1. Restore the prior mirror from Git or backup if humans need the previous readable output.
2. Keep the original source file unchanged.
3. Pin or revert the converter dependency if needed.
4. Run `tools/vaultwright.py status` and inspect converter-related stale states.
5. Record the decision in `log.md`.

If conversion fails before writing, Vaultwright records an `error` lifecycle state and leaves the
previous mirror untouched. Fix the converter/source issue, rerun `tools/vaultwright.py sync`, then
confirm `tools/vaultwright.py status` returns the source to `clean`.

## Recover Curated Notes

Curated notes are human-maintained records. Restore them from Git or filesystem backup, not from
generated mirrors. If an agent made a bad curated edit:

```bash
git diff
git restore -- path/to/note.md
python3.11 tools/vaultwright.py lint
```

Only restore with explicit owner approval when the note contains current business decisions.

## Source Missing Review

Vaultwright does not delete mirrors automatically when a source disappears. A missing source means:

- the source was intentionally moved or deleted;
- a cloud-sync file is not pinned locally;
- a path changed;
- a backup or restore is incomplete.

Resolve the source first. If the deletion is intentional, archive or remove the mirror through a
human-reviewed change and keep the audit trail.

## Release Gate

Before public release, recovery must be tested on a copied vault:

- delete `_mirrors/` and regenerate;
- interrupt sync and rerun;
- force a converter failure and verify the previous mirror is preserved, then fix the converter and
  verify sync returns the record to `clean`;
- remove one source and verify `source_missing`;
- edit a generated region and verify `manual_modification`;
- move one source and verify `source_moved` blocks new mirror generation while the previous mirror
  exists, then remove or move the previous mirror and verify the new mirror can be generated;
- change the Office mirror root with the old mirror present and verify `conflict`, then remove the
  old mirror and verify the new mirror can be generated;
- run `tools/vaultwright.py recovery` and verify the checklist matches the manifest states;
- restore a curated note from Git;
- run no-data scan and lint after recovery.

The test suite now exercises the copied-vault regeneration path, source-byte preservation,
converter-failure recovery that preserves the prior mirror, conversion-race aborts that preserve
the prior mirror, `source_missing`, `manual_modification`, lint, and generated-text no-data scan
checks on the Northwind example. Operator backup/restore drills and full copied-vault no-data scans
on pilot vaults are still required before production use.
