# Vaultwright V1 Finish-Line Matrix

This matrix is the execution control document for the 2026-06-23 whitepaper revision and
`docs/adr/0001-profile-driven-v1-architecture.md`.

Current progress and next execution order are summarized in
`docs/V1_PROGRESS_AUDIT_2026-06-23.md`.

Its job is to keep development converging. Work is v1-aligned only when it advances a listed
requirement, replaces a weaker implementation, or preserves existing gates while preparing a
required migration. New ideas that do not map here move to the post-v1 backlog.

## Stage-Gate Plan

| Stage | Gate | Required Evidence | Status |
| --- | --- | --- | --- |
| 0. Scope freeze and architecture decision | Product statement, six-layer architecture, v1 profiles, v1 non-goals, and stop rule are approved and tracked | ADR 0001 plus this matrix are committed; README/product docs point to them | Complete |
| 1. Kernel and packaging convergence | Runtime logic moves into `src/vaultwright/`; vault-local scripts become compatibility shims; profile and core schemas exist; generated mirrors become machine-owned with annotation migration | Package owns behavior; tests prove source integrity, idempotency, lifecycle, recovery, migration, and safety | In progress |
| 2. Official profiles | `business-operations`, `research-learning`, `software-project`, and `blank` initialize from the same core package | Profile fixtures pass identical lifecycle and no-data gates; no core hard-coding of profile folders/types/statuses | Not started |
| 3. Obsidian adapter and skills | Obsidian integration stays optional; governance skills and profile-aware Bases/Canvas outputs exist | Generated `.base` and `.canvas` artifacts pass syntax/integrity tests; core tests pass without Obsidian | Not started |
| 4. Evidence index and exploration gate | Local SQLite/FTS graph index, `index build`, `index status`, `explore`, MCP exploration tool, and benchmark comparison exist | Deletion/rebuild equivalence, provenance on every result, no cross-workspace retrieval, and material benchmark improvement | Not started |
| 5. Explorer and context builder | Only if Stage 4 passes: local read-only Explorer and context pack export | Explorer reads shared index/profile model; no UI-only business logic; accessibility and browser checks pass | Conditional |
| 6. External validation and v1 release | Three structured pilots complete; release artifact installs and upgrades; limitations and support boundaries are published | Business-operations, research-learning, and software-project pilots all produce measured improvements and source-backed handoffs | Not started |

## Mandatory V1 Core Finish Line

