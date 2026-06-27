# Changelog

All notable changes to Vaultwright are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); Python package prereleases use PEP 440.

## [Unreleased]

### Added
- Closed the Stage 2 V1-C3 official-profile gate: `vaultwright init --profile` now scaffolds
  `business-operations`, `research-learning`, `software-project`, and `blank` from the package,
  with non-business profile folders, generated scaffold docs, matching domain maps, and
  profile-declared note templates derived from the selected contract; tests now add a synthetic
  source to each initialized profile and verify clean Office mirror lifecycle/status/lint behavior.
- Closed the Stage 1B V1-C10 safety gate in the controlling docs after the focused, affected,
  full-suite, packaging, lint, no-data, template-copy, shell syntax, diff, and residue gates passed
  for journaled changed-file materialization.
- Added optional Stage 1B native watch capture with `vaultwright watch --native`, backed by the
  `vaultwright[watch]` watchdog extra; native events are observed only under configured content
  roots, buffered, normalized through the existing feed filters, and flushed through journal replay.
- Added deterministic Stage 1B journaled-materialization benchmark evidence with
  `scripts/benchmark_journaled_materialization.py`, proving known-path replay over 1,000 synthetic
  sources performs zero whole-workspace discovery, hashes no untouched source bodies, and invokes
  the converter once for one modified source.
- Added Stage 1B move/recreate replay coverage: reconciliation now requeues resolved
  `source_moved` records after the previous generated mirror is removed, allowing
  `sync --changed` to generate the new mirror with the same source ID, and tests cover
  delete/recreate returning a source record to `clean`.
- Added Stage 1B deleted-source replay handling: manifest-backed `deleted` journal events now mark
  Office source records `source_missing`, retain generated mirrors for review, append audit
  evidence, and finish as applied work instead of generic review-required events.
- Added Stage 1B watch startup orchestration with `vaultwright watch --once`, composing startup
  reconciliation, feed-event queueing, and journal replay; optional native capture is now handled
  by `vaultwright watch --native`.
- Added Stage 1B changed-file sync orchestration with `vaultwright sync --changed`, composing
  explicit reconciliation and journal replay while preserving the existing full-sync path as
  `vaultwright sync` / `vaultwright sync --full`.
- Added Stage 1B explicit reconciliation with `vaultwright reconcile`, queuing missed created,
  modified, moved, deleted, and review-required candidate events from source/manifest state with
  metadata-first comparison and candidate-only hashing for safe move detection.
- Added Stage 1B idempotent journal replay with `vaultwright journal replay`, recovering
  interrupted `processing` events under the workspace lease, explicitly retrying failed events
  only with `--retry-failed`, and exposing bounded/JSON replay output.
- Added a Stage 1B lease-protected changed-source worker primitive that claims journal events,
  runs source-addressable Office materialization for current-path events, records source identity
  on finished journal rows, and finishes events as applied, review-required, or failed.
- Added deterministic Stage 1B file-stability settling for changed-source candidates, with
  injectable clock/sleeper/fingerprint tests and optional pre-conversion settling in the
  source-addressable Office materialization primitive.
- Added a Stage 1B source-addressable Office materialization primitive that processes one
  vault-relative source through the existing Office mirror engine, preserves source bytes, honors
  profile-defined mirror roots, writes manifest/audit state, and skips unchanged conversions.
- Added Stage 1B journal worker coordination primitives: workspace lease acquisition/release,
  stale-lease takeover, transactional event claiming, claimed-event finishing, failed-event retry,
  and recovery of events left `processing` after an interrupted worker.
- Added deterministic Stage 1B change-feed and metadata-fingerprint primitives, including a static
  test feed, generated/local/operational path filtering, event coalescing before queueing, and a
  no-full-hash fast path when the cheap fingerprint is unchanged.
- Added the first Stage 1B journal foundation: package-owned changed-file event/state modules,
  local `.vaultwright/state.sqlite` initialization, `vaultwright journal status`, `.vaultwright/`
  ignore/no-data safeguards, and focused persistence tests without starting watcher delivery.
- Closed the Stage 1A kernel/profile-convergence gate in the controlling docs, preserving the
  package-runtime/shim boundary and opening the Stage 1B journaled materialization lane.
- Documented the Stage 1A profile-assumption inventory across package code, copied-tool shims,
  templates, examples, and tests, with classifications for universal invariants, business profile
  data, legacy compatibility fallbacks, test fixtures, and verified defects.
- Adopted the June 24 canonical white paper, added ADR 0002 for journaled incremental
  materialization, split Stage 1 into Stage 1A/Stage 1B in the finish-line controls, and added
  V1-C10 for journaled changed-file materialization while preserving full sync as the
  baseline/recovery path.
- Added the 2026-06-23 strategic whitepaper revision, ADR 0001, and `docs/V1_FINISH_LINE.md` so
  v1 work is gated by the profile-driven architecture, explicit non-goals, and Core/Explorer
  finish-line matrix.
- Added an initial package-owned profile contract validator plus `_meta/profile.yml` for the
  current `business-operations` template, establishing the first Stage 1 profile-schema seam.
- Added package-owned v1 profile contracts for `research-learning`, `software-project`, and
  `blank`; `vaultwright profile list/show` now exposes all four official profile contracts.
- Added a shared runtime profile helper for active content roots so lint, catalog, overlap
  calibration, and repo mirror output validation use the same profile-owned folder fallback.
- Added shared runtime profile frontmatter-key ordering so Office and GitHub generated mirrors
  place profile-owned context fields consistently before managed source/repo metadata.
- The installable `vaultwright` CLI now supports `init --profile business-operations`,
  `profile list`, `profile show`, and `profile validate` against the package-owned profile
  contract.
