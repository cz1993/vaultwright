#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Print a read-only copied-vault sandbox readiness report."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from vaultwright import recovery as recovery_module
from vaultwright.runtime_profile import configured_office_mirror_root, is_repo_notes_path

DEFAULT_ROOT = Path.cwd()
SOURCE_MANIFEST = Path("_meta/source-manifest.json")
REPO_MANIFEST = Path("_meta/repo-manifest.json")
AUDIT_LOG = Path("_meta/sync-audit.jsonl")
BENCHMARK_TASKS = Path("_meta/agent-readiness-tasks.yml")
BENCHMARK_RESULTS = Path("_meta/agent-readiness-results.yml")
REQUIRED_FILES = (
    "CLAUDE.md",
    "INDEX.md",
    "RETENTION.md",
    "_meta/domain-map.yml",
    "_meta/mirror-config.yml",
    "_meta/lint-config.yml",
)
REQUIRED_TOOLS = (
    "sync_office_md.py",
    "sync_github_repos.py",
    "lint_vault.py",
    "conversion_report.py",
    "m365_report.py",
    "migration_report.py",
    "pilot_report.py",
    "recovery_report.py",
)
EXCLUDED_PARTS = {
    ".git",
    ".github",
    ".githooks",
    ".obsidian",
    "_archive",
    "_fixtures",
    "_meta",
    "_mirrors",
    "_templates",
    "_tmp",
    "node_modules",
    "tools",
}
SOURCE_EXTS = {".doc", ".docx", ".pdf", ".pptx", ".xlsx"}


def run_capture(cmd: list[str], cwd: Path, timeout: int = 5) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def contained_by(path: Path, candidate_parent: Path) -> bool:
    return path == candidate_parent or candidate_parent in path.parents


def source_boundary(root: Path, source_root: Path | None) -> tuple[dict[str, Any], list[str], list[str]]:
    if source_root is None:
        return {"provided": False, "status": "not_provided"}, [
            "source-root not provided; copied-vault boundary was not verified."
        ], []
    resolved_root = root.resolve()
    resolved_source = source_root.expanduser().resolve()
    if not resolved_source.exists():
        return {
            "provided": True,
            "status": "source_root_missing",
        }, [], ["source-root does not exist; copied-vault boundary cannot be verified."]
    if resolved_root == resolved_source:
        return {
            "provided": True,
            "status": "same_path",
        }, [], ["vault root and source-root are the same path; do not pilot against original documents."]
    if contained_by(resolved_root, resolved_source):
        return {
            "provided": True,
            "status": "vault_inside_source_root",
        }, [], ["vault root is inside source-root; copy the source collection outside the original tree first."]
    if contained_by(resolved_source, resolved_root):
        return {
            "provided": True,
            "status": "source_root_inside_vault",
        }, [], ["source-root is inside the vault; confirm the original source folder was not nested into the pilot copy."]
    return {"provided": True, "status": "distinct"}, [], []


def load_json_records(root: Path, rel: Path) -> tuple[list[dict], list[str], list[str]]:
    path = root / rel
    if not path.exists():
        return [], [f"{rel.as_posix()}: missing"], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], [], [f"{rel.as_posix()}: invalid JSON ({exc.__class__.__name__})"]
    if not isinstance(data, dict):
        return [], [], [f"{rel.as_posix()}: must be a JSON object"]
    records = data.get("records", [])
    if not isinstance(records, list):
        return [], [], [f"{rel.as_posix()}: records must be a list"]
    bad = sum(1 for record in records if not isinstance(record, dict))
    errors = [f"{rel.as_posix()}: {bad} records are not objects"] if bad else []
    return [record for record in records if isinstance(record, dict)], [], errors


def manifest_summary(records: list[dict], id_key: str) -> dict[str, Any]:
    states = Counter(str(record.get("lifecycle_state", "unknown") or "unknown") for record in records)
    missing_ids = sum(1 for record in records if not str(record.get(id_key, "")).strip())
    warnings = sum(len(record.get("warnings", [])) for record in records if isinstance(record.get("warnings"), list))
    errors = sum(len(record.get("errors", [])) for record in records if isinstance(record.get("errors"), list))
    return {
        "records": len(records),
        "states": dict(sorted(states.items())),
        "missing_ids": missing_ids,
        "warnings": warnings,
        "errors": errors,
    }


def managed_source_mirror(path: Path) -> bool:
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:600]
    except OSError:
        return False
    return "type: source-mirror" in head


def managed_repo_mirror(path: Path) -> bool:
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:600]
    except OSError:
        return False
    return "type: repo-mirror" in head


