#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Validate and summarize Vaultwright agent-readiness benchmark task packs."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASKS = Path("_meta/agent-readiness-tasks.yml")
DEFAULT_RESULTS = Path("_meta/agent-readiness-results.yml")
REQUIRED_MODES = {"raw_source_folder", "document_chat_transcript", "vaultwright_markdown"}
FAMILIES = {"answer", "reconcile", "update", "audit", "consolidate"}
RESULT_ALLOWED_FIELDS = {
    "task_id",
    "mode",
    "score",
    "reviewer_corrections",
    "elapsed_seconds",
    "cited_source_paths",
    "cited_generated_mirror_paths",
    "privacy_or_provenance_violation",
}
RESULT_PACK_ALLOWED_FIELDS = {"schema_version", "corpus", "results"}


def display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def rel_path(value: str) -> Path | None:
    path = Path(str(value))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return None
    return path


def load_tasks(path: Path) -> tuple[dict, list[str]]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return {}, [f"{display_path(path)}: invalid YAML ({exc.__class__.__name__})"]
    if not isinstance(data, dict):
        return {}, [f"{display_path(path)}: must be a mapping"]
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
        "path": display_path(path),
        "corpus": data.get("corpus"),
        "tasks": len(tasks),
        "families": sorted(families),
        "source_paths": source_count,
        "generated_mirror_paths": generated_count,
        "curated_paths": curated_count,
        "require_generated": require_generated,
    }
    return summary, errors, warnings


def valid_non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def valid_score(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value in {0, 1, 2}


def task_ids_from_pack(data: dict) -> set[str]:
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        return set()
    return {
        str(task.get("id", "")).strip()
        for task in tasks
        if isinstance(task, dict) and str(task.get("id", "")).strip()
    }


def task_path_refs_from_pack(data: dict) -> dict[str, dict[str, set[str]]]:
    refs: dict[str, dict[str, set[str]]] = {}
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        return refs
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("id", "")).strip()
        if not task_id:
            continue
        refs[task_id] = {
            "cited_source_paths": set(path_list(task.get("source_paths", [])) or []),
            "cited_generated_mirror_paths": set(path_list(task.get("generated_mirror_paths", [])) or []),
        }
    return refs


def path_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    return [str(item) for item in value]


def validate_result_paths(
    label: str,
    field: str,
    values: object,
    errors: list[str],
    *,
    allowed_paths: set[str] | None,
) -> int:
    paths = path_list(values)
    if paths is None:
        errors.append(f"{label}: {field} must be a list")
        return 0
    valid = 0
    for value in paths:
        rel = rel_path(value)
        if rel is None:
            errors.append(f"{label}: invalid {field} path {value}")
            continue
        if field == "cited_source_paths" and "_mirrors" in rel.parts:
            errors.append(f"{label}: cited_source_paths must not point into _mirrors: {value}")
            continue
        if field == "cited_generated_mirror_paths" and "_mirrors" not in rel.parts:
            errors.append(f"{label}: cited_generated_mirror_paths must point into _mirrors: {value}")
            continue
        if not (ROOT / rel).exists():
            errors.append(f"{label}: cited path does not exist: {value}")
            continue
        if allowed_paths is not None and rel.as_posix() not in allowed_paths:
            errors.append(f"{label}: {field} must cite a path declared by the task: {value}")
            continue
        valid += 1
    return valid