- `vaultwright lint` and `vaultwright catalog` now read `_meta/profile.yml` for profile-defined
  domains, note types, statuses, required properties, and canonical content folders. The migration
  report now uses profile-defined canonical domains while `_meta/domain-map.yml` remains the legacy
  alias compatibility layer.
- The installable `vaultwright catalog` command now runs package-owned catalog code from
  `src/vaultwright/`, while the vault-local `tools/catalog_report.py` remains available as a
  compatibility surface.
- Added package-owned `profile diff` and read-only `profile migrate --plan` commands so profile
  version drift, missing profile files, and template drift can be reviewed before any write-mode
  profile migration.
- Added `docs/PROFILE_SCHEMA.md` and conservative package-owned `profile migrate --write` support
  that creates missing shared/profile-planned directories and copies missing packaged
  profile/template files without overwriting existing files, source documents, generated mirrors,
  or annotation sidecars.
- Profile validation now requires domain, note-type, and status identifiers to be lowercase
  kebab-case, and required/optional frontmatter property names to be lowercase frontmatter keys
  without duplicates.
- Profile validation now rejects unknown fields inside domain, note-type, and status definitions,
  and validates optional `purpose` strings so profile data stays declarative.
- Profile validation now rejects unknown fields inside `folder_plan` entries and
  `policy_defaults`, keeping profile bootstrap and policy data schema-declared.
- Profile validation now rejects frontmatter keys that are listed as both required and optional,
  keeping generated views, lint, and repo-context inference aligned with one profile-owned field
  contract.
- Profile validation now requires `templates`, `views`, and `skills` entries to be safe
  vault-relative artifact paths without duplicates.
- Profile validation now enforces safe domain folders plus non-empty `folder_plan` records whose
  paths stay inside declared profile domains, and profile migration creates directories from that
  validated folder plan.
- Profile validation now rejects duplicate or nested domain folders, keeping profile-driven domain
  routing, migration, and mirror placement unambiguous.
- `vaultwright overlap` now reads the active profile's domain folders when choosing curated notes
  for calibration, so profile-defined content roots participate without hard-coded business
  folders.
- `vaultwright overlap` now also reads profile-defined context frontmatter fields when counting
  inbound wikilinks, so non-business profiles can use fields such as `research_project` without
  inheriting `account`/`client` assumptions.
- Profile status definitions can now declare `attention: true` and `inactive: true`; generated
  Bases use the attention role for review views, and lint/overlap use inactive statuses instead of
  hard-coded business status names when skipping retired notes.
- Profile note type definitions can now declare `machine_owned: true`; validation enforces boolean
  values, overlap excludes machine-owned artifacts, and migration frontmatter cleanup ignores them
  without relying only on hard-coded mirror type names.
- `vaultwright catalog` now separates profile-defined machine-owned Markdown artifacts from curated
  Markdown/domain counts, while surfacing them as their own inventory metric.
- `vaultwright m365` now separates profile-defined machine-owned Markdown artifacts, including
  repo mirrors, from curated Markdown counts in handoff inventory.
- `vaultwright sandbox` now reports profile-defined machine-owned Markdown separately from curated
  Markdown in copied-vault preflight inventory.
- Profiles now own generated mirror status defaults with `policy_defaults.mirror_status` and
  `policy_defaults.repo_stub_status`; Office/repo sync, lint, and annotation migration use those
  values instead of hard-coded `active`/`draft` checks for generated mirror metadata.
- Profiles now own Office mirror placement defaults with `policy_defaults.mirror_mode` and
  `policy_defaults.mirror_root`; Office sync and lint use those values when
  `_meta/mirror-config.yml` does not override them.
- Profile migration now creates the target profile's `policy_defaults.mirror_root` directory
  instead of assuming `_mirrors/`, while preserving the legacy fallback for older profiles.
- Office mirror domain routing now uses active profile domain folders as canonical, with
  `_meta/domain-map.yml` retained only for legacy aliases and compatibility guidance.
- Catalog, Microsoft 365 handoff, sandbox, doctor, review-ledger classification, and migration
  guidance now classify generated source mirrors from the active Office mirror root instead of
  assuming `_mirrors/`.
- `vaultwright migration --worksheet`, `--runbook`, and frontmatter-normalization worksheets now
  print the active profile identity plus canonical domain folders, and direct unknown folder/domain
  decisions back to `_meta/profile.yml` while keeping `_meta/domain-map.yml` as the legacy alias
  layer.
- Benchmark task-pack validation, result citation validation, and `benchmark --init-tasks`
  scaffolding now use the active Office mirror root for generated mirror evidence paths.
- `vaultwright pilot` now excludes the active Office mirror root from workspace inventory, so
  custom generated roots are not counted as operator content or source candidates.
- `vaultwright recovery` now excludes the active Office mirror root from missing-manifest source
  evidence checks, so custom generated roots do not trigger false unsynced-source warnings.
- Profile validation now rejects templates, views, skills, and benchmark task packs declared inside
  `policy_defaults.mirror_root`, keeping generated Office mirrors separate from profile artifacts.
- Generated `Documents.base` review-attention filters now use only profile-declared
  `attention: true` status roles instead of inferring business-oriented status names.
- `vaultwright doctor` now reports profile-declared generated view health through the profile view
  planner, warning on missing or stale views without assuming every profile owns `Documents.base`.
- `vaultwright doctor` now validates the active profile contract first and treats
  `_meta/domain-map.yml` and `_meta/mirror-config.yml` as legacy alias/override files for
  profile-driven vaults, while preserving legacy required-file checks for profile-less vaults.
- `vaultwright lint` now treats a missing `_meta/domain-map.yml` as a non-blocking legacy-alias
  warning when a valid profile contract provides canonical domains, while profile-less legacy
  vaults still fail when the domain map is missing.
- `vaultwright lint` now loads `_meta/profile.yml` through the package profile validator before
  deriving allowed domains, note types, statuses, policy defaults, and content roots, so invalid
  profile contracts block lint before unsafe profile data can drive checks.
