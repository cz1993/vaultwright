# Vaultwright Profile Schema

Vaultwright profiles are versioned contracts that describe a workspace's domain vocabulary, allowed
metadata, starter folders, views, skills, and benchmark hooks. Core runtime code should read this
contract instead of hard-coding business-specific folders, note types, statuses, or required
properties.

The current schema is `schema_version: 1`. The only packaged profile today is
`business-operations` at `profile_version: 0.1.0`.

## Contract File

Each vault stores its active profile at:

```text
_meta/profile.yml
```

The packaged target profile is copied from:

```text
template/_meta/profile.yml
```

Use these commands to inspect and validate the contract:

```bash
vaultwright profile list
vaultwright profile show business-operations
vaultwright --root <vault> profile validate
vaultwright --root <vault> profile diff 0.1.0
vaultwright --root <vault> profile migrate --plan
vaultwright --root <vault> profile migrate --write
vaultwright --root <vault> profile views --check
vaultwright --root <vault> profile views --write
```

## Required Fields

`schema_version`
: Integer schema identifier. Must currently be `1`.

`id`
: Lowercase kebab-case profile identifier, for example `business-operations`.

`name`
: Human-readable profile name.

`profile_version`
: Version string for the profile contract. The current built-in profile uses `0.1.0`.

`description`
: Optional human-readable summary.

`domains`
: Mapping of domain IDs to domain definitions. Domain IDs must be lowercase kebab-case
  identifiers. Domain definitions may only contain `folder` and optional `purpose`. Each domain
  must define `folder`. Domain folders must be safe vault-relative POSIX paths, and they must be
  unique and non-overlapping so profile-driven routing can map each vault path to one canonical
  domain without ambiguity. When present, `purpose` must be a non-empty string.

`note_types`
: Mapping of allowed note type IDs to definitions. Note type IDs must be lowercase kebab-case
  identifiers. Note type definitions may only contain optional `purpose` and `machine_owned`.
  A note type definition may include `machine_owned: true` when notes of that type are regenerated
  artifacts rather than curated human notes; catalog, Microsoft 365 handoff, and sandbox inventory
  report them separately from curated Markdown, and overlap calibration and migration frontmatter
  cleanup exclude those note types. When present, `purpose` must be a non-empty string.

`statuses`
: Mapping of allowed workflow status IDs to definitions. Status IDs must be lowercase kebab-case
  identifiers. Status definitions may only contain optional `purpose`, `attention`, and `inactive`.
  A status definition may include `attention: true` when notes in that state should appear in
  generated review-attention views, and `inactive: true` when notes in that state should be
  excluded from active overlap calibration. When present, `purpose` must be a non-empty string.

`required_properties`
: List of frontmatter keys required on curated notes and managed notes where applicable. Entries
  must be lowercase frontmatter keys using letters, numbers, and underscores. They must not contain
  duplicates and must not also appear in `optional_properties`.

`optional_properties`
: List of frontmatter keys accepted by the profile but not required. GitHub repo mirror sync,
  lint, and annotation migration treat optional properties other than universal fields such as
  `owner`, `tags`, and `related` as profile-specific repo context fields when they appear in
  `tools/repos.yml`. Entries must follow the same lowercase frontmatter-key and duplicate rules as
  `required_properties`, and must not also appear in `required_properties`.

`folder_plan`
: Non-empty list of starter folder records. Each current record uses `path` and `domain`; the
  record may only contain those two fields. The `domain` must reference `domains`, and the `path`
  must stay inside that domain's declared folder.

`templates`
: List of template file paths expected in the vault. Entries must be safe vault-relative artifact
  paths and must not contain duplicates.

`views`
: List of view files expected in the vault, such as `Documents.base`. Entries must be safe
  vault-relative artifact paths and must not contain duplicates.

`skills`
: List of profile-specific agent skill paths. Empty for the current profile. Entries must be safe
  vault-relative artifact paths and must not contain duplicates.

`benchmark_tasks`
: List of packaged benchmark task-pack paths. Entries must be safe vault-relative `.yml` or
  `.yaml` paths. Empty for the current profile.

`policy_defaults`
: Mapping reserved for profile-level defaults such as retention, governance, and generated-output
  locations. The current schema accepts only `mirror_mode`, `mirror_root`, `mirror_status`,
  `repo_stub_status`, `repo_notes_dir`, `context_aliases`, `original_sources_authoritative`, and
  `real_data_in_repo`. The current profile uses `repo_notes_dir` to set the default GitHub
  repository mirror folder when `tools/repos.yml` does not declare `settings.notes_dir`,
  `mirror_mode` and `mirror_root` for Office mirror placement when `_meta/mirror-config.yml` does
  not override them, `mirror_status` for refreshed machine-owned source/repo mirrors, and
  `repo_stub_status` for repository mirrors that have not been successfully fetched yet. The
  current profile also uses `context_aliases` to declare compatibility aliases between optional
  frontmatter context fields; for example, `client: account` means `client` is treated as an alias
  of canonical `account` in repo-mirror frontmatter generation, lint checks, and annotation
  migration. The current profile
  also declares
  `original_sources_authoritative: true` and `real_data_in_repo: false`, which preserve the
  Vaultwright policy that source systems remain authoritative and real/private data stays outside
  the repository. `repo_notes_dir`, when present, must be a safe vault-relative folder inside a
  declared profile domain and must not overlap the profile's Office mirror root. `context_aliases`,
  when present, must be a mapping whose keys and targets are distinct optional frontmatter
  properties declared by the profile.

