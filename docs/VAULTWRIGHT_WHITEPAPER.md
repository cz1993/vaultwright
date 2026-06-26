# Vaultwright Whitepaper

**Status:** canonical strategic product revision, incremental-materialization architecture, and finite v1 execution brief
**Date:** 2026-06-24
**Repository reviewed:** `cz1993/vaultwright` at commit `004a3617f15e8234a056b8b1711b139ebe9b8e2f`
**Audience:** maintainers, design partners, consulting operators, knowledge-management teams, and technical reviewers
**Review posture:** ambitious, practical, evidence-based, source-preserving, and deliberately scope-bounded

## 1. Executive Summary

Vaultwright should become a **profile-driven, governed knowledge-workspace compiler** with a **journaled incremental materialization engine**.

Its durable value is not a particular startup, HR, legal, or finance folder tree. Its durable value is a controlled lifecycle:

1. inventory heterogeneous source collections;
2. preserve originals as authoritative records;
3. capture source changes in a durable local journal;
4. materialize inspectable Markdown read models only for changed sources;
5. attach provenance, lifecycle state, and human review;
6. organize the workspace through a versioned domain profile;
7. build an optional disposable evidence index;
8. render useful human and agent interfaces;
9. reconcile periodically so missed events cannot produce silent drift.

The revised product statement is:

> **Vaultwright compiles changing source collections into governed, profile-driven knowledge workspaces that humans and AI agents can inspect, navigate, cite, and refresh without replacing the original records.**

The most important new decision is architectural:

> **Normal operation should be event-driven and incremental; full scans should become reconciliation and recovery paths.**

The database-mirroring analogy is useful but must be applied carefully. Office files, PDFs, repositories, and ordinary filesystems do not provide a database-grade write-ahead log containing paragraph-, sheet-, or slide-level transactions. Vaultwright therefore cannot perform literal WAL shipping. It can implement the useful operational properties:

- a durable ordered change journal;
- at-least-once event processing;
- idempotent replay;
- materialization checkpoints;
- atomic read-model replacement;
- crash recovery;
- periodic reconciliation against the authoritative source tree.

A lightweight model may optionally interpret **semantic deltas** after deterministic extraction. It must never own change detection, hashing, lifecycle truth, mirror correctness, or the clean/stale decision.

The strategic expansion still follows one rule:

> **Generalize the engine, not the launch market.**

Vaultwright can support business operations, research and learning, and software-project documentation through profiles while retaining professional-services teams as the first commercial wedge.

## 2. Decision Recommendation

Proceed with the profile-driven v1 plan and add **journaled changed-file synchronization** as a mandatory kernel requirement.

The implementation should follow six constraints:

1. Source preservation, provenance, review, and lifecycle semantics remain non-negotiable.
2. The change journal is operational state, not a new source of truth.
3. Filesystem events are hints that trigger work; periodic reconciliation remains mandatory.
4. Changed-file processing is the v1 goal. Fine-grained DOCX/PDF delta extraction is not.
5. AI enrichment is optional and proposal-only; the deterministic system must work without a model.
6. The new requirement must replace repeated whole-vault work rather than create another parallel sync system.

The immediate product goal is:

> **After an initial baseline, changing one source should normally hash and convert only that source, update only its derived records, and invalidate only its dependants.**

## 3. Current Repository Assessment

The current repository is materially beyond the original prototype.

As of the reviewed commit:

- Stage 0 scope freeze and architecture decisions are recorded as complete.
- Package-owned runtime covers the main operator commands and mirror implementations.
- The versioned profile contract has closed the Stage 1A kernel/profile-convergence gate.
- Source-authority and no-real-data policy defaults are validated through the profile schema.
- Machine-owned mirrors and annotation-sidecar migration are implemented and treated as closed Stage 1 work.
- Compatibility scripts remain thin shims over package-owned runtime behavior.
- Stage 1B journaled changed-file materialization is implemented and gate-validated on the active
  development branch with focused, affected, full-suite, packaging, lint, no-data, template-copy,
  shell syntax, diff, and residue checks.

