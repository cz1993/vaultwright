#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Compatibility shim for package-owned GitHub repo mirror sync."""
from __future__ import annotations

import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
sys.path = [entry for entry in sys.path if Path(entry or ".").resolve() != TOOL_DIR]

try:
    from vaultwright.mirrors.github_repos import main
except ImportError as exc:
    raise SystemExit(
        "Missing Vaultwright package runtime. Install Vaultwright or run with PYTHONPATH pointing "
        f"at the source checkout. Import error: {exc}"
    ) from exc


if __name__ == "__main__":
    tool_dir = Path(__file__).resolve().parent
    raise SystemExit(
        main(
            default_root=tool_dir.parent,
            default_config=tool_dir / "repos.yml",
        )
    )
