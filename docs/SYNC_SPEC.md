# Sync Specification

## Objective

Vaultwright sync must prove the core product promise: source files remain untouched while generated
knowledge artifacts can be regenerated, audited, and reviewed.

Full sync is the current implemented baseline and remains the recovery/verification path. Stage 1B
adds journaled changed-file materialization as the normal future steady-state path: event-identified
candidate sources are fingerprinted, hashed only when needed, materialized through the same
package-owned mirror logic, and reconciled against authoritative sources because watcher events are
not authoritative.

Journaled incremental materialization is tracked as V1-C10 in `docs/V1_FINISH_LINE.md` and
specified by `docs/adr/0002-journaled-incremental-materialization.md`. The current runtime has the
local journal/state foundation plus deterministic feed filtering, event coalescing, and cheap
metadata fingerprint primitives, plus lease-protected event claims and interrupted-worker recovery.
It also has a source-addressable Office materialization primitive that processes one vault-relative
source through the existing Office mirror engine instead of creating a second mirror writer, plus
deterministic file-stability settling before conversion and a lease-protected worker path for
current-path Office events, plus idempotent journal replay that recovers interrupted processing
events and optionally retries failed events under the same worker lease, plus explicit
reconciliation that queues missed source/manifest events with metadata-first comparison and
candidate-only hashing for safe move detection. `vaultwright sync --changed` composes
reconciliation and replay, while `vaultwright sync` and `vaultwright sync --full` preserve the full
sync recovery path. `vaultwright watch --once` runs the deterministic watch-start cycle: startup
reconciliation, feed-event queueing, and journal replay. `docs/JOURNALED_MATERIALIZATION_BENCHMARK.md`
records synthetic known-path replay evidence. `vaultwright watch --native` provides optional
watchdog-backed native event capture through the same feed/replay boundary.

## Source Identity

Path-based mirror names are user-friendly but insufficient as the durable identity model. Office
mirror sync maintains `_meta/source-manifest.json` with stable source IDs. Repo mirror sync
maintains `_meta/repo-manifest.json` with stable repo IDs derived from configured repo/note
identity.

The future change journal may store paths, fingerprints, hashes, event states, and checkpoints, but
it does not replace manifest-owned source identity or lifecycle state.

Each source record should include:

- stable source ID;
- current source path;
- previous source paths;
- mirror path;
- source file size;
- source hash;
- normalized extracted-content hash;
- converter name and version;
- sync configuration version;
- lifecycle state;
- lifecycle contract path and schema version;
- last successful sync timestamp;
- warnings, omissions, and errors.

Current implementation status:

- implemented for Office mirrors: stable source IDs, current/previous source paths, mirror path,
  source hash/size, converter/config version, lifecycle state, warnings/errors, source-missing
  marking, non-mutating plan/status reports, sensitive-name warnings, duplicate-byte warnings, and
  format-specific conversion-quality warnings, plus contract-backed lifecycle next-action guidance in plan/status
  output, and post-conversion source hash checks that abort mirror writes if the source changes
  while conversion is running, plus mirror-root-change conflict detection when the old generated
  mirror still exists, plus moved-source review blocking while the previous generated mirror still
  exists, plus update-path annotation-migration blocking tests, plus converter-failure and
  mirror-write-failure recovery tests that preserve the previous mirror and allow later clean
  regeneration, plus a read-only conversion spot-check report that turns manifest warnings,
  errors, lifecycle states, formats, and source/mirror existence into an operator review list, plus
  blocking lint checks for generated Office mirrors whose source bytes changed or whose manifest
  lifecycle state is no longer current, plus Office sync/status detection and repair for managed
  source frontmatter metadata drift, plus conservative `.xlsx` mirror cleanup for obvious `NaN`
  placeholders and empty `Unnamed:*` table columns, plus ambiguous same-hash move detection that
  blocks sync as `conflict` when multiple missing manifest records could match one new source, plus
  profile-first source-domain routing with `_meta/domain-map.yml` retained as a legacy alias layer;
