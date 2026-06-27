# Codex Mega Prompt — Converge Vaultwright to Profile-Driven V1 with Journaled Incremental Materialization

Paste this prompt into Codex while it is opened at the root of `cz1993/vaultwright`.

---

You are the principal engineer, architecture steward, test owner, and release-convergence lead for **Vaultwright**.

Your job is not to brainstorm indefinitely. Your job is to move the repository from its current HEAD to the finite v1 finish line defined by the current architecture documents, while preserving all existing source-integrity, lifecycle, recovery, profile, safety, packaging, and evidence gates.

## Mission

Converge Vaultwright into:

> **A profile-driven, governed knowledge-workspace compiler with journaled changed-file materialization, optional Obsidian views, and an evidence-gated index/Explorer path.**

The immediate execution lane is:

1. finish the remaining **Stage 1A kernel/profile convergence** work;
2. implement and close **Stage 1B journaled changed-file synchronization**;
3. only then proceed to the official profiles and later stage gates.

Do not start package-part Office diffing, semantic-delta AI, cloud change feeds, or the visual Explorer during Stage 1A or Stage 1B.

## Resolve Current Reality First

Do not trust the commit hash embedded in this prompt as current.

At the start:

1. Resolve the actual current branch, HEAD SHA, worktree state, and remotes.
2. Read the repository before editing.
3. Identify uncommitted changes and preserve them.
4. Do not overwrite user work.
5. Do not touch real client data, private dogfood vaults, OneDrive sources, or any path outside temporary test directories unless explicitly authorized.
6. Do not push, publish a release, or modify external systems unless explicitly authorized.

Read these files first, when present:

```text
README.md
CHANGELOG.md
CONTRIBUTING.md
pyproject.toml
docs/VAULTWRIGHT_WHITEPAPER.md
docs/revisions/VAULTWRIGHT_WHITEPAPER_2026-06-24.md
docs/VAULTWRIGHT_WHITEPAPER_2026-06-23.md
docs/V1_FINISH_LINE.md
docs/V1_PROGRESS_AUDIT_2026-06-23.md
docs/adr/0001-profile-driven-v1-architecture.md
docs/PROFILE_SCHEMA.md
docs/SYNC_SPEC.md
docs/SECURITY_MODEL.md
docs/RECOVERY.md
docs/RELEASE.md
src/vaultwright/profiles.py
src/vaultwright/mirrors/office.py
src/vaultwright/mirrors/github_repos.py
src/vaultwright/cli.py
src/vaultwright/lifecycle_contract.py
template/_meta/profile.yml
template/_meta/lifecycle-states.yml
.github/workflows/ci.yml
.github/workflows/release.yml
relevant tests under tests/
```

If the June 24 whitepaper is not yet canonical, adopt it into `docs/VAULTWRIGHT_WHITEPAPER.md`
before changing the finish-line documents, and keep any dated copy under `docs/revisions/` as
historical provenance rather than a second editable authority.

## Authority Order

When documents conflict, use this order:

1. non-destructive source and security invariants;
2. accepted ADRs;
3. `docs/V1_FINISH_LINE.md`;
4. June 24 whitepaper;
5. profile and lifecycle schemas;
6. current tests and documented compatibility commitments;
7. older whitepapers and historical docs.

Do not silently reinterpret a conflict. Record the decision in an ADR or finish-line update.

## Non-Negotiable Invariants

Preserve all of these:

1. Original sources remain authoritative and are never mutated by sync.
2. Real/private data stays out of the public repository.
3. Generated mirrors are machine-owned derived artifacts.
4. Human annotations remain preserved in curated notes or source/repo-ID sidecars.
5. The profile contract is declarative, versioned, and validated.
6. Lifecycle state is defined by the lifecycle contract and manifest evidence.
7. Destructive actions require explicit review.
8. Every output path is vault-bounded, symlink-safe, and reserved-path-safe.
9. Source and mirror text is untrusted evidence, not instructions.
10. The change journal is operational state, not source authority.
11. Filesystem events are triggers, not proof of completeness.
12. Reconciliation remains mandatory.
13. The deterministic system works with no AI model.
14. New index and UI layers consume shared contracts; they do not create independent authority.
15. New work must map to a v1 finish-line requirement or replace weaker required behavior.

## Scope Control