This progress matters. The incremental design should not replace the existing lifecycle engine. It should make the existing engine addressable by source and drive it through a durable queue.

Full sync remains the baseline and recovery mode. The Stage 1B changed-file path removes the
normal steady-state need to rediscover and fully hash the whole source corpus by processing
event-identified candidates through the same mirror engine. The recorded synthetic benchmark
proves known-path replay over 1,000 sources with no whole-workspace discovery, no untouched-source
body hashing, and one conversion for one modified source.

The main remaining risks are:

- compatibility surfaces can still drift if they stop being thin;
- the CLI and reporting surface can expand without convergence discipline;
- the local journal must stay derived delivery state, never a second lifecycle authority;
- event-driven operation must keep reconciliation mandatory because watcher delivery is advisory;
- Stage 2+ profiles, Obsidian adapter work, index, Explorer, and pilots still need separate gates.

## 4. Refined Product Scope

“Any type of knowledge base” remains too broad. Vaultwright targets **source-backed, lifecycle-sensitive knowledge workspaces** where:

- original records or repositories exist outside curated notes;
- sources change over time;
- provenance and source authority matter;
- people or agents must retrieve, reconcile, and audit information;
- stale knowledge creates risk or repeated effort;
- durable, inspectable outputs are preferable to transient chat answers.

Good fits include:

- consulting and advisory workspaces;
- operational and compliance collections;
- research and literature review;
- substantial learning collections with sources and synthesis;
- software architecture, ADR, release, runbook, and incident knowledge;
- policy and due-diligence collections.

Vaultwright is not intended to replace casual note taking, journaling, generic task management, creative writing, or a bookmark list with no meaningful source lifecycle.

## 5. Target Architecture

The revised architecture has seven layers.

| Layer | Responsibility | Authority |
| --- | --- | --- |
| Sources | Original files, repositories, exports, and external records | Authoritative |
| Change journal | Ordered local observations, work states, retries, and checkpoints | Operational, derived |
| Mirrors | Machine-generated Markdown and extraction metadata | Derived materialized read model |
| Curated knowledge | Human-reviewed notes, syntheses, entities, and decisions | Human-governed |
| Profile | Domain vocabulary, schemas, templates, views, skills, and benchmarks | Versioned contract |
| Evidence index | Full-text and graph index for retrieval and context assembly | Disposable derived cache |
| Presentation | Obsidian, catalogs, Canvas, Explorer, MCP, and context packs | Derived interface |

The core flow is:

```text
Authoritative sources
        ↓
change capture + reconciliation
        ↓
durable journal
        ↓
deterministic extraction/materialization
        ↓
machine-owned mirrors + manifests + audit
        ↓
curated knowledge + human review
        ↓
optional evidence index
        ↓
Obsidian / catalog / Explorer / MCP / context packs
```

The change journal and evidence index must not duplicate event capture. When the index exists, it consumes successfully materialized journal events.

## 6. Horizontal Core and Vertical Profiles

### 6.1 Domain-neutral kernel

The core owns universal behavior:

- source discovery and disposition;
- stable source identity;
- lifecycle state transitions;
- journal sequencing and replay;
- deterministic extraction;
- mirror materialization;
- provenance and audit events;
- human-review records;
- schema validation;
- safe migrations;
- derived index invalidation;
- renderer and adapter interfaces.

It must not contain business-specific folders, statuses, note types, or frontmatter fields.

### 6.2 Versioned profile contract

A profile is a declarative package defining:

- domains and folders;
- note types and property rules;
- statuses and roles;
- templates and views;
- benchmark tasks;
- repository and mirror placement defaults;
- source-authority and data-handling policy defaults;
- optional source handling and incremental-extraction policies.

Suggested incremental policy fields are:

```yaml
change_capture:
  enabled: true
  debounce_ms: 1500
  settle_interval_ms: 500
  settle_checks: 3
  reconcile_on_start: true
  reconcile_interval_hours: 24

incremental_extraction:
  docx: file
  pptx: file
  xlsx: file
  pdf: file
  markdown: heading

semantic_delta:
  enabled: false
  proposal_only: true
  may_write_curated_notes: false
```

