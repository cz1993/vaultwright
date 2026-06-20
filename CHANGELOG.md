# Changelog

All notable changes to Vaultwright are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).

## [0.1.0] — unreleased

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
- Added `pyproject.toml` and the source-installable `vaultwright` console entry point, which
  delegates to vault-local tools instead of forking sync/lint behavior.
- Packaged the starter vault template under `src/vaultwright/template`, so `vaultwright init` can
  scaffold from an installed wheel without a source checkout or `VAULTWRIGHT_REPO`.
- CI now builds a wheel, installs it into a clean environment, and smoke-tests packaged
  `vaultwright init`, `doctor`, `plan`, `benchmark`, `conversion`, `migration`, `pilot`, and JSON
  `recovery` delegation.
- `vaultwright doctor` now reports manifest lifecycle counts, sync audit presence, recovery action
  counts, git backup posture, GitHub auth posture, optional Obsidian config/plugin posture, and
  `.gitignore` backup guard coverage as read-only preflight context.
- Added `tools/recovery_report.py` and `vaultwright recovery`, a read-only recovery checklist for
  non-clean source/repo manifest records and missing generated paths.
- Added `tools/conversion_report.py` and `vaultwright conversion`, a read-only conversion
  spot-check report that prioritizes manifest records by lifecycle state, warning/error metadata,
  source format, and source/mirror existence without claiming an automated quality score.
- Added `tools/migration_report.py` and `vaultwright migration`, a read-only report for legacy
  alias folders and unknown top-level folders, including non-reserved hidden/underscore folders,
  before any manual migration.
- Added `tools/pilot_report.py`, `vaultwright pilot`, and `docs/PILOT_WORKSHEET.md` for aggregate
  design-partner evidence capture without printing source or mirror content.
- Recovery reports now attach the latest matching sync-audit status, lifecycle state, warnings, and
  errors for each manifest item that needs operator action.
- Recovery reports now flag stale atomic temp files left by interrupted writes, without deleting
  them automatically.
- Recovery JSON output now includes compact total/office/repo/temp summary counts for automation.
- Recovery reports now surface previous generated mirror paths for source-move and mirror-root
  conflict records, so operators can see which retained mirror needs review before regeneration.
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

### Known TODO before release hardening
- Decide CLA vs DCO; secure the "Vaultwright" name; draft the commercial agreement.
- Finalize tagged release artifact publishing and install verification from a published artifact.
- Calibrate near-duplicate/overlap thresholds with design-partner corpora.
