# Vaultwright V1 Finish-Line Matrix

This matrix is the execution control document for the canonical white paper,
`docs/adr/0001-profile-driven-v1-architecture.md`,
`docs/adr/0002-journaled-incremental-materialization.md`, and
`docs/PROFILE_SCHEMA.md`.

Current progress and next execution order are summarized in
`docs/V1_PROGRESS_AUDIT_2026-06-23.md`.

Its job is to keep development converging. Work is v1-aligned only when it advances a listed
requirement, replaces a weaker implementation, or preserves existing gates while preparing a
required migration. New ideas that do not map here move to the post-v1 backlog.

## Stage-Gate Plan

| Stage | Gate | Required Evidence | Status |
| --- | --- | --- | --- |
| 0. Scope freeze and architecture decision | Product statement, seven-layer architecture, v1 profiles, v1 non-goals, journaled incremental architecture, and stop rules are approved and tracked | ADR 0001, ADR 0002, this matrix, and the canonical white paper are committed; README/product docs point to them | Complete |
| 1A. Kernel and profile convergence | Runtime logic moves into `src/vaultwright/`; vault-local scripts become compatibility shims; profile/core schemas exist; generated mirrors become machine-owned with annotation migration; remaining profile assumptions are enumerated and either profile-owned, legacy compatibility, tests, or universal invariants | Package owns behavior; tests prove source integrity, idempotency, lifecycle, recovery, migration, profile validation, mirror annotation, and safety | Complete |
| 1B. Journaled changed-file materialization | Durable local journal, source-addressable materialization, event coalescing, metadata-first fingerprints, replay, reconciliation, lock/lease safety, and full-sync recovery path exist | One changed source avoids whole-vault steady-state hashing/conversion; missed/interrupted work recovers; benchmark records paths/files/bytes/conversions/events; focused, affected, full-suite, packaging, lint, no-data, template-copy, shell syntax, diff, and residue gates pass | Complete |
| 2. Official profiles | `business-operations`, `research-learning`, `software-project`, and `blank` initialize from the same core package | Profile fixtures pass identical lifecycle and no-data gates; no core hard-coding of profile folders/types/statuses | Complete |
| 3. Obsidian adapter and skills | Obsidian integration stays optional; governance skills and profile-aware Bases/Canvas outputs exist | Generated `.base` and `.canvas` artifacts pass syntax/integrity tests; core tests pass without Obsidian | Paused behind Stage 2 |
| 4. Evidence index and exploration gate | Local SQLite/FTS graph index, `index build`, `index status`, `explore`, MCP exploration tool, and benchmark comparison exist; the index consumes applied journal events rather than its own watcher | Deletion/rebuild equivalence, provenance on every result, no cross-workspace retrieval, and material benchmark improvement | Not started |
| 5. Explorer and context builder | Only if Stage 4 passes: local read-only Explorer and context pack export | Explorer reads shared profile/journal/index model; no UI-only business logic; accessibility and browser checks pass | Conditional |
| 6. External validation and v1 release | Three structured pilots complete; release artifact installs and upgrades; limitations and support boundaries are published | Business-operations, research-learning, and software-project pilots all produce measured improvements and source-backed handoffs, including baseline, changed-file sync, downtime/reconciliation, recovery, and handoff evidence | Not started |

## Mandatory V1 Core Finish Line