- `vaultwright lint` now reuses the shared runtime profile context helpers directly for context
  fields and aliases, preserving profile-less legacy fallback without local duplicate defaults.
- `vaultwright lint` now reuses the shared runtime repo-notes directory helpers for repo-mirror
  path checks, so configured `tools/repos.yml` notes directories and profile defaults share one
  fallback path.
- Shared runtime profile helpers now load `_meta/profile.yml` through the package profile
  validator before exposing domains, status roles, mirror defaults, repo context fields, or repo
  mirror folders to sync/report code; invalid contracts fall back to legacy defaults instead of
  partially trusted profile data, and GitHub repo sync reuses the shared helper path.
- `vaultwright catalog` and `vaultwright migration` now load profile domain routing through the
  package profile validator before reporting canonical profile folders, so invalid profile
  contracts surface as report errors instead of letting partial profile data drive routing.
- `vaultwright benchmark` and the aggregate `vaultwright pilot` report now load profile-declared
  `benchmark_tasks` paths through the package profile validator, while explicit `--tasks` and the
  legacy `_meta/agent-readiness-tasks.yml` path remain supported.
- Added package-owned `profile views --check` and `profile views --write` commands that generate
  the profile-owned `Documents.base` file from `_meta/profile.yml`, with CI smoke coverage for
  source and wheel installs.
- GitHub repo mirror sync and lint now read the profile's `policy_defaults.repo_notes_dir` as the
  default repo-mirror location, and generated repo-mirror frontmatter derives its domain from the
  profile's domain/folder mapping.
- GitHub repo mirror sync and lint now read `policy_defaults.context_aliases`, so the
  `business-operations` profile can declare `client` as an alias of `account` without forcing that
  business-specific rule onto any valid profile that omits the policy.
- Profile validation now requires `policy_defaults.repo_notes_dir`, when present, to be a safe
  vault-relative folder inside a declared profile domain and separate from the Office mirror root.
- Profile validation now enforces boolean source-authority/no-real-data policy defaults, requiring
  `original_sources_authoritative: true` and `real_data_in_repo: false` when those defaults are
  declared.
- GitHub repo mirror sync, lint, and annotation migration now derive repo-context frontmatter keys
  from the active profile's optional properties, preserving the business profile's
  `account`/`client` compatibility while allowing non-business profiles to use their own context
  fields.
- Office source-mirror frontmatter ordering now uses the active profile's context fields before
  managed source metadata, instead of privileging business-only context keys in every profile.
- GitHub repo-mirror frontmatter ordering now uses the active profile's context fields before
  managed repo metadata, and runtime helpers no longer infer business context aliases from a
  profile ID when `policy_defaults.context_aliases` is absent.
- GitHub repo mirror sync now reuses the shared runtime profile context helpers directly for
  repo-context fields and aliases, preserving profile-less legacy fallback without local duplicate
  defaults.
- Annotation migration now also reads `policy_defaults.context_aliases` when comparing generated
  repo-mirror frontmatter with `tools/repos.yml`, so profile-defined aliases are not mistaken for
  human mirror annotations.
- Annotation migration now reuses the shared runtime profile context helpers for repo-context
  fields and aliases, preserving profile-less legacy fallback without a separate local copy.
- Review-ledger classification now accepts profile-defined `machine_owned` Markdown note types as
  generated review targets while still recording only metadata, hashes, and frontmatter fields.
- Microsoft 365 handoff, sandbox preflight, recovery, and review-ledger reporting now resolve repo
  mirror folders from the active profile or `tools/repos.yml`, and the vault-local report scripts
  delegate to the package runtime to prevent implementation drift.
- Generic doctor, sandbox, pilot, benchmark, and conversion report copy now uses workspace,
  protected-identifier, private-evidence, and source-backed language instead of client-specific
  wording on profile-neutral workflows.
- Vault-local catalog, conversion, migration, overlap, benchmark, and pilot tools now also delegate
  to the package runtime, leaving copied vault scripts as compatibility shims for package-owned
  behavior.
- The vault-local `tools/vaultwright.py` operator wrapper now delegates to the package CLI while
  preserving the copied vault root as the default `--root`.
- Added package-owned `migrate annotations --plan` and `migrate annotations --write` commands that
  move above-sentinel mirror notes and preserved frontmatter into `_meta/mirror-annotations/`
  sidecars keyed by `source_id` or `repo_id`, without editing original sources or generated mirrors.
- Office and repo mirror sync now recognize matching annotation sidecars and reset regenerated
  mirrors to machine-owned headers instead of carrying migrated human annotations forward.
- `vaultwright lint` now blocks generated source/repo mirrors that still contain above-sentinel
  human annotations unless a matching `_meta/mirror-annotations/` sidecar exists.
- Office and repo sync now stop preserving legacy above-sentinel annotations automatically: unmigrated
  annotations become force-blocking review work, and fresh mirrors use machine-owned headers without
  a curated `## Notes` region.
- Office mirror planning, sync, and status behavior now lives in package-owned
  `vaultwright.mirrors.office`; vault-local `tools/sync_office_md.py` is a compatibility shim copied
  through the package template and examples.
- GitHub repo mirror planning, sync, and status behavior now lives in package-owned
  `vaultwright.mirrors.github_repos`; vault-local `tools/sync_github_repos.py` is a compatibility
  shim copied through the package template and examples.
- The installable `vaultwright plan`, `vaultwright sync`, and `vaultwright status` commands now
  orchestrate the package-owned Office and repo sync modules directly, while the vault-local
  `tools/vaultwright.py` wrapper remains available for compatibility.
- The installable `vaultwright doctor` command now runs package-owned preflight checks from
  `vaultwright.doctor`, including dependency, manifest, lifecycle-contract, recovery, review-ledger,
  Obsidian, backup, git, and GitHub auth posture checks.
