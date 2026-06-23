#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Compatibility shim for package-owned Office mirror sync."""
from __future__ import annotations

import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
sys.path = [entry for entry in sys.path if Path(entry or ".").resolve() != TOOL_DIR]

try:
    from vaultwright.mirrors.office import main
except ImportError as exc:
    raise SystemExit(
        "Missing Vaultwright package runtime. Install Vaultwright or run with PYTHONPATH pointing "
        f"at the source checkout. Import error: {exc}"
    ) from exc


if __name__ == "__main__":
    raise SystemExit(main(default_root=Path(__file__).resolve().parent.parent))