| ID | Requirement | Current Evidence | Gap To Close | Stage |
| --- | --- | --- | --- | --- |
| V1-C1 | One installable cross-platform core package owns runtime behavior | `pyproject.toml` exposes a `vaultwright` console entry point; CI installs package; installed `vaultwright plan`, `vaultwright sync`, and `vaultwright status` orchestrate package-owned Office/repo sync modules directly; `vaultwright doctor` runs package-owned preflight checks; `vaultwright catalog` runs package-owned catalog code; `vaultwright lint` runs package-owned lint code; `vaultwright conversion` runs package-owned conversion spot-check/result-pack code; `vaultwright m365` runs package-owned Microsoft 365 handoff-report code; `vaultwright migration` runs package-owned legacy folder/frontmatter migration-report code; `vaultwright overlap` runs package-owned overlap-calibration code; `vaultwright benchmark` runs package-owned agent-readiness task/result/worksheet code; `vaultwright pilot` runs package-owned aggregate pilot-evidence code; `vaultwright sandbox` runs package-owned copied-vault preflight code; `vaultwright recovery` runs package-owned recovery-report code; `vaultwright review` runs package-owned review-ledger code; Office mirror planning/sync/status runs from `vaultwright.mirrors.office`; GitHub repo mirror planning/sync/status runs from `vaultwright.mirrors.github_repos`; vault-local sync, lint, catalog, conversion, m365, migration, overlap, benchmark, pilot, sandbox, recovery, review-ledger, and operator-wrapper tools are compatibility shims copied through the package template and examples | Closed for Stage 1A; keep copied `template/tools/` scripts as thin compatibility shims and prevent implementation drift after Stage 1B | 1 |
| V1-C2 | One versioned profile contract | `src/vaultwright/profiles.py` validates schema version 1, safe profile vocabulary identifiers, schema-declared domain/note-type/status/folder-plan/policy-default fields, disjoint required/optional frontmatter fields, safe profile artifact paths, safe separation between profile artifact paths and the profile Office mirror root, safe unique non-overlapping domain folders, `folder_plan` paths/domains, safe profile benchmark-task paths, safe profile repo-mirror folder defaults, safe context-alias defaults, boolean note-type role flags, boolean status-role flags, profile-owned Office mirror placement defaults, profile-owned generated-mirror status defaults, and profile-owned source-authority/no-real-data policy defaults; `_meta/profile.yml` declares the current `business-operations` template with profile-owned machine-owned note type roles, attention/inactive status roles, `client: account` context aliasing, and source-authority/no-real-data policy defaults; `docs/PROFILE_SCHEMA.md` documents schema fields, validation rules, migration semantics, generated-view semantics, `benchmark_tasks`, repo context fields, status roles, `policy_defaults.repo_notes_dir`, `policy_defaults.context_aliases`, `policy_defaults.mirror_mode`, `policy_defaults.mirror_root`, `policy_defaults.mirror_status`, `policy_defaults.repo_stub_status`, `policy_defaults.original_sources_authoritative`, and `policy_defaults.real_data_in_repo`; package CLI exposes `init --profile` for all official profiles, `profile list`, `profile show`, `profile validate`, `profile diff`, `profile migrate --plan`, conservative `profile migrate --write`, and `profile views --check/--write`; profile migration creates missing directories from the profile `folder_plan` and target `policy_defaults.mirror_root`; linter and catalog read validated profile domains, note types, statuses, required properties, optional properties, and canonical folders; overlap calibration reads profile domain folders when selecting curated notes, profile-defined context fields when counting inbound wikilinks, profile-defined inactive statuses when excluding retired notes, and profile-defined machine-owned note types when excluding generated artifacts; catalog, Microsoft 365 handoff, and sandbox inventory separate profile-defined machine-owned Markdown artifacts from curated/domain Markdown counts; review-ledger classification accepts profile-defined machine-owned Markdown artifacts as generated review targets; profile-generated Bases read only profile-defined attention statuses, and doctor reports profile-declared generated view health; doctor validates the active profile contract and treats `_meta/domain-map.yml`/`_meta/mirror-config.yml` as legacy alias/override files for profile-driven vaults; benchmark task/result validation, task scaffolding, and aggregate pilot reporting read profile-declared benchmark task packs and active Office mirror evidence paths, and pilot workspace inventory plus recovery source-evidence preflight exclude the active Office mirror root; Office sync derives canonical source domains and mirror paths from profile domain folders while retaining `_meta/domain-map.yml` only for legacy aliases; Office sync, lint, catalog, Microsoft 365 handoff, sandbox preflight, doctor, migration guidance, and review-ledger classification read profile/configured Office mirror placement defaults instead of assuming `_mirrors/`; Office/repo mirror sync and annotation detection read profile-owned generated-mirror statuses instead of hard-coded `active`/`draft`; GitHub repo mirror sync/lint read the validated profile default repo-mirror folder, derive repo-mirror domains from profile folder mappings, and derive repo context frontmatter plus context aliases from profile optional properties/policy defaults; annotation migration uses the shared runtime profile context helpers and treats matching profile-defined repo context/context aliases as generated metadata instead of human annotations; Microsoft 365 handoff, sandbox preflight, recovery, and review-ledger reporting resolve repo mirror folders from the active profile or `tools/repos.yml`; migration reporting reads profile canonical domains with `_meta/domain-map.yml` as a non-authoritative alias layer, ignores profile-defined machine-owned note types during frontmatter cleanup, and prints active profile identity/canonical domain folders in migration runbooks and worksheets before unknown folder/domain classification | Closed for Stage 1A; use the profile-assumption inventory as the control list, and defer richer generated views, skills, benchmark packs, and pilots to their later gated stages | 1 |
| V1-C3 | Three official content profiles plus a blank starter | Existing template approximates `business-operations`; government-services example exercises that profile shape; package-owned `research-learning`, `software-project`, and `blank` profile contracts now validate and are exposed through `vaultwright profile list/show`; package-owned profile scaffolding initializes `research-learning`, `software-project`, and `blank` with profile-derived folders, generated scaffold docs, matching `_meta/domain-map.yml`, profile-specific note templates, and shared tool shims while preserving the `business-operations` compatibility template; focused tests run profile validation, lint, generated-view checks, and no-real-data policy checks for all four official profiles | Closed for Stage 2; richer profile-specific generated views, skills, benchmark packs, and external pilots stay in their later gated stages | 2 |
| V1-C4 | Safe migration path from current business template | Migration reports and frontmatter domain normalization now use profile-defined canonical domains while retaining domain-map aliases; package-owned `profile migrate --plan` and conservative `profile migrate --write` exist; write mode creates missing shared, target Office mirror-root, and `folder_plan` directories and copies missing packaged profile/template files without overwriting sources, mirrors, or drifted existing files | Closed for Stage 1A; broader workspace/profile migration coverage expands with later profile work | 1 |
| V1-C5 | Machine-owned mirrors with preserved human annotations | Package-owned `migrate annotations --plan` and `--write` preserve legacy mirror notes/frontmatter into `_meta/mirror-annotations/` sidecars keyed by source/repo ID; fresh mirrors use machine-owned headers without a curated `## Notes` region; Office/repo sync blocks unmigrated above-sentinel annotations as force-blocking review work and rewrites migrated mirrors as machine-owned when a matching sidecar exists; lint blocks unmigrated mirror annotations | Closed for Stage 1; keep compatibility tests and recovery guidance current while broader migration UX evolves | 1 |
| V1-C6 | Obsidian adapter and first-party governance skill pack | Template ships Obsidian-compatible Markdown, Bases, and CLAUDE guidance | Need `vaultwright obsidian doctor`, tested skill install guidance, and Vaultwright-specific governance skills | 3 |
| V1-C7 | Profile-aware catalogs, Bases, and Canvas outputs | `vaultwright catalog` emits Markdown/HTML inventory from manifests; `vaultwright profile views --check/--write` generates the profile-owned `Documents.base` file from `_meta/profile.yml`, and CI smoke tests check it for source and wheel installs | Need richer profile-specific Base presets plus generated Canvas recipes | 3 |
| V1-C8 | Three external profile pilots | Dogfood copy and government-services example provide internal evidence; benchmark and pilot reporting can now discover profile-declared benchmark task packs | Need one structured external pilot each for business-operations, research-learning, and software-project | 6 |
| V1-C9 | Tagged v1 release with upgrade, recovery, security, and support docs | Recovery, security, release, and design-partner docs exist | Need profile-aware upgrade/recovery docs, release artifact validation, and published known limitations | 6 |
| V1-C10 | Journaled changed-file materialization | ADR 0002 defines authority boundaries, local derived-state journal semantics, event states, metadata fingerprints, debounce/stability, replay, reconciliation, locking, security, model boundary, adoption, rollback, and benchmark evidence requirements; the canonical white paper and supporting docs now make full sync the baseline/recovery path and journaled materialization the Stage 1B steady-state target. Package-owned `vaultwright.changes` modules now initialize `.vaultwright/state.sqlite`, persist journal events and state transitions, expose `vaultwright journal status`, keep local derived state ignored while staged commits are blocked by the no-data scan, provide deterministic static-feed queueing behind a feed interface, filter generated/local/operational/temp paths before queueing, coalesce repeated events for the same path, compute cheap metadata fingerprints before optional full hashing, support workspace leases, stale-lease recovery, transactional event claims, claimed-event finish checkpoints, failed-event retry, recovery of interrupted `processing` events, expose a source-addressable Office materialization primitive that reuses the existing mirror engine for one vault-relative source, provide deterministic file-stability settling before conversion, process claimed current-path Office events through a lease-protected worker primitive, apply manifest-backed deleted events as `source_missing` while retaining generated mirrors, replay resolved `source_moved` records after old mirror cleanup, replay delete/recreate back to `clean`, replay recoverable journal work idempotently with `vaultwright journal replay`, queue missed source/manifest work through explicit `vaultwright reconcile`, expose `vaultwright sync --changed` plus explicit `vaultwright sync --full`, expose `vaultwright watch --once` for deterministic startup reconciliation, feed queueing, and replay, expose optional watchdog-backed `vaultwright watch --native` capture over configured content roots, record synthetic benchmark evidence in `docs/JOURNALED_MATERIALIZATION_BENCHMARK.md`, and pass the focused, affected, full-suite, packaging, lint, no-data, template-copy, shell syntax, diff, and residue gates. | Closed for Stage 1B; keep full sync as recovery and keep later profile/index/adapter work gated | 1B |