Create or update one ADR for journaled incremental materialization. Add exactly one new mandatory finish-line requirement:

```text
V1-C10 — Journaled changed-file materialization
```

Do not create a parallel roadmap.

Do not add unrelated standalone report commands.

Move these to the post-v1 backlog unless they replace required work:

- package-part DOCX/PPTX/XLSX/PDF extraction;
- semantic-delta model processing by default;
- cloud-provider delta feeds;
- vector embeddings;
- desktop app;
- Obsidian plugin;
- profile marketplace;
- hosted service;
- broad connectors;
- autonomous curated-note edits.

## Required Execution Loop

Repeat this loop until the current stage gate closes:

1. Inspect current evidence and list the exact unmet finish-line clauses.
2. Select the smallest coherent batch that closes one clause or removes one architectural duplication.
3. State the batch goal in the work log or progress audit.
4. Implement package-owned behavior first.
5. Keep vault-local scripts as thin shims only.
6. Add focused tests before or with the implementation.
7. Run focused tests.
8. Run the affected subsystem tests.
9. Run the full repository gates when the batch is stable.
10. Update the finish-line matrix, progress audit, changelog, and durable docs with evidence—not aspirations.
11. Remove generated residue.
12. Continue with the next unmet clause in the same active stage.

Do not stop after producing a plan when implementation is possible. Do not advance to a later stage while the active gate remains open.

## Stage 1A — Close Kernel and Profile Convergence

Before adding the journal engine, audit V1-C1, V1-C2, V1-C4, and V1-C5 against the current code.

### Required Stage 1A work

1. Enumerate remaining hard-coded profile vocabulary in package code:
   - domains and folders;
   - note types;
   - statuses and status roles;
   - required and optional properties;
   - mirror roots and repository note locations;
   - view assumptions;
   - benchmark task paths;
   - source policy defaults.
2. Classify each occurrence as:
   - universal core invariant;
   - profile-owned value;
   - legacy compatibility mapping;
   - defect.
3. Remove or profile-drive every non-universal runtime assumption required by V1-C2.
4. Keep `_meta/domain-map.yml` only as a documented legacy alias/migration layer where already intended.
5. Keep package modules authoritative and compatibility scripts minimal.
6. Preserve annotation migration and machine-owned mirror behavior.
7. Keep source-authority/no-real-data profile policy checks strict.

### Stage 1A exit evidence

Stage 1A is closed only when:

- the remaining profile-dependent behavior is explicitly accounted for;
- package runtime owns all required behavior;
- compatibility shims contain no independent implementation;
- profile validation, migration, mirror, lint, catalog, recovery, review, benchmark, and example tests pass;
- the full repository suite and safety gates pass;
- the finish-line matrix records evidence and no vague “remaining behavior” placeholder that can be concretely resolved remains.

If Stage 1A is already closed by current HEAD, prove it from code/tests/docs and advance directly to Stage 1B.

## Stage 1B — Journaled Changed-File Materialization

### Design goal

After an initial baseline, changing one source should normally:

- enqueue one logical change;
- avoid whole-vault recursive discovery on the event-processing path;
- avoid reading or hashing untouched source bodies;
- hash the candidate source;
- convert it at most once after the file settles;
- atomically update its mirror and manifest evidence;
- invalidate only related derived artifacts;
- checkpoint the event as applied;
- remain recoverable through replay and reconciliation.

### Do not claim literal database WAL shipping

Ordinary filesystems and Office files do not provide semantic transactions. Implement the useful properties:

- durable ordered event journal;
- at-least-once delivery;
- idempotent application;
- checkpoints;
- retries;
- atomic materialization;
- startup and scheduled reconciliation;
- explicit full-sync recovery.

### Proposed package boundaries

Prefer package-owned modules resembling:

```text
src/vaultwright/changes/__init__.py
src/vaultwright/changes/journal.py
src/vaultwright/changes/models.py
src/vaultwright/changes/coalesce.py
src/vaultwright/changes/reconcile.py
src/vaultwright/changes/watcher.py
src/vaultwright/changes/worker.py
src/vaultwright/locking.py
```

Adapt names to the current package architecture; do not create duplicate abstractions that already exist.

### State location

Use a private local state directory:

```text
.vaultwright/state.sqlite
```

Requirements:

