# Sync Specification

## Objective

Vaultwright sync must prove the core product promise: source files remain untouched while generated
knowledge artifacts can be regenerated, audited, and reviewed.

## Source Identity

Path-based mirror names are user-friendly but insufficient as the durable identity model. Office
mirror sync maintains `_meta/source-manifest.json` with stable source IDs. Repo mirror sync
maintains `_meta/repo-manifest.json` with stable repo IDs derived from configured repo/note
identity.

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
- last successful sync timestamp;
- warnings, omissions, and errors.

Current implementation status:

- implemented for Office mirrors: stable source IDs, current/previous source paths, mirror path,
  source hash/size, converter/config version, lifecycle state, warnings/errors, source-missing
  marking, non-mutating plan/status reports, sensitive-name warnings, duplicate-byte warnings, and
  format-specific conversion-quality warnings, plus lifecycle next-action guidance in plan/status
  output, and post-conversion source hash checks that abort mirror writes if the source changes
  while conversion is running, plus mirror-root-change conflict detection when the old generated
  mirror still exists, plus moved-source review blocking while the previous generated mirror still
  exists, plus converter-failure and mirror-write-failure recovery tests that preserve the previous
  mirror and allow later clean regeneration;
- implemented for repo mirrors: stable repo IDs, configured/resolved repo, note path, local-tree or
  remote HEAD hash, lifecycle state, warnings/errors, non-mutating plan/status reports, and
  generated-region manual-edit detection, plus lifecycle next-action guidance in plan/status output;
- partially implemented: move detection by unique hash match when the old manifest path is absent;
- not complete: full rename/move UX, rollback automation, quantitative conversion-quality scoring,
  and exhaustive conflict-resolution flows.

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

## Rename, Move, and Delete Handling

- Rename/move should be detected by stable source ID and source hash where possible, not treated
  only as delete plus create.
- When a source move changes the generated mirror path, sync should not create the new mirror while
  the previous generated mirror still exists. The operator must preserve, move, archive, or remove
  the old mirror first so curated notes are not stranded and duplicate generated mirrors are not
  created.
- Source deletion should not delete mirrors automatically. It should mark the manifest record as
  `source_missing` and surface a review action.
- Mirror path changes should be planned before writes and reported after writes.

## Conflict Rules

Sync must flag conflict when:

- the generated region was manually edited;
- a mirror exists at the target path but does not belong to the source ID;
- the configured mirror root changes and an old mirror still exists;
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

## Idempotency

A second sync with unchanged source bytes, unchanged converter/config version, and unchanged curated
region must produce no content diff.

Idempotency tests must cover:

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

Rollback guidance lives in `docs/RECOVERY.md` and must be tested before a public release.

## Original Source Integrity

Tests must prove that sync does not mutate original source bytes.

The release gate is byte-for-byte equality of source files before and after sync for representative
supported formats and skipped/unsupported files.
