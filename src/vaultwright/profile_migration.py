# SPDX-License-Identifier: AGPL-3.0-or-later
"""Read-only profile diff and migration planning."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from vaultwright.profiles import ProfileContract, profile_folder_paths
from vaultwright.runtime_profile import LEGACY_MIRROR_ROOT


SHARED_TEMPLATE_FILES = (
    ".gitignore",
    "AGENTS.md",
    "CLAUDE.md",
    "Documents.base",
    "INDEX.md",
    "RETENTION.md",
    "_meta/conventions.md",
    "_meta/domain-map.yml",
    "_meta/lifecycle-states.yml",
    "_meta/lint-config.yml",
    "_meta/mirror-config.yml",
    "_meta/profile.yml",
    "log.md",
    "tools/requirements.txt",
)
SHARED_TEMPLATE_DIRS = (
    "_archive",
    "_meta",
    "_templates",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def string_set(values: Any) -> set[str]:
    if isinstance(values, dict):
        return {str(key) for key in values}
    if isinstance(values, list):
        return {str(value) for value in values}
    return set()


def path_set(values: list[Path]) -> set[str]:
    return {value.as_posix() for value in values}


def profile_differences(current: ProfileContract, target: ProfileContract) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    if current.schema_version != target.schema_version:
        differences.append(
            {
                "field": "schema_version",
                "kind": "changed",
                "current": current.schema_version,
                "target": target.schema_version,
            }
        )
    if current.id != target.id:
        differences.append({"field": "id", "kind": "changed", "current": current.id, "target": target.id})
    if current.profile_version != target.profile_version:
        differences.append(
            {
                "field": "profile_version",
                "kind": "changed",
                "current": current.profile_version,
                "target": target.profile_version,
            }
        )

    for field in (
        "domains",
        "note_types",
        "statuses",
        "required_properties",
        "optional_properties",
        "templates",
        "views",
        "skills",
        "benchmark_tasks",
    ):
        current_values = string_set(getattr(current, field))
        target_values = string_set(getattr(target, field))
        missing = sorted(target_values - current_values)
        extra = sorted(current_values - target_values)
        if missing:
            differences.append({"field": field, "kind": "missing", "items": missing})
        if extra:
            differences.append({"field": field, "kind": "extra", "items": extra})

    current_folder_plan = path_set(profile_folder_paths(current))
    target_folder_plan = path_set(profile_folder_paths(target))
    missing_folder_plan = sorted(target_folder_plan - current_folder_plan)
    extra_folder_plan = sorted(current_folder_plan - target_folder_plan)
    if missing_folder_plan:
        differences.append({"field": "folder_plan", "kind": "missing", "items": missing_folder_plan})
    if extra_folder_plan:
        differences.append({"field": "folder_plan", "kind": "extra", "items": extra_folder_plan})

    for domain, target_definition in target.domains.items():
        current_definition = current.domains.get(domain)
        if not isinstance(current_definition, dict) or not isinstance(target_definition, dict):
            continue
        current_folder = str(current_definition.get("folder", ""))
        target_folder = str(target_definition.get("folder", ""))
        if current_folder != target_folder:
            differences.append(
                {
                    "field": f"domains.{domain}.folder",
                    "kind": "changed",
                    "current": current_folder,
                    "target": target_folder,
                }
            )
    return differences


def target_file_paths(target: ProfileContract) -> list[Path]:
    rels = {Path(rel) for rel in SHARED_TEMPLATE_FILES}
    rels.update(Path(rel) for rel in target.templates)
    rels.update(Path(rel) for rel in target.views)
    return sorted(rels, key=lambda path: path.as_posix())


def target_mirror_root_path(target: ProfileContract) -> Path:
    value = target.policy_defaults.get("mirror_root")
    if isinstance(value, str) and value.strip():
        return Path(value.strip())
    return Path(LEGACY_MIRROR_ROOT)


def target_dir_paths(target: ProfileContract) -> list[Path]:
    rels = {Path(rel) for rel in SHARED_TEMPLATE_DIRS}
    rels.add(target_mirror_root_path(target))
    rels.update(profile_folder_paths(target))
    return sorted(rels, key=lambda path: path.as_posix())


def profile_migration_plan(
    root: Path,
    template_root: Path,
    current: ProfileContract | None,
    target: ProfileContract,
    target_profile_path: Path,
) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []

    if current is None:
        actions.append(
            {
                "action": "copy-template-file",
                "path": "_meta/profile.yml",
                "target_sha256": sha256_file(target_profile_path),
                "reason": "vault has no profile contract yet",
            }
        )
        differences = [
            {
                "field": "_meta/profile.yml",
                "kind": "missing",
                "target": target.profile_version,
            }
        ]
    elif current.id != target.id:
        blockers.append(
            {
                "code": "profile-id-mismatch",
                "detail": f"current profile {current.id} cannot migrate to target profile {target.id}",
            }
        )
        differences = profile_differences(current, target)
    else:
        differences = profile_differences(current, target)
        for difference in differences:
            actions.append(
                {
                    "action": "review-profile-contract",
                    "path": "_meta/profile.yml",
                    "reason": difference,
                }
            )

    if not blockers:
        for rel in target_dir_paths(target):
            if not (root / rel).exists():
                actions.append(
                    {
                        "action": "create-directory",
                        "path": rel.as_posix(),
                        "reason": "target profile expects this directory",
                    }
                )

        planned_copies = {
            str(action.get("path", ""))
            for action in actions
            if action.get("action") == "copy-template-file"
        }
        for rel in target_file_paths(target):
            source = template_root / rel
            destination = root / rel
            if not source.exists():
                blockers.append(
                    {
                        "code": "target-file-missing",
                        "detail": f"packaged target profile file is missing: {rel.as_posix()}",
                    }
                )
                continue
            target_sha = sha256_file(source)
            if not destination.exists():
                if rel.as_posix() not in planned_copies:
                    actions.append(
                        {
                            "action": "copy-template-file",
                            "path": rel.as_posix(),
                            "target_sha256": target_sha,
                            "reason": "target profile expects this file",
                        }
                    )
                continue
            current_sha = sha256_file(destination)
            if current_sha != target_sha:
                actions.append(
                    {
                        "action": "review-template-drift",
                        "path": rel.as_posix(),
                        "current_sha256": current_sha,
                        "target_sha256": target_sha,
                        "reason": "existing file differs from the target profile template",
                    }
                )

    return {
        "profile_id": current.id if current else target.id,
        "current_version": current.profile_version if current else None,
        "target_version": target.profile_version,
        "target_profile_path": str(target_profile_path),
        "differences": differences,
        "actions": actions,
        "blockers": blockers,
        "summary": {
            "actions": len(actions),
            "blockers": len(blockers),
            "up_to_date": not actions and not blockers,
        },
    }


def checked_rel_path(rel: str) -> Path:
    if not rel.strip():
        raise ValueError("unsafe migration path: empty")
    path = Path(rel)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe migration path: {rel}")
    return path


def write_profile_migration(root: Path, template_root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    written: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    if plan.get("blockers"):
        for blocker in plan["blockers"]:
            errors.append(
                {
                    "path": "",
                    "action": "blocked",
                    "detail": str(blocker.get("detail", blocker.get("code", "migration blocker"))),
                }
            )
        return {
            "written": written,
            "skipped": skipped,
            "errors": errors,
            "summary": {"written": 0, "skipped": 0, "errors": len(errors)},
        }

    for action in plan.get("actions", []):
        action_type = str(action.get("action", ""))
        path_text = str(action.get("path", ""))
        try:
            rel = checked_rel_path(path_text)
        except ValueError as exc:
            errors.append({"action": action_type, "path": path_text, "detail": str(exc)})
            continue

        destination = root / rel
        if action_type == "create-directory":
            if destination.exists():
                if destination.is_dir():
                    skipped.append(
                        {
                            "action": action_type,
                            "path": rel.as_posix(),
                            "detail": "directory already exists",
                        }
                    )
                else:
                    errors.append(
                        {
                            "action": action_type,
                            "path": rel.as_posix(),
                            "detail": "path exists and is not a directory",
                        }
                    )
                continue
            destination.mkdir(parents=True, exist_ok=True)
            written.append({"action": action_type, "path": rel.as_posix(), "detail": "directory created"})
            continue

        if action_type == "copy-template-file":
            source = template_root / rel
            if not source.exists() or not source.is_file():
                errors.append(
                    {
                        "action": action_type,
                        "path": rel.as_posix(),
                        "detail": "packaged target file is missing",
                    }
                )
                continue
            expected_sha = str(action.get("target_sha256", ""))
            actual_sha = sha256_file(source)
            if expected_sha and actual_sha != expected_sha:
                errors.append(
                    {
                        "action": action_type,
                        "path": rel.as_posix(),
                        "detail": "packaged target file changed since planning",
                    }
                )
                continue
            if destination.exists():
                skipped.append(
                    {
                        "action": action_type,
                        "path": rel.as_posix(),
                        "detail": "destination exists; not overwritten",
                    }
                )
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            written.append({"action": action_type, "path": rel.as_posix(), "detail": "file copied"})
            continue

        if action_type in {"review-profile-contract", "review-template-drift"}:
            skipped.append(
                {
                    "action": action_type,
                    "path": rel.as_posix(),
                    "detail": "manual review required; existing files are not overwritten",
                }
            )
            continue

        errors.append({"action": action_type, "path": rel.as_posix(), "detail": "unknown action"})

    return {
        "written": written,
        "skipped": skipped,
        "errors": errors,
        "summary": {
            "written": len(written),
            "skipped": len(skipped),
            "errors": len(errors),
        },
    }