These settings should have safe core defaults. Profiles may tune them but may not disable source authority, auditability, or reconciliation safeguards.

### 6.3 Official v1 profiles

Ship exactly:

- `business-operations`;
- `research-learning`;
- `software-project`;
- `blank`.

A reading list remains a workflow inside `research-learning`. “Enterprise” remains a policy and deployment tier, not a universal taxonomy profile.

## 7. Journaled Incremental Materialization

### 7.1 Database log-shipping analogy

| Database concept | Vaultwright equivalent |
| --- | --- |
| Primary database | Authoritative source collection |
| WAL/log stream | Durable observed-change journal |
| Log sequence number | Monotonic event sequence |
| Log receiver | Filesystem or provider change-feed adapter |
| Replay worker | Deterministic extraction/materialization worker |
| Read replica | Markdown mirrors and derived index |
| Replay checkpoint | Last successfully applied event sequence |
| Base backup | Initial full inventory and materialization |
| Consistency check | Periodic source/manifest/mirror reconciliation |

The analogy stops at transaction granularity. A filesystem watcher normally reports that a file changed, not the semantic transaction inside it.

### 7.2 Operational state database

Use a private local SQLite database, excluded from Git and ordinary vault synchronization:

```text
.vaultwright/state.sqlite
```

It may use SQLite WAL mode for reliable local transactions. It must not contain source document bodies. It may contain relative paths, fingerprints, hashes, event metadata, retry state, and optional extracted-part cache entries.

Minimum tables:

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

Optional part/chunk caching is added only after changed-file processing is complete and benchmarked.

### 7.3 Delivery and replay semantics

The system should provide **at-least-once delivery with idempotent application**, not claim exactly-once processing.

Event states:

```text
queued
  → coalesced
  → stabilizing
  → fingerprinted
  → extracting
  → materialized
  → applied
```

Terminal or review states include:

```text
ignored
deferred
review_required
failed_retryable
failed_terminal
```

A crash before `applied` leaves the event replayable. Replaying an already materialized event must produce no incorrect duplicate output.

### 7.4 Trigger sources

The v1 adapter set is deliberately small:

- local filesystem changes;
- explicit CLI enqueue for testing and automation;
- Git repository HEAD/tree changes through the existing repo-sync mechanism.

Cloud-provider delta feeds are post-v1 unless they replace a required pilot integration.

Filesystem events are not authoritative. Event loss, queue overflow, cloud-sync behavior, replacement-style saves, and watcher downtime are expected conditions. Therefore:

```text
live event capture
+ startup reconciliation
+ scheduled reconciliation
+ explicit full recovery sync
```

is mandatory.

### 7.5 Debounce and file-stability gate

Office applications and synchronization clients can emit several events for one logical save.

For a candidate change:

1. coalesce repeated events for the same logical path;
2. ignore known temporary Office lock files;
3. wait for the debounce interval;
4. sample size and modification time;
5. require stable metadata across configured settle checks;
6. hash the candidate source;
7. hash it again after conversion;
8. materialize only if the source remained stable.

Ten rapid events before processing should normally become one conversion of the latest stable source state.

### 7.6 Metadata fingerprint before full hashing

The fast path compares:

```text
relative path
filesystem file identifier when available
size
mtime_ns
```

Decision logic:

```text
fingerprint unchanged
    → no content hash and no extraction

fingerprint changed
    → compute full SHA-256

SHA-256 unchanged
    → metadata/move handling only

SHA-256 changed
    → extraction and materialization
```

Filesystem IDs are matching hints, not durable identity. Stable Vaultwright source IDs remain manifest-owned.

### 7.7 Changed-file first, package-part later

V1 requires changed-file incrementality only.

| Format | V1 increment | Conditional later increment |
| --- | --- | --- |
| DOCX | whole changed file | paragraph/section or package-part extraction if benchmarks justify it |
| PPTX | whole changed file | changed slides, notes, and media relationships |
| XLSX | whole changed file | changed worksheets plus shared-string dependency handling |
| PDF | whole changed file | page-aware extraction only with a reliable backend |
| Markdown/text | changed file | heading/content-defined chunks |
| Git repository | changed repository/file set | symbol-level semantics delegated to CodeGraph adapter |

