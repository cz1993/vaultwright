# Vaultwright CLI

The vault-local wrapper exists today as `template/tools/vaultwright.py` and is copied into new
vaults. The source-installable console entry point is defined in `pyproject.toml` as
`vaultwright = vaultwright.cli:main`.

Current wrapper commands:

| Command | Does |
| --- | --- |
| `python3.11 tools/vaultwright.py init <dir>` | scaffold a vault when run from the repo checkout |
| `python3.11 tools/vaultwright.py plan` | inventory source files and proposed mirror actions without writing |
| `python3.11 tools/vaultwright.py sync` | run the Office + GitHub repo mirror syncs |
| `python3.11 tools/vaultwright.py status` | report manifest-backed clean, stale, missing, conflicted, and unsupported states |
| `python3.11 tools/vaultwright.py lint` | run the vault health check |
| `python3.11 tools/vaultwright.py doctor` | check required files, Python version, and Python dependencies; warn on missing repo config or token env |

Use `--root <vault-dir>` before the subcommand to operate on another vault that has its own
`tools/` directory, for example `python3.11 tools/vaultwright.py --root ~/client-vault plan`.

For source/development installs:

```bash
python3.11 -m pip install -e .
vaultwright --root ~/client-vault plan
vaultwright init ~/new-vault
```

`vaultwright init` currently requires a source/editable install or `VAULTWRIGHT_REPO` pointing at a
Vaultwright checkout so it can copy the template.

Design notes:
- Keep it dependency-light (Python stdlib + PyYAML + markitdown).
- The wrapper calls the existing scripts as the source of truth; do not fork sync/lint logic.
- Future release packaging should include the same commands without changing the underlying
  sync/lint implementations.
