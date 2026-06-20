#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Thin operator CLI for a Vaultwright vault.

This wrapper intentionally delegates to the existing tools so the operator commands do not fork
sync or lint behavior.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
DEFAULT_ROOT = TOOL_DIR.parent


def run(cmd: list[str], cwd: Path) -> int:
    result = subprocess.run(cmd, cwd=cwd)
    return result.returncode


def run_capture(cmd: list[str], cwd: Path, timeout: int = 5) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


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


def command_migration(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    cmd = python_cmd(root, "migration_report.py")
    if args.json:
        cmd.append("--json")
    return run(cmd, root)


def command_recovery(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    cmd = python_cmd(root, "recovery_report.py")
    if args.json:
        cmd.append("--json")
    return run(cmd, root)


def count_manifest_states(path: Path, id_key: str) -> tuple[str, str | None]:
    if not path.exists():
        return f"{path.name}: not generated yet", None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"{path.name}: unreadable JSON", f"{path.name}: invalid JSON ({exc.__class__.__name__})"
    records = data.get("records", [])
    if not isinstance(records, list):
        return f"{path.name}: invalid records", f"{path.name}: records must be a list"
    valid = [record for record in records if isinstance(record, dict)]
    state_counts = Counter(str(record.get("lifecycle_state", "unknown")) for record in valid)
    missing_ids = sum(1 for record in valid if not str(record.get(id_key, "")).strip())
    state_summary = ", ".join(f"{state}={state_counts[state]}" for state in sorted(state_counts)) or "no states"
    message = f"{path.name}: {len(valid)} records ({state_summary})"
    warning = f"{path.name}: {missing_ids} records missing {id_key}" if missing_ids else None
    return message, warning


def git_preflight(root: Path) -> tuple[list[str], list[str]]:
    info: list[str] = []
    warnings: list[str] = []
    git = shutil.which("git")
    if not git:
        warnings.append("git not found; curated-note backup posture cannot be checked.")
        return info, warnings
    inside = run_capture([git, "rev-parse", "--is-inside-work-tree"], root)
    if not inside or inside.returncode != 0 or inside.stdout.strip() != "true":
        warnings.append("Vault root is not inside a git work tree; back up curated notes before production sync.")
        return info, warnings
    top_level = run_capture([git, "rev-parse", "--show-toplevel"], root)
    if top_level and top_level.returncode == 0:
        info.append(f"git: inside work tree ({top_level.stdout.strip()})")
    else:
        info.append("git: inside work tree")
    status = run_capture([git, "status", "--short"], root)
    if status and status.returncode == 0:
        if status.stdout.strip():
            warnings.append("git working tree has uncommitted changes; confirm backups before production sync.")
        else:
            info.append("git working tree: clean")
    return info, warnings


def github_auth_preflight(root: Path) -> tuple[list[str], list[str]]:
    info: list[str] = []
    warnings: list[str] = []
    if os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
        info.append("GitHub auth: environment token detected")
        return info, warnings
    gh = shutil.which("gh")
    if not gh:
        warnings.append("GitHub auth: no GH_TOKEN/GITHUB_TOKEN or gh CLI found; private repo sync will not authenticate.")
        return info, warnings
    auth = run_capture([gh, "auth", "status", "-h", "github.com"], root)
    if auth and auth.returncode == 0:
        info.append("GitHub auth: gh is authenticated for github.com")
    else:
        warnings.append("GitHub auth: not confirmed; private repo sync needs gh auth or an env token.")
    return info, warnings


def recovery_preflight(root: Path) -> tuple[list[str], list[str]]:
    info: list[str] = []
    warnings: list[str] = []
    script = root / "tools" / "recovery_report.py"
    if not script.exists():
        return info, warnings
    try:
        spec = importlib.util.spec_from_file_location("vaultwright_recovery_report_for_doctor", script)
        if not spec or not spec.loader:
            raise ImportError("cannot load recovery_report.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        items, report_warnings, report_errors = module.build_report(root)
        summary = module.summary_counts(items)
    except Exception as exc:
        detail = f"{exc.__class__.__name__}: {str(exc)[:120]}"
        warnings.append(f"recovery: unavailable ({detail})")
        return info, warnings
    warnings.extend(f"recovery: {warning}" for warning in report_warnings)
    warnings.extend(f"recovery: {error}" for error in report_errors)
    total = int(summary.get("total", 0))
    if total:
        item_word = "item" if total == 1 else "items"
        verb = "needs" if total == 1 else "need"
        warnings.append(
            "recovery: "
            f"{total} {item_word} {verb} operator action "
            f"(office={summary.get('office', 0)}, repo={summary.get('repo', 0)}, temp={summary.get('temp', 0)}); "
            "run `vaultwright recovery`."
        )
    else:
        info.append("recovery: no action items")
    return info, warnings


def command_doctor(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    info: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []

    print(f"vaultwright doctor: {root}")
    if sys.version_info < (3, 11):
        errors.append("Python 3.11+ is required.")
    else:
        info.append(f"Python: {sys.version.split()[0]}")
    for rel in ("CLAUDE.md", "INDEX.md", "_meta/domain-map.yml", "_meta/mirror-config.yml"):
        if not (root / rel).exists():
            errors.append(f"Missing required vault file: {rel}")
    if (root / "_mirrors").exists():
        info.append("Office mirror root: _mirrors")
    else:
        info.append("Office mirror root: _mirrors (will be created on first sync)")
    for script in (
        "sync_office_md.py",
        "sync_github_repos.py",
        "lint_vault.py",
        "benchmark_tasks.py",
        "migration_report.py",
        "recovery_report.py",
    ):
        if not (root / "tools" / script).exists():
            errors.append(f"Missing tool: tools/{script}")
    for module in ("yaml", "markitdown"):
        if importlib.util.find_spec(module) is None:
            errors.append(f"Missing Python dependency: {module}")
        else:
            info.append(f"Python dependency: {module}")
    source_summary, source_warning = count_manifest_states(root / "_meta" / "source-manifest.json", "source_id")
    repo_summary, repo_warning = count_manifest_states(root / "_meta" / "repo-manifest.json", "repo_id")
    info.extend([source_summary, repo_summary])
    if source_warning:
        warnings.append(source_warning)
    if repo_warning:
        warnings.append(repo_warning)
    audit = root / "_meta" / "sync-audit.jsonl"
    if audit.exists():
        try:
            events = sum(1 for line in audit.read_text(encoding="utf-8").splitlines() if line.strip())
            info.append(f"sync-audit.jsonl: {events} events")
        except UnicodeDecodeError:
            warnings.append("sync-audit.jsonl: unreadable text")
    else:
        info.append("sync-audit.jsonl: not generated yet")
    if not (root / "tools" / "repos.yml").exists():
        warnings.append("No tools/repos.yml found; repo sync will skip until configured.")
    recovery_info, recovery_warnings = recovery_preflight(root)
    git_info, git_warnings = git_preflight(root)
    gh_info, gh_warnings = github_auth_preflight(root)
    info.extend(recovery_info)
    warnings.extend(recovery_warnings)
    info.extend(git_info)
    warnings.extend(git_warnings)
    info.extend(gh_info)
    warnings.extend(gh_warnings)

    for item in info:
        print(f"  info: {item}")
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
    migration = sub.add_parser("migration", help="Print a read-only legacy folder migration report.")
    migration.add_argument("--json", action="store_true", help="Print machine-readable migration JSON.")
    migration.set_defaults(func=command_migration)
    recovery = sub.add_parser("recovery", help="Print a read-only manifest recovery checklist.")
    recovery.add_argument("--json", action="store_true", help="Print machine-readable recovery JSON.")
    recovery.set_defaults(func=command_recovery)
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
