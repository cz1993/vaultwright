# Vaultwright V1 Progress Audit — 2026-06-23 / 2026-06-24

This audit maps the current implementation to the canonical `docs/VAULTWRIGHT_WHITEPAPER.md`,
`docs/adr/0001-profile-driven-v1-architecture.md`,
`docs/adr/0002-journaled-incremental-materialization.md`, and
`docs/V1_FINISH_LINE.md`.

## 2026-06-24 Architecture Adoption

Current checkpoint before Phase A: `main` was at
`004a3617f15e8234a056b8b1711b139ebe9b8e2f` with no tracked modifications, the two June 24
steering drafts untracked, and the latest `main` CI run green.

Phase A adopts the June 24 white paper as the canonical white paper, moves the dated copy to
`docs/revisions/`, and adds ADR 0002 for journaled incremental materialization. The current code
does not implement Stage 1B yet: `watch`, `sync --changed`, `sync --full`, `journal status`,
`journal replay`, and `reconcile` remain V1-C10 targets. Stage 2 and Stage 3 implementation
evidence remains preserved, but those lanes are paused behind Stage 1B in the execution order.

## 2026-06-25 Stage 1B Journal Foundation

This checkpoint starts Stage 1B with the smallest V1-C10 foundation slice. Package-owned
`vaultwright.changes.events` and `vaultwright.changes.journal` now define the local journal event
vocabulary, create `.vaultwright/state.sqlite`, persist event state transitions, and expose
read-only status payloads. The package CLI exposes `vaultwright journal status` with optional
`--init` and `--json` flags. The root, template, packaged-template, and example `.gitignore` files
ignore `.vaultwright/`, and the no-data scanner skips local derived state during ordinary scans
while blocking force-staged `.vaultwright/` files.

This is intentionally not a watcher, reconciler, replay engine, changed-file sync path, or
materialization worker. No Stage 2+ profile, Obsidian, index, Explorer, package-part diffing, cloud
adapter, embedding, model-lifecycle, enrichment, or visualization work is started by this
checkpoint. Architectural compatibility with journaled incremental materialization is preserved:
the journal is source-addressable, local derived state is excluded from source control, full sync
remains the baseline/recovery path, and status output reports queue/sequence/worker state without
becoming a retrieval index.

## 2026-06-25 Stage 1B Feed and Fingerprint Foundation

This checkpoint adds the deterministic trigger-feed and fast-candidate-fingerprint layer for
V1-C10 without adding a native watcher dependency. `vaultwright.changes.feed` defines a replaceable
feed interface, a static test feed, shared filtering for generated Office/repo mirrors, local
`.vaultwright/` state, operational/template paths, Office lock files, and atomic-write temporary
files, plus deterministic coalescing before journal queueing. `vaultwright.changes.fingerprint`
records path, existence, file/symlink state, size, nanosecond mtime, and filesystem identity hint
as a cheap token, and exposes a testable helper that does not call the full-hash function when the
token is unchanged.

This remains a foundation slice. It does not start native filesystem watching, debounce/settle
timers, source-addressable materialization, changed-source workers, reconciliation, replay, worker
locking, performance benchmarking, or any Stage 2+ lane. Architectural compatibility is preserved:
watcher delivery remains advisory, ignored paths are derived through existing runtime profile and
mirror helper APIs, and unchanged fingerprints can short-circuit full hashing before later worker
integration.

## 2026-06-25 Stage 1B Lease and Claim Foundation

This checkpoint adds the journal worker-coordination layer needed before a changed-source worker can
materialize events safely. `vaultwright.changes.journal` now supports workspace-scoped lease
acquisition and release, active-holder enforcement, stale-lease recovery, transactional event
claiming, claimed-event finish checkpoints, failed-event retry, and recovery of events left in
`processing` after an interrupted worker. `vaultwright journal status` now distinguishes active
locks from stale leases in human-readable output and JSON status.

This is still not a materialization worker, replay command, reconciler, native watcher, or changed
sync command. No source files are modified by the new journal primitives, and the existing full-sync
path remains the baseline/recovery path. Architectural compatibility with journaled incremental
materialization is preserved: SQLite transactions protect event claims and checkpoints, stale locks
can be taken over, and interrupted `processing` events can be returned to the queue instead of being
lost.

## 2026-06-25 Stage 1B Source-Addressable Office Materialization Foundation

This checkpoint adds the worker-facing Office materialization primitive without adding a worker,
replay command, reconciler, native watcher, or changed sync command. `vaultwright.changes.materialize`
accepts one vault-relative source path and delegates source identity, profile-aware domain routing,
profile-defined mirror roots, lifecycle transitions, annotation policy, atomic writes,
source-change-during-conversion checks, manifest updates, and audit events to the existing
package-owned Office mirror engine.

This preserves the Stage 1B architecture: the journaled path does not introduce a second mirror
engine, and full sync remains the baseline/recovery path. Focused tests prove that one requested
source materializes without converting unrelated sources, unchanged sources skip conversion through
the existing planning semantics, source bytes remain unchanged during normal materialization, and
profile-specific Office mirror roots are honored.

## 2026-06-25 Stage 1B File-Stability Foundation

This checkpoint adds deterministic source-settling checks for changed-source candidates without
adding a native watcher or real-time correctness dependency. `vaultwright.changes.stability` polls
the existing metadata fingerprint until it remains unchanged for a configurable settle interval or
until a bounded timeout expires. The helper accepts injectable fingerprint, clock, and sleeper
functions so tests do not depend on OS notification timing or wall-clock sleeps.

The source-addressable Office materialization primitive can now opt into this settle check before
planning, hashing, converting, or writing. If the candidate keeps changing until timeout, it returns
`skipped:unstable-source` without conversion, manifest writes, audit writes, mirror writes, or
source mutation. This preserves the existing post-conversion source-hash safeguard and adds the
pre-conversion stability gate needed before worker integration.

