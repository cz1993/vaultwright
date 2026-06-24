#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Compatibility shim for package-owned recovery reporting."""
from __future__ import annotations

import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
sys.path = [entry for entry in sys.path if Path(entry or ".").resolve() != TOOL_DIR]

try:
    from vaultwright.recovery import *  # noqa: F403
    from vaultwright.recovery import main as _package_main
except ImportError as exc:
    raise SystemExit(
        "Missing Vaultwright package runtime. Install Vaultwright or run with PYTHONPATH pointing "
        f"at the source checkout. Import error: {exc}"
    ) from exc


if __name__ == "__main__":
    raise SystemExit(_package_main(root=TOOL_DIR.parent))