def workspace_inventory(root: Path) -> dict[str, Any]:
    content_files = 0
    source_candidates = 0
    bytes_total = 0
    extensions: Counter[str] = Counter()
    raw_folder_generated_mirrors = 0
    dedicated_generated_mirrors = 0
    repo_mirrors = 0
    mirror_root = configured_office_mirror_root(root)
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root)
        suffix = path.suffix.lower() or "[no extension]"
        office_mirror = bool(mirror_root.parts) and rel.parts[: len(mirror_root.parts)] == mirror_root.parts
        excluded = office_mirror or any(part in EXCLUDED_PARTS for part in rel.parts)
        if suffix == ".md" and managed_source_mirror(path):
            if office_mirror:
                dedicated_generated_mirrors += 1
            elif not excluded:
                raw_folder_generated_mirrors += 1
        if is_repo_notes_path(root, rel) and suffix == ".md" and managed_repo_mirror(path):
            repo_mirrors += 1
        if excluded:
            continue
        content_files += 1
        extensions[suffix] += 1
        if suffix in SOURCE_EXTS:
            source_candidates += 1
        try:
            bytes_total += path.stat().st_size
        except OSError:
            pass
    return {
        "content_files": content_files,
        "content_bytes": bytes_total,
        "source_candidates": source_candidates,
        "extensions": dict(sorted(extensions.items())),
        "dedicated_generated_mirrors": dedicated_generated_mirrors,
        "raw_folder_generated_mirrors": raw_folder_generated_mirrors,
        "repo_mirrors": repo_mirrors,
    }