## 2026-06-25 Stage 1B Changed-Source Worker Foundation

This checkpoint wires the first changed-source worker path without adding watcher delivery, replay
CLI, reconciliation, changed sync, or benchmarks. `vaultwright.changes.worker` acquires the
workspace lease, claims one queued/ready event transactionally, runs source-addressable Office
materialization for current-path events, records materialized source ID/hash back onto the finished
journal row, and finishes the event as `applied`, `review-required`, or `failed`.

The worker remains deliberately bounded. Unsupported current paths and no-current-path events such
as deletes finish as `review-required`; materialization errors finish as `failed` so existing
failed-event retry can return them to the queue. Focused tests cover one supported event, unsupported
source review, delete/no-current-path review, converter failure and retry, active-lease contention,
and draining multiple ready events under one lease.

## 2026-06-25 Stage 1B Journal Replay Foundation

This checkpoint adds the idempotent replay path for recoverable journal work without starting
watcher delivery, reconciliation, changed sync, native watch capture, benchmarks, or broader
delete/move handling. `vaultwright.changes.replay` acquires the workspace lease, recovers events
left in `processing`, optionally requeues failed events only when requested, and then drains
claimable events through the existing `vaultwright.changes.worker` materialization path under that
single lease.

The package CLI exposes `vaultwright journal replay` with a process-scoped holder by default,
optional `--holder`, `--retry-failed`, `--max-events`, `--lease-ttl-seconds`, and `--json`.
Focused tests cover interrupted-worker replay, explicit failed-event retry, repeated idempotent
replay, active-lease contention, argument validation, and JSON CLI output for a review-required
unsupported source.

## 2026-06-25 Stage 1B Explicit Reconciliation Foundation

This checkpoint adds explicit source/manifest reconciliation without adding native watcher startup,
changed sync, benchmark measurement, or broader delete/move lifecycle automation.
`vaultwright.changes.reconcile` discovers current Office/PDF candidates through the existing
Office mirror scanner, compares current source metadata against `_meta/source-manifest.json`, and
queues missed journal events for created, modified, moved, deleted, or ambiguous review-required
candidate work. It records `last_reconciliation_at` in the local journal state and avoids queuing a
duplicate event when an unresolved matching event already exists.

The reconciliation pass stays metadata-first. It does not full-hash unchanged or metadata-changed
known paths; it hashes only suspicious new paths whose size matches missing manifest records so a
same-hash move can preserve source identity in a `moved` event. Focused tests cover no-op
reconciliation, missed create, missed metadata update, missing-source delete, candidate-only move
hashing, duplicate unresolved-event suppression, and `vaultwright reconcile --json`.

## 2026-06-25 Stage 1B Changed Sync Foundation

This checkpoint adds the first `sync --changed` command path without starting native filesystem
watching, benchmark measurement, or broader delete/move lifecycle automation.
`vaultwright.changes.changed_sync` composes explicit reconciliation and journal replay: it queues
missed source/manifest events, then processes claimable journal work through the existing
lease-protected worker and source-addressable materialization primitive. Plain `vaultwright sync`
continues to run the existing full Office/repo sync path, and `vaultwright sync --full` names that
baseline/recovery path explicitly.

Focused tests cover a changed-sync pass that reconciles, materializes one changed source, preserves
source bytes, and updates the journal checkpoint; a second unchanged changed-sync pass that queues
nothing and does not convert; `vaultwright sync --changed --json` on a review-required legacy
source; and rejecting changed-sync-only JSON/options unless `--changed` is selected.

## 2026-06-25 Stage 1B Watch Startup Foundation

This checkpoint adds deterministic watch startup orchestration without adding continuous native
filesystem watching, benchmark measurement, or broader delete/move lifecycle automation.
`vaultwright.changes.watch` runs one explicit watch cycle: optional startup reconciliation,
normalized/coalesced feed-event queueing through the existing change-feed interface, and journal
replay through the existing lease-protected worker and source-addressable materialization path.
`vaultwright watch --once` exposes that one-cycle path; plain `vaultwright watch` exits with
guidance instead of pretending continuous native delivery is implemented.

Focused tests cover startup reconciliation that discovers and materializes a missed source, an
injected static feed with repeated events and temporary Office lock-file filtering that produces
one replayed conversion, `vaultwright watch --once --json` on a review-required legacy source, and
the guarded plain `watch` command message.

## 2026-06-25 Stage 1B Deleted Source Lifecycle Foundation

This checkpoint adds manifest-backed deleted-source replay without adding continuous native
filesystem watching, benchmark measurement, or broader move/recreate lifecycle automation.
`vaultwright.changes.materialize.materialize_office_delete` applies one missing-source event using
the existing Office manifest semantics: it marks the matching record `source_missing`, retains the
generated mirror for operator review, writes the source manifest, and appends audit evidence.
`vaultwright.changes.worker` routes `deleted` journal events with a previous path through that
source-addressable delete primitive; deleted events without matching manifest evidence still
require review.

Focused tests cover the delete materializer, the lease-protected worker path, and
`vaultwright sync --changed` after a previously synced source is removed. They verify that the
source manifest reaches `source_missing`, the retained mirror remains on disk, and the journal
event finishes as applied work instead of generic review-required work.

## 2026-06-25 Stage 1B Move and Recreate Lifecycle Foundation

This checkpoint closes the bounded Stage 1B move/recreate replay path without adding continuous
native filesystem watching or benchmark measurement. Reconciliation now treats a `source_moved`
manifest record whose previous generated mirror has been removed as replayable changed-source
work. That lets the safe move sequence complete in two changed-sync passes: first block while the
old mirror exists, then create the new generated mirror with the same source ID after the operator
removes or archives the old mirror.

