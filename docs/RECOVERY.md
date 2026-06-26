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

## Copied-Vault Sandbox Preflight

Before piloting on a real document collection, duplicate the source collection and run Vaultwright
only in the copied vault. Then run the read-only sandbox report:

```bash
python3.11 tools/vaultwright.py sandbox --source-root /path/to/original-documents
python3.11 tools/vaultwright.py sandbox --source-root /path/to/original-documents --json
```

The report verifies that the pilot vault is not the same path as the original source root, checks
required Vaultwright files/tools, counts source candidates, flags generated source mirrors sitting
outside `_mirrors/`, summarizes manifest/audit/recovery readiness, and checks basic git backup
posture. It does not print source paths, document text, mirror text, or repository document bodies.
Treat sandbox errors as blockers before the first sync. Treat warnings as review items to resolve
or explicitly accept in the private pilot worksheet.

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

Full sync remains the authoritative recovery mode after Stage 1B. The future local journal and
state database are derived operational state; if they are lost or suspect, stop any watcher, run
reconciliation or full sync, and rebuild journal state from sources and manifests rather than
treating the journal as authority.

## Recover From Interrupted Sync

Mirror writes are atomic, so an interrupted sync should preserve either the prior complete mirror or
the new complete mirror. A hard interruption can also leave a hidden atomic temp file such as
`.registration.md.12345.tmp` beside the target. After interruption:

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

Interrupted Stage 1B changed-file materialization should first be inspected with
`vaultwright journal status` and recovered with `vaultwright journal replay`. Replay recovers
events left in `processing`; use `vaultwright journal replay --retry-failed` only when a failed
event is ready for an explicit retry. Use `vaultwright reconcile` to queue missed source/manifest
events before replaying recovered work, or use `vaultwright sync --changed` to run those two steps
as one changed-file pass. `vaultwright watch --once` runs the same startup reconciliation posture
plus any queued feed work for a deterministic one-cycle watch check. When changed sync, replay,
reconciliation, or watch startup cannot prove consistency, run full sync as the recovery path.

When an error state exists, inspect the newest `_meta/sync-audit.jsonl` event for that `source_id` or
`repo_id`. The event records the generated artifact path, lifecycle state, sync status, and
structured `warnings` / `errors` without embedding source document text or repo document bodies.
When the vault has `_meta/lifecycle-states.yml`, source/repo manifest records and audit events also
identify that lifecycle contract path and schema version so reviewers can tie a state back to the
operator contract used by sync.

Important limitation: without the old manifest, Vaultwright cannot prove whether an existing
generated region is pristine. Existing Office and repo mirrors without a manifest-generated baseline
are treated as review-required, and `--force` will not accept them as clean. If the sentinel boundary
is valid, run `vaultwright migrate annotations --write` to preserve any legacy above-sentinel
annotations before regenerating from the original source. If the sentinel is missing or altered,
restore the mirror from backup or remove the untrusted mirror after preserving any known-curated
notes elsewhere, then regenerate from the source.

## Recovery Report

Use the read-only recovery report before changing files:

```bash
python3.11 tools/vaultwright.py recovery
python3.11 tools/vaultwright.py recovery --worksheet
python3.11 tools/vaultwright.py recovery --runbook
python3.11 tools/vaultwright.py recovery --json
```

The report reads `_meta/source-manifest.json`, `_meta/repo-manifest.json`,
`_meta/lifecycle-states.yml`, `tools/repos.yml`, and the latest matching events in
`_meta/sync-audit.jsonl`, then lists only records that need operator action. It does not move,
delete, regenerate, or archive anything. Use `--worksheet` when you need a Markdown review
checklist for a private pilot record before changing files. Use `--runbook` when you need a
state-grouped execution protocol for resolving the queue in a controlled batch. Treat recovery
output as triage evidence for:

- `planned`, `source_changed`, `source_moved`, `stale`, `converter_changed`, `unsupported`,
  `source_missing`, `manual_modification`, `conflict`, and `error` Office records;
- missing generated mirror paths;
- `planned`, `repo_changed`, `stale`, `unreachable`, `repo_unconfigured`,
  `manual_modification`, `conflict`, and `error` repo records;
- previously synced repo manifest records whose `tools/repos.yml` entry is now missing, even before
  the repo sync has persisted `repo_unconfigured` back to `_meta/repo-manifest.json`;
- missing repo mirror notes;
- stale atomic temp files left by interrupted writes.

The JSON form includes `summary.total`, `summary.office`, `summary.repo`, and `summary.temp`
counts for automation, plus the same item-level reasons, fallback actions, warnings, errors, and
latest audit context as the human report. Office and repo items also include a structured
`lifecycle` object from `_meta/lifecycle-states.yml` with `entry_condition`, `explanation`,
`permitted_next_actions`, `exit_condition`, and `manifest_state`. The worksheet prints the
contract-backed explanation, next actions, and exit condition for each item so operators can see
how to leave the state safely.
The runbook form groups the same queue into resolution paths for missing Office sources, moved
sources, repo mirrors whose config entry was removed, manual generated-region edits, conflicts or
errors, and stale atomic temp files. It prints execution rules and verification gates, but does not
change files.
For Office move and mirror-root conflict records, the report also includes `previous_target`,
`previous_target_exists`, and `previous_target_reason` so operators can identify the retained
generated mirror that must be preserved, moved, archived, or removed before syncing again.
For ambiguous move conflicts, the report and Office manifest record include
`ambiguous_move_candidates` with the missing source paths whose bytes match the new source. Choose
the correct history manually, or preserve/archive the old mirrors and treat the new file as a
deliberate duplicate or new source before rerunning sync. The human report shows a bounded
candidate summary with a total count; use `vaultwright recovery --json` when the full candidate list
is longer than the human summary.
For manifest repair mistakes where multiple non-synthetic records claim the same current source
path, the report includes `duplicate_source_ids`. Correct the duplicate manifest records before
syncing; Vaultwright will not choose one source history silently.