The first performance win comes from not touching unchanged files. Rewriting one generated Markdown mirror atomically is generally cheap compared with repeatedly reading, hashing, and converting an entire corpus.

### 7.8 Dependency invalidation

A successfully applied source event should update or invalidate only related derived artifacts:

```text
source → mirror
mirror/source → catalog entry
mirror/source → evidence-index records
mirror/source → review decision freshness
mirror/source → curated-note review queue
```

The system may mark curated notes as potentially affected, but it must not silently rewrite human-governed knowledge.

## 8. Lightweight Model Policy

A model is not part of mirror correctness.

### Tier 0 — deterministic core

No model is used for:

- event capture;
- source identity;
- fingerprinting or hashing;
- Office/PDF extraction selection;
- lifecycle transitions;
- mirror generation;
- journal checkpoints;
- reconciliation;
- audit events.

### Tier 1 — optional small local delta assistant

After deterministic extraction, a lightweight model may receive only:

- changed old chunks;
- changed new chunks;
- bounded surrounding headings;
- explicitly selected linked-note summaries.

It may propose:

- a semantic change summary;
- affected entities;
- possible links;
- curated notes that may need review;
- a human-readable review explanation.

Its output is a proposal tied to a source ID, source hash, and journal sequence. It cannot mark an event applied or a mirror clean.

### Tier 2 — explicit larger-model review

Complex cross-document reconciliation may be invoked manually. It is not an automatic steady-state dependency.

### Model admission gate

Tier 1 enters the default product only if a measured pilot shows lower reviewer effort or better stale-note detection without unacceptable false positives, privacy risk, or model startup cost. Otherwise it remains optional research.

## 9. Obsidian Integration

Obsidian remains an optional presentation and authoring adapter.

The product should:

- remain compatible with Obsidian-flavored Markdown;
- interoperate with `kepano/obsidian-skills` rather than duplicate syntax guidance;
- ship Vaultwright-specific governance skills;
- generate profile-aware Bases and Canvas views;
- expose lifecycle and review queues inside those views;
- continue to pass all core tests without Obsidian installed.

The journal should not depend on Obsidian being open. Obsidian-specific file changes may be observed as ordinary source or curated-note events according to profile policy.

A first-party Obsidian plugin remains outside v1.

## 10. Evidence Index and Exploration

The local evidence index remains a conditional Stage 4 feature, but its incremental architecture is now simpler:

- it consumes successfully applied journal events;
- it deletes or updates only records linked to changed source/mirror/note identities;
- it records the applied journal sequence and source hash;
- it exposes freshness relative to the materialization checkpoint;
- it remains disposable and rebuildable.

No second file watcher is allowed for the index.

The initial index remains SQLite plus full-text and explicit graph tables. Vector embeddings are not required for v1.

Primary interfaces remain:

```text
vaultwright index build
vaultwright index status
vaultwright explore "How is this decision supported?"
```

and one MCP tool:

```text
vaultwright_explore
```

The Stage 4 benchmark still decides whether index and Explorer features stay in v1.

## 11. Visual Explorer and Context Builder

The visual Explorer remains conditional on the evidence-index gate.

Required jobs:

- orient to the collection;
- inspect lifecycle health;
- trace claim-to-source provenance;
- view journal lag and unresolved events;
- identify stale reviews or potentially affected curated notes;
- select a bounded context pack;
- export a reviewable handoff.

The existing static catalog remains the portable snapshot. The Explorer must read shared profile, journal, lifecycle, and index models; it must not implement separate business logic.

## 12. Security and Governance

Incremental operation introduces new controls.

### 12.1 Local state sensitivity

The journal database may expose filenames, relative paths, hashes, timing, and operational history. It must:

- be excluded from Git;
- be omitted from public examples;
- remain local by default;
- use safe filesystem permissions;
- avoid source and mirror bodies unless a later cache is explicitly enabled;
- be securely disposable and rebuildable.