- Vault health checks now live in package-owned `vaultwright.lint`; vault-local
  `tools/lint_vault.py` is a compatibility shim copied through the package template and examples.
- The installable `vaultwright conversion` command now runs package-owned `vaultwright.conversion`
  code; vault-local `tools/conversion_report.py` remains available as a compatibility surface, and
  CI smoke tests cover package-level conversion JSON output.
- The installable `vaultwright m365` command now runs package-owned `vaultwright.m365` code;
  vault-local `tools/m365_report.py` remains available as a compatibility surface, and CI smoke
  tests cover package-level handoff JSON output.
- The installable `vaultwright migration` command now runs package-owned `vaultwright.migration`
  code; vault-local `tools/migration_report.py` remains available as a compatibility surface, and
  CI smoke tests cover package-level migration JSON output.
- The installable `vaultwright overlap` command now runs package-owned `vaultwright.overlap` code;
  vault-local `tools/overlap_report.py` remains available as a compatibility surface, and CI smoke
  tests cover package-level overlap JSON output.
- The installable `vaultwright benchmark` command now runs package-owned `vaultwright.benchmark`
  code; vault-local `tools/benchmark_tasks.py` remains available as a compatibility surface, and
  package tests cover task/result validation, private scaffolds, and worksheets without the
  vault-local wrapper.
- The installable `vaultwright pilot` command now runs package-owned `vaultwright.pilot` code and
  imports package-owned report modules for its aggregate evidence summaries; vault-local
  `tools/pilot_report.py` remains available as a compatibility surface.
- The installable `vaultwright sandbox` command now runs package-owned `vaultwright.sandbox` code
  and imports package-owned recovery reporting for its copied-vault preflight; vault-local
  `tools/sandbox_report.py` remains available as a compatibility surface.
- The installable `vaultwright recovery` command now runs package-owned `vaultwright.recovery`
  code; vault-local `tools/recovery_report.py` remains available as a compatibility surface, and
  CI smoke tests cover package-level JSON and worksheet output.
- The installable `vaultwright review` command now runs package-owned `vaultwright.review_ledger`
  code; vault-local `tools/review_ledger.py` remains available as a compatibility surface, and CI
  smoke tests cover package-level record/check behavior.
- Added `tools/catalog_report.py` and `vaultwright catalog`, which writes a generated
  source-path-only `CATALOG.md` inventory gateway with domain, format, lifecycle, mirror, repo,
  unmanaged-source, and legacy-folder summaries.
- `vaultwright catalog --html` now writes the same path-and-metadata-only inventory as a static
  `CATALOG.html` gateway with aggregate charts for reviewers who prefer a browser surface.
- `vaultwright catalog` now surfaces lifecycle contract provenance from source/repo manifests,
  showing which contract path and schema version govern manifest lifecycle states.
- `_meta/mirror-config.yml` now supports `office_mirrors.include_pdf: true` so unattended syncs can
  refresh text-based PDF mirrors and keep PDF source records under lifecycle provenance coverage.
- CI and release smoke checks now compile and exercise `catalog`, including packaged-template
  installation coverage and Markdown/HTML `catalog --check` freshness validation.
- Added `docs/MICROSOFT_365_HANDOFF.md` and `vaultwright m365`, a read-only handoff readiness
  report for Microsoft 365, SharePoint, OneDrive, Copilot Studio, and connector review paths.
- Updated the Microsoft 365 handoff and whitepaper guidance to treat Vaultwright as a Copilot
  supplement while warning that SharePoint/OneDrive, Copilot Studio uploads, Dataverse,
  connectors, and Retrieval API paths have different file-type and retrieval behavior.
- Regenerated the private copied dogfood vault outside the repo with dedicated `_mirrors/`
  storage, `CATALOG.md`, `CATALOG.html`, and read-only conversion, migration, recovery, pilot, and
  Microsoft 365 review reports; no private source content was added to the repository.
- Added `tools/review_ledger.py` and `vaultwright review`, a metadata-only review ledger that
  records reviewer/status decisions against generated artifact hashes and reports stale approvals
  when reviewed artifacts change.
- `vaultwright pilot` now summarizes review-ledger aggregate counts, including reviewed artifacts,
  stale/missing reviews, and non-approved decisions, without exposing artifact paths or notes.
- `vaultwright pilot` now also summarizes overlap-calibration aggregate counts and current
  thresholds, without exposing note bodies, shared terms, source text, paths, or reviewer notes.
- `vaultwright doctor` now reports review-ledger approval posture and warns on stale/missing or
  non-approved artifact reviews without printing artifact paths, reviewer names, or notes.
- `vaultwright migration` now reports legacy or unknown note frontmatter domains using
  `_meta/domain-map.yml` aliases, giving operators a read-only cleanup queue before moving notes.
- `vaultwright migration --worksheet` now prints a Markdown review checklist for legacy folder and
  frontmatter-domain cleanup batches.
- `vaultwright migration --normalize-frontmatter-domains` now previews known legacy frontmatter
  domain alias rewrites, and `--write` applies only those `domain` frontmatter changes without
  moving files, touching unknown domains, or editing generated mirrors.
- `vaultwright migration --normalize-frontmatter-domains --worksheet` now prints a dry-run review
  checklist for planned frontmatter alias rewrites, skipped generated mirrors, and unknown domains
  before any write is approved.
- CI and release smoke checks now exercise the normalizer worksheet through the packaged CLI.
- `vaultwright migration --runbook` now prints a read-only legacy folder migration protocol with
  preconditions, execution steps, stop conditions, and current alias/unknown cleanup queues.
