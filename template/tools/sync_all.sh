#!/usr/bin/env bash
# Refresh every knowledge-base mirror (Office files + GitHub repos), then run the linter.
# Built for one unattended cron/launchd job on the machine that holds the vault.
# Auth for private repos must be available to this environment (gh auth / GH_TOKEN).
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR" || exit 1

echo "=== $(date -Iseconds) sync_all ==="
python3 tools/sync_office_md.py --quiet
python3 tools/sync_github_repos.py --quiet
echo "--- lint ---"
python3 tools/lint_vault.py | tail -15
