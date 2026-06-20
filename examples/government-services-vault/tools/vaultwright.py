#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Thin operator CLI for a Vaultwright vault.

This wrapper intentionally delegates to the existing tools so the operator commands do not fork
sync or lint behavior.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
DEFAULT_ROOT = TOOL_DIR.parent


def run(cmd: list[str], cwd: Path) -> int:
    result = subprocess.run(cmd, cwd=cwd)
    return result.returncode


def tool_script(root: Path, script: str) -> Path:
    return root / "tools" / script


def python_cmd(root: Path, script: str, *args: str) -> list[str]:
    return [sys.executable, str(tool_script(root, script)), *args]


def command_plan(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    status = run(python_cmd(root, "sync_office_md.py", "--plan"), root)
    repo_config = root / "tools" / "repos.yml"
    if repo_config.exists():
        status = max(status, run(python_cmd(root, "sync_github_repos.py", "--plan"), root))
    else:
        print("vaultwright plan: no tools/repos.yml found; repo plan skipped")
    return status


def command_sync(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    office = run(python_cmd(root, "sync_office_md.py"), root)
    repos = run(python_cmd(root, "sync_github_repos.py"), root)
    return office or repos


def command_status(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    status = run(python_cmd(root, "sync_office_md.py", "--status"), root)
    repo_config = root / "tools" / "repos.yml"
    if repo_config.exists():
        status = max(status, run(python_cmd(root, "sync_github_repos.py", "--status"), root))
    else:
        print("vaultwright status: no tools/repos.yml found; repo status skipped")
    return status


def command_lint(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    return run(python_cmd(root, "lint_vault.py"), root)


def command_benchmark(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    cmd = python_cmd(root, "benchmark_tasks.py")
    if args.require_generated:
        cmd.append("--require-generated")
    return run(cmd, root)


def command_doctor(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    print(f"vaultwright doctor: {root}")
    if sys.version_info < (3, 11):
        errors.append("Python 3.11+ is required.")
    for rel in ("CLAUDE.md", "INDEX.md", "_meta/domain-map.yml", "_meta/mirror-config.yml"):
        if not (root / rel).exists():
            errors.append(f"Missing required vault file: {rel}")
    for script in ("sync_office_md.py", "sync_github_repos.py", "lint_vault.py", "benchmark_tasks.py"):
        if not (root / "tools" / script).exists():
            errors.append(f"Missing tool: tools/{script}")
    for module in ("yaml", "markitdown"):
        if importlib.util.find_spec(module) is None:
            errors.append(f"Missing Python dependency: {module}")
    if not (root / "tools" / "repos.yml").exists():
        warnings.append("No tools/repos.yml found; repo sync will skip until configured.")
    if not os.environ.get("GH_TOKEN") and not os.environ.get("GITHUB_TOKEN"):
        warnings.append("No GH_TOKEN/GITHUB_TOKEN detected; private GitHub repo sync needs gh auth or an env token.")

    for warning in warnings:
        print(f"  warning: {warning}")
    for error in errors:
        print(f"  error: {error}", file=sys.stderr)
    if errors:
        return 1
    print("vaultwright doctor: OK")
    return 0


def command_init(args: argparse.Namespace) -> int:
    repo_root = TOOL_DIR.parents[1]
    init_script = repo_root / "scripts" / "init.sh"
    if not init_script.exists():
        print("vaultwright init is available from the Vaultwright repository, not from an installed vault copy.", file=sys.stderr)
        return 1
    return run(["bash", str(init_script), str(args.target)], repo_root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vaultwright operator CLI.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Vault root (default: parent of tools/).")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("plan", help="Inventory sources and proposed mirror actions without writing.").set_defaults(func=command_plan)
    sub.add_parser("sync", help="Run Office and repo mirror syncs.").set_defaults(func=command_sync)
    sub.add_parser("status", help="Report manifest-backed lifecycle status.").set_defaults(func=command_status)
    sub.add_parser("lint", help="Run vault health checks.").set_defaults(func=command_lint)
    benchmark = sub.add_parser("benchmark", help="Validate the agent-readiness benchmark task pack.")
    benchmark.add_argument("--require-generated", action="store_true", help="Require generated mirror paths to exist.")
    benchmark.set_defaults(func=command_benchmark)
    sub.add_parser("doctor", help="Check runtime, dependencies, and vault structure.").set_defaults(func=command_doctor)
    init = sub.add_parser("init", help="Scaffold a new vault from the repository template.")
    init.add_argument("target", type=Path)
    init.set_defaults(func=command_init)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
