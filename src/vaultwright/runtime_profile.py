# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tolerant helpers for runtime reads of the active vault profile."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from vaultwright.profiles import ProfileValidationError, load_profile


PROFILE_REL = Path("_meta/profile.yml")
REPO_CONFIG_REL = Path("tools/repos.yml")
MIRROR_CONFIG_REL = Path("_meta/mirror-config.yml")
LEGACY_REPO_NOTES_DIR = "80_sources/repos"
LEGACY_CONTEXT_KEYS = {"account", "client", "program", "vendor"}
LEGACY_CONTEXT_ALIASES = {"client": "account"}
LEGACY_INACTIVE_STATUSES = {"archived", "superseded"}
LEGACY_MACHINE_OWNED_NOTE_TYPES = {"source-mirror", "repo-mirror"}
LEGACY_CONTENT_ROOTS = {
    "00_inbox",
    "10_governance",
    "20_market",
    "30_customers",
    "40_delivery",
    "50_operations",
    "60_finance",
    "70_people",
    "80_sources",
}
LEGACY_MIRROR_MODE = "dedicated"
LEGACY_MIRROR_ROOT = "_mirrors"
LEGACY_MIRROR_STATUS = "active"
LEGACY_REPO_STUB_STATUS = "draft"
FORBIDDEN_MIRROR_ROOT_PARTS = {
    ".git",
    ".githooks",
    ".github",
    ".obsidian",
    "_archive",
    "_fixtures",
    "_meta",
    "_templates",
    "_tmp",
    "node_modules",
    "tools",
}
NON_CONTEXT_PROPERTIES = {
    "title",
    "type",
    "status",
    "domain",
    "created",
    "updated",
    "owner",
    "tags",
    "related",
}


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


def _safe_mirror_root_path(value: object) -> Path | None:
    path = _safe_relative_path(value)
    if path is None:
        return None
    if any(part.startswith(".") or part in FORBIDDEN_MIRROR_ROOT_PARTS for part in path.parts):
        return None
    return path


def load_profile_mapping(root: Path) -> dict[str, Any]:
    path = root / PROFILE_REL
    if not path.exists():
        return {}
    try:
        return load_profile(path).as_dict()
    except ProfileValidationError:
        return {}


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


def profile_content_roots(root: Path) -> set[str]:
    folders = set(profile_domain_folders(root).values())
    return folders or set(LEGACY_CONTENT_ROOTS)


def profile_policy_defaults(root: Path) -> dict[str, Any]:
    defaults = load_profile_mapping(root).get("policy_defaults", {})
    return dict(defaults) if isinstance(defaults, dict) else {}


def profile_optional_properties(root: Path) -> list[str]:
    profile = load_profile_mapping(root)
    raw_properties = profile.get("optional_properties")
    if not isinstance(raw_properties, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for value in raw_properties:
        if not isinstance(value, str):
            continue
        name = value.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def profile_context_keys(root: Path) -> set[str]:
    profile = load_profile_mapping(root)
    if not profile:
        return set(LEGACY_CONTEXT_KEYS)
    return {
        key
        for key in profile_optional_properties(root)
        if key not in NON_CONTEXT_PROPERTIES
    }


def profile_context_aliases(root: Path) -> dict[str, str]:
    profile = load_profile_mapping(root)
    context_keys = profile_context_keys(root)
    if not profile:
        return dict(LEGACY_CONTEXT_ALIASES)

    raw_aliases = profile_policy_defaults(root).get("context_aliases")
    if isinstance(raw_aliases, dict):
        aliases: dict[str, str] = {}
        for alias, target in raw_aliases.items():
            if not isinstance(alias, str) or not isinstance(target, str):
                continue
            alias_key = alias.strip()
            target_key = target.strip()
            if (
                alias_key
                and target_key
                and alias_key != target_key
                and alias_key in context_keys
                and target_key in context_keys
            ):
                aliases[alias_key] = target_key
        return aliases

    return {}


def profile_frontmatter_link_keys(root: Path) -> set[str]:
    return {"related", *profile_context_keys(root)}


def _profile_statuses_with_flag(root: Path, flag: str, legacy: set[str]) -> set[str]:
    profile = load_profile_mapping(root)
    statuses = profile.get("statuses")
    if not isinstance(statuses, dict):
        return set(legacy)

    flagged: set[str] = set()
    saw_flag = False
    for status, definition in statuses.items():
        if not isinstance(definition, dict):
            continue
        if flag not in definition:
            continue
        saw_flag = True
        if definition.get(flag) is True:
            flagged.add(str(status))
    if saw_flag:
        return flagged
    return {str(status) for status in statuses if str(status) in legacy}


def profile_inactive_statuses(root: Path) -> set[str]:
    return _profile_statuses_with_flag(root, "inactive", LEGACY_INACTIVE_STATUSES)


def _profile_note_types_with_flag(root: Path, flag: str, legacy: set[str]) -> set[str]:
    profile = load_profile_mapping(root)
    note_types = profile.get("note_types")
    if not isinstance(note_types, dict):
        return set(legacy)

    flagged: set[str] = set()
    saw_flag = False
    for note_type, definition in note_types.items():
        if not isinstance(definition, dict):
            continue
        if flag not in definition:
            continue
        saw_flag = True
        if definition.get(flag) is True:
            flagged.add(str(note_type))
    if saw_flag:
        return flagged
    return {str(note_type) for note_type in note_types if str(note_type) in legacy}


def profile_machine_owned_note_types(root: Path) -> set[str]:
    return _profile_note_types_with_flag(root, "machine_owned", LEGACY_MACHINE_OWNED_NOTE_TYPES)


def _profile_status_default(root: Path, key: str, legacy: str) -> str:
    value = profile_policy_defaults(root).get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return legacy


def profile_mirror_status(root: Path) -> str:
    return _profile_status_default(root, "mirror_status", LEGACY_MIRROR_STATUS)


def profile_repo_stub_status(root: Path) -> str:
    return _profile_status_default(root, "repo_stub_status", LEGACY_REPO_STUB_STATUS)


def profile_generated_mirror_statuses(root: Path) -> set[str]:
    return {profile_mirror_status(root), profile_repo_stub_status(root)}


def profile_mirror_mode(root: Path) -> str:
    value = profile_policy_defaults(root).get("mirror_mode")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return LEGACY_MIRROR_MODE


def profile_mirror_root(root: Path) -> str:
    value = profile_policy_defaults(root).get("mirror_root")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return LEGACY_MIRROR_ROOT


def configured_office_mirror_root(root: Path) -> Path:
    profile_root = _safe_mirror_root_path(profile_mirror_root(root)) or Path(LEGACY_MIRROR_ROOT)
    path = root / MIRROR_CONFIG_REL
    if not path.exists():
        return profile_root
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return profile_root
    if not isinstance(data, dict):
        return profile_root
    office = data.get("office_mirrors", data)
    if not isinstance(office, dict) or "root" not in office:
        return profile_root
    return _safe_mirror_root_path(office.get("root")) or profile_root


def is_office_mirror_path(root: Path, rel: Path) -> bool:
    mirror_root = configured_office_mirror_root(root)
    return bool(mirror_root.parts) and rel.parts[: len(mirror_root.parts)] == mirror_root.parts


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