Stage 1 V1-C2 note: `vaultwright lint` now matches the profile-contract-first posture used by
doctor, migration, and Office sync. A valid `_meta/profile.yml` provides canonical domains, so a
missing `_meta/domain-map.yml` is a non-blocking legacy-alias warning; malformed or contradictory
domain-map content and profile-less legacy vaults still fail. Lint now loads `_meta/profile.yml`
through the package profile validator before deriving domains, note types, statuses, policy
defaults, and content roots. Shared runtime profile helpers now expose profile-derived sync/report
settings, context fields, context aliases, and active content roots only from a validated profile
contract or the profile-less legacy fallback; lint and GitHub repo sync reuse those helpers instead
of maintaining separate profile parsers or local repo-context fallback defaults. Catalog, overlap
calibration, and repo mirror output validation now share the same profile-owned content-root
fallback. Catalog and migration reporting also load profile domain
routing through the package validator before treating profile-declared folders as canonical, and
Office/GitHub generated mirror frontmatter ordering now shares runtime profile-derived context
keys before managed source/repo metadata. Benchmark/pilot task discovery validates the active
profile before using profile-declared
`benchmark_tasks`. Office source-mirror and GitHub repo-mirror frontmatter ordering now read the
active profile's context fields instead of privileging business-only context keys for every
profile, Office mirror planning reports unsafe output paths against the active profile/configured
mirror root instead of a legacy `_mirrors/` fallback, sandbox preflight now treats legacy
domain-map/mirror-config files as optional when a valid profile contract is present, and runtime
helpers no longer infer business context aliases from the profile ID when
`policy_defaults.context_aliases` is absent. Generic doctor, sandbox, pilot, benchmark, and
conversion report copy now uses workspace, protected-identifier, private-evidence, and
source-backed language instead of client-specific wording on profile-neutral workflows.
Lint repo-mirror path checks now use the shared runtime repo-notes directory helper for configured
`tools/repos.yml` notes directories and profile defaults. Annotation migration now uses the shared
runtime context helper path for repo context keys and aliases, preserving profile-less legacy
fallback without duplicating those defaults locally.