- implemented for Stage 1B Office materialization: `vaultwright.changes.materialize` can process
  one vault-relative Office source through the same Office mirror planning/sync path, preserving
  source bytes, profile-defined mirror roots, manifest updates, audit events, and the existing
  source-change-during-conversion safeguard;
- implemented for Stage 1B candidate stability: `vaultwright.changes.stability` waits for the
  cheap metadata fingerprint to remain unchanged for a configurable settle interval, supports a
  bounded timeout, and can be injected into source-addressable materialization so unstable sources
  skip conversion and writes before worker integration;
- implemented for Stage 1B current-path Office worker processing:
  `vaultwright.changes.worker` acquires the workspace lease, claims queued/ready journal events,
  materializes supported current-path Office sources through `vaultwright.changes.materialize`,
  records source ID/hash on finished journal rows, and finishes unsupported/no-current-path events
  as review-required or materialization errors as failed;
- implemented for Stage 1B deleted-source lifecycle replay:
  manifest-backed `deleted` journal events with a previous source path are applied through
  `vaultwright.changes.materialize.materialize_office_delete`, marking the Office source manifest
  record `source_missing`, retaining the generated mirror for review, appending audit evidence,
  and finishing the journal event as applied; deleted events without matching manifest evidence
  still require review;
- implemented for Stage 1B move/recreate replay: `sync --changed` blocks unambiguous moved-source
  materialization while the previous generated mirror still exists, then reconciliation requeues
  the resolved `source_moved` record after that previous mirror is removed so replay can create the
  new mirror with the same source ID; delete/recreate of the same source path queues a metadata
  update and returns the manifest record to `clean`;
- implemented for Stage 1B journal replay: `vaultwright.changes.replay` and
  `vaultwright journal replay` recover interrupted `processing` events, optionally requeue failed
  events only when `--retry-failed` is requested, process claimable work through the existing
  worker/materialization path under one lease, and expose bounded/JSON replay results;
- implemented for Stage 1B explicit reconciliation: `vaultwright.changes.reconcile` and
  `vaultwright reconcile` discover current Office/PDF candidates through the existing mirror
  scanner, compare source metadata against `_meta/source-manifest.json`, queue missed creates,
  metadata-changed updates, missing-source deletes, and same-hash moves into the local journal,
  requeue resolved `source_moved` records after the previous generated mirror has been removed,
  avoid duplicate unresolved events, update `last_reconciliation_at`, and full-hash only
  suspicious new paths that can match missing manifest records;
- implemented for Stage 1B changed sync: `vaultwright.changes.changed_sync` and
  `vaultwright sync --changed` run explicit reconciliation and then replay claimable journal work
  through the existing worker/materialization path; plain `vaultwright sync` remains the existing
  full Office/repo sync path, and `vaultwright sync --full` names that recovery path explicitly;
- implemented for Stage 1B watch startup orchestration: `vaultwright.changes.watch` and
  `vaultwright watch --once` run startup reconciliation, queue normalized/coalesced feed events
  through the existing change-feed interface, and replay claimable journal work under the existing
  worker lease; plain `vaultwright watch` exits with mode guidance;
- implemented for Stage 1B optional native watch capture: `vaultwright.changes.native_watch` maps
  watchdog events to advisory `ObservedChange` records, watches only existing profile/legacy
  content roots, ignores directories and outside paths, buffers events under a thread-safe handler,
  and `vaultwright watch --native` flushes captured events through the same reconciliation, feed,
  coalescing, lease, replay, and source-addressable materialization path; the optional
  `vaultwright[watch]` extra supplies the watchdog dependency without changing default installs;
