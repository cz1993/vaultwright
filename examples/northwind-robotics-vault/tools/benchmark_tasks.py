#!/usr/bin/env python3
"""Validate and summarize Vaultwright agent-readiness benchmark task packs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASKS = Path("_meta/agent-readiness-tasks.yml")
REQUIRED_MODES = {"raw_source_folder", "document_chat_transcript", "vaultwright_markdown"}
FAMILIES = {"answer", "reconcile", "update", "audit", "consolidate"}


def rel_path(value: str) -> Path | None:
    path = Path(str(value))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return None
    return path


def load_tasks(path: Path) -> tuple[dict, list[str]]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return {}, [f"{path.relative_to(ROOT)}: invalid YAML ({exc.__class__.__name__})"]
    if not isinstance(data, dict):
        return {}, [f"{path.relative_to(ROOT)}: must be a mapping"]
    return data, []


def validate_task_pack(path: Path, *, require_generated: bool = False) -> tuple[dict, list[str], list[str]]:
    data, errors = load_tasks(path)
    warnings: list[str] = []
    if errors:
        return {}, errors, warnings

    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not str(data.get("corpus", "")).strip():
        errors.append("corpus is required")
    modes = data.get("comparison_modes")
    if not isinstance(modes, list) or set(str(mode) for mode in modes) != REQUIRED_MODES:
        errors.append("comparison_modes must include raw_source_folder, document_chat_transcript, and vaultwright_markdown")
    scoring = data.get("scoring")
    if not isinstance(scoring, dict) or str(scoring.get("scale", "")).strip() != "0-2":
        errors.append("scoring.scale must be 0-2")

    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        errors.append("tasks must be a non-empty list")
        tasks = []

    ids: set[str] = set()
    families: set[str] = set()
    source_count = 0
    generated_count = 0
    curated_count = 0

    for index, task in enumerate(tasks):
        label = f"tasks[{index}]"
        if not isinstance(task, dict):
            errors.append(f"{label}: must be a mapping")
            continue
        task_id = str(task.get("id", "")).strip()
        if not task_id:
            errors.append(f"{label}: id is required")
        elif task_id in ids:
            errors.append(f"{label}: duplicate id {task_id}")
        ids.add(task_id)

        family = str(task.get("family", "")).strip()
        if family not in FAMILIES:
            errors.append(f"{task_id or label}: invalid family {family}")
        else:
            families.add(family)

        prompt = str(task.get("prompt", "")).strip()
        if not prompt:
            errors.append(f"{task_id or label}: prompt is required")

        criteria = task.get("success_criteria")
        if not isinstance(criteria, list) or not criteria:
            errors.append(f"{task_id or label}: success_criteria must be non-empty")

        for field in ("source_paths", "generated_mirror_paths", "curated_paths"):
            values = task.get(field, [])
            if not isinstance(values, list):
                errors.append(f"{task_id or label}: {field} must be a list")
                continue
            for value in values:
                rel = rel_path(str(value))
                if rel is None:
                    errors.append(f"{task_id or label}: invalid {field} path {value}")
                    continue
                exists = (ROOT / rel).exists()
                if field == "source_paths":
                    source_count += 1
                    if "_mirrors" in rel.parts:
                        errors.append(f"{task_id or label}: source_paths must not point into _mirrors: {value}")
                    if not exists:
                        errors.append(f"{task_id or label}: missing source path {value}")
                elif field == "curated_paths":
                    curated_count += 1
                    if rel.suffix != ".md":
                        errors.append(f"{task_id or label}: curated_paths must be markdown: {value}")
                    if not exists:
                        errors.append(f"{task_id or label}: missing curated path {value}")
                else:
                    generated_count += 1
                    if "_mirrors" not in rel.parts:
                        errors.append(f"{task_id or label}: generated_mirror_paths must point into _mirrors: {value}")
                    if not exists:
                        message = f"{task_id or label}: generated mirror not present yet: {value}"
                        if require_generated:
                            errors.append(message)
                        else:
                            warnings.append(message)

    if not FAMILIES.issubset(families):
        missing = ", ".join(sorted(FAMILIES - families))
        errors.append(f"task pack must cover all benchmark families; missing: {missing}")

    summary = {
        "path": path.relative_to(ROOT).as_posix(),
        "corpus": data.get("corpus"),
        "tasks": len(tasks),
        "families": sorted(families),
        "source_paths": source_count,
        "generated_mirror_paths": generated_count,
        "curated_paths": curated_count,
        "require_generated": require_generated,
    }
    return summary, errors, warnings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a Vaultwright agent-readiness benchmark task pack.")
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS, help="Task pack path relative to the vault root.")
    parser.add_argument("--require-generated", action="store_true", help="Require generated mirror paths to exist.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary JSON.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    task_path = args.tasks if args.tasks.is_absolute() else ROOT / args.tasks
    if not task_path.exists():
        if args.tasks == DEFAULT_TASKS:
            print(f"benchmark_tasks: no {DEFAULT_TASKS.as_posix()} found; benchmark validation skipped")
            return 0
        print(f"benchmark_tasks: missing task pack: {args.tasks}", file=sys.stderr)
        return 1

    summary, errors, warnings = validate_task_pack(task_path, require_generated=args.require_generated)
    if args.json:
        print(json.dumps({"summary": summary, "warnings": warnings, "errors": errors}, indent=2, sort_keys=True))
    else:
        print(f"benchmark_tasks: {summary.get('tasks', 0)} tasks in {summary.get('path', args.tasks)}")
        if summary:
            print(f"  families: {', '.join(summary['families'])}")
            print(
                "  refs: "
                f"sources={summary['source_paths']} "
                f"generated_mirrors={summary['generated_mirror_paths']} "
                f"curated={summary['curated_paths']}"
            )
        for warning in warnings:
            print(f"  warning: {warning}")
        for error in errors:
            print(f"  error: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
