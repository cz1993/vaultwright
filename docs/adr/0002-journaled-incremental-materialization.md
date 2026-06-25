# ADR 0002: Journaled Incremental Materialization

**Status:** Accepted
**Date:** 2026-06-24
**Decision source:** `docs/VAULTWRIGHT_WHITEPAPER.md`
**Owner:** cz1993

## Context

Vaultwright already has package-owned full sync, source/repo manifests, machine-owned mirrors,
annotation sidecars, lifecycle contracts, safety gates, and profile-driven routing work. Normal
Office sync still has a structural steady-state cost: it discovers eligible sources and computes
content hashes for the corpus during planning before deciding most files are unchanged.

That is acceptable as a baseline and recovery path, but it is too expensive for larger or
frequently changing workspaces. A one-file edit should not repeatedly open and hash every other
source file before Vaultwright can update the one affected mirror.

Office files, PDFs, repositories, and ordinary filesystems do not provide a database write-ahead
log with semantic transactions. Filesystem events can be dropped, coalesced, duplicated, delayed,
or reported before a save is stable. Office applications and cloud sync tools can write through
temporary lock files or atomic replacement patterns. Vaultwright therefore cannot claim literal WAL
shipping.

It can adopt the useful operational properties of log shipping: durable ordered observations,
at-least-once replay, idempotent application, checkpoints, atomic replacement of derived read
models, and reconciliation against authoritative sources.

## Decision

Vaultwright v1 adds a mandatory Stage 1B requirement: **journaled changed-file materialization**.

After an initial baseline, normal steady-state operation should process event-identified candidate
sources instead of repeatedly scanning, opening, and hashing unchanged sources. Full sync remains
available and correct as the recovery, verification, and initial-baseline path.

The architecture has these authority boundaries:

- Original files and repositories remain authoritative.
- Existing source/repo manifests remain durable lifecycle records.
- Generated mirrors remain disposable materialized read models.
- Curated notes remain human-governed.
- The change journal is derived operational delivery state, not source authority.
- Any future evidence index consumes applied journal events and remains disposable.

The local journal uses a private derived-state database such as `.vaultwright/state.sqlite`. It may
use SQLite WAL mode for local transaction durability, but it must not contain source or mirror
bodies. It may contain relative paths, event metadata, retry state, timestamps, fingerprints,
hashes, checkpoints, and lock/lease records. The state directory must be excluded from Git and
treated as rebuildable.

## Event Model

The journal records a monotonic sequence for observed work. Stage 1B must support equivalent event
kinds for:

- `created`
- `modified`
- `moved`
- `deleted`
- `metadata_changed`
- `reconcile_required`

It must support equivalent states for:

- `queued`
- `coalesced`
- `stabilizing`
- `fingerprinted`
- `extracting`
- `materialized`
- `applied`
- `ignored`
- `deferred`
- `review_required`
- `failed_retryable`
- `failed_terminal`

State validation must be centralized rather than scattered free-form strings. A crash before
`applied` leaves replayable work. Replaying already materialized work must be idempotent by
checking current source, manifest, mirror, and journal evidence before writing.

## Fingerprints and Hashing

Before computing a full source hash, Vaultwright compares cheap metadata:

- normalized relative path;
- filesystem identity hint where available;
- size;
- nanosecond modification time.

If the fingerprint is unchanged, normal event-driven processing does not open or fully hash the
source body. If the fingerprint changed, Vaultwright computes SHA-256. If the SHA-256 is unchanged,
it handles metadata or move evidence without conversion. If the SHA-256 changed, it runs the
existing deterministic materialization logic for that candidate.

Filesystem IDs are matching hints only. Manifest-owned source IDs remain durable identity.

## Debounce and File Stability

Event capture must not convert files while writes are still in progress. Stage 1B applies:

- path/event coalescing;
- a debounce interval;
- repeated size and modification-time stability checks;
- a bounded settle timeout;
- a source hash before conversion;
- a source hash after conversion;
- no mirror write if the source changed during conversion.

This reuses and preserves the current source-changed-during-conversion safeguard. Ten rapid save
notifications for one file should normally become one materialization of the latest stable source
state.

## Materialization Boundary

Stage 1B must not introduce a second mirror engine. Incremental processing calls package-owned
Office/repo planning and materialization primitives or extracts shared services from the current
implementation. Full sync and changed-file sync converge on the same logic for:

- source identity;
- profile routing;
- lifecycle transitions;
- mirror path safety;
- atomic writes;
- converter/version handling;
- annotation policy;
- manifest updates;
- audit events.

## Reconciliation and Replay

Watcher delivery is advisory. Vaultwright must reconcile at startup, on explicit command, and on a
schedule where configured. Reconciliation compares configured source roots, manifests, journal
source state, expected mirrors, and managed metadata.

Reconciliation is metadata-first. It hashes only suspicious candidates, enqueues events for missed
creates, updates, moves, deletes, and stale journal records, and can recover events left
`processing` or equivalent after a crash. Full sync remains the recovery path when reconciliation
cannot establish consistency.

Deletes do not automatically delete mirrors. Moves preserve stable identity only when unambiguous.
Ambiguous same-byte moves become review/conflict work rather than guesses. Recreated paths are
resolved against source identity and history.

## Concurrency and Locking

Only one materialization worker may apply events to a workspace at a time. Stage 1B uses a
workspace-scoped lock or lease with process metadata and stale-lock recovery. SQLite transactions
protect event claims and checkpoints. The worker must not hold a database transaction during slow
conversion: claim work transactionally, convert outside the transaction, then record results
transactionally.

Two workers must not silently process the same event concurrently, and process termination must not
permanently lose queued work.

## Security Posture

Every event path is untrusted input. Watcher or provider events cannot bypass existing vault-bound,
symlink-safe, reserved-path, source-boundary, mirror-output, profile-contract, and no-data
safeguards.

The local journal may reveal relative paths, hashes, timestamps, and operational history. It must
be local by default, excluded from Git, disposable, and documented as derived state. It should use
restrictive permissions where practical and avoid source/mirror bodies.

Source and mirror text remain evidence, not instructions. A future semantic-delta assistant must
not change lifecycle truth, checkpoint events, or write curated notes automatically.

## Model Boundary

No model is required for correctness. These remain deterministic:

- event capture;
- coalescing;
- fingerprinting;
- hashing;
- extraction;
- mirror generation;
- manifest state;
- audit state;
- journal state;
- reconciliation.

Package-part extraction and semantic enrichment are explicitly deferred. A future assistant may
propose summaries, links, or affected-note review candidates only after deterministic extraction,
with outputs tied to source ID, source hash, and journal sequence.

## Adoption and Rollback

Adoption is staged:

1. Keep full sync as the baseline and recovery path.
2. Add the journal schema and status/replay surfaces.
3. Add source-addressable materialization primitives.
4. Add deterministic fake-feed tests before native watcher dependence.
5. Add local watcher support behind the feed interface.
6. Add reconciliation and benchmark evidence.

Rollback is safe because the journal is derived state. Operators can stop the watcher, remove or
ignore `.vaultwright/`, run full sync, and rebuild derived state from sources and manifests.

## Consequences

- Stage 1A must close kernel/profile convergence before Stage 1B implementation begins.
- Stage 1B must prove changed-file materialization, replay, reconciliation, concurrency safety, and
  source-byte preservation before official profile work resumes.
- The evidence index and Explorer, if built later, consume applied journal events and must not add
  a second watcher or authority model.
- Performance claims require recorded measurements: paths enumerated, files opened, bytes hashed,
  converter calls, events coalesced/applied, elapsed time, and peak memory where practical.
