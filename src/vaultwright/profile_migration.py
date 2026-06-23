# SPDX-License-Identifier: AGPL-3.0-or-later
"""Read-only profile diff and migration planning."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from vaultwright.profiles import ProfileContract


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
    "_mirrors",
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


def target_dir_paths(target: ProfileContract) -> list[Path]:
    rels = {Path(rel) for rel in SHARED_TEMPLATE_DIRS}
    for definition in target.domains.values():
        if isinstance(definition, dict) and definition.get("folder"):
            rels.add(Path(str(definition["folder"])))
    return sorted(rels, key=lambda path: path.as_posix())


def profile_migration_plan(
    root: Path,
    template_root: Path,
    current: ProfileContract,
    target: ProfileContract,
    target_profile_path: Path,
) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []

    if current.id != target.id:
        blockers.append(
            {
                "code": "profile-id-mismatch",
                "detail": f"current profile {current.id} cannot migrate to target profile {target.id}",
            }
        )

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
        "profile_id": current.id,
        "current_version": current.profile_version,
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