Focused tests cover that full move sequence through `vaultwright.changes.changed_sync`, including
stable source-ID preservation, previous-source-path history, old-mirror review blocking, and
returning the manifest record to `clean` after the new mirror is generated. They also cover
delete/recreate of the same source path returning the record from `source_missing` to `clean`.

## 2026-06-26 Stage 1B Benchmark Evidence

This checkpoint adds deterministic synthetic benchmark evidence without adding continuous native
filesystem watching or any Stage 2+ work. `scripts/benchmark_journaled_materialization.py` builds a
temporary synthetic vault with 1,000 source records, replays a known-path event batch containing
one ten-event save storm, one move, and one deletion, and records structural metrics in
`docs/JOURNALED_MATERIALIZATION_BENCHMARK.md`.

The recorded 1,000-source run queued 3 events after coalescing 12 observations, processed 3 events,
applied 2, left the moved source in expected review state while the previous mirror existed, made
0 discovery calls, enumerated 0 paths through discovery, read/hashed 0 untouched source bodies,
hashed 301 bytes across 3 source-body reads, invoked the converter once, and completed without
failed events. A focused test runs the same harness with a smaller corpus and asserts the
structural pass conditions.

## 2026-06-26 Stage 1B Optional Native Watch Capture

This checkpoint adds optional continuous native watch capture without changing default
dependencies or starting Stage 2+ work. `vaultwright.changes.native_watch` maps watchdog file
events into advisory `ObservedChange` records, observes only existing profile/legacy content roots,
ignores directories and outside paths, and buffers events behind a thread-safe handler.
`vaultwright watch --native` starts the optional watchdog observer, flushes captured events through
the existing feed/coalescing/replay path, and supports bounded `--cycles` for controlled runs.

The optional `vaultwright[watch]` extra supplies `watchdog`; default installs still use only the
existing required dependency set. Focused tests cover content-root selection, event normalization,
directory/outside-path rejection, `watch --once`, plain watch mode guidance, and actionable
`vaultwright[watch]` install guidance when native capture is requested without the extra.

## 2026-06-26 Stage 1B Gate Closure

This checkpoint closes the Stage 1B V1-C10 gate without starting Stage 2+ work. The journaled
changed-file path now has durable local state, feed filtering/coalescing, cheap metadata
fingerprints, source-addressable materialization through the existing Office mirror engine,
file-stability settling, lease-protected event claiming, idempotent replay, explicit
reconciliation, changed-sync orchestration, deterministic watch startup, optional native capture,
deleted/moved/recreated lifecycle replay, and recorded synthetic benchmark evidence.

Gate validation passed after the optional native capture batch:

- focused watch/feed tests: 23 passed;
- affected Stage 1B and safety-adjacent tests: 422 passed;
- full repository suite: 469 passed;
- Python compile checks, template-copy drift check, template lint, shell syntax checks,
  `git diff --check`, no-data scan, built-wheel smoke, optional-extra metadata check, and residue
  check: OK.

The first no-data scan during the packaging gate correctly caught generated
`src/vaultwright.egg-info` residue from wheel building; the residue was removed and the final
no-data and residue checks passed. No architectural conflict was found with journaled incremental
materialization. Stage 2 profile work, Obsidian adapter work, index, Explorer, adapters, model
enrichment, reports, and visualizations remain outside this completed goal.

## 2026-06-25 Stage 1A Profile-Assumption Inventory

This checkpoint closes the first Stage 1A evidence gap by inventorying the remaining hard-coded
profile vocabulary across package code, copied-tool shims, templates, examples, and tests. The
verification used targeted `rg` searches for legacy/default constants, business profile IDs,
profile folder names, mirror roots, repo-note paths, context keys, status values, mirror note
types, generated views, and benchmark task paths across `src/vaultwright`, `template`,
`examples`, and `tests`.

| Surface | Remaining occurrence class | Classification | Stage 1A disposition |
| --- | --- | --- | --- |
| Package runtime fallbacks: `src/vaultwright/runtime_profile.py`, `src/vaultwright/lint.py`, `src/vaultwright/mirrors/office.py`, `src/vaultwright/mirrors/github_repos.py`, and `src/vaultwright/profile_migration.py` | Legacy content roots, repo-note path, context keys/aliases, inactive statuses, generated mirror statuses, mirror mode/root, and profile-less lint defaults remain as fallback constants. | Legacy compatibility fallback | Allowed only when a profile/config is missing, invalid, or absent. New Stage 1B journal code must call the shared runtime profile helpers instead of copying these constants. |
| Package mirror/runtime identities: Office source mirror handling, GitHub repo mirror handling, annotation sidecars, generated sentinel checks, lifecycle state names, and managed metadata keys | `source-mirror`, `repo-mirror`, source/repo manifests, annotation sidecars, lifecycle event labels, and generated-mirror metadata remain named in package code. | Universal invariant | Keep as mirror-layer artifact semantics. If a future profile renames machine-owned note types, it must pass through the profile role helpers rather than changing journal authority rules. |
| Package profile and adapter limits: `src/vaultwright/cli.py`, `src/vaultwright/profiles.py`, `src/vaultwright/views.py`, `src/vaultwright/benchmark.py`, `src/vaultwright/pilot.py`, and `src/vaultwright/sandbox.py` | Official profiles are scaffolded by package-owned init; `Documents.base` remains the only generated view renderer; `_meta/agent-readiness-tasks.yml` remains the default task-pack fallback. | Adapter capability and legacy compatibility fallback | Not a Stage 1A defect. Stage 2 now owns official profile fixtures; Stage 3 owns broader generated view support; benchmark defaults stay fallback behavior behind profile-declared task packs. |
| Copied vault-local tools under `template/tools` and packaged copies under `src/vaultwright/template/tools` | Executable scripts import package modules and pass the copied vault root; profile vocabulary appears in README/operator examples and `repos.example.yml`. | Compatibility shim plus business profile data | Shim posture is acceptable. Implementation logic remains package-owned; the `business-operations` compatibility template remains the flagship copied template while package init can scaffold the other official profiles from contracts. |
| Template, packaged template, built-in profiles, and example vaults | Business folders, statuses, context fields, mirror roots, repo-note paths, and generated views are present in `_meta/profile.yml`, template docs, synthetic example notes, and public-data example fixtures. | Business profile data and sample/test fixture | Allowed. These are profile/template facts, not kernel assumptions, and are covered by template-copy, example regeneration, lint, and no-data gates. |
| Test suite | Hard-coded folders, statuses, context fields, mirror paths, repo-note paths, and generated view names appear throughout `tests/test_*`. | Test fixture and legacy compatibility coverage | Allowed when asserting the business profile, fallback compatibility, or mirror safety behavior. Add non-business profile fixtures in Stage 2 instead of weakening existing safety tests. |
| Defects found in this batch | No package occurrence was verified as a Stage 1A-blocking defect during this inventory. | None | No code fix was required in this atomic batch. Future removals should target only non-universal runtime defects proven by this inventory or by new failing multi-profile tests. |

