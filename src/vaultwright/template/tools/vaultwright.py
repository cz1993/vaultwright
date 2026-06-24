#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Compatibility shim for the package-owned Vaultwright CLI."""
from __future__ import annotations

import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
DEFAULT_ROOT = TOOL_DIR.parent
sys.path = [entry for entry in sys.path if Path(entry or ".").resolve() != TOOL_DIR]

try:
    from vaultwright.cli import main as _package_main
except ImportError as exc:
    raise SystemExit(
        "Missing Vaultwright package runtime. Install Vaultwright or run with PYTHONPATH pointing "
        f"at the source checkout. Import error: {exc}"
    ) from exc


def root_is_explicit(argv: list[str]) -> bool:
    return "--root" in argv or any(arg.startswith("--root=") for arg in argv)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not root_is_explicit(args):
        args = ["--root", str(DEFAULT_ROOT), *args]
    return _package_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