### 12.2 Untrusted events and paths

Every event path is untrusted input. Existing path, symlink, reserved-directory, source-boundary, and output-boundary checks must run again during replay. A watcher event cannot bypass normal safety checks.

### 12.3 Concurrency

Only one materialization worker may apply events to a workspace at a time. Use a workspace lock with stale-lock recovery. SQLite transactions protect journal state; existing atomic file replacement protects mirror writes.

### 12.4 Prompt safety

Source and mirror content remain untrusted evidence. A semantic-delta assistant must receive explicit system instructions that document content cannot override governance policy or request tool execution.

### 12.5 Recovery

A complete recovery path is:

1. stop the watcher;
2. inspect journal status;
3. replay unapplied events;
4. run reconciliation;
5. perform full sync when reconciliation cannot establish consistency;
6. regenerate the index when present;
7. verify lint, review freshness, and source integrity.

## 13. CLI Convergence

Do not create a separate command for every report.

The incremental surface should converge on:

```text
vaultwright watch
vaultwright sync --changed
vaultwright journal status
vaultwright journal replay
vaultwright reconcile
vaultwright sync --full
```

Recommended meanings:

- `watch`: capture local source changes and process the durable queue;
- `sync --changed`: process pending changed-source events and exit;
- `journal status`: show lag, queued, retrying, review-required, and failed events;
- `journal replay`: retry eligible unapplied events idempotently;
- `reconcile`: metadata-first comparison of sources, manifest, journal, and mirrors;
- `sync --full`: explicit recovery/baseline path.

`plan`, `sync`, and `status` may retain compatibility behavior during migration. New commands should replace or group existing behavior rather than expand the conceptual surface indefinitely.

## 14. Validation and Performance Evidence

### 14.1 Functional acceptance tests

The incremental engine is not complete until tests cover:

- initial baseline creation;
- unchanged fingerprint fast path;
- one changed source causing one full hash and at most one conversion;
- rapid save-storm coalescing;
- Office lock-file suppression;
- source changed during conversion;
- move and rename;
- delete and recreate;
- ambiguous same-byte move;
- watcher restart;
- event replay after process failure;
- crash after mirror write but before journal checkpoint;
- duplicate event delivery;
- stale workspace lock;
- two concurrent workers;
- event-source overflow or missed-event simulation;
- reconciliation repair;
- full-sync recovery;
- annotation-sidecar preservation;
- source-byte preservation;
- no-data and path-safety gates.

### 14.2 Structural performance gates

For steady-state event processing:

- no whole-vault recursive discovery occurs for a known changed path;
- untouched source bodies are not read or hashed;
- one settled changed source invokes the converter at most once;
- successfully applied events update only the relevant manifest, audit, catalog/index invalidation, and review dependencies;
- clean replay is idempotent.

### 14.3 Benchmark fixture

Create a synthetic benchmark workspace containing at least:

- 1,000 eligible source records;
- mixed file sizes and supported formats;
- one changed file;
- one rapid-save sequence;
- one move;
- one deletion.

Record:

- paths enumerated;
- files opened;
- source bytes hashed;
- converter invocations;
- journal events created/coalesced/applied;
- elapsed time;
- peak memory where practical.

The important pass condition is behavioral, not a fragile wall-clock number: unchanged source bodies must not be read during normal event replay.

### 14.4 External validation

The three profile pilots must include:

- initial baseline;
- steady-state change processing;
- watcher downtime followed by reconciliation;
- source move/delete recovery;
- review invalidation;
- operator assessment of latency, resource use, clarity, and trust.