def validate_result_pack(
    path: Path,
    task_path: Path,
    *,
    require_complete: bool = False,
) -> tuple[dict, list[str], list[str]]:
    task_data, task_errors = load_tasks(task_path)
    result_data, result_errors = load_tasks(path)
    errors = [*task_errors, *result_errors]
    warnings: list[str] = []
    if errors:
        return {}, errors, warnings
    known_task_ids = task_ids_from_pack(task_data)
    task_refs = task_path_refs_from_pack(task_data)
    if not known_task_ids:
        errors.append(f"{display_path(task_path)}: no benchmark task ids found")
    extra_top_level = sorted(set(result_data) - RESULT_PACK_ALLOWED_FIELDS)
    for field in extra_top_level:
        errors.append(
            f"result pack: unsupported top-level field {field}; "
            "do not store answer text or reviewer notes in result packs"
        )
    if result_data.get("schema_version") != 1:
        errors.append("results schema_version must be 1")
    task_corpus = str(task_data.get("corpus", "")).strip()
    result_corpus = str(result_data.get("corpus", "")).strip()
    if result_corpus and task_corpus and result_corpus != task_corpus:
        errors.append(f"results corpus {result_corpus} does not match task corpus {task_corpus}")

    results = result_data.get("results")
    if not isinstance(results, list) or not results:
        errors.append("results must be a non-empty list")
        results = []

    seen: set[tuple[str, str]] = set()
    mode_summary: dict[str, dict[str, float | int]] = {
        mode: {
            "results": 0,
            "score": 0,
            "max_score": 0,
            "average_score": 0.0,
            "reviewer_corrections": 0,
            "violations": 0,
            "timed_results": 0,
            "elapsed_seconds": 0.0,
        }
        for mode in sorted(REQUIRED_MODES)
    }

    for index, result in enumerate(results):
        label = f"results[{index}]"
        if not isinstance(result, dict):
            errors.append(f"{label}: must be a mapping")
            continue
        task_id = str(result.get("task_id", "")).strip()
        mode = str(result.get("mode", "")).strip()
        extra_fields = sorted(set(result) - RESULT_ALLOWED_FIELDS)
        for field in extra_fields:
            errors.append(
                f"{task_id or label}: unsupported result field {field}; "
                "do not store answer text or reviewer notes in result packs"
            )
        if not task_id:
            errors.append(f"{label}: task_id is required")
        elif task_id not in known_task_ids:
            errors.append(f"{label}: unknown task_id {task_id}")
        if mode not in REQUIRED_MODES:
            errors.append(f"{task_id or label}: invalid mode {mode}")
        elif task_id:
            key = (task_id, mode)
            if key in seen:
                errors.append(f"{task_id}: duplicate result for mode {mode}")
            seen.add(key)

        score = result.get("score")
        if not valid_score(score):
            errors.append(f"{task_id or label}: score must be 0, 1, or 2")
            score_value = 0
        else:
            score_value = int(score)

        corrections = result.get("reviewer_corrections", 0)
        if not valid_non_negative_int(corrections):
            errors.append(f"{task_id or label}: reviewer_corrections must be a non-negative integer")
            correction_count = 0
        else:
            correction_count = int(corrections)

        citation_count = 0
        for field in ("cited_source_paths", "cited_generated_mirror_paths"):
            if field in result:
                citation_count += validate_result_paths(
                    task_id or label,
                    field,
                    result[field],
                    errors,
                    allowed_paths=task_refs.get(task_id, {}).get(field),
                )
        if score_value > 0 and citation_count == 0:
            warnings.append(f"{task_id or label}: scored result has no cited source or mirror paths")

        violation = result.get("privacy_or_provenance_violation", False)
        if not isinstance(violation, bool):
            errors.append(f"{task_id or label}: privacy_or_provenance_violation must be true or false")
            violation = False

        elapsed = result.get("elapsed_seconds")
        elapsed_value = 0.0
        has_elapsed = False
        if elapsed is not None:
            if (
                isinstance(elapsed, bool)
                or not isinstance(elapsed, (int, float))
                or not math.isfinite(float(elapsed))
                or elapsed < 0
            ):
                errors.append(f"{task_id or label}: elapsed_seconds must be a finite non-negative number")
            else:
                elapsed_value = float(elapsed)
                has_elapsed = True

        if mode in mode_summary:
            summary = mode_summary[mode]
            summary["results"] = int(summary["results"]) + 1
            summary["score"] = int(summary["score"]) + score_value
            summary["max_score"] = int(summary["max_score"]) + 2
            summary["reviewer_corrections"] = int(summary["reviewer_corrections"]) + correction_count
            summary["violations"] = int(summary["violations"]) + (1 if violation else 0)
            if has_elapsed:
                summary["timed_results"] = int(summary["timed_results"]) + 1
                summary["elapsed_seconds"] = float(summary["elapsed_seconds"]) + elapsed_value

    for summary in mode_summary.values():
        count = int(summary["results"])
        summary["average_score"] = round(float(summary["score"]) / count, 2) if count else 0.0
        summary["elapsed_seconds"] = round(float(summary["elapsed_seconds"]), 2)

    expected = {(task_id, mode) for task_id in known_task_ids for mode in REQUIRED_MODES}
    missing = sorted(expected - seen)
    if missing:
        message = f"benchmark results incomplete: missing {len(missing)} task/mode scores"
        if require_complete:
            errors.append(message)
        else:
            warnings.append(message)

    summary = {
        "path": display_path(path),
        "task_pack": display_path(task_path),
        "corpus": result_corpus or task_corpus,
        "results": len(results),
        "expected_results": len(expected),
        "missing_results": len(missing),
        "complete": not missing,
        "modes": mode_summary,
    }
    return summary, errors, warnings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a Vaultwright agent-readiness benchmark task pack.")
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS, help="Task pack path relative to the vault root.")
    parser.add_argument("--results", type=Path, help="Optional benchmark results path relative to the vault root.")
    parser.add_argument("--require-generated", action="store_true", help="Require generated mirror paths to exist.")
    parser.add_argument("--require-results", action="store_true", help="Require benchmark results for every task/mode pair.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary JSON.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    task_path = args.tasks if args.tasks.is_absolute() else ROOT / args.tasks
    result_path_arg = args.results or DEFAULT_RESULTS
    result_path = result_path_arg if result_path_arg.is_absolute() else ROOT / result_path_arg
    if not task_path.exists():
        if args.tasks == DEFAULT_TASKS and not args.results and not args.require_results and not result_path.exists():
            print(f"benchmark_tasks: no {DEFAULT_TASKS.as_posix()} found; benchmark validation skipped")
            return 0
        print(f"benchmark_tasks: missing task pack: {args.tasks}", file=sys.stderr)
        return 1

    summary, errors, warnings = validate_task_pack(task_path, require_generated=args.require_generated)
    result_summary: dict = {}
    should_validate_results = bool(args.results) or args.require_results or result_path.exists()
    if should_validate_results:
        if not result_path.exists():
            errors.append(f"benchmark_results: missing result pack: {result_path_arg}")
        else:
            result_summary, result_errors, result_warnings = validate_result_pack(
                result_path,
                task_path,
                require_complete=args.require_results,
            )
            errors.extend(result_errors)
            warnings.extend(result_warnings)
    if args.json:
        print(
            json.dumps(
                {"summary": summary, "result_summary": result_summary, "warnings": warnings, "errors": errors},
                indent=2,
                sort_keys=True,
            )
        )
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
        if result_summary:
            print(f"benchmark_results: {result_summary.get('results', 0)} results in {result_summary['path']}")
            modes = result_summary.get("modes", {})
            for mode in sorted(modes):
                mode_info = modes[mode]
                print(
                    f"  {mode}: "
                    f"results={mode_info['results']} "
                    f"score={mode_info['score']}/{mode_info['max_score']} "
                    f"avg={mode_info['average_score']:.2f} "
                    f"corrections={mode_info['reviewer_corrections']} "
                    f"violations={mode_info['violations']}"
                )
        for warning in warnings:
            print(f"  warning: {warning}")
        for error in errors:
            print(f"  error: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
