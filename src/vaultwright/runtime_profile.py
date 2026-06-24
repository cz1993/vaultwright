# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tolerant helpers for runtime reads of the active vault profile."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROFILE_REL = Path("_meta/profile.yml")
REPO_CONFIG_REL = Path("tools/repos.yml")
LEGACY_REPO_NOTES_DIR = "80_sources/repos"


def _safe_relative_path(value: object) -> Path | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    path = Path(text)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return None
    return path


def load_profile_mapping(root: Path) -> dict[str, Any]:
    path = root / PROFILE_REL
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def profile_domain_folders(root: Path) -> dict[str, str]:
    domains = load_profile_mapping(root).get("domains", {})
    if not isinstance(domains, dict):
        return {}
    out: dict[str, str] = {}
    for domain, definition in domains.items():
        if not isinstance(definition, dict):
            continue
        folder = _safe_relative_path(definition.get("folder"))
        if folder:
            out[str(domain)] = folder.as_posix()
    return out


def profile_policy_defaults(root: Path) -> dict[str, Any]:
    defaults = load_profile_mapping(root).get("policy_defaults", {})
    return dict(defaults) if isinstance(defaults, dict) else {}


def profile_repo_notes_dir(root: Path) -> str:
    configured = _safe_relative_path(profile_policy_defaults(root).get("repo_notes_dir"))
    if configured:
        return configured.as_posix()
    source_folder = _safe_relative_path(profile_domain_folders(root).get("sources"))
    if source_folder:
        return source_folder.joinpath("repos").as_posix()
    return LEGACY_REPO_NOTES_DIR


def configured_repo_notes_dir(root: Path) -> str | None:
    path = root / REPO_CONFIG_REL
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        return None
    configured = _safe_relative_path(settings.get("notes_dir"))
    return configured.as_posix() if configured else None


def repo_notes_dirs(root: Path) -> list[str]:
    out: list[str] = []
    for value in (configured_repo_notes_dir(root), profile_repo_notes_dir(root)):
        if value and value not in out:
            out.append(value)
    return out


def rel_is_under(rel: Path, directory: Path) -> bool:
    return rel == directory or (
        len(rel.parts) > len(directory.parts)
        and rel.parts[: len(directory.parts)] == directory.parts
    )


def is_repo_notes_path(root: Path, rel: Path) -> bool:
    return any(rel_is_under(rel, Path(notes_dir)) for notes_dir in repo_notes_dirs(root))