- CI and release smoke checks now exercise the migration runbook through the packaged CLI.
- `vaultwright recovery --worksheet` now prints a read-only Markdown recovery checklist with
  lifecycle actions, lifecycle-contract explanations/exit conditions, previous mirror context,
  bounded conflict summaries, and latest audit context.
- `vaultwright recovery --runbook` now prints a read-only, state-grouped resolution protocol for
  missing sources, moved sources, unconfigured repo mirrors, manual generated-region edits,
  conflicts/errors, and interrupted write temp files.
- CI and release smoke checks now exercise recovery worksheet and runbook output through the
  packaged CLI.
- Added `tools/sandbox_report.py` and `vaultwright sandbox`, a read-only copied-vault preflight for
  safe pilot workspaces that checks source-root separation, mirror isolation, manifest/recovery
  readiness, and backup posture without printing source paths or document text.
- CI and release smoke checks now compile and exercise `sandbox`, including packaged-template
  installation coverage.
- The installable `vaultwright` console entry point now exercises `sandbox` through the package
  runtime while the vault-local wrapper remains available for compatibility.
- Office sync now blocks ambiguous same-hash source moves as `conflict` when multiple missing
  manifest records could match one new source path.
- Office sync now exits nonzero for review-blocking sync states and flags duplicate exact
  source-path manifest records as `conflict` instead of choosing one source history silently.
- Added `scripts/sync_template_copies.py` plus CI/release drift checks so the packaged template and
  example vault tool copies stay aligned with the canonical `template/` sources.
- `vaultwright benchmark` now reports citation counts and supports `--require-citations` so scored
  agent-readiness results can be gated on declared source or generated-mirror evidence.
- `vaultwright benchmark` now tracks prompt-safety review and prompt-safety violations in private
  result packs, with `--require-prompt-safety` for strict design-partner gates.
- CI and release wheel smoke checks now exercise benchmark result validation with
  `--require-citations` and `--require-prompt-safety` through the packaged CLI.
- `vaultwright benchmark --init-tasks` now writes a private task-pack scaffold from synced
  source/mirror manifest metadata, giving copied pilot vaults a starting benchmark without reading
  or copying document bodies.
- `vaultwright benchmark --init-results` now writes a private, fillable result-pack scaffold for
  every task/mode pair, avoiding hand-built pilot result files while keeping answer text and
  reviewer notes out of aggregate benchmark data.
- `vaultwright benchmark --worksheet` now prints a private Markdown run sheet from the task pack,
  including prompts, rubric, evidence counts, and per-mode scoring fields without source paths,
  mirror paths, answers, or reviewer notes.
- The no-data scanner now rejects private agent-readiness task packs unless they are approved
  public examples, preventing copied-vault benchmark prompts and path lists from entering the repo.
- `vaultwright conversion --init-results` now creates private metadata-only conversion-quality
  result scaffolds, `vaultwright conversion --results ... --require-reviewed` validates
  reviewer-entered status/score/correction/issue-code aggregates, `vaultwright pilot` summarizes
  those aggregates, and the no-data scanner blocks conversion-quality result packs from the public
  repo.
- Conversion review guides and scaffolds now print the allowed result-pack schema, and quickstart
  commands clarify that `--require-reviewed` runs after the private scaffold is filled.
- Generated catalog and Microsoft 365/Copilot handoff reports now include explicit agent
  prompt-safety guidance for treating source and mirror text as untrusted evidence, not
  instructions.
- CI and release wheel smoke checks now exercise conversion-quality scaffold creation plus reviewed
  result-pack validation through the packaged CLI.
- Repo sync/status now detects managed `repo` frontmatter identity drift as stale and normal sync
  rewrites the managed field from the configured/resolved repo identity.
- Repo sync/status now marks previously synced repo mirrors as `repo_unconfigured` when their
  `tools/repos.yml` entry is removed, preserving mirrors until an operator restores config or
  deliberately retires the manifest record.
- `vaultwright recovery` now compares `_meta/repo-manifest.json` with `tools/repos.yml` so removed
  repo config entries are surfaced as `repo_unconfigured` before another repo sync rewrites the
  manifest.
- `vaultwright catalog` and `vaultwright m365` now use the same repo config comparison, so
  retained repo mirrors whose `tools/repos.yml` entry was removed appear as `repo_unconfigured` in
  inventory and handoff readiness reports before another repo sync runs.
- `vaultwright lint` now blocks repo manifest records that are no longer governed by
  `tools/repos.yml`, preventing clean-looking retained repo mirrors from passing release gates
  after their config entry is removed.
- Added `_meta/lifecycle-states.yml` as the machine-readable Office/repo lifecycle contract, and
  `vaultwright doctor` now validates that every state has entry conditions, explanations, permitted
  next actions, and exit conditions during preflight.
- Office and repo sync plan/status guidance now reads `_meta/lifecycle-states.yml`, and generated
  source/repo manifest records plus sync audit events record the lifecycle contract path/schema
  version that governed each lifecycle state.
- Office sync/status now detects managed source frontmatter metadata drift as stale and normal
  sync rewrites the managed fields from the manifest/source.
- Office sync now strips obvious spreadsheet extraction noise from `.xlsx` mirrors, including
  empty `Unnamed:*` table columns and `NaN` placeholder cells.
- Lint overlap warnings now include human-gated consolidation suggestions, using inbound-link
  counts when available to identify the likely canonical note.
- Lint now treats broken path-qualified wikilinks as unresolved instead of falling back to
  same-stem notes in other folders, while still allowing same-path extension matches.
- Lint now blocks explicit `tools/repos.yml` entries when the configured generated `repo-mirror`
  note is missing, unmanaged, pointed at an invalid output path, or tied to a different repo
  identity.
- GitHub repo sync and lint now reject duplicate `tools/repos.yml` entries that resolve to the
  same generated repo-mirror note path, preventing partial syncs and source-identity conflicts.