For each item with audit history, the report includes the latest audit timestamp, status, lifecycle
state, lifecycle contract provenance when available, and structured warnings/errors. This is
diagnostic metadata only; it should not contain raw document text or repo documentation bodies.

For `temp:interrupted_write` items, rerun status/sync first to confirm the canonical generated file
or manifest is complete. Then remove the temp file after backup review; Vaultwright does not delete
it automatically.

For Office `conflict` records caused by a mirror-root or mirror-mode change, archive or remove the
previous generated mirror after review. Vaultwright will not write the new mirror path while the
old generated mirror still exists, because that would leave two generated notes claiming the same
source.

For Office `source_moved` records with `previous_mirror_path`, migrate any legacy annotations from
the old mirror, then move, archive, or remove that previous generated mirror. Vaultwright will not
write the new mirror path while the old generated mirror still exists.

For Office `conflict` records with `ambiguous_move_candidates`, do not force sync. Multiple missing
manifest records have identical bytes, so Vaultwright cannot prove which prior source path moved.
Use the candidate paths, old mirrors, and Git history/backups to choose the correct source record;
if you want to preserve one candidate's source history, edit or restore the manifest deliberately.
If the new file should be treated as a deliberate new or duplicate source, either restore the
candidate source files to their manifest paths so they are no longer missing, or deliberately edit
or remove the old candidate manifest records after preserving their old mirrors. Simply moving the
old files to an archive path without manifest resolution leaves the original manifest paths missing
and the conflict active. Rerun status after the resolution; the conflict clears once fewer than two
matching missing candidates remain.

For Office `conflict` records with `duplicate_source_ids`, do not sync until the manifest has a
single non-synthetic source record for that current source path. Keep the source ID whose history is
correct, restore the other source files to their actual paths or archive their mirrors deliberately,
then rerun status.

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

If writing the mirror fails, Vaultwright records an `error` lifecycle state and leaves the previous
mirror untouched. Fix the filesystem, permission, disk-space, or cloud-sync issue, rerun
`tools/vaultwright.py sync`, then confirm the source returns to `clean`.

Repo mirror note writes follow the same rule: a write failure records an `error` lifecycle state,
keeps the previous repo note, and can recover to `clean` after the filesystem issue is fixed and
sync is rerun.

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

- run `tools/vaultwright.py sandbox --source-root <original-source-root>` and resolve errors;
- delete `_mirrors/` and regenerate;
- interrupt sync and rerun;
- force a converter failure and verify the previous mirror is preserved, then fix the converter and
  verify sync returns the record to `clean`;
- force a mirror-write failure and verify the previous mirror is preserved, then fix the filesystem
  issue and verify sync returns the record to `clean`;
- force a repo-note write failure and verify the previous repo note is preserved, then fix the
  filesystem issue and verify sync returns the record to `clean`;
- remove one source and verify `source_missing`;
- change one source and verify `source_changed`, change mirror configuration and verify `stale`,
  and change converter metadata or version and verify `converter_changed`;
- configure one new source/repo and verify `planned`;
- change one repo fixture or HEAD and verify `repo_changed`, make a configured repo unreachable
  and verify `unreachable`, then remove a synced repo config entry and verify
  `repo_unconfigured`;
- edit a generated region and verify `manual_modification`;
- move one source and verify `source_moved` blocks new mirror generation while the previous mirror
  exists, then remove or move the previous mirror and verify the new mirror can be generated;
- change the Office mirror root with the old mirror present and verify `conflict`, then remove the
  old mirror and verify the new mirror can be generated;
- run `tools/vaultwright.py recovery` and verify the checklist matches the manifest states;
- restore a curated note from Git;
- run no-data scan and lint after recovery.

Stage 1B adds recovery gates for journal replay, missed-event reconciliation, stale-lock recovery,
duplicate event delivery, crash after mirror write but before checkpoint, and full-sync recovery
after journal loss. The current replay path covers interrupted `processing` events and explicit
failed-event retry; the current explicit reconciliation path queues missed create, update, delete,
move, and review-required candidate events; the current `watch --once` path runs deterministic
startup reconciliation, feed queueing, and replay; manifest-backed deleted events now mark records
`source_missing` while retaining generated mirrors. Continuous native watch delivery and broader
move/recreate lifecycle automation remain open.

The test suite now exercises the copied-vault regeneration path, source-byte preservation,
converter-failure, Office mirror-write-failure, and repo-note write-failure recovery that preserve
the prior generated file, interrupted-write temp detection, conversion-race aborts that preserve
the prior mirror, `source_missing`, `manual_modification`, lint, and generated-text no-data scan
checks on the Northwind example. Example regeneration tests also assert source bytes stay unchanged
across plan, dry-run, sync, status, and lint operations, and that stable generated outputs remain
unchanged across a second sync.
Operator backup/restore drills and full copied-vault no-data scans on pilot vaults are still
required before production use.