Architectural compatibility with journaled incremental materialization: no conflict was found. The
journaled Stage 1B path must stay source-addressable and profile-aware by depending on the same
runtime profile helpers and mirror artifact semantics already inventoried here; it must not create
a second set of business-folder, mirror-root, repo-note, or status constants.

## 2026-06-25 Stage 1A Closure

Stage 1A is closed for the current V1 execution order. The closure is scoped: it proves the kernel
and profile-convergence gate is satisfied before Stage 1B starts, not that later official-profile,
Obsidian, index, Explorer, or release-pilot work has resumed.

| Gate item | Closure evidence |
| --- | --- |
| Package modules authoritative | `vaultwright` CLI commands dispatch to package-owned modules; copied `template/tools/*.py` and packaged template tool copies import package modules and pass the copied vault root as compatibility shims. |
| Profile-derived runtime values | Lint, catalog, migration, Office sync, GitHub repo sync, benchmark, pilot, sandbox, recovery, Microsoft 365 handoff, review-ledger, generated views, and annotation migration use validated profile contracts or shared runtime profile helpers, with legacy fallbacks only for profile-less compatibility. |
| Invalid profile data blocked | `src/vaultwright/profiles.py` validates schema version, safe identifiers, safe paths, folder plans, policy defaults, context aliases, source-authority defaults, and no-real-data defaults before runtime paths, sync, lint, reports, or migration use profile data. |
| Legacy override posture clear | `_meta/domain-map.yml` and `_meta/mirror-config.yml` remain documented as legacy alias/config override layers; valid `_meta/profile.yml` is the canonical profile contract. |
| Mirror and annotation safety | Fresh Office/repo mirrors are machine-owned, sync blocks unmigrated above-sentinel annotations, annotation sidecars preserve human notes, and lint blocks unmigrated mirror annotations. |
| Remaining profile assumptions | The inventory above classifies remaining hard-coded vocabulary as universal mirror-layer invariant, business profile/template data, legacy compatibility fallback, or test fixture; no Stage 1A-blocking defect was verified. |
| Journaled materialization compatibility | No architectural conflict was found. Stage 1B must reuse existing profile helpers and mirror materialization semantics instead of adding new business-folder, mirror-root, repo-note, context, or status constants. |

Local closure validation for this batch:

- `pytest -q -p no:cacheprovider`: 398 passed.
- `python -m compileall -q src template/tools scripts tests` with bytecode redirected outside the
  repo: OK.
- `scripts/no_data_scan.py`: OK.
- `scripts/sync_template_copies.py --check`: clean.
- `PYTHONPATH=src template/tools/lint_vault.py`: OK.
- `bash -n scripts/init.sh`, `bash -n template/tools/sync_all.sh`, and
  `bash -n .githooks/pre-commit`: OK.
- `git diff --check`: OK.
- no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, `__pycache__`, or `*.pyc` residue remains in
  the repo.

## Integrity Baseline

- Local branch started clean and synced with `origin/main`.
- Latest remote CI before this slice was green for `f70dad9`.
- Dependency check used an external temporary Python 3.12 virtual environment, not a repo-local
  `.venv`, with `pytest`, `pyyaml`, and `markitdown[docx,pptx,xlsx]`.
- Local validation after the first execution slice:
  - `pytest -p no:cacheprovider`: 256 passed.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - regenerated both example vaults in a temp directory, then no-data scanned and linted them: OK.
  - no `.venv`, `.pytest_cache`, `__pycache__`, or `*.egg-info` artifacts remain in the repo.
- Local validation after the profile-aware report/recovery slice:
  - focused profile/report, lifecycle, release-workflow, template-copy, packaged-template, and
    affected sync-behavior tests: OK.
  - `pytest -p no:cacheprovider -q`: 281 passed.
  - `python3.11 -m py_compile` over template tools, package modules, and release scripts: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - focused wheel install smoke ran copied `m365_report.py`, `recovery_report.py`,
    `sandbox_report.py`, and `review_ledger.py` against an installed wheel: OK.
  - no `__pycache__` residue remains in the repo.
- Local validation after copied-tool shim convergence:
  - focused packaged-template, lifecycle, catalog, conversion, migration, overlap, benchmark, and
    pilot tests: OK.
  - `pytest -p no:cacheprovider -q`: 282 passed.
  - `python3.11 -m py_compile` over template tools, package modules, and release scripts with
    bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - focused wheel install smoke ran copied catalog, conversion, migration, overlap, benchmark,
    pilot, m365, recovery, sandbox, and review-ledger scripts against an installed wheel: OK.
  - no `build/`, `dist/`, `.egg-info`, or `__pycache__` residue remains in the repo.
