#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Validate and summarize Vaultwright agent-readiness benchmark task packs."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

from vaultwright.profiles import ProfileValidationError, load_profile
from vaultwright.runtime_profile import configured_office_mirror_root


DEFAULT_ROOT = Path.cwd()
ROOT = DEFAULT_ROOT
PROFILE = Path("_meta/profile.yml")
DEFAULT_TASKS = Path("_meta/agent-readiness-tasks.yml")
DEFAULT_RESULTS = Path("_meta/agent-readiness-results.yml")
SOURCE_MANIFEST = Path("_meta/source-manifest.json")
MODE_ORDER = ("raw_source_folder", "document_chat_transcript", "vaultwright_markdown")
REQUIRED_MODES = set(MODE_ORDER)
FAMILY_ORDER = ("answer", "reconcile", "update", "audit", "consolidate")
FAMILIES = set(FAMILY_ORDER)
RESERVED_CURATED_PARTS = {
    ".git",
    ".github",
    ".githooks",
    "_fixtures",
    "_meta",
    "_mirrors",
    "_templates",
    "_tmp",
    "node_modules",
    "tools",
}
CURATED_EXCLUDED_NAMES = {
    "AGENTS.md",
    "CATALOG.md",
    "CLAUDE.md",
    "README.md",
    "RETENTION.md",
    "log.md",
}
RESULT_ALLOWED_FIELDS = {
    "task_id",
    "mode",
    "score",
    "reviewer_corrections",
    "elapsed_seconds",
    "cited_source_paths",
    "cited_generated_mirror_paths",
    "privacy_or_provenance_violation",
    "prompt_safety_reviewed",
    "prompt_safety_violation",
}
RESULT_PACK_ALLOWED_FIELDS = {"schema_version", "corpus", "results"}


def active_mirror_root() -> Path:
    return configured_office_mirror_root(ROOT)


def under_path_root(rel: Path, root: Path) -> bool:
    return bool(root.parts) and rel.parts[: len(root.parts)] == root.parts


def configure_root(root: Path | None = None) -> Path:
    global ROOT
    ROOT = (root or DEFAULT_ROOT).expanduser().resolve()
    return ROOT


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


def safe_yaml_output_path(path_arg: Path, label: str) -> Path:
    path = path_arg if path_arg.is_absolute() else ROOT / path_arg
    resolved_root = ROOT.resolve()
    resolved = path.expanduser().resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"{label} output must stay inside the vault") from exc
    if resolved.suffix not in {".yml", ".yaml"}:
        raise ValueError(f"{label} output must be a .yml or .yaml file")
    if resolved.exists() and resolved.is_dir():
        raise ValueError(f"{label} output must be a file, not a directory")
    return resolved


def profile_task_paths(root: Path) -> tuple[list[Path], list[str], list[str]]:
    path = root / PROFILE
    if not path.exists():
        return [], [], []
    try:
        profile = load_profile(path)
    except ProfileValidationError as exc:
        message = str(exc).replace(str(path), PROFILE.as_posix())
        return [], [], [f"{PROFILE.as_posix()}: invalid profile contract ({message})"]

    raw_paths = profile.benchmark_tasks
    if raw_paths in (None, []):
        return [], [], []
    paths: list[Path] = []
    seen: set[str] = set()
    for value in raw_paths:
        rel = Path(str(value).strip())
        rel_text = rel.as_posix()
        if rel_text in seen:
            continue
        seen.add(rel_text)
        paths.append(rel)
    return paths, [], []


def resolved_task_paths(task_arg: Path | None) -> tuple[list[Path], list[str], list[str], str]:
    if task_arg is not None:
        return [task_arg if task_arg.is_absolute() else ROOT / task_arg], [], [], "explicit"
    profile_paths, warnings, errors = profile_task_paths(ROOT)
    if errors:
        return [], warnings, errors, "profile"
    if profile_paths:
        return [ROOT / rel for rel in profile_paths], warnings, [], "profile"
    return [ROOT / DEFAULT_TASKS], warnings, [], "legacy"


