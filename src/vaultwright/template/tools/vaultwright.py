#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Thin operator CLI for a Vaultwright vault.

This wrapper intentionally delegates to the existing tools so the operator commands do not fork
sync or lint behavior.
"""
from __future__ import annotations

import argparse
import fnmatch
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
GITIGNORE_REQUIRED_PATTERNS = {
    "data/": "data/.vaultwright-doctor-check",
    "secrets/": "secrets/.vaultwright-doctor-check",
    "private/": "private/.vaultwright-doctor-check",
    ".env": ".env",
    "*.pem": "vaultwright-doctor-check.pem",
    ".obsidian/workspace*.json": ".obsidian/workspace.json",
}


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
    if args.tasks:
        cmd.extend(["--tasks", str(args.tasks)])
    if args.results:
        cmd.extend(["--results", str(args.results)])
    if args.init_tasks:
        cmd.append("--init-tasks")
    if args.init_results:
        cmd.append("--init-results")
    if args.force:
        cmd.append("--force")
    if args.scaffold_sources != 5:
        cmd.extend(["--scaffold-sources", str(args.scaffold_sources)])
    if args.scaffold_curated != 5:
        cmd.extend(["--scaffold-curated", str(args.scaffold_curated)])
    if args.worksheet:
        cmd.append("--worksheet")
    if args.require_generated:
        cmd.append("--require-generated")
    if args.require_results:
        cmd.append("--require-results")
    if args.require_citations:
        cmd.append("--require-citations")
    if args.json:
        cmd.append("--json")
    return run(cmd, root)


def command_conversion(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    cmd = python_cmd(root, "conversion_report.py")
    if args.json:
        cmd.append("--json")
    if args.guide:
        cmd.append("--guide")
    if args.low_risk_per_format != 1:
        cmd.extend(["--low-risk-per-format", str(args.low_risk_per_format)])
    return run(cmd, root)


def command_migration(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    cmd = python_cmd(root, "migration_report.py")
    if args.json:
        cmd.append("--json")
    if args.worksheet:
        cmd.append("--worksheet")
    if args.runbook:
        cmd.append("--runbook")
    if args.normalize_frontmatter_domains:
        cmd.append("--normalize-frontmatter-domains")
    if args.write:
        cmd.append("--write")
    return run(cmd, root)


def command_pilot(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    cmd = python_cmd(root, "pilot_report.py")
    if args.json:
        cmd.append("--json")
    if args.worksheet:
        cmd.append("--worksheet")
    return run(cmd, root)


def command_recovery(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    cmd = python_cmd(root, "recovery_report.py")
    if args.json:
        cmd.append("--json")
    if args.worksheet:
        cmd.append("--worksheet")
    return run(cmd, root)


def command_m365(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    cmd = python_cmd(root, "m365_report.py")
    if args.json:
        cmd.append("--json")
    return run(cmd, root)


def command_review(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    cmd = python_cmd(root, "review_ledger.py")
    if args.artifact:
        cmd.extend(["--artifact", str(args.artifact)])
    if args.status:
        cmd.extend(["--status", args.status])
    if args.reviewer:
        cmd.extend(["--reviewer", args.reviewer])
    if args.note:
        cmd.extend(["--note", args.note])
    if args.kind:
        cmd.extend(["--kind", args.kind])
    if args.json:
        cmd.append("--json")
    if args.check:
        cmd.append("--check")
    return run(cmd, root)


def command_catalog(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    cmd = python_cmd(root, "catalog_report.py")
    if args.json:
        cmd.append("--json")
    if args.html:
        cmd.append("--html")
    if args.stdout:
        cmd.append("--stdout")
    if args.check:
        cmd.append("--check")
    if args.output != Path("CATALOG.md"):
        cmd.extend(["--output", str(args.output)])
    if args.max_items != 500:
        cmd.extend(["--max-items", str(args.max_items)])
    return run(cmd, root)


def command_sandbox(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    cmd = python_cmd(root, "sandbox_report.py")
    if args.source_root:
        cmd.extend(["--source-root", str(args.source_root)])
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


def active_gitignore_patterns(path: Path) -> list[str]:
    patterns: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(stripped)
    return patterns


def gitignore_rule_matches(pattern: str, rel_path: str) -> bool:
    pattern = pattern.strip()
    if not pattern:
        return False
    if pattern.endswith("/"):
        prefix = pattern.lstrip("/")
        return rel_path == prefix.rstrip("/") or rel_path.startswith(prefix)
    pattern = pattern.strip("/")
    if "/" not in pattern:
        parts = rel_path.split("/")
        return any(fnmatch.fnmatch(part, pattern) for part in parts)
    return fnmatch.fnmatch(rel_path, pattern) or rel_path.startswith(pattern.rstrip("/") + "/")


def gitignore_ignores(patterns: list[str], rel_path: str) -> bool:
    ignored = False
    for pattern in patterns:
        negated = pattern.startswith("!")
        body = pattern[1:] if negated else pattern
        if gitignore_rule_matches(body, rel_path):
            ignored = not negated
    return ignored


def negates_required_pattern(pattern: str, required: str, sample: str) -> bool:
    if not pattern.startswith("!"):
        return False
    body = pattern[1:].strip("/")
    required_body = required.strip("/")
    if gitignore_rule_matches(body, sample):
        return True
    if required.endswith("/") and (body == required_body or body.startswith(required)):
        return True
    return False


def backup_preflight(root: Path) -> tuple[list[str], list[str]]:
    info: list[str] = []
    warnings: list[str] = []
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        warnings.append("backup guard: .gitignore missing; local data/secret patterns are not protected.")
    else:
        active_patterns = active_gitignore_patterns(gitignore)
        missing = [
            pattern
            for pattern, sample in GITIGNORE_REQUIRED_PATTERNS.items()
            if not gitignore_ignores(active_patterns, sample)
        ]
        reopened = [
            pattern
            for pattern, sample in GITIGNORE_REQUIRED_PATTERNS.items()
            if any(negates_required_pattern(rule, pattern, sample) for rule in active_patterns)
        ]
        if missing or reopened:
            details = []
            if missing:
                details.append("missing effective ignores: " + ", ".join(missing))
            if reopened:
                details.append("negated high-risk paths: " + ", ".join(reopened))
            warnings.append("backup guard: .gitignore unsafe; " + "; ".join(details))
        else:
            info.append("backup guard: .gitignore covers high-risk local data patterns")

    git = shutil.which("git")
    if not git:
        return info, warnings
    inside = run_capture([git, "rev-parse", "--is-inside-work-tree"], root)
    if not inside or inside.returncode != 0 or inside.stdout.strip() != "true":
        return info, warnings
    top_level = run_capture([git, "rev-parse", "--show-toplevel"], root)
    if top_level and top_level.returncode == 0:
        git_root = Path(top_level.stdout.strip()).resolve()
        if git_root == root.resolve():
            info.append("backup boundary: vault root is git root")
        else:
            warnings.append("backup boundary: vault is inside a parent git work tree; confirm client boundary before pilots.")
    commits = run_capture([git, "rev-list", "--count", "HEAD"], root)
    if not commits or commits.returncode != 0:
        warnings.append("backup history: no git commits found; create a backup baseline before pilot sync.")
    else:
        info.append(f"backup history: {commits.stdout.strip()} commits")
    remotes = run_capture([git, "remote"], root)
    if remotes and remotes.returncode == 0 and remotes.stdout.strip():
        info.append(f"backup remotes: {len(remotes.stdout.split())} configured")
    else:
        warnings.append("backup remotes: none configured; confirm another backup exists before pilot work.")
    return info, warnings


def obsidian_preflight(root: Path) -> tuple[list[str], list[str]]:
    info: list[str] = []
    warnings: list[str] = []
    bases = root / "Documents.base"
    if bases.exists():
        info.append("Obsidian Bases index: Documents.base present")
    else:
        warnings.append("Obsidian Bases index: Documents.base missing; CLI correctness is unaffected.")

    obsidian = root / ".obsidian"
    if not obsidian.exists():
        info.append("Obsidian: .obsidian not present (optional UI; CLI correctness unaffected)")
        return info, warnings
    if not obsidian.is_dir():
        warnings.append("Obsidian: .obsidian exists but is not a directory")
        return info, warnings
    info.append("Obsidian: .obsidian present")

    for filename in ("app.json", "core-plugins.json", "community-plugins.json"):
        path = obsidian / filename
        if not path.exists():
            info.append(f"Obsidian {filename}: not present")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            warnings.append(f"Obsidian {filename}: unreadable text")
            continue
        except OSError as exc:
            warnings.append(f"Obsidian {filename}: unreadable ({exc.__class__.__name__})")
            continue
        except json.JSONDecodeError as exc:
            warnings.append(f"Obsidian {filename}: invalid JSON ({exc.__class__.__name__})")
            continue
        if filename == "community-plugins.json":
            if not isinstance(data, list):
                warnings.append("Obsidian community-plugins.json: expected a list")
            elif data:
                warnings.append(
                    f"Obsidian community plugins: {len(data)} enabled; review plugin trust boundary before pilots."
                )
            else:
                info.append("Obsidian community plugins: none enabled")
        elif filename == "core-plugins.json":
            if isinstance(data, dict):
                enabled = sum(1 for value in data.values() if value)
                info.append(f"Obsidian core plugins: {enabled} enabled")
            elif isinstance(data, list):
                info.append(f"Obsidian core plugins: {len(data)} listed")
            else:
                warnings.append("Obsidian core-plugins.json: expected a list or mapping")
        else:
            info.append("Obsidian app.json: readable")

    plugins_dir = obsidian / "plugins"
    if plugins_dir.exists() and plugins_dir.is_dir():
        plugin_dirs = [path for path in plugins_dir.iterdir() if path.is_dir()]
        if plugin_dirs:
            warnings.append(
                f"Obsidian installed plugin directories: {len(plugin_dirs)} found; review local plugin code before pilots."
            )
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


def review_preflight(root: Path) -> tuple[list[str], list[str]]:
    info: list[str] = []
    warnings: list[str] = []
    script = root / "tools" / "review_ledger.py"
    if not script.exists():
        return info, warnings
    try:
        spec = importlib.util.spec_from_file_location("vaultwright_review_ledger_for_doctor", script)
        if not spec or not spec.loader:
            raise ImportError("cannot load review_ledger.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        report, report_warnings = module.build_report(root)
    except Exception as exc:
        detail = f"{exc.__class__.__name__}: {str(exc)[:120]}"
        warnings.append(f"review ledger: unavailable ({detail})")
        return info, warnings

    warnings.extend(f"review ledger: {warning}" for warning in report_warnings)
    reviewed = int(report.get("reviewed_artifacts", 0) or 0)
    if not reviewed:
        info.append("review ledger: no reviewed artifacts yet")
        return info, warnings

    statuses = report.get("statuses", {}) if isinstance(report.get("statuses"), dict) else {}
    states = report.get("current_states", {}) if isinstance(report.get("current_states"), dict) else {}
    status_summary = ", ".join(f"{key}={statuses[key]}" for key in sorted(statuses)) or "no statuses"
    state_summary = ", ".join(f"{key}={states[key]}" for key in sorted(states)) or "no states"
    info.append(f"review ledger: {reviewed} reviewed artifact(s) ({status_summary}; {state_summary})")

    stale_or_missing = sum(
        int(count)
        for state, count in states.items()
        if str(state) != "current" and isinstance(count, int)
    )
    non_approved = sum(
        int(count)
        for status, count in statuses.items()
        if str(status) != "approved" and isinstance(count, int)
    )
    if stale_or_missing:
        warnings.append(
            f"review ledger: {stale_or_missing} reviewed artifact(s) are stale, missing, or unreadable; "
            "run `vaultwright review`."
        )
    if non_approved:
        warnings.append(
            f"review ledger: {non_approved} reviewed artifact(s) are not approved; run `vaultwright review`."
        )
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
        "catalog_report.py",
        "conversion_report.py",
        "m365_report.py",
        "migration_report.py",
        "pilot_report.py",
        "recovery_report.py",
        "review_ledger.py",
        "sandbox_report.py",
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
    review_info, review_warnings = review_preflight(root)
    obsidian_info, obsidian_warnings = obsidian_preflight(root)
    backup_info, backup_warnings = backup_preflight(root)
    git_info, git_warnings = git_preflight(root)
    gh_info, gh_warnings = github_auth_preflight(root)
    info.extend(recovery_info)
    warnings.extend(recovery_warnings)
    info.extend(review_info)
    warnings.extend(review_warnings)
    info.extend(obsidian_info)
    warnings.extend(obsidian_warnings)
    info.extend(backup_info)
    warnings.extend(backup_warnings)
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
    benchmark = sub.add_parser("benchmark", help="Validate the agent-readiness benchmark task pack and optional result pack.")
    benchmark.add_argument("--tasks", type=Path, help="Task pack path relative to the vault root.")
    benchmark.add_argument("--results", type=Path, help="Optional benchmark results path relative to the vault root.")
    benchmark.add_argument("--init-tasks", action="store_true", help="Create a private benchmark task scaffold.")
    benchmark.add_argument("--init-results", action="store_true", help="Create a private benchmark result scaffold.")
    benchmark.add_argument("--force", action="store_true", help="Overwrite an existing task or result scaffold.")
    benchmark.add_argument("--scaffold-sources", type=int, default=5, help="Maximum source/mirror pairs for --init-tasks.")
    benchmark.add_argument("--scaffold-curated", type=int, default=5, help="Maximum curated markdown notes for --init-tasks.")
    benchmark.add_argument("--worksheet", action="store_true", help="Print a private benchmark run worksheet.")
    benchmark.add_argument("--require-generated", action="store_true", help="Require generated mirror paths to exist.")
    benchmark.add_argument("--require-results", action="store_true", help="Require benchmark results for every task/mode pair.")
    benchmark.add_argument(
        "--require-citations",
        action="store_true",
        help="Fail scored benchmark results that do not cite a declared source or generated mirror path.",
    )
    benchmark.add_argument("--json", action="store_true", help="Print machine-readable benchmark JSON.")
    benchmark.set_defaults(func=command_benchmark)
    conversion = sub.add_parser("conversion", help="Print a read-only conversion spot-check report.")
    conversion.add_argument("--json", action="store_true", help="Print machine-readable conversion JSON.")
    conversion.add_argument("--guide", action="store_true", help="Append an operator conversion-review checklist.")
    conversion.add_argument(
        "--low-risk-per-format",
        type=int,
        default=1,
        help="Include this many low-risk sample records per format in the spot-check list.",
    )
    conversion.set_defaults(func=command_conversion)
    migration = sub.add_parser("migration", help="Report legacy folder/frontmatter migration work.")
    migration_output = migration.add_mutually_exclusive_group()
    migration_output.add_argument("--json", action="store_true", help="Print machine-readable migration JSON.")
    migration_output.add_argument("--worksheet", action="store_true", help="Print a Markdown migration review worksheet.")
    migration_output.add_argument("--runbook", action="store_true", help="Print a Markdown legacy-folder migration runbook.")
    migration.add_argument(
        "--normalize-frontmatter-domains",
        action="store_true",
        help="Preview known legacy frontmatter domain aliases that can be rewritten to canonical domains.",
    )
    migration.add_argument(
        "--write",
        action="store_true",
        help="With --normalize-frontmatter-domains, rewrite known frontmatter domain aliases. Does not move files.",
    )
    migration.set_defaults(func=command_migration)
    pilot = sub.add_parser("pilot", help="Print a read-only design-partner pilot evidence report.")
    pilot_output = pilot.add_mutually_exclusive_group()
    pilot_output.add_argument("--json", action="store_true", help="Print machine-readable pilot JSON.")
    pilot_output.add_argument(
        "--worksheet",
        action="store_true",
        help="Print a redacted Markdown pilot worksheet summary.",
    )
    pilot.set_defaults(func=command_pilot)
    recovery = sub.add_parser("recovery", help="Print a read-only manifest recovery checklist.")
    recovery_output = recovery.add_mutually_exclusive_group()
    recovery_output.add_argument("--json", action="store_true", help="Print machine-readable recovery JSON.")
    recovery_output.add_argument("--worksheet", action="store_true", help="Print a Markdown recovery review worksheet.")
    recovery.set_defaults(func=command_recovery)
    m365 = sub.add_parser("m365", help="Print a read-only Microsoft 365/Copilot handoff report.")
    m365.add_argument("--json", action="store_true", help="Print machine-readable handoff JSON.")
    m365.set_defaults(func=command_m365)
    review = sub.add_parser("review", help="Record or summarize metadata-only artifact review decisions.")
    review.add_argument("--artifact", type=Path, help="Generated artifact to review, relative to the vault root.")
    review.add_argument("--status", choices=["approved", "blocked", "deferred", "needs-work"], help="Review decision to record.")
    review.add_argument("--reviewer", help="Reviewer name or role for a recorded decision.")
    review.add_argument("--note", default="", help="Short metadata-only review note.")
    review.add_argument("--kind", help="Override artifact kind after path safety checks.")
    review.add_argument("--json", action="store_true", help="Print machine-readable review ledger output.")
    review.add_argument("--check", action="store_true", help="Fail unless every latest review is approved and current.")
    review.set_defaults(func=command_review)
    catalog = sub.add_parser("catalog", help="Generate a source-path-only documentation catalog.")
    catalog.add_argument("--json", action="store_true", help="Print machine-readable catalog JSON.")
    catalog.add_argument("--html", action="store_true", help="Write or print an HTML catalog instead of Markdown.")
    catalog.add_argument("--stdout", action="store_true", help="Print catalog output instead of writing a file.")
    catalog.add_argument("--check", action="store_true", help="Fail if the catalog output is missing or stale.")
    catalog.add_argument(
        "--output",
        type=Path,
        default=Path("CATALOG.md"),
        help="Catalog path relative to the vault root. Defaults to CATALOG.html when --html is used.",
    )
    catalog.add_argument(
        "--max-items",
        type=int,
        default=500,
        help="Maximum source/repo records to list per catalog section; use 0 for no limit.",
    )
    catalog.set_defaults(func=command_catalog)
    sandbox = sub.add_parser("sandbox", help="Print a read-only copied-vault sandbox readiness report.")
    sandbox.add_argument(
        "--source-root",
        type=Path,
        help="Original source collection root. Used only to verify the pilot vault is a separate copy.",
    )
    sandbox.add_argument("--json", action="store_true", help="Print machine-readable sandbox JSON.")
    sandbox.set_defaults(func=command_sandbox)
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