- implemented for Stage 1B benchmark evidence:
  `scripts/benchmark_journaled_materialization.py` builds a temporary synthetic vault with 1,000
  source records, replays a known-path event batch with one save storm, one move, and one deletion,
  and records paths enumerated, source bodies read, bytes hashed, converter invocations, event
  counts, elapsed time, and peak memory in `docs/JOURNALED_MATERIALIZATION_BENCHMARK.md`;
- implemented for repo mirrors: stable repo IDs, configured/resolved repo, note path, local-tree or
  remote HEAD hash, lifecycle state, warnings/errors, non-mutating plan/status reports, and
  generated-region manual-edit detection, plus contract-backed lifecycle next-action guidance in plan/status
  output, plus repo stub-to-populated tests that preserve configured generated frontmatter without
  carrying legacy in-mirror notes forward, plus repo-note write-failure recovery tests that preserve
  the previous note and allow later clean regeneration,
  plus config validation and blocking lint checks for duplicate configured repo note targets, plus
  blocking lint checks for configured repo entries whose expected generated note is missing or
  unmanaged, and for generated repo mirrors whose manifest lifecycle state is no longer current,
  whose frontmatter repo or commit drifts from the manifest, or whose local source tree changed,
  plus repo sync/status detection and repair for managed repo frontmatter identity drift, plus
  `repo_unconfigured` lifecycle reporting and lint blocking when a previously synced repo mirror is
  retained after its `tools/repos.yml` entry is removed;
- implemented for mirror-annotation migration: `vaultwright migrate annotations --plan` reports
  above-sentinel source/repo mirror annotations without printing their text, and `--write` stores
  them under `_meta/mirror-annotations/source/<source_id>.md` or
  `_meta/mirror-annotations/repo/<repo_id>.md` while leaving original sources and generated mirrors
  untouched; fresh Office and repo mirrors use machine-owned headers without a curated `## Notes`
  region; sync blocks unmigrated above-sentinel annotations as force-blocking review work and, after
  a matching sidecar exists, resets regenerated mirrors to a machine-owned header instead of
  preserving the migrated human annotation region in the mirror; lint blocks generated source/repo
  mirrors with unmigrated above-sentinel annotations so release gates force sidecar migration;
- implemented for lifecycle operator semantics: the template now includes
  `_meta/lifecycle-states.yml`, a machine-readable Office/repo state contract with entry
  conditions, user-visible explanations, permitted next actions, exit conditions, and
  manifest-state markers; sync plan/status guidance reads this contract, source/repo manifest
  records and audit events identify the contract path/schema version that governed the lifecycle
  state, `vaultwright doctor` validates the contract during preflight, and tests ensure sync/report
  states remain covered;
- partially implemented: full move/rename UX beyond unique hash matching and ambiguous-move
  conflict detection;
- not complete: full rename/move UX, rollback automation, automated conversion-quality scoring
  beyond private operator-entered result packs, and exhaustive conflict-resolution flows.

Human review decisions are recorded outside generated artifacts in `_meta/review-ledger.jsonl`.
The ledger stores artifact paths, hashes, reviewer/status fields, and short metadata notes. It does
not change source files, mirror bodies, manifests, or lifecycle states, but it lets operators detect
when a prior approval is stale because the reviewed artifact hash changed.

## Lifecycle States

Minimum states:

- `planned`
- `clean`
- `source_changed`
- `stale`
- `regenerated`
- `reviewed`
- `unsupported`
- `source_missing`
- `source_moved`
- `conflict`
- `manual_modification`
- `converter_changed`
- `error`

Every release-ready state must have:

- entry condition;
- user-visible explanation;
- permitted next actions;
- exit condition.

The authoritative machine-readable contract lives in `_meta/lifecycle-states.yml` in every
initialized vault. Sync plan/status guidance reads this contract and falls back to local concise
guidance only when a nonstandard or damaged vault is missing the contract. New lifecycle states
must be added to the contract and covered by tests before release.

## Rename, Move, and Delete Handling