def display_task_arg(path: Path) -> str:
    if path.is_absolute():
        try:
            return path.relative_to(ROOT).as_posix()
        except ValueError:
            return path.as_posix()
    return path.as_posix()


def single_task_path(
    task_paths: list[Path],
    *,
    source: str,
    operation: str,
) -> tuple[Path | None, list[str]]:
    if len(task_paths) == 1:
        return task_paths[0], []
    if source == "profile":
        return None, [
            f"benchmark_tasks: {operation} needs one task pack; pass --tasks because the profile declares {len(task_paths)} packs"
        ]
    return None, [f"benchmark_tasks: {operation} needs one task pack"]


def safe_task_output_path(path_arg: Path) -> Path:
    return safe_yaml_output_path(path_arg, "task scaffold")


def safe_result_output_path(path_arg: Path) -> Path:
    return safe_yaml_output_path(path_arg, "result scaffold")


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "task"


def load_json_mapping(rel: Path) -> tuple[dict, list[str]]:
    path = ROOT / rel
    if not path.exists():
        return {}, [f"{rel.as_posix()}: missing; run sync before initializing benchmark tasks"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [f"{rel.as_posix()}: invalid JSON ({exc.__class__.__name__})"]
    if not isinstance(data, dict):
        return {}, [f"{rel.as_posix()}: must be a JSON object"]
    return data, []


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
    mirror_root = active_mirror_root()
    mirror_label = mirror_root.as_posix()

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
                    if under_path_root(rel, mirror_root):
                        errors.append(f"{task_id or label}: source_paths must not point into {mirror_label}: {value}")
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
                    if not under_path_root(rel, mirror_root):
                        errors.append(f"{task_id or label}: generated_mirror_paths must point into {mirror_label}: {value}")
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


def source_manifest_pairs(limit: int) -> tuple[list[dict[str, str]], int, list[str], list[str]]:
    data, errors = load_json_mapping(SOURCE_MANIFEST)
    warnings: list[str] = []
    if errors:
        return [], 0, errors, warnings
    records = data.get("records")
    if not isinstance(records, list):
        return [], 0, [f"{SOURCE_MANIFEST.as_posix()}: records must be a list"], warnings

    pairs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    mirror_root = active_mirror_root()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            warnings.append(f"{SOURCE_MANIFEST.as_posix()}: skipped non-object record {index}")
            continue
        source_rel = rel_path(str(record.get("current_source_path", "")))
        mirror_rel = rel_path(str(record.get("mirror_path", "")))
        if source_rel is None or mirror_rel is None:
            warnings.append(f"{SOURCE_MANIFEST.as_posix()}: skipped record {index} with invalid source or mirror path")
            continue
        if under_path_root(source_rel, mirror_root) or not under_path_root(mirror_rel, mirror_root):
            warnings.append(f"{SOURCE_MANIFEST.as_posix()}: skipped record {index} with incompatible source or mirror path")
            continue
        source_path = ROOT / source_rel
        mirror_path = ROOT / mirror_rel
        if not source_path.exists() or not mirror_path.exists():
            continue
        key = (source_rel.as_posix(), mirror_rel.as_posix())
        if key in seen:
            continue
        seen.add(key)
        pairs.append(
            {
                "source": source_rel.as_posix(),
                "mirror": mirror_rel.as_posix(),
                "state": str(record.get("lifecycle_state", "")),
            }
        )

    pairs.sort(key=lambda item: (0 if item["state"] == "clean" else 1, item["source"]))
    return pairs[:limit], len(pairs), [], warnings


def curated_path_candidates(limit: int) -> list[str]:
    if limit <= 0:
        return []
    candidates: list[Path] = []
    mirror_root = active_mirror_root()
    for path in ROOT.rglob("*.md"):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(ROOT)
        if under_path_root(rel, mirror_root):
            continue
        if RESERVED_CURATED_PARTS.intersection(rel.parts):
            continue
        if path.name in CURATED_EXCLUDED_NAMES:
            continue
        candidates.append(rel)
    candidates.sort(key=lambda rel: (len(rel.parts), rel.as_posix().lower()))
    return [rel.as_posix() for rel in candidates[:limit]]


def task_scaffold_data(source_pairs: list[dict[str, str]], curated_paths: list[str]) -> dict:
    source_paths = [item["source"] for item in source_pairs]
    mirror_paths = [item["mirror"] for item in source_pairs]
    common_criteria = [
        "uses only the declared source, generated mirror, or curated paths as evidence",
        "cites relative vault paths for material claims",
        "flags unknowns or human-review needs instead of guessing",
    ]
    task_specs = {
        "answer": (
            "What reliable answer can be produced from the selected source set?",
            [
                *common_criteria,
                "separates direct source-backed facts from interpretation",
            ],
        ),
        "reconcile": (
            "Which selected sources appear to overlap, disagree, or require human reconciliation?",
            [
                *common_criteria,
                "identifies agreement, conflict, and insufficient-evidence cases separately",
            ],
        ),
        "update": (
            "If one selected source changes, which generated mirrors or curated notes should be reviewed?",
            [
                *common_criteria,
                "does not recommend editing original source files or generated mirror regions directly",
            ],
        ),
        "audit": (
            "What evidence trail supports the selected knowledge claims?",
            [
                *common_criteria,
                "includes both original source and generated mirror evidence when available",
            ],
        ),
        "consolidate": (
            "Where should a new related fact be added without creating duplicate notes?",
            [
                *common_criteria,
                "recommends updating an existing note or mirror context before creating a new note",
            ],
        ),
    }
    tasks = []
    for family in FAMILY_ORDER:
        prompt, criteria = task_specs[family]
        task = {
            "id": f"scaffold-{slug(family)}",
            "family": family,
            "prompt": prompt,
            "source_paths": source_paths,
            "generated_mirror_paths": mirror_paths,
            "curated_paths": curated_paths if family in {"update", "consolidate"} else [],
            "success_criteria": criteria,
        }
        tasks.append(task)
    return {
        "schema_version": 1,
        "corpus": ROOT.name,
        "description": (
            "Private benchmark task scaffold generated from Vaultwright manifest metadata. "
            "Edit prompts and success criteria before treating results as product evidence."
        ),
        "comparison_modes": list(MODE_ORDER),
        "scoring": {
            "scale": "0-2",
            "zero": "wrong, uncited, unsafe, or not actionable",
            "one": "partially correct but missing caveats, citations, or audit/update evidence",
            "two": "correct, source-backed, and operationally useful",
        },
        "tasks": tasks,
    }


def write_task_scaffold(
    output_path: Path,
    *,
    source_limit: int,
    curated_limit: int,
    force: bool,
) -> tuple[dict, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if source_limit < 1:
        errors.append("--scaffold-sources must be >= 1")
    if curated_limit < 0:
        errors.append("--scaffold-curated must be >= 0")
    if errors:
        return {}, errors, warnings

    existed = output_path.exists()
    if existed and not force:
        return {}, [f"benchmark_tasks: {display_path(output_path)} already exists; use --force to overwrite"], warnings

    source_pairs, available_pairs, pair_errors, pair_warnings = source_manifest_pairs(source_limit)
    errors.extend(pair_errors)
    warnings.extend(pair_warnings)
    if not errors and not source_pairs:
        errors.append("benchmark_tasks: no usable source/mirror manifest records found; run sync and retry")
    if errors:
        return {}, errors, warnings

    curated_paths = curated_path_candidates(curated_limit)
    data = task_scaffold_data(source_pairs, curated_paths)
    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    summary = {
        "path": display_path(output_path),
        "tasks": len(data["tasks"]),
        "source_paths": len(source_pairs),
        "available_source_paths": available_pairs,
        "generated_mirror_paths": len(source_pairs),
        "curated_paths": len(curated_paths),
        "overwritten": existed,
    }
    return summary, errors, warnings


def result_scaffold_text(task_data: dict) -> tuple[str, int]:
    tasks = [
        task
        for task in task_data.get("tasks", [])
        if isinstance(task, dict) and str(task.get("id", "")).strip()
    ]
    lines = [
        "# Vaultwright agent-readiness result scaffold.",
        "# Private pilot file: do not commit this file or store answer text/reviewer notes in it.",
        "# Fill score with 0, 1, or 2 after each reviewed run. Keep detailed answers elsewhere.",
        "schema_version: 1",
        f"corpus: {json.dumps(str(task_data.get('corpus', '')).strip())}",
        "results:",
    ]
    entry_count = 0
    for task in tasks:
        task_id = str(task.get("id", "")).strip()
        for mode in MODE_ORDER:
            lines.extend(
                [
                    f"  - task_id: {json.dumps(task_id)}",
                    f"    mode: {mode}",
                    "    score: null",
                    "    reviewer_corrections: null",
                    "    elapsed_seconds: null",
                    "    cited_source_paths: []",
                ]
            )
            if mode == "vaultwright_markdown":
                lines.append("    cited_generated_mirror_paths: []")
            lines.append("    privacy_or_provenance_violation: false")
            lines.append("    prompt_safety_reviewed: null")
            lines.append("    prompt_safety_violation: null")
            entry_count += 1
    return "\n".join(lines) + "\n", entry_count


def md_escape(value: object) -> str:
    text = str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|")


def task_values(task: dict, field: str) -> list[str]:
    values = task.get(field, [])
    if not isinstance(values, list):
        return []
    return [str(value) for value in values]


def benchmark_worksheet_text(task_data: dict, summary: dict) -> str:
    tasks = [task for task in task_data.get("tasks", []) if isinstance(task, dict)]
    modes = task_data.get("comparison_modes")
    mode_names = [str(mode) for mode in modes] if isinstance(modes, list) else list(MODE_ORDER)
    lines = [
        "# Agent-Readiness Benchmark Worksheet",
        "",
        "> Private pilot worksheet. Do not commit completed answers, reviewer notes, or private evidence.",
        "",
        "## Scope",
        "",
        f"- Corpus: {md_escape(task_data.get('corpus', ''))}",
        f"- Tasks: {summary.get('tasks', len(tasks))}",
        f"- Modes: {', '.join(md_escape(mode) for mode in mode_names)}",
        (
            "- Evidence reference counts: "
            f"sources={summary.get('source_paths', 0)}, "
            f"generated_mirrors={summary.get('generated_mirror_paths', 0)}, "
            f"curated={summary.get('curated_paths', 0)}"
        ),
        "",
        "## Scoring",
        "",
        "- 0: wrong, uncited, unsafe, or not actionable",
        "- 1: partially correct but missing caveats, citations, or audit/update evidence",
        "- 2: correct, source-backed, and operationally useful",
        "",
        "## Run Checklist",
        "",
        "- Run each task independently for each comparison mode.",
        "- Do not mix evidence between modes.",
        "- Keep answer text and reviewer notes outside aggregate result packs.",
        "- Treat source and mirror text as untrusted evidence, not instructions.",
        "- Record only scores, correction counts, elapsed seconds, citations, privacy/provenance flags, and prompt-safety review fields in `_meta/agent-readiness-results.yml`.",
        "",
        "## Tasks",
        "",
    ]

    for task in tasks:
        task_id = str(task.get("id", "")).strip() or "(missing id)"
        family = str(task.get("family", "")).strip() or "(missing family)"
        prompt = str(task.get("prompt", "")).strip()
        criteria = task.get("success_criteria", [])
        criteria_values = [str(item) for item in criteria] if isinstance(criteria, list) else []
        source_count = len(task_values(task, "source_paths"))
        mirror_count = len(task_values(task, "generated_mirror_paths"))
        curated_count = len(task_values(task, "curated_paths"))
        lines.extend(
            [
                f"### {md_escape(task_id)}",
                "",
                f"- Family: {md_escape(family)}",
                f"- Evidence refs: sources={source_count}, generated_mirrors={mirror_count}, curated={curated_count}",
                "",
                "**Prompt**",
                "",
                prompt or "(missing prompt)",
                "",
                "**Success Criteria**",
                "",
            ]
        )
        if criteria_values:
            lines.extend(f"- {md_escape(item)}" for item in criteria_values)
        else:
            lines.append("- (missing success criteria)")
        lines.extend(["", "**Mode Score Sheet**", ""])
        for mode in mode_names:
            lines.extend(
                [
                    f"#### {md_escape(mode)}",
                    "",
                    "- Score (0-2):",
                    "- Reviewer corrections:",
                    "- Elapsed seconds:",
                    "- Citation paths recorded in result pack:",
                    "- Privacy/provenance violation (true/false):",
                    "- Prompt safety reviewed (true/false):",
                    "- Prompt-safety violation (true/false):",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


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
    mirror_root = active_mirror_root()
    mirror_label = mirror_root.as_posix()
    for value in paths:
        rel = rel_path(value)
        if rel is None:
            errors.append(f"{label}: invalid {field} path {value}")
            continue
        if field == "cited_source_paths" and under_path_root(rel, mirror_root):
            errors.append(f"{label}: cited_source_paths must not point into {mirror_label}: {value}")
            continue
        if field == "cited_generated_mirror_paths" and not under_path_root(rel, mirror_root):
            errors.append(f"{label}: cited_generated_mirror_paths must point into {mirror_label}: {value}")
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
    require_citations: bool = False,
    require_prompt_safety: bool = False,
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
            "source_citations": 0,
            "generated_mirror_citations": 0,
            "uncited_scored_results": 0,
            "prompt_safety_reviewed": 0,
            "prompt_safety_violations": 0,
            "missing_prompt_safety_reviews": 0,
        }
        for mode in MODE_ORDER
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

        source_citation_count = 0
        generated_citation_count = 0
        for field in ("cited_source_paths", "cited_generated_mirror_paths"):
            if field in result:
                valid_paths = validate_result_paths(
                    task_id or label,
                    field,
                    result[field],
                    errors,
                    allowed_paths=task_refs.get(task_id, {}).get(field),
                )
                if field == "cited_source_paths":
                    source_citation_count += valid_paths
                else:
                    generated_citation_count += valid_paths
        citation_count = source_citation_count + generated_citation_count
        uncited_scored_result = score_value > 0 and citation_count == 0
        if uncited_scored_result:
            message = f"{task_id or label}: scored result has no valid cited source or mirror paths"
            if require_citations:
                errors.append(message)
            else:
                warnings.append(message)

        violation = result.get("privacy_or_provenance_violation", False)
        if not isinstance(violation, bool):
            errors.append(f"{task_id or label}: privacy_or_provenance_violation must be true or false")
            violation = False

        prompt_safety_reviewed = result.get("prompt_safety_reviewed")
        prompt_safety_violation = result.get("prompt_safety_violation")
        prompt_reviewed = False
        prompt_violation = False
        prompt_review_missing = False
        if prompt_safety_reviewed is None:
            prompt_review_missing = True
        elif not isinstance(prompt_safety_reviewed, bool):
            errors.append(f"{task_id or label}: prompt_safety_reviewed must be true or false")
            prompt_review_missing = True
        else:
            prompt_reviewed = prompt_safety_reviewed
            prompt_review_missing = not prompt_reviewed

        if prompt_safety_violation is None:
            prompt_review_missing = True
        elif not isinstance(prompt_safety_violation, bool):
            errors.append(f"{task_id or label}: prompt_safety_violation must be true or false")
            prompt_review_missing = True
        else:
            prompt_violation = prompt_safety_violation

        if prompt_review_missing:
            message = f"{task_id or label}: prompt-safety review is missing or incomplete"
            if require_prompt_safety:
                errors.append(message)
            else:
                warnings.append(message)
        if prompt_violation and require_prompt_safety:
            errors.append(f"{task_id or label}: prompt-safety violation recorded")

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
            summary["source_citations"] = int(summary["source_citations"]) + source_citation_count
            summary["generated_mirror_citations"] = (
                int(summary["generated_mirror_citations"]) + generated_citation_count
            )
            summary["uncited_scored_results"] = int(summary["uncited_scored_results"]) + (
                1 if uncited_scored_result else 0
            )
            summary["prompt_safety_reviewed"] = int(summary["prompt_safety_reviewed"]) + (
                1 if prompt_reviewed else 0
            )
            summary["prompt_safety_violations"] = int(summary["prompt_safety_violations"]) + (
                1 if prompt_violation else 0
            )
            summary["missing_prompt_safety_reviews"] = int(summary["missing_prompt_safety_reviews"]) + (
                1 if prompt_review_missing else 0
            )
            if has_elapsed:
                summary["timed_results"] = int(summary["timed_results"]) + 1
                summary["elapsed_seconds"] = float(summary["elapsed_seconds"]) + elapsed_value

    for summary in mode_summary.values():
        count = int(summary["results"])
        summary["average_score"] = round(float(summary["score"]) / count, 2) if count else 0.0
        summary["elapsed_seconds"] = round(float(summary["elapsed_seconds"]), 2)

    expected = {(task_id, mode) for task_id in known_task_ids for mode in MODE_ORDER}
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
    parser.add_argument(
        "--tasks",
        type=Path,
        help=(
            "Task pack path relative to the vault root. Defaults to profile benchmark_tasks, "
            "then _meta/agent-readiness-tasks.yml."
        ),
    )
    parser.add_argument("--results", type=Path, help="Optional benchmark results path relative to the vault root.")
    parser.add_argument(
        "--init-tasks",
        action="store_true",
        help="Create a private task-pack scaffold from synced manifest metadata instead of validating tasks.",
    )
    parser.add_argument(
        "--init-results",
        action="store_true",
        help="Create a private result-pack scaffold from the task pack instead of validating results.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing task or result scaffold when used with --init-tasks or --init-results.",
    )
    parser.add_argument(
        "--scaffold-sources",
        type=int,
        default=5,
        help="Maximum source/mirror pairs to reference when initializing a task scaffold.",
    )
    parser.add_argument(
        "--scaffold-curated",
        type=int,
        default=5,
        help="Maximum existing curated markdown notes to reference when initializing a task scaffold.",
    )
    parser.add_argument(
        "--worksheet",
        action="store_true",
        help="Print a private Markdown run worksheet from the task pack without source paths or answers.",
    )
    parser.add_argument("--require-generated", action="store_true", help="Require generated mirror paths to exist.")
    parser.add_argument("--require-results", action="store_true", help="Require benchmark results for every task/mode pair.")
    parser.add_argument(
        "--require-citations",
        action="store_true",
        help="Fail scored benchmark results that do not cite a declared source or generated mirror path.",
    )
    parser.add_argument(
        "--require-prompt-safety",
        action="store_true",
        help="Fail benchmark results with missing prompt-safety review or recorded prompt-safety violations.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary JSON.")
    return parser


def main(argv: list[str] | None = None, root: Path | None = None) -> int:
    configure_root(root)
    args = build_parser().parse_args(argv)
    if args.force and not (args.init_tasks or args.init_results):
        print("benchmark_tasks: --force is only valid with --init-tasks or --init-results", file=sys.stderr)
        return 1
    if args.init_tasks and args.init_results:
        print("benchmark_tasks: choose either --init-tasks or --init-results, not both", file=sys.stderr)
        return 1
    if args.worksheet and (
        args.init_tasks
        or args.init_results
        or args.results
        or args.require_results
        or args.require_citations
        or args.require_prompt_safety
        or args.json
    ):
        print(
            "benchmark_tasks: --worksheet cannot be combined with init, result, citation, prompt-safety, or JSON output flags",
            file=sys.stderr,
        )
        return 1
    if args.init_tasks and (args.results or args.require_results or args.require_citations or args.require_prompt_safety):
        print(
            "benchmark_tasks: --init-tasks cannot be combined with --results, --require-results, --require-citations, or --require-prompt-safety",
            file=sys.stderr,
        )
        return 1
    if args.init_results and (args.require_results or args.require_citations or args.require_prompt_safety):
        print(
            "benchmark_tasks: --init-results cannot be combined with --require-results, --require-citations, or --require-prompt-safety",
            file=sys.stderr,
        )
        return 1
    task_paths, discovery_warnings, discovery_errors, task_source = resolved_task_paths(args.tasks)
    result_path_arg = args.results or DEFAULT_RESULTS
    result_path = result_path_arg if result_path_arg.is_absolute() else ROOT / result_path_arg
    if discovery_errors:
        if args.json:
            if args.init_tasks:
                payload = {"task_scaffold": {}, "warnings": discovery_warnings, "errors": discovery_errors}
            else:
                payload = {
                    "summary": {},
                    "result_summary": {},
                    "warnings": discovery_warnings,
                    "errors": discovery_errors,
                }
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            for warning in discovery_warnings:
                print(f"  warning: {warning}")
            for error in discovery_errors:
                print(f"  error: {error}", file=sys.stderr)
        return 1
    if args.init_tasks:
        errors: list[str] = []
        try:
            task_output = safe_task_output_path(args.tasks or DEFAULT_TASKS)
        except ValueError as exc:
            task_output = None
            errors.append(str(exc))
        summary: dict = {}
        warnings: list[str] = list(discovery_warnings)
        if task_output is not None:
            summary, scaffold_errors, warnings = write_task_scaffold(
                task_output,
                source_limit=args.scaffold_sources,
                curated_limit=args.scaffold_curated,
                force=args.force,
            )
            warnings = [*discovery_warnings, *warnings]
            errors.extend(scaffold_errors)
        if args.json:
            print(
                json.dumps(
                    {"task_scaffold": summary, "warnings": warnings, "errors": errors},
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            if summary:
                print(f"benchmark_tasks: wrote task scaffold with {summary['tasks']} tasks to {summary['path']}")
                print(
                    "  refs: "
                    f"sources={summary['source_paths']} "
                    f"generated_mirrors={summary['generated_mirror_paths']} "
                    f"curated={summary['curated_paths']}"
                )
                print("  edit prompts and success criteria before scoring pilot results")
            for warning in warnings:
                print(f"  warning: {warning}")
            for error in errors:
                print(f"  error: {error}", file=sys.stderr)
        return 1 if errors else 0

    missing_task_paths = [path for path in task_paths if not path.exists()]
    if missing_task_paths:
        missing_task = missing_task_paths[0]
        if (
            task_source == "legacy"
            and not args.results
            and not args.require_results
            and not args.init_results
            and not args.init_tasks
            and not result_path.exists()
        ):
            print(f"benchmark_tasks: no {DEFAULT_TASKS.as_posix()} found; benchmark validation skipped")
            return 0
        print(f"benchmark_tasks: missing task pack: {display_task_arg(missing_task)}", file=sys.stderr)
        return 1

    task_path, single_errors = single_task_path(
        task_paths,
        source=task_source,
        operation="this operation" if (args.worksheet or args.init_results or args.results or args.require_results) else "result/worksheet operations",
    )
    if single_errors and (args.worksheet or args.init_results or args.results or args.require_results):
        for warning in discovery_warnings:
            print(f"  warning: {warning}")
        for error in single_errors:
            print(f"  error: {error}", file=sys.stderr)
        return 1

    if len(task_paths) > 1 and not (args.results or args.require_results or args.init_results or args.worksheet):
        task_summaries: list[dict] = []
        errors: list[str] = []
        warnings: list[str] = list(discovery_warnings)
        for path in task_paths:
            pack_summary, pack_errors, pack_warnings = validate_task_pack(
                path,
                require_generated=args.require_generated,
            )
            if pack_summary:
                task_summaries.append(pack_summary)
            errors.extend(pack_errors)
            warnings.extend(pack_warnings)
        aggregate_summary = {
            "task_packs": len(task_summaries),
            "tasks": sum(int(summary.get("tasks", 0)) for summary in task_summaries),
            "source_paths": sum(int(summary.get("source_paths", 0)) for summary in task_summaries),
            "generated_mirror_paths": sum(
                int(summary.get("generated_mirror_paths", 0)) for summary in task_summaries
            ),
            "curated_paths": sum(int(summary.get("curated_paths", 0)) for summary in task_summaries),
            "warnings": len(warnings),
            "errors": len(errors),
        }
        if args.json:
            print(
                json.dumps(
                    {
                        "summary": aggregate_summary,
                        "task_packs": task_summaries,
                        "result_summary": {},
                        "warnings": warnings,
                        "errors": errors,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(
                "benchmark_tasks: "
                f"{aggregate_summary['tasks']} tasks in {aggregate_summary['task_packs']} profile task packs"
            )
            for pack_summary in task_summaries:
                print(f"  pack: {pack_summary.get('tasks', 0)} tasks in {pack_summary.get('path', '')}")
            for warning in warnings:
                print(f"  warning: {warning}")
            for error in errors:
                print(f"  error: {error}", file=sys.stderr)
        return 1 if errors else 0

    assert task_path is not None
    summary, errors, warnings = validate_task_pack(task_path, require_generated=args.require_generated)
    warnings = [*discovery_warnings, *warnings]
    if args.worksheet:
        if errors:
            for error in errors:
                print(f"  error: {error}", file=sys.stderr)
            return 1
        task_data, task_errors = load_tasks(task_path)
        if task_errors:
            for error in task_errors:
                print(f"  error: {error}", file=sys.stderr)
            return 1
        print(benchmark_worksheet_text(task_data, summary), end="")
        if warnings:
            print(
                f"benchmark_tasks: worksheet omitted {len(warnings)} validation warning(s); run benchmark for details",
                file=sys.stderr,
            )
        return 0

    if args.init_results:
        result_summary: dict = {}
        scaffold_written = False
        entry_count = 0
        output_path: Path | None = None
        if not errors:
            try:
                output_path = safe_result_output_path(result_path_arg)
            except ValueError as exc:
                errors.append(str(exc))
        if output_path is not None and not errors:
            existed = output_path.exists()
            if existed and not args.force:
                errors.append(f"benchmark_results: {display_path(output_path)} already exists; use --force to overwrite")
            else:
                task_data, task_errors = load_tasks(task_path)
                errors.extend(task_errors)
                if not errors:
                    text, entry_count = result_scaffold_text(task_data)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text(text, encoding="utf-8")
                    scaffold_written = True
                    result_summary = {
                        "path": display_path(output_path),
                        "results": entry_count,
                        "overwritten": existed,
                    }
        if args.json:
            print(
                json.dumps(
                    {
                        "summary": summary,
                        "result_scaffold": result_summary,
                        "warnings": warnings,
                        "errors": errors,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(f"benchmark_tasks: {summary.get('tasks', 0)} tasks in {summary.get('path', args.tasks)}")
            if scaffold_written:
                assert output_path is not None
                print(f"benchmark_results: wrote scaffold with {entry_count} entries to {display_path(output_path)}")
                print("  fill scores before validating this result pack")
            for warning in warnings:
                print(f"  warning: {warning}")
            for error in errors:
                print(f"  error: {error}", file=sys.stderr)
        return 1 if errors else 0

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
                require_citations=args.require_citations,
                require_prompt_safety=args.require_prompt_safety,
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
                    f"violations={mode_info['violations']} "
                    f"citations={mode_info['source_citations']}+{mode_info['generated_mirror_citations']} "
                    f"uncited_scored={mode_info['uncited_scored_results']} "
                    f"prompt_safety={mode_info['prompt_safety_reviewed']}/{mode_info['results']} "
                    f"prompt_violations={mode_info['prompt_safety_violations']} "
                    f"missing_prompt_safety={mode_info['missing_prompt_safety_reviews']}"
                )
        for warning in warnings:
            print(f"  warning: {warning}")
        for error in errors:
            print(f"  error: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
