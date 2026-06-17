# Vaultwright CLI (roadmap)

A thin, installable wrapper over the scripts in `template/tools/` — planned for a later phase
(v0 ships the template + scripts; see the repo README "Status").

Planned commands:

| Command | Does |
| --- | --- |
| `vaultwright init <dir>` | scaffold a vault from the template (what `scripts/init.sh` does today) |
| `vaultwright sync` | run the Office + GitHub repo mirror syncs |
| `vaultwright lint` | run the vault health check |
| `vaultwright doctor` | check prerequisites (Obsidian config, Python deps, `gh` auth, network) |

Design notes:
- Keep it dependency-light (Python stdlib + PyYAML + markitdown), packaged for `pipx install vaultwright`.
- The CLI should call the same code as `template/tools/` (single source of truth), not fork it.
- Until it lands, use `scripts/init.sh` and the `tools/*.py` scripts directly.