Stage 1A profile-assumption inventory note: `docs/V1_PROGRESS_AUDIT_2026-06-23.md` now classifies
the remaining hard-coded profile vocabulary across package code, copied-tool shims, templates,
examples, and tests as universal mirror-layer invariants, business profile data, legacy
compatibility fallbacks, or test fixtures. No inventory-confirmed Stage 1A-blocking defect is
known. Stage 1B journaled materialization must reuse the shared runtime profile helpers and
mirror artifact semantics rather than introducing a second set of folder, mirror-root, repo-note,
context, or status constants.

## Conditional V1 Explorer Finish Line

Stage 4 decides whether these stay in v1 or move to post-v1. Do not build a visual Explorer before
the index has benchmark evidence.

| ID | Requirement | Gate Evidence | Stage |
| --- | --- | --- | --- |
| V1-E10 | Disposable local evidence index | SQLite/FTS index rebuilds equivalently, stores graph edges with provenance, and never becomes authoritative | 4 |
| V1-E11 | Exploration CLI/MCP interface | `vaultwright explore` and `vaultwright_explore` return bounded context with lifecycle, review, provenance, token estimate, and prompt-safety guidance | 4 |
| V1-E12 | Read-only visual Explorer with context export | Localhost-only Explorer reads shared profile/index model and exports Markdown/JSON context packs | 5 |

## Open Work Mapping

