#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Print a read-only design-partner pilot evidence report."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SOURCE_MANIFEST = Path("_meta/source-manifest.json")
REPO_MANIFEST = Path("_meta/repo-manifest.json")
AUDIT_LOG = Path("_meta/sync-audit.jsonl")
BENCHMARK_TASKS = Path("_meta/agent-readiness-tasks.yml")
BENCHMARK_RESULTS = Path("_meta/agent-readiness-results.yml")
EXCLUDED_PARTS = {
    ".git",
    ".github",
    ".githooks",
    ".obsidian",
    "_fixtures",
    "_meta",
    "_mirrors",
    "_templates",
    "_tmp",
    "node_modules",
    "tools",
}
OFFICE_SOURCE_EXTS = {".doc", ".docx", ".pdf", ".pptx", ".xlsx"}


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


def count_strings(records: list[dict], key: str, fallback: str = "unknown") -> dict[str, int]:
    counts = Counter(str(record.get(key, fallback) or fallback) for record in records)
    return dict(sorted(counts.items()))


def count_list_items(records: list[dict], key: str) -> int:
    total = 0
    for record in records:
        value = record.get(key)
        if isinstance(value, list):
            total += len([item for item in value if str(item).strip()])
    return total


def manifest_summary(records: list[dict], id_key: str, format_key: str = "") -> dict[str, Any]:
    missing_ids = sum(1 for record in records if not str(record.get(id_key, "")).strip())
    summary: dict[str, Any] = {
        "records": len(records),
        "missing_ids": missing_ids,
        "states": count_strings(records, "lifecycle_state"),
        "warnings": count_list_items(records, "warnings"),
        "errors": count_list_items(records, "errors"),
    }
    if format_key:
        summary["formats"] = count_strings(records, format_key)
        summary["total_size_bytes"] = sum(
            int(record.get("source_size", 0))
            for record in records
            if isinstance(record.get("source_size"), int)
        )
    return summary


def workspace_inventory(root: Path) -> dict[str, Any]:
    files = 0
    bytes_total = 0
    extensions: Counter[str] = Counter()
    office_candidates = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        files += 1
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        bytes_total += size
        suffix = path.suffix.lower() or "[no extension]"
        extensions[suffix] += 1
        if suffix in OFFICE_SOURCE_EXTS:
            office_candidates += 1
    return {
        "content_files": files,
        "content_bytes": bytes_total,
        "office_source_candidates": office_candidates,
        "extensions": dict(sorted(extensions.items())),
    }