## Validation Rules

`vaultwright profile validate` currently enforces:

- no unknown top-level fields;
- all required top-level fields are present;
- `schema_version` matches the installed schema version;
- `id` is lowercase kebab-case;
- scalar identity fields are non-empty strings;
- mapping fields are YAML mappings;
- list fields are YAML lists;
- required and optional frontmatter property entries are lowercase frontmatter keys, do not
  contain duplicates, and do not overlap each other;
- template, view, and skill entries are safe vault-relative artifact paths, do not contain
  duplicates, and do not overlap `policy_defaults.mirror_root`;
- benchmark task entries are safe vault-relative `.yml` or `.yaml` paths;
- benchmark task entries do not overlap `policy_defaults.mirror_root`;
- domain, note-type, and status identifiers are lowercase kebab-case;
- domain, note-type, and status definitions only use schema-declared fields;
- optional domain, note-type, and status `purpose` values are non-empty strings;
- every domain definition includes a non-empty vault-relative `folder`;
- domain folders are unique and non-overlapping;
- `folder_plan` contains mapping entries with vault-relative POSIX `path` values and non-empty
  `domain` values;
- `folder_plan` entries only use schema-declared fields;
- every `folder_plan` domain references a declared profile domain;
- every `folder_plan` path stays inside its declared domain folder;
- duplicate `folder_plan` paths are rejected.
- optional `note_types.<type>.machine_owned` values are booleans.
- optional `statuses.<status>.attention` and `statuses.<status>.inactive` values are booleans.
- `policy_defaults` only uses schema-declared fields.
- optional `policy_defaults.mirror_mode` is either `dedicated` or `sibling`.
- optional `policy_defaults.mirror_root` is a safe vault-relative generated-output folder.
- optional `policy_defaults.repo_notes_dir` is a safe vault-relative folder inside a declared
  profile domain and does not overlap `policy_defaults.mirror_root`.
- optional `policy_defaults.context_aliases` is a mapping of distinct optional frontmatter
  property aliases to optional frontmatter property targets.
- optional `policy_defaults.mirror_status` and `policy_defaults.repo_stub_status` values reference
  declared statuses.
- optional `policy_defaults.original_sources_authoritative` and
  `policy_defaults.real_data_in_repo` values are booleans.
- optional `policy_defaults.original_sources_authoritative`, when present, must be `true`.
- optional `policy_defaults.real_data_in_repo`, when present, must be `false`.

`vaultwright lint`, `vaultwright catalog`, and `vaultwright overlap` read `_meta/profile.yml` for
domain folders. Catalog, Microsoft 365 handoff, and sandbox inventory also read profile-defined
machine-owned note types so generated Markdown artifacts are reported separately from curated
Markdown/domain note counts. Overlap calibration also reads `related` plus the active profile's
context frontmatter fields when counting inbound wikilinks for candidate ranking, and it excludes
notes in profile-defined inactive statuses and machine-owned note types. Lint also reads allowed
note types, statuses, required properties, and inactive status roles.
The review ledger accepts profile-defined machine-owned Markdown note types as generated artifacts
eligible for metadata-only review decisions; it records hashes and frontmatter metadata, not
artifact bodies.
`vaultwright benchmark` and the aggregate `vaultwright pilot` evidence report read profile-declared
`benchmark_tasks`, while an explicit `--tasks` argument still takes precedence and the legacy
`_meta/agent-readiness-tasks.yml` path remains a compatibility fallback. Benchmark task-pack
validation, result citation validation, and `benchmark --init-tasks` scaffolding also resolve
generated source-mirror evidence against the active Office mirror root. The aggregate pilot
workspace inventory also excludes the active Office mirror root from operator-content and source
candidate counts, and recovery excludes the active Office mirror root when checking whether a
missing source manifest still has source evidence in the vault. GitHub repo mirror sync and
lint read
`policy_defaults.repo_notes_dir` for the default repository-mirror folder, derive repo-mirror
frontmatter domains from the profile's domain/folder mapping, and normalize repo context aliases
from `policy_defaults.context_aliases`. Annotation migration uses the same context aliases when
deciding whether repo-mirror frontmatter is generated metadata or human annotation. Office mirror
sync derives canonical source domains and canonical mirror paths from the active profile's domain
folders, while
`_meta/domain-map.yml` remains a legacy alias layer for old source-folder names. Office mirror sync,
lint, catalog, Microsoft 365 handoff, sandbox preflight, doctor, migration guidance, and
review-ledger classification read `policy_defaults.mirror_mode` and `policy_defaults.mirror_root`
as generated-output defaults while honoring `_meta/mirror-config.yml` as an operator override.
Review-ledger classification also reads profile-defined `machine_owned` note type roles when
deciding whether a Markdown artifact is generated and reviewable.
Source/repo mirror sync and annotation migration read `policy_defaults.mirror_status` and
`policy_defaults.repo_stub_status` when generating mirrors and deciding which mirror statuses are
machine metadata rather than human annotations. Repo mirror context frontmatter also comes from the
active profile's optional
properties, so the `business-operations` profile keeps `account`/`client` compatibility while other
profiles can declare fields such as `research_project` or `component` without inheriting that
business-specific alias unless they opt in. Lint and annotation migration also read
`context_aliases` when checking context frontmatter against repo configuration. Microsoft 365
handoff, sandbox preflight, recovery, and review-ledger
reporting also resolve repo mirror folders from the active profile, while honoring an explicit
`tools/repos.yml` `settings.notes_dir` override. The `vaultwright migration` command uses
`_meta/profile.yml` for canonical domain folders and `_meta/domain-map.yml` for legacy aliases.
`_meta/domain-map.yml` remains a legacy alias and operator guidance layer; it must not contradict
the profile's canonical domain folders.