- Lint now blocks generated repo mirrors when the frontmatter `repo` identity drifts from the
  repo manifest's configured or resolved repo identity.
- Lint now skips generated `_meta/*.md` reports and the generated `CATALOG.md` gateway for note
  frontmatter/orphan checks, keeping copied-vault review output focused on curated-note issues.
- Lint now reports legacy frontmatter domain aliases with canonical recommendations, for example
  `marketing -> market (20_market/)`, so copied-vault cleanup queues align with `vaultwright
  migration`.
- Added `tools/overlap_report.py` and `vaultwright overlap`, a read-only overlap-threshold
  calibration report that summarizes candidate counts across threshold bands without printing note
  bodies, shared terms, source text, or reviewer notes.
- CI and release smoke checks now exercise `overlap --json` and `overlap --worksheet` through the
  packaged CLI.

### Fixed
- Office mirror planning now reports unsafe mirror-output errors against the active
  profile/configured mirror root instead of falling back to a legacy `_mirrors/` record path.
- `vaultwright sandbox` no longer treats `_meta/domain-map.yml` and `_meta/mirror-config.yml` as
  required files when a valid profile contract can provide canonical domains and mirror defaults.

### Known TODO before stable release hardening
- Decide CLA vs DCO; secure the "Vaultwright" name; draft the commercial agreement.
- Calibrate the default near-duplicate/overlap thresholds with design-partner corpora.

## [0.1.0a1] — 2026-06-20

Initial scaffold extracted and generalized from a real small-business vault.

### Added
- **Template vault** (`template/`): the `CLAUDE.md` schema, `_meta/conventions.md`, Obsidian note
  templates (`_templates/`), the `Documents.base` dynamic index, `INDEX.md`, `RETENTION.md`, and a
  seeded `log.md`.
- **Tools** (`template/tools/`): Office→markdown mirror sync (markitdown), GitHub repo mirror sync,
  the vault linter, and `sync_all.sh`.
- **Release-readiness guardrails**: a no-data scanner, tracked pre-commit hook, GitHub Actions CI,
  and pytest coverage for fresh-vault sync behavior.
- Documented Python 3.11+ as the supported runtime for the current `markitdown` dependency.
- Added the synthetic `examples/northwind-robotics-vault/` corpus and provenance ledger for testing
  generated vault readability without real business data.
- Added `examples/government-services-vault/`, a public-service document showcase built from
  generated Office fixtures covering Canadian business-startup workflows: CRA business
  registration, GST/HST readiness, CRA account access, and funding/support discovery.
- Added `docs/VAULTWRIGHT_WHITEPAPER.md`, a professional review whitepaper covering progress,
  limitations, validation posture, dogfood results, and future roadmap.
- Updated the whitepaper to frame Vaultwright's future direction as an agent-ready markdown
  substrate, not only a human-managed knowledge-base workflow.
- Added `docs/AGENT_READINESS_BENCHMARK.md` and aligned public docs around proving agent value
  against raw source folders and one-off document-chat outputs.
- Added a source-linked government-services agent-readiness task pack under
  `examples/government-services-vault/_meta/agent-readiness-tasks.yml`.
- Added `tools/benchmark_tasks.py` and `vaultwright benchmark` to validate agent-readiness task
  packs before and after generated mirrors exist.
- `vaultwright benchmark` now validates optional `_meta/agent-readiness-results.yml` result packs
  and reports aggregate per-mode scores, correction counts, and privacy/provenance violation
  counts without printing answer text or reviewer notes.
- Vendored the full AGPL-3.0 license text into `LICENSE`, kept project-specific licensing notices
  in `NOTICE`, and added SPDX headers to source/tool/test files.
- Added a test gate to keep SPDX headers present on Python and shell source files.
- Added `docs/PRODUCT.md`, `docs/SYNC_SPEC.md`, and `docs/SECURITY_MODEL.md` to narrow the first
  product promise and define release-critical lifecycle/security contracts.
- Office mirror sync now supports non-mutating `--plan` and manifest-backed `--status` reporting,
  and writes `_meta/source-manifest.json` on sync with stable source IDs, source hashes, mirror
  paths, converter/config version, lifecycle state, warnings, and last successful sync.
- Office and repo plan/status output now includes lifecycle next-action guidance for review,
  missing, moved, changed, unreachable, conflict, unsupported, and error states.
- Added `tools/vaultwright.py`, a thin operator wrapper for `plan`, `sync`, `status`, `lint`, and
  `doctor`, plus repo-root `init`.
- Added `pyproject.toml` and the source-installable `vaultwright` console entry point; current
  command behavior has since converged into package-owned modules while vault-local tools remain
  compatibility shims.
- Packaged the starter vault template under `src/vaultwright/template`, so `vaultwright init` can
  scaffold from an installed wheel without a source checkout or `VAULTWRIGHT_REPO`.
- CI now builds a wheel, installs it into a clean environment, and smoke-tests packaged
  `vaultwright init`, `doctor`, `plan`, `benchmark`, `conversion`, `migration`, `pilot`, and JSON
  `recovery` delegation.
- Added a tag-driven GitHub Release workflow and `docs/RELEASE.md`; `v*` tags build artifacts,
  install-test the wheel, upload workflow artifacts, and create a draft prerelease for owner review
  without publishing to PyPI. The workflow keeps build/test read-only and refuses to clobber an
  existing release unless it is still both draft and prerelease.
- Modernized Python package license metadata to use an SPDX expression plus explicit `LICENSE` and
  `NOTICE` files, avoiding deprecated setuptools license-table and classifier warnings.
- Updated GitHub Actions workflow dependencies to current majors for CI and release automation,
  removing the Node 20 runtime deprecation warning path.
- `vaultwright doctor` now reports manifest lifecycle counts, sync audit presence, recovery action
  counts, git backup posture, GitHub auth posture, optional Obsidian config/plugin posture, and
  `.gitignore` backup guard coverage as read-only preflight context.
