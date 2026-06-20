#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Refresh every knowledge-base mirror (Office files + GitHub repos), then run the linter.
# Built for one unattended cron/launchd job on the machine that holds the vault.
# Auth for private repos must be available to this environment (gh auth / GH_TOKEN).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR" || exit 1
PYTHON="${VAULTWRIGHT_PYTHON:-}"
if [ -z "$PYTHON" ]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON="python3.11"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
  else
    echo "error: Python 3.11+ is required" >&2
    exit 127
  fi
fi
"$PYTHON" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("error: Python 3.11+ is required")
PY

echo "=== $(date -Iseconds) sync_all ==="
"$PYTHON" tools/sync_office_md.py --quiet
"$PYTHON" tools/sync_github_repos.py --quiet
echo "--- lint ---"
"$PYTHON" tools/lint_vault.py | tail -15
