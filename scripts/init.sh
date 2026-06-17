#!/usr/bin/env bash
# Bootstrap a new Vaultwright knowledge base from template/.
# Usage: bash scripts/init.sh <target-dir>
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-}"

if [ -z "$TARGET" ]; then
  echo "usage: bash scripts/init.sh <target-dir>"
  exit 1
fi
if [ -e "$TARGET" ] && [ -n "$(ls -A "$TARGET" 2>/dev/null || true)" ]; then
  echo "refusing: '$TARGET' exists and is not empty"
  exit 1
fi

mkdir -p "$TARGET"
cp -R "$HERE/template/." "$TARGET/"

cat <<EOF
✅ Vaultwright vault created at: $TARGET

Next steps:
  1) Open it in Obsidian ("Open folder as vault"); enable core plugins: Properties, Bases, Graph.
  2) Point your AI agent (Claude Code / Codex) at the folder — it reads CLAUDE.md first.
  3) pip install -r tools/requirements.txt
  4) python3 tools/sync_office_md.py                 # mirror Office files
     cp tools/repos.example.yml tools/repos.yml      # then edit, and:
     python3 tools/sync_github_repos.py              # mirror GitHub repos
     python3 tools/lint_vault.py                     # health check

See docs/quickstart.md in the Vaultwright repo for details.
EOF