def audit_summary(root: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    path = root / AUDIT_LOG
    if not path.exists():
        return {"events": 0, "statuses": {}, "states": {}}, [f"{AUDIT_LOG.as_posix()}: missing"], []
    statuses: Counter[str] = Counter()
    states: Counter[str] = Counter()
    warnings: list[str] = []
    errors: list[str] = []
    events = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return {"events": 0, "statuses": {}, "states": {}}, [], [f"{AUDIT_LOG.as_posix()}: unreadable text"]
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            warnings.append(f"{AUDIT_LOG.as_posix()}: line {line_number} invalid JSON; skipped")
            continue
        if not isinstance(event, dict):
            warnings.append(f"{AUDIT_LOG.as_posix()}: line {line_number} is not an object; skipped")
            continue
        events += 1
        statuses[str(event.get("status", "unknown") or "unknown")] += 1
        states[str(event.get("lifecycle_state", "unknown") or "unknown")] += 1
    return {
        "events": events,
        "statuses": dict(sorted(statuses.items())),
        "states": dict(sorted(states.items())),
    }, warnings, errors


def git_summary(root: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    git = shutil.which("git")
    if not git:
        return {"available": False, "inside_work_tree": False}, [
            "git not found; backup boundary and clean-tree posture were not verified."
        ], []
    inside = run_capture([git, "rev-parse", "--is-inside-work-tree"], root)
    if not inside or inside.returncode != 0 or inside.stdout.strip() != "true":
        return {"available": True, "inside_work_tree": False}, [
            "vault root is not inside a git work tree; create a backup baseline before pilot sync."
        ], []
    top_level = run_capture([git, "rev-parse", "--show-toplevel"], root)
    git_root_is_vault = bool(top_level and top_level.returncode == 0 and Path(top_level.stdout.strip()).resolve() == root.resolve())
    status = run_capture([git, "status", "--short"], root)
    clean = bool(status and status.returncode == 0 and not status.stdout.strip())
    warnings: list[str] = []
    if not git_root_is_vault:
        warnings.append("vault is inside a parent git work tree; confirm client/project boundary before pilot work.")
    if not clean:
        warnings.append("git working tree is not clean; commit or back up the copied vault before pilot sync.")
    return {
        "available": True,
        "inside_work_tree": True,
        "git_root_is_vault": git_root_is_vault,
        "working_tree_clean": clean,
    }, warnings, []


def recovery_summary(root: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    try:
        items, warnings, errors = recovery_module.build_report(root)
        summary = dict(recovery_module.summary_counts(items))
        return {
            "available": True,
            "items": int(summary.get("total", 0)),
            "office": int(summary.get("office", 0)),
            "repo": int(summary.get("repo", 0)),
            "temp": int(summary.get("temp", 0)),
        }, warnings, errors
    except Exception as exc:
        return {"available": False, "items": 0}, [], [f"recovery report failed: {exc.__class__.__name__}"]


def benchmark_presence(root: Path) -> dict[str, bool]:
    return {
        "tasks": (root / BENCHMARK_TASKS).exists(),
        "results": (root / BENCHMARK_RESULTS).exists(),
    }


def required_file_report(root: Path) -> tuple[dict[str, Any], list[str]]:
    missing_files = [rel for rel in REQUIRED_FILES if not (root / rel).exists()]
    missing_tools = [f"tools/{rel}" for rel in REQUIRED_TOOLS if not (root / "tools" / rel).exists()]
    errors = [f"missing required vault file: {rel}" for rel in missing_files]
    errors.extend(f"missing required tool: {rel}" for rel in missing_tools)
    return {
        "missing_files": missing_files,
        "missing_tools": missing_tools,
    }, errors


def build_report(root: Path, source_root: Path | None = None) -> tuple[dict[str, Any], list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    required, required_errors = required_file_report(root)
    boundary, boundary_warnings, boundary_errors = source_boundary(root, source_root)
    source_records, source_warnings, source_errors = load_json_records(root, SOURCE_MANIFEST)
    repo_records, repo_warnings, repo_errors = load_json_records(root, REPO_MANIFEST)
    audit, audit_warnings, audit_errors = audit_summary(root)
    git, git_warnings, git_errors = git_summary(root)
    recovery, recovery_warnings, recovery_errors = recovery_summary(root)
    inventory = workspace_inventory(root)
    if inventory["raw_folder_generated_mirrors"]:
        mirror_root = configured_office_mirror_root(root).as_posix()
        warnings.append(
            f"raw source folders contain generated source mirrors; use dedicated {mirror_root}/ output before pilot review."
        )
    if recovery.get("items", 0):
        warnings.append("recovery has operator-action items; run `vaultwright recovery` before relying on mirrors.")
    warnings.extend([
        *boundary_warnings,
        *source_warnings,
        *repo_warnings,
        *audit_warnings,
        *git_warnings,
        *recovery_warnings,
    ])
    errors.extend([
        *required_errors,
        *boundary_errors,
        *source_errors,
        *repo_errors,
        *audit_errors,
        *git_errors,
        *recovery_errors,
    ])
    report = {
        "required": required,
        "source_boundary": boundary,
        "inventory": inventory,
        "source_manifest": manifest_summary(source_records, "source_id"),
        "repo_manifest": manifest_summary(repo_records, "repo_id"),
        "audit": audit,
        "git": git,
        "recovery": recovery,
        "benchmark": benchmark_presence(root),
    }
    return report, warnings, errors


def print_counts(label: str, counts: dict[str, int]) -> None:
    rendered = ", ".join(f"{key}={counts[key]}" for key in sorted(counts)) or "none"
    print(f"  {label}: {rendered}")


def print_human(report: dict[str, Any], warnings: list[str], errors: list[str]) -> None:
    print("vaultwright sandbox")
    print("sandbox: read-only copied-vault preflight; no source content or source paths were printed")
    for warning in warnings:
        print(f"  warning: {warning}")
    for error in errors:
        print(f"  error: {error}")
    boundary = report["source_boundary"]
    print(f"sandbox: source boundary status={boundary['status']}")
    inventory = report["inventory"]
    print(
        "sandbox: workspace "
        f"content_files={inventory['content_files']} "
        f"content_bytes={inventory['content_bytes']} "
        f"source_candidates={inventory['source_candidates']}"
    )
    print(
        "sandbox: generated mirrors "
        f"dedicated={inventory['dedicated_generated_mirrors']} "
        f"raw_folder={inventory['raw_folder_generated_mirrors']} "
        f"repo={inventory['repo_mirrors']}"
    )
    print_counts("extensions", inventory["extensions"])
    source = report["source_manifest"]
    repo = report["repo_manifest"]
    print(
        "sandbox: source manifest "
        f"records={source['records']} warnings={source['warnings']} errors={source['errors']}"
    )
    print_counts("source states", source["states"])
    print(f"sandbox: repo manifest records={repo['records']} warnings={repo['warnings']} errors={repo['errors']}")
    print_counts("repo states", repo["states"])
    audit = report["audit"]
    print(f"sandbox: audit events={audit['events']}")
    recovery = report["recovery"]
    print(
        "sandbox: recovery "
        f"available={recovery['available']} "
        f"items={recovery['items']} "
        f"office={recovery.get('office', 0)} "
        f"repo={recovery.get('repo', 0)} "
        f"temp={recovery.get('temp', 0)}"
    )
    git = report["git"]
    print(
        "sandbox: git "
        f"available={git['available']} "
        f"inside_work_tree={git.get('inside_work_tree', False)} "
        f"root_is_vault={git.get('git_root_is_vault', False)} "
        f"clean={git.get('working_tree_clean', False)}"
    )
    benchmark = report["benchmark"]
    print(f"sandbox: benchmark tasks={benchmark['tasks']} results={benchmark['results']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print a read-only copied-vault sandbox readiness report.")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=None,
        help="Original source collection root. Used only to verify the pilot vault is a separate copy.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable sandbox JSON.")
    return parser


def main(argv: list[str] | None = None, root: Path | None = None) -> int:
    args = build_parser().parse_args(argv)
    active_root = (root or DEFAULT_ROOT).expanduser().resolve()
    report, warnings, errors = build_report(active_root, args.source_root)
    payload = {"report": report, "warnings": warnings, "errors": errors}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_human(report, warnings, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