- Added `tools/recovery_report.py` and `vaultwright recovery`, a read-only recovery checklist for
  non-clean source/repo manifest records and missing generated paths.
- Added `tools/conversion_report.py` and `vaultwright conversion`, a read-only conversion
  spot-check report that prioritizes manifest records by lifecycle state, warning/error metadata,
  source format, and source/mirror existence without claiming an automated quality score.
- `vaultwright conversion --guide` now appends a manifest-aware operator checklist for conversion
  review, including priority handling, format-specific caveats, and sign-off criteria without
  printing source or mirror content.
- Added `tools/migration_report.py` and `vaultwright migration`, a read-only report for legacy
  alias folders and unknown top-level folders, including non-reserved hidden/underscore folders,
  before any manual migration.
- Added `tools/pilot_report.py`, `vaultwright pilot`, and `docs/PILOT_WORKSHEET.md` for aggregate
  design-partner evidence capture without printing source or mirror content.
- Added `vaultwright pilot --worksheet`, a redacted Markdown summary mode for private pilot records
  that reports aggregate counts and review queues without source paths or document content.
- Added `_meta/lint-config.yml` so overlap-warning thresholds can be tuned in copied pilot vaults
  without changing linter code.
- Lint now blocks stale generated Office mirrors when source bytes changed or the source manifest
  lifecycle state is no longer current, so operators rerun sync before relying on old mirrors.
- Lint now also blocks stale generated repo mirrors when repo manifest lifecycle state is no longer
  current, repo frontmatter commit metadata drifts from the manifest, or a local repo fixture tree
  changed.
- Recovery reports now attach the latest matching sync-audit status, lifecycle state, warnings, and
  errors for each manifest item that needs operator action.
- Recovery reports now flag stale atomic temp files left by interrupted writes, without deleting
  them automatically.
- Recovery JSON output now includes compact total/office/repo/temp summary counts for automation.
- Recovery reports now surface previous generated mirror paths for source-move and mirror-root
  conflict records, so operators can see which retained mirror needs review before regeneration.
- Recovery guidance and regression coverage now include refresh/planned lifecycle states such as
  `source_changed`, `stale`, `converter_changed`, `planned`, `repo_changed`, and `unreachable`.
- GitHub repo sync now supports non-mutating `--plan` and manifest-backed `--status` reporting,
  and writes `_meta/repo-manifest.json` with stable repo IDs, configured/resolved repo, note path,
  local-tree or remote-HEAD hash, lifecycle state, warnings, and last successful sync.
- Added regression coverage for documented sync idempotency edge cases: empty repo configs,
  unsupported Office sources, Office lock-file skips, and alias-to-canonical mirror routing.
- Office and repo syncs now append machine-readable events to `_meta/sync-audit.jsonl`.
- Office and repo sync audit events now include generated artifact paths plus structured lifecycle
  warnings/errors for recovery diagnostics without embedding source content.
- Office planning now reports warning counts for sensitive-looking paths, duplicate source bytes,
  and format-specific conversion-quality risks.
- Added `docs/RECOVERY.md` and `docs/DESIGN_PARTNER_PROTOCOL.md`.
- Reworked the whitepaper around the consulting buyer, before/after workflow, lifecycle model,
  agent permissions, evidence gaps, service-led business model, release gates, and technical
  appendix.
- CI and pytest now regenerate and lint example vaults in temporary copies.
- Replaced the department-shaped starter folders with a function-based file plan and domain map:
  intake, governance, market, customers, delivery, operations, finance, people, and sources.
- Added `_meta/mirror-config.yml` and `_mirrors/` as the default dedicated storage for generated
  Office mirrors and optional PDF text mirrors.
- Linter now enforces `domain` values from `_meta/domain-map.yml`, so old department aliases cannot
  silently become canonical note metadata.
- **`scripts/init.sh`** to bootstrap a new vault from the template.
- **Docs**: `methodology.md`, `positioning.md` (honest landscape), `quickstart.md`.
- **Licensing**: AGPL-3.0 core + commercial dual-license model (`LICENSING.md`), `TRADEMARK.md`,
  DCO-based `CONTRIBUTING.md`.

### Fixed
- `sync_all.sh` now fails when a required sync command fails instead of masking errors behind a
  later successful lint.
- Packaged-template parity tests now ignore generated Python bytecode caches created by CI compile
  preflight steps.
- Office mirror sync now aborts the mirror write if source bytes change during conversion, records
  an error lifecycle state, and preserves the previous mirror.
- Office mirror sync now reports a conflict when the configured mirror root or mode changes while
  the previous generated mirror still exists, preventing duplicate generated mirrors for one
  source.
- Office mirror sync now blocks moved-source regeneration while the previous generated mirror still
  exists, so operators must preserve, move, archive, or remove the old mirror before creating the
  new generated path.
- Added regression coverage for converter failures: the previous mirror is preserved, the manifest
  records `error`, and a later successful sync returns the record to `clean`.
- Office mirror write failures now return a recoverable `error` lifecycle state instead of
  bubbling out of sync, preserving the previous mirror and allowing a later clean regeneration.
- Repo mirror note write failures now return a recoverable `error` lifecycle state, preserving the
  previous note and allowing a later clean regeneration.
- GitHub repo sync now skips cleanly when the default `tools/repos.yml` is absent, while explicit
  missing configs fail.
- `repos.example.yml` no longer contains an active placeholder that could resolve to a real
  third-party repo.
- No-data scanning now catches modern `sk-proj-...`-style API keys and force-staged files under
  high-risk paths such as `secrets/`.
- No-data scanning now blocks force-staged OS/generated artifacts such as `.DS_Store` and logs.
- No-data scanning now blocks symlinks and scans staged symlink entries by git mode.
- Default no-data scanning now includes ignored untracked paths, so ignored data, secrets, logs,
  caches, and OS artifacts cannot hide in the checkout.