## Profile-Generated Views

`vaultwright profile views --check` is read-only. It loads the current vault profile and fails when
a supported generated view is missing or stale, or when the profile requests a view path this
installed Vaultwright version cannot safely generate.

`vaultwright profile views --write` regenerates supported profile-owned view files. In the current
release, the supported generated view is `Documents.base`. Its tables are derived from the active
profile's required properties, optional properties, note types, and statuses:

- core document tables use profile-defined frontmatter keys;
- source mirror and repo mirror tables are emitted only when the profile declares those note types;
- review-attention filters are emitted from statuses marked `attention: true`, with legacy
  name-based fallback only for older profiles that have not yet declared status roles.

Generated view writes are explicit and may replace stale generated view files. They do not move,
delete, or rewrite source documents, generated mirrors, annotation sidecars, or curated markdown
notes.

## Migration Semantics

`vaultwright profile migrate --plan` is read-only. It reports:

- missing profile contract files;
- missing shared directories, the target profile's Office mirror root, and `folder_plan`
  directories;
- missing packaged template/view files;
- profile version or vocabulary drift;
- existing template/view files that differ from the packaged target;
- blockers such as target profile ID mismatch.

`vaultwright profile migrate --write` is intentionally conservative. It may:

- create missing shared directories, the target profile's Office mirror root, and `folder_plan`
  directories;
- copy missing packaged template/view files;
- copy `_meta/profile.yml` into older vaults that do not yet have a profile contract.

It will not:

- overwrite existing files;
- move, delete, or rewrite source documents;
- edit generated mirrors;
- migrate mirror annotations;
- normalize frontmatter domains;
- resolve template drift automatically.

Use `vaultwright profile views --write` after reviewing view drift when you want to regenerate the
profile-owned `Documents.base` file from the active profile contract.

Use `vaultwright migration --normalize-frontmatter-domains --worksheet` for frontmatter cleanup
review, and `vaultwright migrate annotations --write` for mirror annotation sidecars. Profile
migration and annotation migration are separate safety boundaries.

## Current `business-operations` Shape

The current packaged profile defines these canonical domains:

```text
intake -> 00_inbox
governance -> 10_governance
market -> 20_market
customers -> 30_customers
delivery -> 40_delivery
operations -> 50_operations
finance -> 60_finance
people -> 70_people
sources -> 80_sources
```

Its current generated-output defaults are:

```text
repo_notes_dir -> 80_sources/repos
mirror_mode -> dedicated
mirror_root -> _mirrors
mirror_status -> active
repo_stub_status -> draft
```

Allowed note types are:

```text
moc, entity, note, guide, policy, record, source-mirror, source-ref, repo-mirror
```

Allowed statuses are:

```text
draft, active, in-review, sent, signed, submitted, awarded, superseded, archived
```

The packaged business profile marks `source-mirror` and `repo-mirror` as machine-owned note types,
marks `draft` and `in-review` as attention states, and marks `superseded` and `archived` as
inactive states for overlap/lint calibration.

These values belong to the `business-operations` profile, not the long-term core. Future
`research-learning`, `software-project`, and `blank` profiles must define their own domains, note
types, statuses, views, and benchmark hooks before Stage 2 starts.