## 15. Current Risks

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Filesystem events are mistaken for authoritative WAL | Critical | Treat events as triggers; require reconciliation and full recovery paths |
| Journal becomes a second source of truth | Critical | Sources and manifests remain authoritative; journal is rebuildable operational state |
| Scope expands into custom parsers for every format | High | V1 stops at changed-file incrementality |
| Model becomes required for correctness | High | Tier 0 deterministic system is complete without AI |
| Event storms waste work | High | Debounce, coalescing, settle checks, idempotent event keys |
| Missed events create silent stale mirrors | High | Startup and scheduled reconciliation; overflow/missed-event tests |
| Journal leaks sensitive operational metadata | High | Local-only state, Git exclusion, minimal payloads, safe permissions |
| Two workers corrupt state | High | Workspace lock plus SQLite transactions and atomic materialization |
| Profile expansion and journal work run in parallel indefinitely | Critical | Stage 1A and Stage 1B have explicit sequential gates |
| Index duplicates watcher logic | Medium | Index consumes applied journal events only |
| Package-part extraction consumes the roadmap | High | Benchmark-gated post-v1 optimization |
| Scope never closes | Critical | Fixed v1 definition and explicit stop rules |

## 16. Finite V1 Execution Plan

Later stages do not begin until prior gates are met.

### Stage 0 — Scope freeze and architecture decision

**Status:** complete.

Retain the existing product statement, profile list, non-goals, and finish-line matrix. Add this incremental architecture through one ADR and one finish-line requirement rather than creating a parallel roadmap.

### Stage 1A — Kernel and profile convergence

**Current status:** complete.

The Stage 1A gate closed after the remaining profile-assumption inventory found no
Stage 1A-blocking runtime defect and classified remaining vocabulary as profile data, legacy
compatibility fallback, test fixture, or universal mirror-layer invariant. The closed gate
preserves these constraints:

- keep package modules authoritative;
- keep compatibility scripts thin;
- preserve machine-owned mirror and annotation-sidecar guarantees;
- keep migration, lifecycle, recovery, catalog, review, safety, and benchmark behavior passing.

**Exit criteria:**

- all remaining hard-coded profile vocabulary is enumerated and either removed or explicitly justified as universal;
- V1-C1, V1-C2, V1-C4, and V1-C5 meet their Stage 1 definitions;
- the full existing suite and repository gates pass.

The Stage 1B journaled materialization gate is closed. Stage 2+ profile, Obsidian, index, and
Explorer work remains paused until opened by a new, explicitly bounded batch or goal.

### Stage 1B — Journaled changed-file synchronization

Requirement **V1-C10: journaled incremental materialization** is closed for Stage 1B.

Delivered:

- package-owned journal module and SQLite schema;
- source-addressable Office synchronization API;
- deterministic change-feed adapter plus optional native filesystem capture;
- event coalescing and file-stability gate;
- metadata-first reconciliation;
- `watch --once`, optional `watch --native`, `sync --changed`, `sync --full`,
  `journal status/replay`, and `reconcile` surfaces;
- workspace locking;
- crash-replay and missed-event recovery tests;
- synthetic large-vault benchmark;
- updated recovery, security, profile, and operator documentation.

**Exit criteria passed:**

- one changed source causes no full-vault discovery on the event path;
- untouched source bodies are not hashed;
- one settled save causes at most one conversion;
- replay is idempotent;
- missed events are found through reconciliation;
- full sync remains a correct recovery path;
- no model is required;
- all existing gates remain green.

**Stop rule:** do not implement Office package-part extraction or semantic-delta AI in this stage.

### Stage 2 — Official profiles

Deliver exactly:

- `blank`;
- `business-operations`;
- `research-learning`;
- `software-project`.

All profiles use the same journal, mirror, lifecycle, and safety engine.

### Stage 3 — Obsidian adapter and skills

Deliver optional Obsidian compatibility, governance skills, profile-aware Bases, and generated Canvas recipes. No plugin.

### Stage 4 — Evidence-index gate

Build the disposable SQLite/full-text graph index on top of applied journal events. Benchmark with and without the index.

If it materially improves context precision, citation quality, review effort, or tool-call count, continue to Stage 5. Otherwise remove it from the v1 critical path.

### Stage 5 — Conditional Explorer

Only after the Stage 4 gate passes, build the localhost read-only Explorer and context export.

### Stage 6 — Three pilots and release

Run one external pilot for each maintained content profile. Each pilot includes baseline, changed-file processing, downtime/reconciliation, recovery, and handoff.

## 17. V1 Definition of Done