- No-data scanning now sweeps hidden OOXML text parts such as Word headers/footers and package
  relationship files, not only the main document body.
- OOXML metadata scanning now blocks unexpected company, manager, title, custom-property, and
  similar identity-bearing document properties.
- OOXML relationship parts now receive payment-card checks as well as token/secret checks.
- OOXML custom XML parts now receive payment-card checks.
- Staged no-data scans now read provenance allowlists from the staged index, preventing unstaged
  provenance edits from allowing staged data files.
- CI regenerates the synthetic example vault in a temporary copy so generated mirrors stay out of
  the source tree.
- Office mirrors now default to `_mirrors/<canonical-source-path>.md` instead of sitting beside the
  original Office files; `--mirror-mode sibling` remains available for legacy vaults.
- Office mirror writes are now transactional and preserve the previous mirror if conversion or
  frontmatter generation fails.
- Repo mirror writes are now transactional and preserve the previous note if writing fails.
- Office sync now reports legacy `.doc` sources as unsupported, marks missing sources in the
  manifest without deleting mirrors, and refuses to silently overwrite manual edits below the
  generated sentinel unless explicitly forced.
- Repo sync now refuses to silently overwrite manual edits below the generated sentinel unless
  explicitly forced.
- Office sync now rejects symlinked source files before hashing or conversion, preventing a vault
  symlink from mirroring external/private content.
- Office sync now keeps mirrors in `manual_modification` review when the generated sentinel is
  removed or an existing mirror has no manifest-generated baseline, instead of accepting it as clean.
- `--force` now still refuses Office mirrors whose generated sentinel is missing or whose existing
  mirror has no manifest-generated baseline, because the tool cannot safely distinguish curated
  content from corrupted generated output without that boundary.
- Office sync now requires the generated sentinel as an exact standalone line, so altered boundary
  text cannot be treated as a trusted generated-region marker.
- Repo sync now applies the same exact-line sentinel boundary check, blocking forced rewrites when
  a repo mirror's generated boundary has been altered.
- Repo sync now also treats existing repo mirrors without a manifest-generated baseline as
  review-required, so a lost repo manifest cannot silently re-baseline generated content.
- Repo sync now reports generated-region tampering before repo reachability state, so an offline or
  private repo cannot hide a manual edit below the generated sentinel.
- Repo sync now treats an existing hand-authored target note, missing repo sentinel, or mismatched
  `repo_id` as a conflict instead of taking over the note.
- The no-data scanner now allows generated `_meta/sync-audit.jsonl` files in temporary validation
  vaults while still scanning their text for secrets.
- CI now smoke-tests the installed `vaultwright` console entry point and validates both example
  vaults after mirror regeneration.
- Added a copied-vault recovery regression test covering mirror regeneration, source-byte
  preservation, `source_missing`, `manual_modification`, lint, and no-data scanning.
- Example regeneration tests now snapshot representative source payloads and assert plan, dry-run,
  sync, status, and lint operations leave source bytes unchanged.
- Example regeneration tests now assert a second sync leaves stable generated mirrors, repo notes,
  and manifests unchanged while treating `_meta/sync-audit.jsonl` as append-only history.
- Added repo mirror regression coverage for upgrading an unreachable pending stub into a populated
  mirror while preserving curated notes and frontmatter.
- Added Office mirror regression coverage proving update sync preserves user-owned frontmatter and
  curated notes while refreshing managed source metadata.
- Example generated-residue tests now use pattern checks for `_mirrors/`, manifests, audit logs,
  repo mirrors, sibling Office mirrors, and `.mirror.md` fallback files, not only hardcoded
  expected paths.
- Scaffolded/example vault `.gitignore` files now include high-risk `data/`, `secrets/`,
  `private/`, and log patterns.
- Office mirror routing now maps old folder aliases such as `clients/`, `marketing/`, and
  `finance/` to canonical function folders under `_mirrors/`.
- Office sync and lint now ignore temporary Office lock files such as `~$brief.docx`.
- Repo/frontmatter tooling now prefers `account` metadata while preserving legacy `client` input.
- Repo mirror output paths now reject escaping `note` and `notes_dir` values before writing.
- Repo mirror output paths now reject reserved or symlinked operational paths inside the vault.
- Repo mirror notes now require exact lowercase `.md` filenames so generated mirrors are linted.
- Vault lint now enforces domain-to-folder placement from `_meta/domain-map.yml`, blocking old
  department folders from silently returning.
- Vault lint now blocks conflicting `account` and legacy `client` frontmatter values.
- Vault lint now blocks `client` without canonical `account` and uppercase markdown extensions.
- Vault lint now reports likely duplicate/overlap notes as warning-only anti-proliferation
  candidates, excluding generated source/repo mirrors.
- Vault lint now excludes generated source/repo mirrors from orphan-note warnings, and CI asserts
  regenerated example vaults have zero orphan curated notes and zero overlap warnings.
- Vault lint now only exempts generated source/repo mirrors from orphan/overlap checks when they
  live in their managed mirror locations.
- Vault lint now requires generated sentinels and matching manifest records before source/repo
  mirrors can bypass orphan/overlap warnings, and sibling-mode source mirrors must use canonical or
  aliased domain roots.
- Vault lint now requires an Office mirror candidate to be a managed generated mirror before it can
  satisfy mirror-gap checks, so hand-authored sibling notes cannot mask missing generated mirrors.
- No-data scanning no longer exempts `_meta/sync-audit.jsonl` from staged/default provenance checks;
  the generated-audit exemption is limited to explicit temp-path validation scans.
- No-data scanning now blocks force-staged Python packaging artifacts such as `*.egg-info/`,
  `build/`, and `dist/`.