- excluded from Git and package examples;
- verified by `doctor` or equivalent preflight;
- no source or mirror bodies in the initial schema;
- relative paths only where practical;
- safe permissions where supported;
- rebuildable from sources, manifests, and reconciliation;
- SQLite transactions; WAL mode is acceptable for local durability;
- schema version and migration support.

Update no-data and ignore behavior carefully. Do not weaken the repository scanner’s general protection merely to accommodate the state database. Permit the exact derived-state location through explicit policy and tests.

### Minimum schema

Implement the equivalent of:

```sql
change_events(
    sequence INTEGER PRIMARY KEY,
    event_key TEXT UNIQUE,
    event_type TEXT NOT NULL,
    source_id TEXT,
    path TEXT,
    previous_path TEXT,
    observed_at TEXT NOT NULL,
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    error_detail TEXT
);

source_state(
    source_id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    filesystem_id TEXT,
    size INTEGER,
    mtime_ns INTEGER,
    source_sha256 TEXT,
    extractor TEXT,
    extractor_version TEXT,
    config_version TEXT,
    last_observed_sequence INTEGER,
    last_applied_sequence INTEGER
);

journal_meta(
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Normalize and constrain states in code. Include schema migrations from the beginning, even when only version 1 exists.

### Event types

Support:

```text
created
modified
moved
deleted
metadata_changed
reconcile_required
```

### Event states

Support an explicit state machine equivalent to:

```text
queued
coalesced
stabilizing
fingerprinted
extracting
materialized
applied
ignored
deferred
review_required
failed_retryable
failed_terminal
```

Do not store free-form status strings throughout the code without centralized validation.

### Event identity and replay

- Generate a stable event key from workspace identity, event type, normalized paths, and observed fingerprint/version data.
- Duplicate delivery must not produce duplicate destructive effects.
- A crash before `applied` leaves replayable work.
- A crash after mirror write but before checkpoint must replay idempotently by comparing current mirror/manifest/source evidence.
- Use at-least-once semantics; do not claim exactly-once.

### Source-addressable mirror API

Refactor the existing Office mirror implementation so the worker can process one explicitly supplied source without rediscovering the vault.

Required separation:

```text
plan_source(root, source_path, ...)
materialize_source(root, source_path, ...)
reconcile_sources(root, ...)
full_sync(root, ...)
```

Use current naming if equivalent APIs already exist.

Preserve all existing checks:

- symlink/source-boundary validation;
- mirror output safety;
- source hashing;
- source-changed-during-conversion detection;
- managed-frontmatter validation;
- lifecycle contract metadata;
- annotation-sidecar protection;
- move/conflict behavior;
- atomic mirror write;
- audit event generation;
- manifest stability.

Do not bypass `plan_one`/`sync_one` safety by writing a fast but weaker path. Refactor shared logic instead.

### Change-feed adapter

Create an interface that can accept:

- native/local filesystem events;
- explicit test/CLI events;
- later provider-specific events.

Use a small cross-platform watcher dependency only if needed. Pin and document it. Keep the watcher behind the adapter interface so tests do not require native event delivery.

The v1 watcher must:

- monitor configured source roots only;
- ignore generated mirrors, local state, metadata, tools, templates, caches, and known temporary files;
- normalize paths through existing safety policy;
- coalesce repeated events;
- request reconciliation when event loss/overflow is reported;
- never treat watcher completeness as guaranteed.

### Debounce and settle

Implement configurable defaults approximately equivalent to:

```yaml
change_capture:
  debounce_ms: 1500
  settle_interval_ms: 500
  settle_checks: 3
  max_settle_seconds: 30
  reconcile_on_start: true
  reconcile_interval_hours: 24