| ID | Requirement | Current Evidence | Gap To Close | Stage |
| --- | --- | --- | --- | --- |
| V1-C1 | One installable cross-platform core package owns runtime behavior | `pyproject.toml` exposes a `vaultwright` console entry point; CI installs package; installed `vaultwright plan`, `vaultwright sync`, and `vaultwright status` orchestrate package-owned Office/repo sync modules directly; `vaultwright doctor` runs package-owned preflight checks; `vaultwright catalog` runs package-owned catalog code; `vaultwright lint` runs package-owned lint code; `vaultwright recovery` runs package-owned recovery-report code; `vaultwright review` runs package-owned review-ledger code; Office mirror planning/sync/status runs from `vaultwright.mirrors.office`; GitHub repo mirror planning/sync/status runs from `vaultwright.mirrors.github_repos`; vault-local sync, lint, recovery, review-ledger, and operator-wrapper tools remain compatibility surfaces | Runtime still lives partly in copied `template/tools/` scripts; continue moving remaining commands into `src/vaultwright/` and leave vault-local tools as compatibility shims | 1 |
| V1-C2 | One versioned profile contract | `src/vaultwright/profiles.py` validates schema version 1; `_meta/profile.yml` declares the current `business-operations` template; package CLI exposes `init --profile business-operations`, `profile list`, `profile show`, `profile validate`, `profile diff`, and read-only `profile migrate --plan`; linter/catalog read profile domains, note types, statuses, required properties, and canonical folders | Need full profile schema docs, write-mode profile migration support, and remaining core behavior reading profile data | 1 |
| V1-C3 | Three official content profiles plus a blank starter | Existing template approximates `business-operations`; government-services example exercises that profile shape | Need `business-operations`, `research-learning`, `software-project`, and `blank` as package-owned profiles | 2 |
| V1-C4 | Safe migration path from current business template | Migration reports, frontmatter domain normalization, and package-owned `profile migrate --plan` exist | Need write-mode workspace/profile migration that moves from current template to profile contract without source mutation or annotation loss | 1 |
| V1-C5 | Machine-owned mirrors with preserved human annotations | Package-owned `migrate annotations --plan` and `--write` preserve legacy mirror notes/frontmatter into `_meta/mirror-annotations/` sidecars keyed by source/repo ID; fresh mirrors use machine-owned headers without a curated `## Notes` region; Office/repo sync blocks unmigrated above-sentinel annotations as force-blocking review work and rewrites migrated mirrors as machine-owned when a matching sidecar exists; lint blocks unmigrated mirror annotations | Closed for Stage 1; keep compatibility tests and recovery guidance current while broader migration UX evolves | 1 |
| V1-C6 | Obsidian adapter and first-party governance skill pack | Template ships Obsidian-compatible Markdown, Bases, and CLAUDE guidance | Need `vaultwright obsidian doctor`, tested skill install guidance, and Vaultwright-specific governance skills | 3 |
| V1-C7 | Profile-aware catalogs, Bases, and Canvas outputs | `vaultwright catalog` emits Markdown/HTML inventory from manifests | Need catalog/view generation to read profile contracts and emit profile-specific Bases/Canvas recipes | 3 |
| V1-C8 | Three external profile pilots | Dogfood copy and government-services example provide internal evidence | Need one structured external pilot each for business-operations, research-learning, and software-project | 6 |
| V1-C9 | Tagged v1 release with upgrade, recovery, security, and support docs | Recovery, security, release, and design-partner docs exist | Need profile-aware upgrade/recovery docs, release artifact validation, and published known limitations | 6 |

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
| Copied vault-local scripts | V1-C1 | Refactor into package modules first; leave scripts only as shims during migration; Office sync, repo sync, installed plan/sync/status orchestration, doctor, lint, catalog, recovery, and review are the current package-owned examples |
| Hard-coded business folders, note types, statuses, and linter assumptions | V1-C2, V1-C3, V1-C7 | Continue extracting into profile contracts before adding more profiles; `lint` and `catalog` now read profile-defined allowed values and canonical folders |
| Current business template and examples | V1-C3, V1-C4 | Treat as `business-operations`; migrate rather than fork |
| Above-sentinel notes in generated mirrors | V1-C5 | Preserve first with `migrate annotations --write`; sync blocks unmigrated mirror annotations, fresh mirrors are machine-owned, and sidecar-aware sync makes migrated mirrors machine-owned on the next regeneration |
| Obsidian Bases and future Canvas outputs | V1-C6, V1-C7 | Adapter only; correctness must remain testable without Obsidian |
| Agent-readiness benchmark | V1-C8, V1-E10, V1-E11 | Make profile-aware and use it to decide the Stage 4 Explorer gate |
| Catalog JSON/Markdown/HTML | V1-C1, V1-C7, V1-E12 | Package-owned `vaultwright catalog` is now the shared view-model path; continue stabilizing it before richer UI |
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
vaultwright migrate annotations --plan
vaultwright migrate annotations --write
vaultwright index build
vaultwright index status
vaultwright explore "question"
```

Existing report commands may remain while they are release-critical compatibility surfaces. New
standalone report commands are not allowed unless they replace existing behavior or map directly to
a finish-line requirement above.

Current Stage 1 command status: `init --profile business-operations`, `profile list`,
`profile show`, `profile validate`, `profile diff`, read-only `profile migrate --plan`,
`migrate annotations --plan`, `migrate annotations --write`, `plan`, `sync`, `status`, `doctor`,
`lint`, `catalog`, `recovery`, and `review` are implemented against package-owned runtime. Office mirror
planning/sync/status and repo mirror planning/sync/status are package-owned while their vault-local
tools remain compatibility surfaces; vault-local recovery and review-ledger tooling remains as a
compatibility surface.
Sidecar-aware Office/repo sync rewrites migrated mirrors as machine-owned on regeneration; fresh
mirrors are machine-owned; sync and lint block unmigrated mirror annotations.
Write-mode `profile migrate`, `index`, and `explore` remain gated future work.

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
