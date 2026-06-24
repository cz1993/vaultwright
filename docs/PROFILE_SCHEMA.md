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
: Mapping of domain IDs to domain definitions. Each domain must define `folder`.

`note_types`
: Mapping of allowed note type IDs to definitions.

`statuses`
: Mapping of allowed workflow status IDs to definitions.

`required_properties`
: List of frontmatter keys required on curated notes and managed notes where applicable.

`optional_properties`
: List of frontmatter keys accepted by the profile but not required.

`folder_plan`
: Non-empty list of starter folder records. Each current record uses `path` and `domain`; the
  `domain` must reference `domains`, and the `path` must stay inside that domain's declared
  folder.

`templates`
: List of template file paths expected in the vault.

`views`
: List of view files expected in the vault, such as `Documents.base`.

`skills`
: List of profile-specific agent skill paths. Empty for the current profile.

`benchmark_tasks`
: List of packaged benchmark task-pack paths. Empty for the current profile.

`policy_defaults`
: Mapping reserved for profile-level defaults such as retention, governance, and generated-output
locations. The current profile uses `repo_notes_dir` to set the default GitHub repository mirror
folder when `tools/repos.yml` does not declare `settings.notes_dir`.

## Validation Rules

`vaultwright profile validate` currently enforces:

- no unknown top-level fields;
- all required top-level fields are present;
- `schema_version` matches the installed schema version;
- `id` is lowercase kebab-case;
- scalar identity fields are non-empty strings;
- mapping fields are YAML mappings;
- list fields are YAML lists;
- path/list entries for required properties, optional properties, templates, views, skills, and
  benchmark tasks are strings;
- every domain definition includes a non-empty vault-relative `folder`;
- `folder_plan` contains mapping entries with vault-relative POSIX `path` values and non-empty
  `domain` values;
- every `folder_plan` domain references a declared profile domain;
- every `folder_plan` path stays inside its declared domain folder;
- duplicate `folder_plan` paths are rejected.

`vaultwright lint` and `vaultwright catalog` read `_meta/profile.yml` for domain folders, allowed
note types, statuses, and required properties. GitHub repo mirror sync and lint read
`policy_defaults.repo_notes_dir` for the default repository-mirror folder and derive repo-mirror
frontmatter domains from the profile's domain/folder mapping. Microsoft 365 handoff, sandbox
preflight, recovery, and review-ledger reporting also resolve repo mirror folders from the active
profile, while honoring an explicit `tools/repos.yml` `settings.notes_dir` override. The
`vaultwright migration` command uses `_meta/profile.yml` for canonical domain folders and
`_meta/domain-map.yml` for legacy aliases. `_meta/domain-map.yml` remains a legacy alias and
operator guidance layer; it must not contradict the profile's canonical domain folders.

## Profile-Generated Views

`vaultwright profile views --check` is read-only. It loads the current vault profile and fails when
a supported generated view is missing or stale, or when the profile requests a view path this
installed Vaultwright version cannot safely generate.

`vaultwright profile views --write` regenerates supported profile-owned view files. In the current
release, the supported generated view is `Documents.base`. Its tables are derived from the active
profile's required properties, optional properties, note types, and statuses:

- core document tables use profile-defined frontmatter keys;
- source mirror and repo mirror tables are emitted only when the profile declares those note types;
- review-attention filters are emitted only when the profile declares supported review statuses.

Generated view writes are explicit and may replace stale generated view files. They do not move,
delete, or rewrite source documents, generated mirrors, annotation sidecars, or curated markdown
notes.

## Migration Semantics

`vaultwright profile migrate --plan` is read-only. It reports:

- missing profile contract files;
- missing shared and `folder_plan` directories;
- missing packaged template/view files;
- profile version or vocabulary drift;
- existing template/view files that differ from the packaged target;
- blockers such as target profile ID mismatch.

`vaultwright profile migrate --write` is intentionally conservative. It may:

- create missing shared and `folder_plan` directories;
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
```

Allowed note types are:

```text
moc, entity, note, guide, policy, record, source-mirror, source-ref, repo-mirror
```

Allowed statuses are:

```text
draft, active, in-review, sent, signed, submitted, awarded, superseded, archived
```

These values belong to the `business-operations` profile, not the long-term core. Future
`research-learning`, `software-project`, and `blank` profiles must define their own domains, note
types, statuses, views, and benchmark hooks before Stage 2 starts.