### Mandatory V1 Core

Vaultwright v1 Core is finished when all of the following exist and pass:

1. one installable cross-platform package owns runtime behavior;
2. one versioned profile contract;
3. `business-operations`, `research-learning`, `software-project`, and `blank` profiles;
4. safe migration from the current business template;
5. machine-owned mirrors with preserved annotation sidecars;
6. journaled changed-file synchronization with replay and reconciliation;
7. profile-aware catalogs, Bases, and Canvas outputs;
8. optional Obsidian governance skills;
9. three external profile pilots;
10. one tagged v1 release with upgrade, recovery, security, benchmark, and support documentation.

### Conditional V1 Explorer

When the Stage 4 benchmark passes, v1 additionally includes:

11. one disposable local evidence index;
12. one exploration CLI/MCP interface;
13. one read-only visual Explorer with context export.

When the index benchmark fails, items 11–13 move to post-v1 and v1 Core closes without them.

After the selected finish line is met, feature work stops. The maintainer resolves release defects, publishes v1, and gathers usage evidence.

## 18. Explicit Post-V1 Backlog

The following are outside v1 unless they replace a mandatory requirement:

- package-part incremental DOCX, PPTX, XLSX, or PDF extraction;
- default semantic-delta model processing;
- cloud-provider change-feed adapters;
- hosted SaaS;
- multi-user real-time collaboration;
- enterprise administration console;
- Obsidian plugin;
- public profile marketplace;
- mobile application;
- universal OCR and high-fidelity layout extraction;
- vector embeddings by default;
- autonomous note deletion or consolidation;
- email and mailbox ingestion;
- broad connector catalog;
- desktop application shell;
- automatic enterprise permission or retention enforcement.

New proposals enter this backlog unless they replace or close a v1 requirement.

## 19. Commercial and Product Implications

Journaled incremental operation strengthens the product in three ways:

1. **Scale:** steady-state cost follows changed sources rather than total corpus size.
2. **Trust:** every source observation, materialization, retry, and checkpoint is explainable.
3. **Agent readiness:** changed evidence can invalidate only relevant context and review surfaces.

The market-facing message should not emphasize “filesystem watchers” or “log shipping.” It should emphasize:

> **Vaultwright keeps governed knowledge workspaces current as source records change, without repeatedly rebuilding the entire collection.**

Professional implementation remains the first commercial path. Profiles broaden adoption; the incremental engine reduces operating burden across all profiles.

## 20. Bottom Line

Vaultwright should retain its profile-driven v1 direction and replace repeated whole-corpus synchronization with a journaled changed-file materialization engine.

The correct design is not AI-driven mirroring. It is:

- deterministic event capture;
- durable ordered work;
- metadata-first change detection;
- full hashing only for candidates;
- atomic materialization;
- idempotent replay;
- mandatory reconciliation;
- optional bounded semantic-delta proposals.

This architecture preserves the existing source-authority and lifecycle work while making the product practical for larger and more frequently changing collections.

The scope remains finite: changed-file incrementality is mandatory; package-part extraction and lightweight-model enrichment are conditional later work. The project returns to profiles, Obsidian integration, the evidence-index gate, three pilots, and a tagged v1 release after the incremental kernel requirement is closed.

## References Reviewed

- Vaultwright repository: https://github.com/cz1993/vaultwright
- Vaultwright June 23 strategic whitepaper: `docs/VAULTWRIGHT_WHITEPAPER_2026-06-23.md`
- Vaultwright v1 finish-line matrix: `docs/V1_FINISH_LINE.md`
- ADR 0001 profile-driven v1 architecture: `docs/adr/0001-profile-driven-v1-architecture.md`
- ADR 0002 journaled incremental materialization:
  `docs/adr/0002-journaled-incremental-materialization.md`
- Vaultwright profile schema: `docs/PROFILE_SCHEMA.md`
- Obsidian Agent Skills: https://github.com/kepano/obsidian-skills
- CodeGraph: https://github.com/colbymchenry/codegraph
- RepoPrompt Community Edition: https://github.com/repoprompt/repoprompt-ce