- Local validation after operator-wrapper shim convergence:
  - focused packaged-template and wrapper root-default tests: OK.
  - `pytest -p no:cacheprovider -q`: 283 passed.
  - `python3.11 -m py_compile` over template tools, package modules, and release scripts with
    bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - fresh wheel install smoke ran copied `tools/vaultwright.py doctor` from another working
    directory and copied `tools/vaultwright.py --root ... plan` against an initialized vault: OK.
  - copied `tools/vaultwright.py` delegates to the package CLI while preserving its own vault as
    default `--root` when invoked from another working directory.
  - no `build/`, `dist/`, `.egg-info`, or `__pycache__` residue remains in the repo.
- Local validation after folder-plan contract hardening:
  - focused profile contract and profile migration tests: OK.
  - affected profile-driven report and release-workflow tests: OK.
  - `pytest -p no:cacheprovider -q`: 289 passed.
  - `python3.11 -m py_compile` over template tools, package modules, and release scripts with
    bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - fresh wheel install smoke ran `init --profile business-operations`, `profile validate`,
    `profile migrate --plan --json`, and `profile migrate --write --json` for a missing
    `folder_plan` directory: OK.
  - no `build/`, `dist/`, `.egg-info`, or `__pycache__` residue remains in the repo.
- Local validation after profile-aware overlap calibration:
  - focused profile-driven overlap and copied-wrapper overlap tests: OK.
  - affected profile-driven report, overlap, and pilot tests: OK.
  - `pytest -p no:cacheprovider -q`: 290 passed.
  - `python3.11 -m py_compile` over template tools, package modules, and release scripts with
    bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - fresh wheel install smoke ran `overlap --json` against profile-defined `25_research` notes:
    OK.
  - no `build/`, `dist/`, `.egg-info`, or `__pycache__` residue remains in the repo.
- Local validation after profile-aware benchmark task discovery:
  - focused profile-contract and profile-driven benchmark/pilot tests: OK.
  - affected profile-contract, profile-driven report, sync-behavior, benchmark, and pilot tests:
    175 passed.
  - `pytest -p no:cacheprovider -q`: 294 passed.
  - `python3.11 -m py_compile` over template tools, package modules, and release scripts with
    bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - fresh wheel install smoke, built with `pip wheel --no-deps`, ran `benchmark --json` and
    `pilot --json` against a profile-declared `_meta/research-agent-readiness-tasks.yml` pack:
    OK.
  - no `build/`, `dist/`, `.egg-info`, or `__pycache__` residue remains in the repo.
- Local validation after profile-derived repo context frontmatter:
  - focused profile-driven repo-context sync/lint/annotation test: OK.
  - affected profile-driven report, annotation migration, lint, and sync-behavior tests:
    205 passed.
  - `pytest -p no:cacheprovider -q`: 295 passed.
  - `python3.11 -m py_compile` over template tools, package modules, and release scripts with
    bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - fresh wheel install smoke, built with `pip wheel --no-deps`, ran `sync`, `lint`, and
    `migrate annotations --plan --json` against a profile-declared repo context field set:
    OK.
  - no `build/`, `dist/`, `.egg-info`, or `__pycache__` residue remains in the repo.
- Local validation after profile-aware overlap context links:
  - focused profile-driven overlap, lint-overlap, copied-wrapper overlap, and package overlap tests:
    17 passed.
  - `pytest -p no:cacheprovider -q`: 296 passed.
  - `python3.11 -m py_compile` over template tools, package modules, and release scripts with
    bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - fresh wheel install smoke, built with `pip wheel --no-deps`, ran `overlap --json` against a
    profile-declared `research_project` frontmatter link and confirmed legacy `account` links did
    not count when the active profile omitted that context field: OK.
  - no `build/`, `dist/`, `.egg-info`, or `__pycache__` residue remains in the repo.
- Local validation after profile-owned status roles:
  - focused profile-contract, profile-driven report, lint-overlap, and packaged-overlap tests:
    48 passed.
  - `pytest -p no:cacheprovider -q`: 299 passed.
  - `python3.11 -m py_compile` over template tools, package modules, and release scripts with
    bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - fresh wheel install smoke, built with `pip wheel --no-deps`, confirmed `overlap --json`
    excludes only profile-declared inactive statuses and `profile views --write` emits
    `Documents.base` attention filters from `attention: true`: OK.
  - no `build/`, `dist/`, `.egg-info`, or `__pycache__` residue remains in the repo.
- Local validation after profile-owned generated mirror status defaults:
  - focused profile-contract, profile-driven report, and sync-behavior tests: 187 passed.
  - `pytest -p no:cacheprovider -q`: 306 passed.
  - `python3.11 -m py_compile` over changed package modules: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
  - `git diff --check`: OK.
- Local validation after profile-owned Office mirror placement defaults:
  - focused profile-contract, Office sync, and lint tests: 7 passed.
  - affected profile-contract, sync-behavior, and lint-vault test files: 230 passed.
  - `pytest -p no:cacheprovider -q`: 312 passed.
  - `python3.11 -m py_compile` over template tools, package modules, and release scripts with
    bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
- Local validation after active Office mirror root reporting:
  - focused configured-mirror-root report test: 1 passed.
  - affected profile-driven report file: 18 passed.
  - affected profile-driven report plus sync-behavior files: 157 passed.
  - `pytest -p no:cacheprovider -q`: 313 passed.
  - `python3.11 -m py_compile` over template tools, package modules, and release scripts with
    bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
- Local validation after active Office mirror root benchmark validation:
  - focused configured-mirror-root benchmark test: 1 passed.
  - focused profile-driven report plus benchmark sync-behavior tests: 23 passed.
  - affected profile-driven report plus sync-behavior files: 158 passed.
  - `pytest -p no:cacheprovider -q`: 314 passed.
  - `python3.11 -m py_compile` over template tools, package modules, and release scripts with
    bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
