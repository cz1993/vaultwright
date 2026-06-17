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
- **`scripts/init.sh`** to bootstrap a new vault from the template.
- **Docs**: `methodology.md`, `positioning.md` (honest landscape), `quickstart.md`.
- **Licensing**: AGPL-3.0 core + commercial dual-license model (`LICENSING.md`), `TRADEMARK.md`,
  DCO-based `CONTRIBUTING.md`.

### Known TODO before public release
- Vendor the full AGPL-3.0 text into `LICENSE`.
- Decide CLA vs DCO; secure the "Vaultwright" name; draft the commercial agreement.
- Build the `vaultwright` CLI (see `cli/README.md`).
- Add near-duplicate/overlap detection to the linter (anti-proliferation).
