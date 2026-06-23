# SPDX-License-Identifier: AGPL-3.0-or-later
"""Profile contract loading and validation."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PROFILE_SCHEMA_VERSION = 1
PROFILE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
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


def validate_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ProfileValidationError(f"{field} must be a non-empty string")


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

    for domain, definition in data["domains"].items():
        validate_string(domain, "domain key")
        if not isinstance(definition, dict):
            raise ProfileValidationError(f"domains.{domain} must be a mapping")
        validate_string(definition.get("folder"), f"domains.{domain}.folder")


def load_profile(path: Path) -> ProfileContract:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProfileValidationError(f"{path} is not valid YAML: {exc}") from exc
    except OSError as exc:
        raise ProfileValidationError(f"cannot read profile: {path}: {exc}") from exc
    return ProfileContract.from_mapping(raw)