- Local validation after profile-first Office source-domain routing:
  - focused profile-domain Office routing regression plus existing alias-routing tests: 3 passed.
  - affected profile-driven report plus lint files: 75 passed.
  - affected sync-behavior file: 140 passed.
  - `pytest -p no:cacheprovider -q`: 315 passed.
  - `python3.11 -m py_compile` over template tools, package modules, and release scripts with
    bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
- Local validation after profile vocabulary identifier hardening:
  - focused profile-contract tests: 40 passed.
  - affected profile-contract, profile-driven report, lint, and packaged-template tests:
    117 passed.
  - `pytest -p no:cacheprovider -q`: 320 passed.
  - `python3.11 -m py_compile` over template tools, package modules, and release scripts with
    bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after profile repo-mirror folder default hardening:
  - focused profile-contract tests: 44 passed.
  - affected profile-contract, profile-driven report, lint, and sync-behavior tests: 259 passed.
  - `pytest -p no:cacheprovider -q`: 324 passed.
  - `python3.11 -m py_compile` over template tools, package modules, and release scripts with
    bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
- Local validation after profile artifact path hardening:
  - focused profile-contract tests: 48 passed.
  - affected profile-contract, profile-driven report, packaged-template, and example tests:
    76 passed.
  - `pytest -p no:cacheprovider -q`: 328 passed.
  - `python3.11 -m py_compile` over template tools, package modules, and release scripts with
    bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after profile source-authority/no-real-data policy hardening:
  - focused profile-contract tests: 52 passed.
  - affected profile-contract, profile-driven report, packaged-template, and example tests:
    80 passed.
  - `pytest -p no:cacheprovider -q`: 332 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after unique/non-overlapping domain folder hardening:
  - focused profile-contract tests: 54 passed.
  - affected profile-contract, profile-driven report, packaged-template, and example tests:
    82 passed.
  - `pytest -p no:cacheprovider -q`: 334 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after disjoint frontmatter property hardening:
  - focused profile-contract tests: 55 passed.
  - affected profile-contract, profile-driven report, packaged-template, and example tests:
    83 passed.
  - `pytest -p no:cacheprovider -q`: 335 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after nested profile definition field hardening:
  - focused profile-contract tests: 61 passed.
  - affected profile-contract, profile-driven report, packaged-template, and example tests:
    89 passed.
  - `pytest -p no:cacheprovider -q`: 341 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after profile-owned context alias policy:
  - focused profile-contract, lint, sync-behavior, and example tests: 271 passed.
  - `pytest -p no:cacheprovider -q`: 348 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
- Local validation after strict folder-plan and policy-default fields:
  - focused profile-contract tests: 68 passed.
  - affected profile-contract, profile-driven report, packaged-template, and example tests:
    96 passed.
  - `pytest -p no:cacheprovider -q`: 350 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after annotation-migration context alias handling:
  - focused annotation-migration tests: 5 passed.
  - affected annotation-migration, profile-driven report, and sync-behavior tests: 165 passed.
  - `pytest -p no:cacheprovider -q`: 351 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after profile-owned review artifact classification:
  - focused profile-driven report tests: 20 passed.
  - affected profile-driven report, sync-behavior, and packaged-template tests: 163 passed.
  - `pytest -p no:cacheprovider -q`: 352 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after catalog machine-owned Markdown inventory:
  - focused profile-driven catalog/machine-owned tests: 5 passed.
  - affected profile-driven report and sync-behavior catalog tests: 31 passed.
  - `pytest -p no:cacheprovider -q`: 353 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after Microsoft 365 machine-owned Markdown inventory:
  - focused profile-driven m365/catalog tests: 2 passed.
  - focused sync-behavior m365/handoff tests: 3 passed.
  - affected profile-driven report, sync-behavior report-surface, and packaged-template tests:
    44 passed.
  - `pytest -p no:cacheprovider -q`: 354 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after sandbox machine-owned Markdown inventory:
  - focused profile-driven sandbox/catalog/m365 tests: 3 passed.
  - focused sync-behavior sandbox tests: 3 passed.
  - affected profile-driven report, sync-behavior report-surface, and packaged-template tests:
    45 passed.
  - `pytest -p no:cacheprovider -q`: 355 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after profile migration mirror-root planning:
  - focused profile migration/mirror-root tests: 9 passed.
  - full profile-contract tests: 69 passed.
  - affected profile/report package smoke tests: 23 passed, 2 deselected.
  - `pytest -p no:cacheprovider -q`: 356 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after pilot active mirror-root inventory:
  - focused profile-driven pilot/benchmark mirror-root tests: 2 passed, 21 deselected.
  - full profile-driven report tests: 23 passed.
  - affected sync-behavior pilot/benchmark/recovery tests: 27 passed, 114 deselected.
  - `pytest -p no:cacheprovider -q`: 356 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after recovery active mirror-root source-evidence preflight:
  - focused profile-driven recovery mirror-root tests: 2 passed, 22 deselected.
  - full profile-driven report tests: 24 passed.
  - affected sync-behavior recovery/mirror-root tests: 9 passed, 132 deselected.
  - `pytest -p no:cacheprovider -q`: 357 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after profile artifact mirror-root separation:
  - focused profile artifact/mirror-root contract tests: 8 passed, 65 deselected.
  - full profile-contract tests: 73 passed.
  - `pytest -p no:cacheprovider -q`: 361 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after generated Base attention-role fallback removal:
  - focused profile view-generation tests: 3 passed, 71 deselected.
  - profile views CLI/migration touchpoint tests: 3 passed, 71 deselected.
  - full profile-contract tests: 74 passed.
  - `pytest -p no:cacheprovider -q`: 362 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after profile-declared doctor view reporting:
  - focused doctor preflight tests: 10 passed, 133 deselected.
  - focused profile view/check/write tests: 5 passed, 69 deselected.
  - template-copy drift regression checks after syncing example README copies: 2 passed.
  - `pytest -p no:cacheprovider -q`: 364 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after profile-contract-first doctor required-file posture:
  - focused doctor preflight tests: 13 passed, 133 deselected.
  - `pytest -p no:cacheprovider -q`: 367 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after profile-first migration runbook/worksheet guidance:
  - focused migration report tests: 5 passed, 20 deselected.
  - `pytest -p no:cacheprovider -q`: 368 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after profile-contract-first lint domain-map posture:
  - focused lint tests: 58 passed.
  - `pytest -p no:cacheprovider -q`: 369 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after profile-validator-backed lint contract loading:
  - focused lint profile/domain-map tests: 10 passed, 49 deselected.
  - `pytest -p no:cacheprovider -q`: 370 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after validator-backed runtime profile helper loading:
  - focused profile-contract/runtime helper tests: 76 passed.
  - affected profile/report/sync tests: 68 passed, 103 deselected.
  - targeted invalid-profile fixture regressions: 6 passed, 246 deselected.
  - `pytest -p no:cacheprovider -q`: 372 passed.
  - `python3.11 -m py_compile` over template tools, package modules, release scripts, and tests
    with bytecode redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after validator-backed catalog/migration profile domain routing:
  - focused profile-driven catalog/migration/domain tests: 10 passed, 17 deselected.
  - `pytest -p no:cacheprovider -q`: 374 passed.
  - `python -m py_compile` over template tools, package modules, scripts, and tests with bytecode
    redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh`, `bash -n template/tools/sync_all.sh`, and
    `bash -n .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after validator-backed benchmark/pilot task discovery:
  - focused profile-driven benchmark/pilot tests: 5 passed, 24 deselected.
  - affected profile-driven report tests: 29 passed.
  - affected copied-wrapper benchmark/pilot tests: 23 passed, 123 deselected.
  - `pytest -p no:cacheprovider -q`: 376 passed.
  - `python -m py_compile` over template tools, package modules, scripts, and tests with bytecode
    redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh`, `bash -n template/tools/sync_all.sh`, and
    `bash -n .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after profile-aware Office source-mirror frontmatter ordering:
  - focused Office sync profile/frontmatter-order tests: 3 passed, 144 deselected.
  - affected Office/profile context tests: 53 passed, 94 deselected.
  - affected profile-driven report context tests: 6 passed, 23 deselected.
  - `pytest -p no:cacheprovider -q`: 377 passed.
  - `python -m py_compile` over template tools, package modules, scripts, and tests with bytecode
    redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh`, `bash -n template/tools/sync_all.sh`, and
    `bash -n .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.
