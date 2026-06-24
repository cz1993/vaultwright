# SPDX-License-Identifier: AGPL-3.0-or-later
"""Profile contract loading and validation."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


PROFILE_SCHEMA_VERSION = 1
PROFILE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PROFILE_KEY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
REQUIRED_FIELDS = {
    "schema_version",
    "id",
    "name",
    "profile_version",
    "domains",
    "note_types",
    "statuses",
    "required_properties",
    "optional_properties",
    "folder_plan",
    "templates",
    "views",
    "skills",
    "benchmark_tasks",
    "policy_defaults",
}
OPTIONAL_FIELDS = {"description"}
LIST_FIELDS = {
    "required_properties",
    "optional_properties",
    "folder_plan",
    "templates",
    "views",
    "skills",
    "benchmark_tasks",
}
MAPPING_FIELDS = {"domains", "note_types", "statuses", "policy_defaults"}
FORBIDDEN_PROFILE_PATH_PARTS = {".git", ".githooks", ".github", "node_modules"}
NOTE_TYPE_BOOLEAN_FIELDS = {"machine_owned"}
STATUS_BOOLEAN_FIELDS = {"attention", "inactive"}
POLICY_STATUS_DEFAULT_FIELDS = {"mirror_status", "repo_stub_status"}
POLICY_BOOLEAN_DEFAULT_FIELDS = {"original_sources_authoritative", "real_data_in_repo"}
POLICY_REQUIRED_TRUE_DEFAULT_FIELDS = {"original_sources_authoritative"}
POLICY_REQUIRED_FALSE_DEFAULT_FIELDS = {"real_data_in_repo"}
MIRROR_MODES = {"dedicated", "sibling"}
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
FORBIDDEN_REPO_NOTES_DIR_PARTS = {
    ".git",
    ".githooks",
    ".github",
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
FORBIDDEN_PROFILE_ARTIFACT_PATH_PARTS = {
    ".git",
    ".githooks",
    ".github",
    ".obsidian",
    "_archive",
    "_fixtures",
    "_meta",
    "_mirrors",
    "_tmp",
    "node_modules",
    "tools",
}


class ProfileValidationError(ValueError):
    """Raised when a profile contract is missing required structure."""


@dataclass(frozen=True)
class ProfileContract:
    schema_version: int
    id: str
    name: str
    profile_version: str
    domains: dict[str, Any]
    note_types: dict[str, Any]
    statuses: dict[str, Any]
    required_properties: list[Any]
    optional_properties: list[Any]
    folder_plan: list[Any]
    templates: list[Any]
    views: list[Any]
    skills: list[Any]
    benchmark_tasks: list[Any]
    policy_defaults: dict[str, Any]
    description: str = ""

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ProfileContract":
        validate_profile_mapping(data)
        return cls(
            schema_version=int(data["schema_version"]),
            id=str(data["id"]),
            name=str(data["name"]),
            profile_version=str(data["profile_version"]),
            domains=dict(data["domains"]),
            note_types=dict(data["note_types"]),
            statuses=dict(data["statuses"]),
            required_properties=list(data["required_properties"]),
            optional_properties=list(data["optional_properties"]),
            folder_plan=list(data["folder_plan"]),
            templates=list(data["templates"]),
            views=list(data["views"]),
            skills=list(data["skills"]),
            benchmark_tasks=list(data["benchmark_tasks"]),
            policy_defaults=dict(data["policy_defaults"]),
            description=str(data.get("description", "")),
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "profile_version": self.profile_version,
            "schema_version": self.schema_version,
            "domains": len(self.domains),
            "note_types": len(self.note_types),
            "statuses": len(self.statuses),
            "templates": len(self.templates),
            "views": len(self.views),
        }


def validate_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ProfileValidationError(f"{field} must be a non-empty string")


def validate_profile_key(value: Any, field: str) -> str:
    validate_string(value, field)
    text = str(value).strip()
    if not PROFILE_KEY_RE.fullmatch(text):
        raise ProfileValidationError(f"{field} must be lowercase kebab-case")
    return text


def validate_frontmatter_key(value: Any, field: str) -> str:
    validate_string(value, field)
    text = str(value).strip()
    if not FRONTMATTER_KEY_RE.fullmatch(text):
        raise ProfileValidationError(f"{field} must be a lowercase frontmatter key")
    return text


def validate_profile_path(value: Any, field: str) -> PurePosixPath:
    validate_string(value, field)
    text = str(value).strip()
    if "\\" in text:
        raise ProfileValidationError(f"{field} must use POSIX-style '/' separators")
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts or not path.parts or path.as_posix() == ".":
        raise ProfileValidationError(f"{field} must stay inside the vault")
    if any(part.startswith(".") or part in FORBIDDEN_PROFILE_PATH_PARTS for part in path.parts):
        raise ProfileValidationError(f"{field} contains a reserved path component")
    return path


def validate_mirror_root(value: Any, field: str) -> PurePosixPath:
    path = validate_profile_path(value, field)
    if any(part.startswith(".") or part in FORBIDDEN_MIRROR_ROOT_PARTS for part in path.parts):
        raise ProfileValidationError(f"{field} contains a reserved path component")
    return path


def validate_repo_notes_dir(
    value: Any,
    field: str,
    domain_folders: dict[str, PurePosixPath],
    mirror_root: PurePosixPath | None,
) -> PurePosixPath:
    path = validate_profile_path(value, field)
    if any(part.startswith(".") or part in FORBIDDEN_REPO_NOTES_DIR_PARTS for part in path.parts):
        raise ProfileValidationError(f"{field} contains a reserved path component")
    if not any(path_is_under(path, folder) for folder in domain_folders.values()):
        raise ProfileValidationError(f"{field} must be inside a declared domain folder")
    if mirror_root and (path_is_under(path, mirror_root) or path_is_under(mirror_root, path)):
        raise ProfileValidationError(f"{field} must not overlap policy_defaults.mirror_root")
    return path


def validate_profile_artifact_path(value: Any, field: str) -> PurePosixPath:
    path = validate_profile_path(value, field)
    if any(part.startswith(".") or part in FORBIDDEN_PROFILE_ARTIFACT_PATH_PARTS for part in path.parts):
        raise ProfileValidationError(f"{field} contains a reserved path component")
    return path


def validate_profile_artifact_list(values: list[Any], field: str) -> None:
    seen_paths: set[str] = set()
    for value in values:
        path = validate_profile_artifact_path(value, f"{field} entry")
        path_text = path.as_posix()
        if path_text in seen_paths:
            raise ProfileValidationError(f"{field} entries must not contain duplicates")
        seen_paths.add(path_text)


def path_is_under(path: PurePosixPath, directory: PurePosixPath) -> bool:
    return path == directory or (
        len(path.parts) > len(directory.parts)
        and path.parts[: len(directory.parts)] == directory.parts
    )


def validate_folder_plan(folder_plan: Any, domain_folders: dict[str, PurePosixPath]) -> None:
    if not folder_plan:
        raise ProfileValidationError("folder_plan must contain at least one starter folder")

    seen_paths: set[str] = set()
    for index, entry in enumerate(folder_plan):
        field = f"folder_plan[{index}]"
        if not isinstance(entry, dict):
            raise ProfileValidationError(f"{field} must be a mapping")
        path = validate_profile_path(entry.get("path"), f"{field}.path")
        domain = entry.get("domain")
        domain_name = validate_profile_key(domain, f"{field}.domain")
        if domain_name not in domain_folders:
            raise ProfileValidationError(f"{field}.domain must reference a declared domain")
        if not path_is_under(path, domain_folders[domain_name]):
            raise ProfileValidationError(f"{field}.path must be inside domains.{domain_name}.folder")
        path_text = path.as_posix()
        if path_text in seen_paths:
            raise ProfileValidationError(f"{field}.path duplicates another folder_plan path")
        seen_paths.add(path_text)


def validate_domain_folders(domain_folders: dict[str, PurePosixPath]) -> None:
    seen_folders: dict[str, str] = {}
    for domain_name, folder in domain_folders.items():
        folder_text = folder.as_posix()
        previous_domain = seen_folders.get(folder_text)
        if previous_domain:
            raise ProfileValidationError(
                f"domains.{domain_name}.folder duplicates domains.{previous_domain}.folder"
            )
        seen_folders[folder_text] = domain_name

    items = list(domain_folders.items())
    for index, (domain_name, folder) in enumerate(items):
        for other_domain, other_folder in items[index + 1 :]:
            if path_is_under(folder, other_folder) or path_is_under(other_folder, folder):
                raise ProfileValidationError(
                    f"domains.{domain_name}.folder must not overlap domains.{other_domain}.folder"
                )


def validate_profile_mapping(data: Any) -> None:
    if not isinstance(data, dict):
        raise ProfileValidationError("profile must be a mapping")

    unknown = sorted(set(data) - REQUIRED_FIELDS - OPTIONAL_FIELDS)
    if unknown:
        raise ProfileValidationError(f"unknown profile fields: {', '.join(unknown)}")

    missing = sorted(REQUIRED_FIELDS - set(data))
    if missing:
        raise ProfileValidationError(f"missing profile fields: {', '.join(missing)}")

    if data.get("schema_version") != PROFILE_SCHEMA_VERSION:
        raise ProfileValidationError(f"schema_version must be {PROFILE_SCHEMA_VERSION}")

    validate_string(data.get("id"), "id")
    if not PROFILE_ID_RE.fullmatch(str(data["id"])):
        raise ProfileValidationError("id must be lowercase kebab-case")

    validate_string(data.get("name"), "name")
    validate_string(data.get("profile_version"), "profile_version")

    for field in MAPPING_FIELDS:
        if not isinstance(data.get(field), dict):
            raise ProfileValidationError(f"{field} must be a mapping")

    for field in LIST_FIELDS:
        if not isinstance(data.get(field), list):
            raise ProfileValidationError(f"{field} must be a list")

    for field in ("required_properties", "optional_properties", "templates", "views", "skills", "benchmark_tasks"):
        for value in data[field]:
            if not isinstance(value, str):
                raise ProfileValidationError(f"{field} entries must be strings")
    for field in ("required_properties", "optional_properties"):
        seen_properties: set[str] = set()
        for value in data[field]:
            name = validate_frontmatter_key(value, f"{field} entries")
            if name in seen_properties:
                raise ProfileValidationError(f"{field} entries must not contain duplicates")
            seen_properties.add(name)
    for field in ("templates", "views", "skills"):
        validate_profile_artifact_list(data[field], field)
    for value in data["benchmark_tasks"]:
        path = validate_profile_path(value, "benchmark_tasks entry")
        if path.suffix not in {".yml", ".yaml"}:
            raise ProfileValidationError("benchmark_tasks entries must be .yml or .yaml files")

    domain_folders: dict[str, PurePosixPath] = {}
    for domain, definition in data["domains"].items():
        domain_name = validate_profile_key(domain, "domain key")
        if not isinstance(definition, dict):
            raise ProfileValidationError(f"domains.{domain} must be a mapping")
        domain_folders[domain_name] = validate_profile_path(
            definition.get("folder"),
            f"domains.{domain}.folder",
        )
    validate_domain_folders(domain_folders)

    for note_type, definition in data["note_types"].items():
        note_type_name = validate_profile_key(note_type, "note_types key")
        if not isinstance(definition, dict):
            raise ProfileValidationError(f"note_types.{note_type} must be a mapping")
        for field in NOTE_TYPE_BOOLEAN_FIELDS:
            if field in definition and not isinstance(definition[field], bool):
                raise ProfileValidationError(f"note_types.{note_type_name}.{field} must be true or false")

    for status, definition in data["statuses"].items():
        status_name = validate_profile_key(status, "status key")
        if not isinstance(definition, dict):
            raise ProfileValidationError(f"statuses.{status} must be a mapping")
        for field in STATUS_BOOLEAN_FIELDS:
            if field in definition and not isinstance(definition[field], bool):
                raise ProfileValidationError(f"statuses.{status_name}.{field} must be true or false")

    for field in POLICY_STATUS_DEFAULT_FIELDS:
        if field not in data["policy_defaults"]:
            continue
        value = data["policy_defaults"][field]
        validate_string(value, f"policy_defaults.{field}")
        if str(value).strip() not in data["statuses"]:
            raise ProfileValidationError(f"policy_defaults.{field} must reference a declared status")

    for field in POLICY_BOOLEAN_DEFAULT_FIELDS:
        if field not in data["policy_defaults"]:
            continue
        value = data["policy_defaults"][field]
        if not isinstance(value, bool):
            raise ProfileValidationError(f"policy_defaults.{field} must be true or false")
        if field in POLICY_REQUIRED_TRUE_DEFAULT_FIELDS and value is not True:
            raise ProfileValidationError(f"policy_defaults.{field} must be true")
        if field in POLICY_REQUIRED_FALSE_DEFAULT_FIELDS and value is not False:
            raise ProfileValidationError(f"policy_defaults.{field} must be false")

    if "mirror_mode" in data["policy_defaults"]:
        mirror_mode = data["policy_defaults"]["mirror_mode"]
        validate_string(mirror_mode, "policy_defaults.mirror_mode")
        if str(mirror_mode).strip() not in MIRROR_MODES:
            raise ProfileValidationError("policy_defaults.mirror_mode must be one of: dedicated, sibling")

    mirror_root: PurePosixPath | None = None
    if "mirror_root" in data["policy_defaults"]:
        mirror_root = validate_mirror_root(data["policy_defaults"]["mirror_root"], "policy_defaults.mirror_root")

    if "repo_notes_dir" in data["policy_defaults"]:
        validate_repo_notes_dir(
            data["policy_defaults"]["repo_notes_dir"],
            "policy_defaults.repo_notes_dir",
            domain_folders,
            mirror_root,
        )

    validate_folder_plan(data["folder_plan"], domain_folders)


def load_profile(path: Path) -> ProfileContract:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProfileValidationError(f"{path} is not valid YAML: {exc}") from exc
    except OSError as exc:
        raise ProfileValidationError(f"cannot read profile: {path}: {exc}") from exc
    return ProfileContract.from_mapping(raw)


def profile_folder_paths(profile: ProfileContract) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    for entry in profile.folder_plan:
        if not isinstance(entry, dict):
            continue
        value = entry.get("path")
        if not isinstance(value, str) or not value.strip():
            continue
        rel = PurePosixPath(value.strip()).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        paths.append(Path(rel))
    return paths
