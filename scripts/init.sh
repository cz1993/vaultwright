#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
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
  3) python3.11 -m pip install -r tools/requirements.txt
  4) cp tools/repos.example.yml tools/repos.yml      # optional: edit to list repos
     python3.11 tools/vaultwright.py doctor
     python3.11 tools/vaultwright.py plan
     python3.11 tools/vaultwright.py sync
     python3.11 tools/vaultwright.py status
     python3.11 tools/vaultwright.py lint

See docs/quickstart.md in the Vaultwright repo for details.
EOF