- Local validation after contract-owned context aliases and profile-aware repo frontmatter ordering:
  - focused runtime profile, lint context-alias, and repo-frontmatter tests: 10 passed.
  - full profile-contract tests: 78 passed.
  - full lint tests: 60 passed.
  - full sync-behavior tests: 149 passed.
  - `pytest -p no:cacheprovider -q`: 382 passed.
  - `python -m py_compile` over template tools, package modules, scripts, and tests with bytecode
    redirected outside the repo: OK.
  - `scripts/no_data_scan.py`: OK.
  - `scripts/sync_template_copies.py --check`: clean.
  - `PYTHONPATH=src template/tools/lint_vault.py`: OK.
  - `bash -n scripts/init.sh`, `bash -n template/tools/sync_all.sh`, and
    `bash -n .githooks/pre-commit`: OK.
  - `git diff --check`: OK.
  - no `build/`, `dist/`, `.egg-info`, `.pytest_cache`, or `__pycache__` residue remains in the repo.

## Whitepaper Progress

Stage 0 is complete: the product statement, seven-layer architecture, fixed v1 profile list,
non-goals, journaled incremental architecture, ADRs, and finish-line matrix are tracked.

Stage 1 is now split into Stage 1A and Stage 1B. Stage 1A is closed by the inventory and closure
evidence above: remaining profile assumptions are either universal, profile-owned, compatibility
fallbacks, or fixtures, and no inventory-confirmed blocking defect is known. Stage 1B is closed by
the V1-C10 implementation and gate evidence above.

