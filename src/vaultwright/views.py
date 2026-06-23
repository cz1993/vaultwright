# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate profile-owned presentation view files."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from vaultwright.profiles import ProfileContract


SUPPORTED_BASES = {"Documents.base"}
FORBIDDEN_VIEW_PARTS = {
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


class IndentedSafeDumper(yaml.SafeDumper):
    """PyYAML dumper that keeps nested lists indented under their parent keys."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        return super().increase_indent(flow, False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def profile_property_names(profile: ProfileContract) -> set[str]:
    return {
        str(value)
        for value in [*profile.required_properties, *profile.optional_properties]
        if isinstance(value, str) and value.strip()
    }


def columns(profile: ProfileContract, preferred: list[str]) -> list[str]:
    properties = profile_property_names(profile)
    return unique(["file.name", *[field for field in preferred if field in properties]])


def primary_columns(profile: ProfileContract) -> list[str]:
    properties = [
        str(value)
        for value in profile.required_properties
        if isinstance(value, str) and value.strip() and value != "title"
    ]
    if "owner" in profile_property_names(profile):
        properties.append("owner")
    return unique(["file.name", *properties])


def note_type_available(profile: ProfileContract, note_type: str) -> bool:
    return note_type in {str(key) for key in profile.note_types}


def attention_statuses(profile: ProfileContract) -> list[str]:
    wanted = ("draft", "in-review", "review", "needs-review", "needs-work", "todo")
    available = {str(key) for key in profile.statuses}
    return [status for status in wanted if status in available]


def status_filter(statuses: list[str]) -> dict[str, list[str]]:
    clauses = [f'status == "{status}"' for status in statuses]
    return {"or": clauses}


def document_base_views(profile: ProfileContract) -> list[dict[str, Any]]:
    views: list[dict[str, Any]] = [
        {
            "type": "table",
            "name": "All documents",
            "order": primary_columns(profile),
            "sort": [{"property": "file.mtime", "direction": "DESC"}],
        },
        {
            "type": "table",
            "name": "By status",
            "order": columns(profile, ["status", "type", "domain", "owner", "updated"]),
            "sort": [{"property": "status", "direction": "ASC"}],
        },
        {
            "type": "table",
            "name": "By domain",
            "order": columns(profile, ["domain", "type", "status", "owner", "updated"]),
            "sort": [{"property": "domain", "direction": "ASC"}],
        },
    ]

    if note_type_available(profile, "source-mirror"):
        views.append(
            {
                "type": "table",
                "name": "Office mirrors",
                "filters": {"and": ['type == "source-mirror"']},
                "order": [
                    "file.name",
                    "source",
                    "source_format",
                    "source_modified",
                    "synced",
                ],
                "sort": [{"property": "synced", "direction": "DESC"}],
            }
        )

    review_statuses = attention_statuses(profile)
    if review_statuses:
        views.append(
            {
                "type": "table",
                "name": "Needs attention",
                "filters": status_filter(review_statuses),
                "order": columns(profile, ["status", "type", "domain", "owner", "updated"]),
            }
        )

    if note_type_available(profile, "repo-mirror"):
        views.append(
            {
                "type": "table",
                "name": "Repos",
                "filters": {"and": ['type == "repo-mirror"']},
                "order": [
                    "file.name",
                    "repo",
                    "default_branch",
                    "last_commit_date",
                    "synced",
                ],
                "sort": [{"property": "synced", "direction": "DESC"}],
            }
        )

    return views


def render_documents_base(profile: ProfileContract) -> str:
    payload = {"views": document_base_views(profile)}
    return yaml.dump(
        payload,
        Dumper=IndentedSafeDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=False,
    )


def checked_view_path(value: str) -> Path:
    path = Path(str(value))
    if not str(value).strip() or path.is_absolute() or ".." in path.parts:
        raise ValueError("view path must stay inside the vault")
    if any(part.startswith(".") or part in FORBIDDEN_VIEW_PARTS for part in path.parts):
        raise ValueError("view path contains a reserved path component")
    if path.suffix != ".base":
        raise ValueError("only .base view files are supported")
    return path


def expected_profile_views(profile: ProfileContract) -> tuple[dict[Path, str], list[dict[str, str]]]:
    expected: dict[Path, str] = {}
    blockers: list[dict[str, str]] = []
    seen: set[str] = set()
    for value in profile.views:
        try:
            rel = checked_view_path(str(value))
        except ValueError as exc:
            blockers.append(
                {
                    "code": "unsafe-view-path",
                    "path": str(value),
                    "detail": str(exc),
                }
            )
            continue
        rel_text = rel.as_posix()
        if rel_text in seen:
            blockers.append(
                {
                    "code": "duplicate-view",
                    "path": rel_text,
                    "detail": "profile lists this view more than once",
                }
            )
            continue
        seen.add(rel_text)
        if rel_text not in SUPPORTED_BASES:
            blockers.append(
                {
                    "code": "unsupported-view",
                    "path": rel_text,
                    "detail": "this installed Vaultwright version can generate only Documents.base",
                }
            )
            continue
        expected[rel] = render_documents_base(profile)
    return expected, blockers


def profile_views_plan(root: Path, profile: ProfileContract) -> dict[str, Any]:
    expected, blockers = expected_profile_views(profile)
    actions: list[dict[str, str]] = []
    views: list[dict[str, str]] = []

    for rel, expected_text in sorted(expected.items(), key=lambda item: item[0].as_posix()):
        destination = root / rel
        target_sha = sha256_text(expected_text)
        if not destination.exists():
            views.append({"path": rel.as_posix(), "state": "missing", "target_sha256": target_sha})
            actions.append(
                {
                    "action": "write-view",
                    "path": rel.as_posix(),
                    "target_sha256": target_sha,
                    "reason": "profile expects this generated view",
                }
            )
            continue
        if not destination.is_file():
            blockers.append(
                {
                    "code": "view-path-not-file",
                    "path": rel.as_posix(),
                    "detail": "profile view path exists but is not a file",
                }
            )
            continue
        try:
            current_text = destination.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            blockers.append(
                {
                    "code": "view-not-utf8",
                    "path": rel.as_posix(),
                    "detail": "profile view file is not UTF-8 text",
                }
            )
            continue
        except OSError as exc:
            blockers.append(
                {
                    "code": "view-unreadable",
                    "path": rel.as_posix(),
                    "detail": str(exc),
                }
            )
            continue
        current_sha = sha256_text(current_text)
        if current_text != expected_text:
            views.append(
                {
                    "path": rel.as_posix(),
                    "state": "stale",
                    "current_sha256": current_sha,
                    "target_sha256": target_sha,
                }
            )
            actions.append(
                {
                    "action": "write-view",
                    "path": rel.as_posix(),
                    "current_sha256": current_sha,
                    "target_sha256": target_sha,
                    "reason": "generated view differs from the active profile",
                }
            )
            continue
        views.append({"path": rel.as_posix(), "state": "current", "target_sha256": target_sha})

    return {
        "profile_id": profile.id,
        "profile_version": profile.profile_version,
        "views": views,
        "actions": actions,
        "blockers": blockers,
        "summary": {
            "views": len(expected),
            "actions": len(actions),
            "blockers": len(blockers),
            "up_to_date": not actions and not blockers,
        },
    }


def write_profile_views(root: Path, profile: ProfileContract) -> dict[str, Any]:
    plan = profile_views_plan(root, profile)
    expected, _blockers = expected_profile_views(profile)
    written: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    if plan["blockers"]:
        for blocker in plan["blockers"]:
            errors.append(
                {
                    "action": "blocked",
                    "path": str(blocker.get("path", "")),
                    "detail": str(blocker.get("detail", blocker.get("code", "profile view blocker"))),
                }
            )
        return {
            "written": written,
            "skipped": skipped,
            "errors": errors,
            "summary": {"written": 0, "skipped": 0, "errors": len(errors)},
        }

    action_paths = {str(action["path"]) for action in plan["actions"] if action.get("action") == "write-view"}
    for rel, expected_text in sorted(expected.items(), key=lambda item: item[0].as_posix()):
        rel_text = rel.as_posix()
        if rel_text not in action_paths:
            skipped.append({"action": "write-view", "path": rel_text, "detail": "already current"})
            continue
        destination = root / rel
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(expected_text, encoding="utf-8")
        except OSError as exc:
            errors.append({"action": "write-view", "path": rel_text, "detail": str(exc)})
            continue
        written.append({"action": "write-view", "path": rel_text, "detail": "view generated from profile"})

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