def audit_summary(root: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    path = root / AUDIT_LOG
    if not path.exists():
        return {"events": 0, "tools": {}, "statuses": {}, "states": {}}, [f"{AUDIT_LOG.as_posix()}: missing"], []
    warnings: list[str] = []
    errors: list[str] = []
    tools: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    states: Counter[str] = Counter()
    events = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return {"events": 0, "tools": {}, "statuses": {}, "states": {}}, [], [
            f"{AUDIT_LOG.as_posix()}: unreadable text"
        ]
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
        tools[str(event.get("tool", "unknown") or "unknown")] += 1
        statuses[str(event.get("status", "unknown") or "unknown")] += 1
        states[str(event.get("lifecycle_state", "unknown") or "unknown")] += 1
    return {
        "events": events,
        "tools": dict(sorted(tools.items())),
        "statuses": dict(sorted(statuses.items())),
        "states": dict(sorted(states.items())),
    }, warnings, errors


def load_tool_module(root: Path, script: str) -> tuple[Any | None, list[str]]:
    path = root / "tools" / script
    if not path.exists():
        return None, [f"tools/{script}: missing"]
    try:
        spec = importlib.util.spec_from_file_location(f"vaultwright_{script.replace('.', '_')}", path)
        if not spec or not spec.loader:
            raise ImportError("cannot load module spec")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, []
    except Exception as exc:
        return None, [f"tools/{script}: unavailable ({exc.__class__.__name__})"]


def conversion_summary(root: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    module, load_errors = load_tool_module(root, "conversion_report.py")
    if not module:
        return {"available": False, "summary": {}}, [], load_errors
    try:
        report, warnings, errors = module.build_report(root, low_risk_per_format=0)
        summary = dict(report.get("summary", {}))
        summary["warnings"] = len(warnings)
        summary["errors"] = len(errors)
        messages = [f"conversion report has {len(warnings)} warnings; run `vaultwright conversion`"] if warnings else []
        failures = [f"conversion report has {len(errors)} errors; run `vaultwright conversion`"] if errors else []
        return {"available": True, "summary": summary}, messages, failures
    except Exception as exc:
        return {"available": False, "summary": {}}, [], [f"conversion report failed: {exc.__class__.__name__}"]


def recovery_summary(root: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    module, load_errors = load_tool_module(root, "recovery_report.py")
    if not module:
        return {"available": False, "summary": {}}, [], load_errors
    try:
        items, warnings, errors = module.build_report(root)
        summary = dict(module.summary_counts(items))
        summary["warnings"] = len(warnings)
        summary["errors"] = len(errors)
        messages = [f"recovery report has {len(warnings)} warnings; run `vaultwright recovery`"] if warnings else []
        failures = [f"recovery report has {len(errors)} errors; run `vaultwright recovery`"] if errors else []
        return {"available": True, "summary": summary}, messages, failures
    except Exception as exc:
        return {"available": False, "summary": {}}, [], [f"recovery report failed: {exc.__class__.__name__}"]


def benchmark_summary(root: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    task_path = root / BENCHMARK_TASKS
    if not task_path.exists():
        return {"available": False, "summary": {}}, [f"{BENCHMARK_TASKS.as_posix()}: missing"], []
    module, load_errors = load_tool_module(root, "benchmark_tasks.py")
    if not module:
        return {"available": False, "summary": {}}, [], load_errors
    try:
        summary, errors, warnings = module.validate_task_pack(task_path, require_generated=False)
        summary = dict(summary)
        summary["warnings"] = len(warnings)
        summary["errors"] = len(errors)
        result_summary: dict[str, Any] = {"available": False}
        result_path = root / BENCHMARK_RESULTS
        if result_path.exists() and hasattr(module, "validate_result_pack"):
            results, result_errors, result_warnings = module.validate_result_pack(
                result_path,
                task_path,
                require_complete=False,
            )
            result_summary = {
                "available": True,
                "summary": results,
                "warnings": len(result_warnings),
                "errors": len(result_errors),
            }
            warnings.extend(result_warnings)
            errors.extend(result_errors)
        summary["results"] = result_summary
        messages = [f"benchmark report has {len(warnings)} warnings; run `vaultwright benchmark`"] if warnings else []
        failures = [f"benchmark report has {len(errors)} errors; run `vaultwright benchmark`"] if errors else []
        return {"available": True, "summary": summary}, messages, failures
    except Exception as exc:
        return {"available": False, "summary": {}}, [], [f"benchmark report failed: {exc.__class__.__name__}"]


def review_summary(root: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    module, load_errors = load_tool_module(root, "review_ledger.py")
    if not module:
        return {"available": False, "summary": {}}, [], load_errors
    try:
        report, warnings = module.build_report(root)
        latest = report.get("latest_reviews", [])
        if not isinstance(latest, list):
            latest = []
        stale_or_missing = 0
        non_approved = 0
        for entry in latest:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("current_state", "") or "") != "current":
                stale_or_missing += 1
            if str(entry.get("status", "") or "") != "approved":
                non_approved += 1
        summary = {
            "events": int(report.get("events", 0) or 0),
            "reviewed_artifacts": int(report.get("reviewed_artifacts", 0) or 0),
            "statuses": report.get("statuses", {}) if isinstance(report.get("statuses"), dict) else {},
            "artifact_kinds": report.get("artifact_kinds", {}) if isinstance(report.get("artifact_kinds"), dict) else {},
            "current_states": report.get("current_states", {}) if isinstance(report.get("current_states"), dict) else {},
            "stale_or_missing": stale_or_missing,
            "non_approved": non_approved,
            "warnings": len(warnings),
        }
        messages = [f"review ledger has {len(warnings)} warnings; run `vaultwright review`"] if warnings else []
        return {"available": True, "summary": summary}, messages, []
    except Exception as exc:
        return {"available": False, "summary": {}}, [], [f"review ledger failed: {exc.__class__.__name__}"]


def build_report(root: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    source_records, source_warnings, source_errors = load_json_records(root, SOURCE_MANIFEST)
    repo_records, repo_warnings, repo_errors = load_json_records(root, REPO_MANIFEST)
    audit, audit_warnings, audit_errors = audit_summary(root)
    conversion, conversion_warnings, conversion_errors = conversion_summary(root)
    recovery, recovery_warnings, recovery_errors = recovery_summary(root)
    benchmark, benchmark_warnings, benchmark_errors = benchmark_summary(root)
    review, review_warnings, review_errors = review_summary(root)
    warnings.extend([
        *source_warnings,
        *repo_warnings,
        *audit_warnings,
        *conversion_warnings,
        *recovery_warnings,
        *benchmark_warnings,
        *review_warnings,
    ])
    errors.extend([
        *source_errors,
        *repo_errors,
        *audit_errors,
        *conversion_errors,
        *recovery_errors,
        *benchmark_errors,
        *review_errors,
    ])
    report = {
        "inventory": workspace_inventory(root),
        "source_manifest": manifest_summary(source_records, "source_id", "source_format"),
        "repo_manifest": manifest_summary(repo_records, "repo_id"),
        "audit": audit,
        "conversion": conversion,
        "recovery": recovery,
        "benchmark": benchmark,
        "review": review,
    }
    return report, warnings, errors


def print_counts(label: str, counts: dict[str, int]) -> None:
    rendered = ", ".join(f"{key}={counts[key]}" for key in sorted(counts)) or "none"
    print(f"  {label}: {rendered}")


def print_human(root: Path, report: dict[str, Any], warnings: list[str], errors: list[str]) -> None:
    print("vaultwright pilot")
    print("pilot: read-only evidence report; no source content was printed")
    for warning in warnings:
        print(f"  warning: {warning}")
    for error in errors:
        print(f"  error: {error}", file=sys.stderr)

    inventory = report["inventory"]
    print(
        "pilot: workspace inventory "
        f"files={inventory['content_files']} "
        f"bytes={inventory['content_bytes']} "
        f"office_candidates={inventory['office_source_candidates']}"
    )
    print_counts("extensions", inventory["extensions"])

    source = report["source_manifest"]
    print(
        "pilot: source manifest "
        f"records={source['records']} "
        f"warnings={source['warnings']} "
        f"errors={source['errors']} "
        f"bytes={source.get('total_size_bytes', 0)}"
    )
    print_counts("source states", source["states"])
    print_counts("source formats", source.get("formats", {}))

    repo = report["repo_manifest"]
    print(f"pilot: repo manifest records={repo['records']} warnings={repo['warnings']} errors={repo['errors']}")
    print_counts("repo states", repo["states"])

    audit = report["audit"]
    print(f"pilot: audit events={audit['events']}")
    print_counts("audit tools", audit["tools"])
    print_counts("audit states", audit["states"])

    conversion = report["conversion"]["summary"]
    print(
        "pilot: conversion "
        f"available={report['conversion']['available']} "
        f"high={conversion.get('high', 0)} "
        f"medium={conversion.get('medium', 0)} "
        f"low={conversion.get('low', 0)}"
    )

    recovery = report["recovery"]["summary"]
    print(
        "pilot: recovery "
        f"available={report['recovery']['available']} "
        f"items={recovery.get('total', 0)}"
    )

    benchmark = report["benchmark"]["summary"]
    print(
        "pilot: benchmark "
        f"available={report['benchmark']['available']} "
        f"tasks={benchmark.get('tasks', 0)}"
    )
    results = benchmark.get("results", {})
    result_summary = results.get("summary", {}) if isinstance(results, dict) else {}
    if isinstance(results, dict) and results.get("available"):
        print(
            "pilot: benchmark results "
            f"available=True "
            f"results={result_summary.get('results', 0)} "
            f"missing={result_summary.get('missing_results', 0)}"
        )
    review = report["review"]["summary"]
    print(
        "pilot: review ledger "
        f"available={report['review']['available']} "
        f"reviewed={review.get('reviewed_artifacts', 0)} "
        f"stale_or_missing={review.get('stale_or_missing', 0)} "
        f"non_approved={review.get('non_approved', 0)}"
    )


def print_worksheet_summary(report: dict[str, Any], warnings: list[str], errors: list[str]) -> None:
    inventory = report["inventory"]
    source = report["source_manifest"]
    repo = report["repo_manifest"]
    audit = report["audit"]
    conversion = report["conversion"]["summary"]
    recovery = report["recovery"]["summary"]
    benchmark = report["benchmark"]["summary"]
    review = report["review"]["summary"]
    results = benchmark.get("results", {})
    result_summary = results.get("summary", {}) if isinstance(results, dict) else {}
    result_available = bool(isinstance(results, dict) and results.get("available"))

    print("# Vaultwright Pilot Evidence Summary")
    print()
    print(
        "Generated from aggregate Vaultwright manifests and reports only. It intentionally omits "
        "source paths, document text, mirror text, answer text, reviewer notes, and client identifiers."
    )
    print()
    print("## Corpus Shape")
    print(f"- Content files: {inventory['content_files']}")
    print(f"- Content bytes: {inventory['content_bytes']}")
    print(f"- Office/PDF source candidates: {inventory['office_source_candidates']}")
    print(f"- Source manifest records: {source['records']}")
    print(f"- Repo manifest records: {repo['records']}")
    print(f"- Source formats: {', '.join(f'{key}={value}' for key, value in sorted(source.get('formats', {}).items())) or 'none'}")
    print()
    print("## Health And Review Queues")
    print(f"- Source warnings/errors: {source['warnings']}/{source['errors']}")
    print(f"- Repo warnings/errors: {repo['warnings']}/{repo['errors']}")
    print(f"- Sync audit events: {audit['events']}")
    print(
        "- Conversion review queue: "
        f"available={report['conversion']['available']} "
        f"high={conversion.get('high', 0)} "
        f"medium={conversion.get('medium', 0)} "
        f"low={conversion.get('low', 0)}"
    )
    print(
        "- Recovery queue: "
        f"available={report['recovery']['available']} "
        f"items={recovery.get('total', 0)}"
    )
    print(
        "- Benchmark tasks: "
        f"available={report['benchmark']['available']} "
        f"tasks={benchmark.get('tasks', 0)}"
    )
    print(
        "- Benchmark results: "
        f"available={result_available} "
        f"records={result_summary.get('results', 0)} "
        f"missing={result_summary.get('missing_results', 0)}"
    )
    print(
        "- Review ledger: "
        f"available={report['review']['available']} "
        f"reviewed={review.get('reviewed_artifacts', 0)} "
        f"stale_or_missing={review.get('stale_or_missing', 0)} "
        f"non_approved={review.get('non_approved', 0)}"
    )
    print(f"- Pilot report warnings/errors: {len(warnings)}/{len(errors)}")
    print()
    print("## Private Worksheet Fields")
    print("- Baseline time to answer fixed questions:")
    print("- Vaultwright time to answer fixed questions:")
    print("- Manual correction count:")
    print("- Operator confidence score:")
    print("- Support time required:")
    print("- Participant returned after one week:")
    print("- Product changes requested:")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print a read-only Vaultwright pilot evidence report.")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Print machine-readable pilot JSON.")
    output.add_argument(
        "--worksheet",
        action="store_true",
        help="Print a redacted Markdown summary for a private pilot worksheet.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report, warnings, errors = build_report(ROOT)
    payload = {
        "report": report,
        "warnings": warnings,
        "errors": errors,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.worksheet:
        print_worksheet_summary(report, warnings, errors)
    else:
        print_human(ROOT, report, warnings, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