| Requirement | Status |
| --- | --- |
| V1-C1 package-owned runtime | Closed for Stage 1A. Package CLI exists; `plan`, `sync`, `status`, `doctor`, `catalog`, `lint`, `conversion`, `m365`, `migration`, `overlap`, `benchmark`, `pilot`, `sandbox`, `recovery`, and `review` are package-owned; Office mirror planning/sync/status lives in `vaultwright.mirrors.office`; GitHub repo mirror planning/sync/status lives in `vaultwright.mirrors.github_repos`; copied sync, lint, catalog, conversion, m365, migration, overlap, benchmark, pilot, sandbox, recovery, review-ledger, and operator-wrapper scripts are compatibility shims. |
| V1-C2 versioned profile contract | Closed for Stage 1A. Schema validation, schema documentation, read-only profile commands, conservative write-mode profile migration, profile-generated `Documents.base` check/write support, validator-backed catalog/migration domain routing, validator-backed benchmark/pilot task discovery, profile-driven migration domain routing, profile-owned Office mirror placement defaults, profile-first Office source-domain routing, profile-aware source/repo-mirror frontmatter ordering, profile/config-aware Office mirror report surfaces, profile-owned repo mirror defaults, profile-owned generated mirror status defaults, profile/config-aware repo mirror report surfaces, profile-derived repo context frontmatter, contract-owned context aliases in repo sync/lint/annotation migration without profile-ID inference, shared profile-derived frontmatter key ordering for generated Office/GitHub mirrors, profile-owned machine-owned note type roles in overlap/migration/review classification plus catalog, Microsoft 365, and sandbox inventory counts, profile-owned status roles without generated-Base name inference, profile-owned source-authority/no-real-data policy defaults, profile-declared generated-view doctor reporting, profile-contract-first doctor required-file posture, profile-contract-first lint domain-map posture, profile-validator-backed lint contract loading, validator-backed runtime profile helpers, shared active-content-root fallback across lint/catalog/overlap/repo mirror validation, lint, GitHub repo sync, and annotation migration shared profile helper usage without local repo-context fallback copies, profile-first migration runbook/worksheet guidance, safe profile vocabulary identifiers, schema-declared nested definition fields, schema-declared folder-plan and policy-default fields, safe disjoint frontmatter property validation, safe profile artifact paths, safe unique non-overlapping domain-folder validation, safe profile artifact/mirror-root separation, validated `folder_plan` paths/domains, safe profile repo-mirror folder defaults, safe profile benchmark-task paths, profile-aware migration mirror-root planning, profile-aware benchmark generated-mirror roots, profile-aware pilot workspace inventory, profile-aware recovery source-evidence preflight, profile-aware overlap content roots/context links/inactive statuses, profile-declared benchmark task discovery, and the classified profile-assumption inventory exist; remaining profile expansion belongs to later gated stages. |
| V1-C3 official profiles | Closed for Stage 2. `business-operations`, `research-learning`, `software-project`, and `blank` validate, are exposed through `vaultwright profile list/show`, and initialize through package-owned `vaultwright init --profile <id>`; non-business profiles derive starter folders, generated scaffold docs, matching domain maps, and template selection from their profile contracts without inheriting business folders or note templates. Synthetic Office-source smoke fixtures now exercise lifecycle, sync, status, and lint behavior for each initialized profile without committing a real/private corpus. |
| V1-C4 safe migration path | Closed for Stage 1A. Reports, frontmatter-domain normalization, read-only plans, and conservative write-mode profile migration exist; migration reports now use profile-defined canonical domains with domain-map aliases, and profile migration creates directories from validated `folder_plan` records plus the target profile's Office mirror root without overwriting sources, mirrors, annotation sidecars, or drifted existing files. Broader workspace/profile migration coverage remains tied to later profile expansion. |
| V1-C5 machine-owned mirrors | Stage 1 closed by this batch. Fresh mirrors are machine-owned, sync blocks unmigrated mirror annotations, sidecar-aware sync rewrites migrated mirrors as machine-owned, and lint blocks unmigrated annotations. |
| V1-C10 journaled changed-file materialization | Closed for Stage 1B. Package-owned journal event/state modules, `.vaultwright/state.sqlite` initialization, `vaultwright journal status`, `.vaultwright/` ignore posture, no-data staged blocking, deterministic feed queueing, generated/local/operational/temp path filtering, repeated-event coalescing, cheap metadata fingerprints, no-full-hash-on-unchanged-fingerprint tests, workspace leases, stale-lease recovery, transactional event claims, claimed-event finish checkpoints, failed-event retry, interrupted-`processing` recovery, a source-addressable Office materialization primitive, deterministic file-stability settling, lease-protected current-path Office worker processing, manifest-backed deleted-event replay to `source_missing`, resolved `source_moved` replay after old-mirror cleanup, delete/recreate replay back to `clean`, idempotent `vaultwright journal replay`, explicit `vaultwright reconcile`, `vaultwright sync --changed`/`--full`, deterministic `vaultwright watch --once` startup/feed/replay orchestration, optional watchdog-backed `vaultwright watch --native` capture, synthetic benchmark evidence, and focused/affected/full safety gate evidence now exist. |

Stage 3 has one preparatory slice: package-owned `profile views --check/--write` generates the
current profile's `Documents.base` without requiring Obsidian. Governance skills, Canvas outputs,
and the broader Obsidian adapter gate remain open. Stages 4, 5, and 6 have not started and should
remain gated until the Obsidian/profile-view gate is intentionally reopened.

## Remaining Execution Plan

1. Stage 1B is closed:
   - journaled changed-file materialization is mapped to V1-C10;
   - full sync remains the baseline and recovery path;
   - benchmark evidence is recorded instead of claiming performance from design alone.
2. Continue Stage 3 only in a new, explicitly bounded batch or goal:
   - optional Obsidian adapter checks;
   - profile-aware Bases/Canvas outputs;
   - governance skill packaging.
3. Hold Stage 4 index and Stage 5 Explorer work until Stage 3 is intentionally complete. The index must earn
   v1 scope through benchmark improvement.

## Next Recommended Slice

Stage 1A and Stage 1B are closed. The Stage 1B V1-C10 slices prove local derived state location,
schema creation, basic status introspection, ignore/no-data posture for `.vaultwright/`, event
state persistence, deterministic feed queueing, path filtering, event coalescing, and cheap
fingerprint-based full-hash avoidance, plus lease-protected event claiming, stale-lock recovery,
failed-event retry, interrupted-processing recovery, and source-addressable Office
materialization through the existing mirror engine without starting profile/content expansion.
Deterministic file-stability settling now exists for candidate
materialization, the first lease-protected worker path now processes current-path Office events,
and `vaultwright journal replay` now performs idempotent interrupted-work recovery plus explicit
failed-event retry. Explicit `vaultwright reconcile` now queues missed source/manifest work with
metadata-first comparison and candidate-only hashing for same-hash move detection.
`vaultwright sync --changed` now composes reconciliation and replay, while `vaultwright sync --full`
names the full-sync recovery path explicitly. `vaultwright watch --once` now provides deterministic
startup reconciliation/feed queueing/replay, and optional `vaultwright watch --native` provides
watchdog-backed event capture over configured content roots. Synthetic benchmark evidence now
proves known-path replay over 1,000 sources avoids whole-workspace discovery and untouched-source
hashing. The current pursuing goal ends at this Stage 1B gate; future work should start a new
explicitly bounded batch and should not automatically start profile, Obsidian, index, Explorer,
adapter, enrichment, report, or visualization work from this goal.