| Open Work | Finish-Line Mapping | Execution Rule |
| --- | --- | --- |
| Copied vault-local scripts | V1-C1 | Keep package modules authoritative; copied sync, lint, catalog, conversion, m365, migration, overlap, benchmark, pilot, sandbox, recovery, review-ledger, and operator-wrapper scripts are now shims |
| Hard-coded business folders, note types, statuses, and linter assumptions | V1-C2, V1-C3, V1-C7 | Use the Stage 1A inventory in `docs/V1_PROGRESS_AUDIT_2026-06-23.md` as the control list; continue extracting only inventory-proven non-universal runtime defects into profile contracts before adding more profiles. `lint`, `catalog`, `migration`, Office mirror placement defaults, overlap calibration roots/context links/inactive statuses, benchmark tasks, repo mirror defaults/context fields, Microsoft 365/sandbox/recovery/review repo/source mirror reporting, and `Documents.base` generation now read validated profile-defined values |
| Current business template and examples | V1-C3, V1-C4 | Treat as `business-operations`; migrate rather than fork |
| Above-sentinel notes in generated mirrors | V1-C5 | Preserve first with `migrate annotations --write`; sync blocks unmigrated mirror annotations, fresh mirrors are machine-owned, and sidecar-aware sync makes migrated mirrors machine-owned on the next regeneration |
| Repeated whole-corpus steady-state sync cost | V1-C10 | Closed for Stage 1B by the journaled changed-file path and benchmark evidence; keep full sync as the recovery path and refresh measurements before later release claims |
| Obsidian Bases and future Canvas outputs | V1-C6, V1-C7 | Adapter only; `profile views --check` keeps generated Bases testable without Obsidian, and Canvas remains open |
| Agent-readiness benchmark | V1-C8, V1-E10, V1-E11 | Keep benchmark task packs profile-declared, keep generated mirror evidence rooted in the active Office mirror root, and use measured results from later profile pilots before deciding the Stage 4 Explorer gate |
| Catalog JSON/Markdown/HTML | V1-C1, V1-C7, V1-E12 | Package-owned `vaultwright catalog` is now the shared view-model path; continue preserving it, but do not broaden UI work before the later profile/index gates |
| Microsoft 365/Copilot handoff | V1-C9 | Keep as support/deployment documentation, not an enterprise taxonomy profile |
| Local evidence index | V1-E10 | Build after profile/core schema groundwork; no vector DB by default |
| Visual Explorer | V1-E12 | Build only if Stage 4 benchmark gate passes |

## Command Surface Rule

The CLI should shrink toward a small stable surface:

```text
vaultwright init --profile business-operations <path>
vaultwright profile list
vaultwright profile show
vaultwright profile validate
vaultwright profile diff <target-profile-version>
vaultwright profile migrate --plan
vaultwright profile migrate --write
vaultwright profile views --check
vaultwright profile views --write
vaultwright migrate annotations --plan
vaultwright migrate annotations --write
vaultwright watch
vaultwright sync --changed
vaultwright sync --full
vaultwright journal status
vaultwright journal replay
vaultwright reconcile
vaultwright index build
vaultwright index status
vaultwright explore "question"
```

Existing report commands may remain while they are release-critical compatibility surfaces. New
standalone report commands are not allowed unless they replace existing behavior or map directly to
a finish-line requirement above.

Current Stage 2 command status: `init --profile business-operations`,
`init --profile research-learning`, `init --profile software-project`, `init --profile blank`, `profile list`,
`profile show`, `profile validate`, `profile diff`, read-only `profile migrate --plan`,
conservative `profile migrate --write`, `profile views --check`, `profile views --write`,
`migrate annotations --plan`, `migrate annotations --write`, `plan`, `sync`, `status`, `doctor`,
`lint`, `catalog`, `conversion`, `m365`, `migration`, `overlap`, `benchmark`, `pilot`, `sandbox`,
`recovery`, and `review` are implemented against package-owned runtime. Copied vault-local sync,
lint, catalog, conversion, m365, migration, overlap, benchmark, pilot, sandbox, recovery,
review-ledger, and operator-wrapper tools are compatibility shims.
Sidecar-aware Office/repo sync rewrites migrated mirrors as machine-owned on regeneration; fresh
mirrors are machine-owned; sync and lint block unmigrated mirror annotations.
`journal status` exists for local derived-state introspection only. `journal replay` exists for
idempotent recovery of interrupted processing events and explicit failed-event retry. `reconcile`
exists for explicit source/manifest repair queueing. `sync --changed` now composes reconcile and
replay; `sync --full` names the existing full sync recovery path explicitly. `watch --once` exists
for deterministic startup reconciliation/feed queueing/replay, and `watch --native` exists as an
optional watchdog-backed capture loop. `index` and `explore` remain gated future work after the
official-profile and Obsidian gates.

## Post-V1 Backlog

The following are explicitly outside v1 unless they replace a v1 requirement:

- hosted SaaS;
- multi-user real-time collaboration;
- enterprise administration console;
- Obsidian plugin;
- public profile marketplace;
- mobile application;
- automatic OCR and high-fidelity layout extraction for every format;
- vector embeddings by default;
- autonomous note deletion or consolidation;
- email and mailbox ingestion;
- broad connector catalog;
- desktop application shell;
- automatic enterprise permission or retention enforcement.
- package-part DOCX/PPTX/XLSX/PDF extraction;
- default semantic-delta model processing;
- cloud-provider change-feed adapters.
