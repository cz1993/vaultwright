# SPDX-License-Identifier: AGPL-3.0-or-later
"""Installable Vaultwright console entry point.

The packaged command delegates operator commands to the target vault's local `tools/vaultwright.py`
wrapper. That keeps the vault tools as the source of truth while allowing a single `vaultwright`
command from editable or wheel installs.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def template_source() -> Path | None:
    env_root = os.environ.get("VAULTWRIGHT_REPO")
    candidates = []
    if env_root:
        candidates.append(Path(env_root))
    here = Path(__file__).resolve()
    candidates.extend(here.parents)
    for candidate in candidates:
        template = candidate / "template"
        if (template / "CLAUDE.md").exists():
            return template
    return None


def ensure_empty_or_missing(target: Path) -> None:
    if target.exists() and any(target.iterdir()):
        raise ValueError(f"refusing: '{target}' exists and is not empty")


def run(cmd: list[str], cwd: Path) -> int:
    return subprocess.run(cmd, cwd=cwd).returncode


def vault_wrapper(root: Path) -> Path:
    wrapper = root / "tools" / "vaultwright.py"
    if not wrapper.exists():
        raise FileNotFoundError(f"{root} does not look like a Vaultwright vault: missing tools/vaultwright.py")
    return wrapper


def command_init(args: argparse.Namespace) -> int:
    template = template_source()
    if not template:
        print(
            "vaultwright init cannot find a packaged template. Reinstall Vaultwright or set "
            "VAULTWRIGHT_REPO to a source checkout.",
            file=sys.stderr,
        )
        return 1
    target = args.target.expanduser().resolve()
    try:
        ensure_empty_or_missing(target)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template, target, dirs_exist_ok=True)
    print(f"Vaultwright vault created at: {target}")
    print("Next: python3.11 tools/vaultwright.py doctor && python3.11 tools/vaultwright.py plan")
    return 0


def command_delegate(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    try:
        wrapper = vault_wrapper(root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return run([sys.executable, str(wrapper), args.command, *getattr(args, "delegate_args", [])], root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vaultwright command-line interface.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Vault root for plan/sync/status/lint/doctor.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Scaffold a new Vaultwright vault from the template.")
    init.add_argument("target", type=Path)
    init.set_defaults(func=command_init)
    for name, help_text in (
        ("plan", "Inventory sources and proposed mirror actions without writing."),
        ("sync", "Run Office and repo mirror syncs."),
        ("status", "Report manifest-backed lifecycle status."),
        ("lint", "Run vault health checks."),
        ("doctor", "Check required files, Python version, and dependencies."),
    ):
        sub.add_parser(name, help=help_text).set_defaults(func=command_delegate, delegate_args=[])
    benchmark = sub.add_parser("benchmark", help="Validate the agent-readiness benchmark task pack and optional result pack.")
    benchmark.add_argument("--tasks", type=Path, help="Task pack path relative to the vault root.")
    benchmark.add_argument("--results", type=Path, help="Optional benchmark results path relative to the vault root.")
    benchmark.add_argument("--require-generated", action="store_true", help="Require generated mirror paths to exist.")
    benchmark.add_argument("--require-results", action="store_true", help="Require benchmark results for every task/mode pair.")
    benchmark.add_argument("--json", action="store_true", help="Print machine-readable benchmark JSON.")
    benchmark.set_defaults(
        func=command_delegate,
        delegate_args=lambda args: (
            (["--tasks", str(args.tasks)] if args.tasks else [])
            + (["--results", str(args.results)] if args.results else [])
            + (["--require-generated"] if args.require_generated else [])
            + (["--require-results"] if args.require_results else [])
            + (["--json"] if args.json else [])
        ),
    )
    conversion = sub.add_parser("conversion", help="Print a read-only conversion spot-check report.")
    conversion.add_argument("--json", action="store_true", help="Print machine-readable conversion JSON.")
    conversion.add_argument("--guide", action="store_true", help="Append an operator conversion-review checklist.")
    conversion.add_argument(
        "--low-risk-per-format",
        type=int,
        default=1,
        help="Include this many low-risk sample records per format in the spot-check list.",
    )
    conversion.set_defaults(
        func=command_delegate,
        delegate_args=lambda args: (
            (["--json"] if args.json else [])
            + (["--guide"] if args.guide else [])
            + (
                ["--low-risk-per-format", str(args.low_risk_per_format)]
                if args.low_risk_per_format != 1
                else []
            )
        ),
    )
    migration = sub.add_parser("migration", help="Print a read-only legacy folder migration report.")
    migration.add_argument("--json", action="store_true", help="Print machine-readable migration JSON.")
    migration.set_defaults(
        func=command_delegate,
        delegate_args=lambda args: ["--json"] if args.json else [],
    )
    pilot = sub.add_parser("pilot", help="Print a read-only design-partner pilot evidence report.")
    pilot.add_argument("--json", action="store_true", help="Print machine-readable pilot JSON.")
    pilot.set_defaults(
        func=command_delegate,
        delegate_args=lambda args: ["--json"] if args.json else [],
    )
    recovery = sub.add_parser("recovery", help="Print a read-only manifest recovery checklist.")
    recovery.add_argument("--json", action="store_true", help="Print machine-readable recovery JSON.")
    recovery.set_defaults(
        func=command_delegate,
        delegate_args=lambda args: ["--json"] if args.json else [],
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if callable(getattr(args, "delegate_args", None)):
        args.delegate_args = args.delegate_args(args)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