```

Before conversion:

1. wait for debounce;
2. sample size and `mtime_ns`;
3. require the configured number of stable samples;
4. hash;
5. convert;
6. hash again;
7. reject the materialization if the source changed during conversion.

Ten rapid modifications before processing should normally yield one conversion of the latest stable state.

### Fast fingerprint

Use metadata only as a fast filter:

```text
relative path
filesystem identifier/inode when available
size
mtime_ns
```

Rules:

- fingerprint unchanged → no content hash;
- fingerprint changed → full SHA-256;
- SHA unchanged → metadata/move handling only;
- SHA changed → materialize.

Filesystem identifiers are hints. Manifest-owned source IDs remain durable identity.

### Moves and deletes

Reuse and strengthen current lifecycle semantics:

- moved source with clear identity → preserve source ID and require existing move safety rules;
- ambiguous same-byte move → review/conflict, never guess;
- deletion → mark source missing and retain generated evidence for review;
- recreate after delete → reconcile against source identity and history;
- no automatic destructive mirror deletion.

### Reconciliation

Implement metadata-first reconciliation that compares:

- configured source roots;
- source manifest;
- journal source state;
- expected mirror paths;
- current mirror existence and managed metadata.

Reconciliation should:

- avoid full content hashing when fingerprints are unchanged;
- enqueue events for discovered drift;
- detect missed creates, modifications, moves, and deletes;
- detect stale journal/source-state records;
- support startup and explicit invocation;
- provide a full recovery path when consistency cannot be established.

### Locking and concurrency

- One materialization worker per workspace.
- Add a workspace lock with PID/process metadata and stale-lock recovery.
- Use SQLite transactions around claiming and updating events.
- Never hold a database transaction open during slow conversion.
- Claim work, release the DB transaction, convert, then transactionally record the result.
- Tests must prove a second worker does not process the same event concurrently.

### CLI convergence

Add or converge toward:

```text
vaultwright watch
vaultwright sync --changed
vaultwright journal status
vaultwright journal replay
vaultwright reconcile
vaultwright sync --full
```

Requirements:

- machine-readable JSON where consistent with current CLI conventions;
- meaningful nonzero exits for review-blocking and failed states;
- concise operator output;
- no new standalone report command for each journal statistic;
- compatibility behavior documented.

### Derived invalidation

On successful materialization, update/invalidate only related data:

- source manifest record;
- mirror;
- audit event;
- catalog freshness;
- review-ledger freshness for the changed artifact;
- evidence-index records when Stage 4 exists;
- curated-note review candidates, without modifying curated notes.

Use stable IDs and journal sequence/source hash evidence.

## Lightweight Model — Explicitly Deferred in Stage 1B

Do not add an AI dependency to the journal or mirror worker.

You may define an interface or ADR note for a future proposal-only semantic-delta assistant, but do not implement model loading, prompts, provider integrations, or automatic note edits in Stage 1B.

Future admission criteria:

- receives changed chunks only;
- bounded context;
- output tied to source ID/hash/journal sequence;
- proposals only;
- measurable reduction in review effort or better stale-note detection;
- no lifecycle authority.

## Mandatory Tests for V1-C10

Add focused unit/integration tests covering at least:

1. initial baseline records source state;
2. unchanged fingerprint performs no source-body read/hash;
3. one changed source performs one full hash and at most one conversion;
4. repeated rapid events coalesce;
5. temporary Office lock files are ignored;
6. source changes during conversion and mirror is not written;
7. move preserves stable identity when unambiguous;
8. ambiguous same-byte move becomes review/conflict;
9. delete marks source missing and retains mirror;
10. delete/recreate reconciles safely;
11. duplicate event delivery is idempotent;
12. crash before materialization replays;
13. crash after mirror write but before checkpoint replays without corrupting output;
14. watcher restart resumes from journal;
15. simulated missed event is discovered by reconciliation;
16. simulated queue overflow requests reconciliation;
17. stale lock can be recovered safely;
18. two workers do not process one event concurrently;
19. full sync remains correct after journal loss;
20. annotation sidecars remain intact;
21. source bytes remain unchanged;
22. unsafe/symlink/reserved paths remain rejected;
23. journal state is excluded from repository data scans and packaging through narrow explicit rules;
24. package wheel and template compatibility paths work.

Instrument tests with fake hashers/converters/read counters where needed. Do not rely only on wall-clock timing.

## Performance Benchmark

Create a deterministic synthetic benchmark, not a private corpus, with at least:

- 1,000 eligible source records;
- mixed sizes and representative supported extensions;
- one modified source;
- one save storm;
- one move;
- one deletion.

Measure and report:

```text
paths enumerated
files opened
source bodies read
bytes hashed
converter invocations
events received
events coalesced
events applied
elapsed time
peak memory when practical
```

Structural pass conditions:

- known-path event processing performs no whole-vault `rglob`/equivalent discovery;
- untouched source bodies are not read or hashed;
- one settled changed source causes at most one converter call;
- clean replay produces no content or manifest drift;
- reconciliation repairs intentionally omitted events.

Do not make a fragile wall-clock percentage the only gate. Record measured deltas honestly.

## Documentation and Control Files

For each completed batch, update as applicable:

```text
docs/VAULTWRIGHT_WHITEPAPER.md
docs/revisions/VAULTWRIGHT_WHITEPAPER_2026-06-24.md
docs/V1_FINISH_LINE.md
docs/V1_PROGRESS_AUDIT_2026-06-23.md or a dated successor
docs/adr/0002-journaled-incremental-materialization.md
docs/SYNC_SPEC.md
docs/SECURITY_MODEL.md
docs/RECOVERY.md
docs/PROFILE_SCHEMA.md
docs/quickstart.md
README.md
CHANGELOG.md
```

Add `V1-C10` to the mandatory core finish line. Update the Stage-Gate Plan so Stage 1B closes before Stage 2 starts.

Do not claim completion without code and test evidence.

## Validation Commands

Adapt to repository conventions and available Python, but the final batch should run the equivalent of:

```bash
python3.11 -m pytest -p no:cacheprovider -q
python3.11 scripts/no_data_scan.py
python3.11 scripts/sync_template_copies.py --check
PYTHONPATH=src python3.11 template/tools/lint_vault.py
python3.11 -m py_compile <all package, template shim, script, and test modules>
bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit
git diff --check
python3.11 -m build
# install built wheel in a clean temporary environment and run release smoke paths
```

Also run all new journal/reconcile focused tests and the synthetic performance benchmark.

Never leave build, test-cache, SQLite state, mirror, manifest, audit, or benchmark residue in the repository unless a fixture is explicitly approved and provenance-safe.

## Stage Advancement Rules

### Advance from Stage 1A to Stage 1B only when

- current Stage 1 profile/kernel gaps are closed or concretely proven closed;
- full gates pass;
- finish-line evidence is updated.

### Advance from Stage 1B to Stage 2 only when

- V1-C10 exit criteria pass;
- full sync remains a valid recovery path;
- no model is required;
- no package-part extraction has entered the critical path;
- full repository gates pass.

### Advance from Stage 2 to Stage 3 only when

- all four official profiles initialize from the same package;
- no profile vocabulary is hard-coded in core;
- identical lifecycle and safety gates pass.

### Advance from Stage 3 to Stage 4 only when

- Obsidian is optional;
- profile Bases/Canvas outputs are valid;
- no plugin is required.

### Stage 4 binding decision

Build the index on applied journal events and benchmark it.

- If it materially improves context precision, citation quality, reviewer correction effort, or tool-call count, select the v1 Explorer path.
- If it does not, remove index/Explorer from the release-critical path and close v1 Core without them.
- Do not iterate indefinitely to force a pass.

### Stage 6 release rule

Run exactly one external pilot for each maintained content profile. All three must exercise baseline, changed-file sync, watcher downtime/reconciliation, recovery, and source-backed handoff.

After the selected v1 finish line is met, stop feature work, resolve release defects, publish, and collect evidence.

## Completion Report Required From You

At the end of each Codex session or coherent implementation batch, report:

1. current HEAD and worktree status;
2. active stage and finish-line IDs addressed;
3. files changed and why;
4. behavior implemented;
5. tests and validation commands run with exact results;
6. benchmark results when relevant;
7. source/security invariants verified;
8. remaining gaps in the active stage only;
9. whether the stage gate is objectively closed;
10. the exact next smallest batch.

Do not provide a vague roadmap. Do not list later-stage ideas unless needed to explain a gate. Do not claim production readiness from tests alone.

## Final Finish Line

The mandatory v1 Core finish line is:

1. package-owned cross-platform runtime;
2. versioned profile contract;
3. four official starters: business operations, research/learning, software project, blank;
4. safe profile/workspace migration;
5. machine-owned mirrors with annotation sidecars;
6. journaled changed-file synchronization with replay and reconciliation;
7. profile-aware catalogs, Bases, and Canvas;
8. optional Obsidian governance skills;
9. three external profile pilots;
10. tagged release with upgrade, recovery, security, benchmark, limitations, and support documentation.

Index, exploration MCP, and visual Explorer are included only if the Stage 4 benchmark gate passes.

Drive the work to one of those terminal outcomes. Do not leave the project in a permanently expanding pre-release state.

---