- Rename/move should be detected by stable source ID and source hash where possible, not treated
  only as delete plus create.
- If a new source's bytes match multiple missing manifest records, sync must not choose a source
  history automatically. It should report `conflict` with the candidate paths so an operator can
  choose the correct history or treat the file as a deliberate duplicate/new source.
- If multiple non-synthetic manifest records claim the same current source path, sync must report
  `conflict` with the duplicate source IDs rather than choosing one manifest record silently.
- When a source move changes the generated mirror path, sync should not create the new mirror while
  the previous generated mirror still exists. The operator must preserve, move, archive, or remove
  the old mirror first so curated notes are not stranded and duplicate generated mirrors are not
  created.
- Source deletion should not delete mirrors automatically. It should mark the manifest record as
  `source_missing` and surface a review action.
- Repo config removal should not delete repo mirrors automatically. It should mark the manifest
  record as `repo_unconfigured` and surface a review action so the operator can restore the config
  entry, archive the mirror, or deliberately remove retired manifest state.
- Mirror path changes should be planned before writes and reported after writes.

## Conflict Rules

Sync must flag conflict when:

- the generated region was manually edited;
- a mirror exists at the target path but does not belong to the source ID;
- the configured mirror root changes and an old mirror still exists;
- a source's bytes match multiple missing manifest records and the correct move history is
  ambiguous;
- multiple non-synthetic manifest records claim the same current source path;
- source and curated note changes require human reconciliation;
- a previous sync failed after partial output.

## Transactional Writes

Mirror writes are atomic in the current Office and repo sync tools:

- write to a temporary file in the target directory;
- fsync or equivalent where practical;
- replace the prior mirror only after successful conversion and frontmatter generation;
- preserve previous mirror when conversion fails.
- preserve previous mirror when the mirror write fails before replacement.
- preserve previous mirror when the source bytes change during conversion, because the extracted
  text can no longer be tied safely to the planned source hash.

Sync should never leave half-written mirrors as successful output.
If an OS/process interruption leaves a hidden atomic temp file behind, `vaultwright recovery` must
surface it as `temp:interrupted_write` so the operator can rerun status/sync and remove the temp
file after backup review.

## Idempotency

A second sync with unchanged source bytes, unchanged converter/config version, and unchanged curated
region must produce no content diff.
The append-only `_meta/sync-audit.jsonl` log may receive new events; idempotency assertions should
compare stable generated mirrors, repo notes, and manifests separately from the audit log.

For Stage 1B, event replay must also be idempotent: duplicate or interrupted journal events must
not produce duplicate successful materialization or corrupt manifests/mirrors.

Current idempotency regression coverage includes:

- Office mirrors;
- the Office source manifest;
- repo mirrors;
- empty repo config;
- unsupported source;
- source lock file skip;
- alias-to-canonical mirror routing.

## Rollback and Audit

Every generated change should be explainable from:

- manifest before/after state;
- source hash;
- converter/config version;
- sync log entry;
- machine-readable `_meta/sync-audit.jsonl` event;
- output path.
- optional `_meta/review-ledger.jsonl` decision tied to the generated artifact hash.

Audit events must include the generated artifact path, lifecycle state, lifecycle contract
path/schema version when available, status, and structured `warnings` / `errors` copied from the
manifest record after the sync attempt. They must not include raw source content, extracted
document text, repo document bodies, secrets, or tokens.

Rollback guidance lives in `docs/RECOVERY.md` and must be tested before a public release.

## Original Source Integrity

Tests must prove that sync does not mutate original source bytes.

The release gate is byte-for-byte equality of source files before and after sync for representative
supported formats and skipped/unsupported files.
Example-vault regeneration tests should snapshot representative source payloads before plan,
dry-run, sync, status, and lint operations, then assert those payloads are unchanged.
They should also run a second sync and assert stable generated mirrors, repo notes, and manifests
remain byte-for-byte unchanged when inputs did not change.
