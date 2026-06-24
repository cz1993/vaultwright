# SPDX-License-Identifier: AGPL-3.0-or-later
"""Migrate human mirror annotations into source-ID-keyed sidecars."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from vaultwright.runtime_profile import (
    profile_context_keys as runtime_profile_context_keys,
    profile_repo_notes_dir,
)


SENTINEL = "%% AUTO-GENERATED BELOW \u2014 DO NOT EDIT %%"
ANNOTATION_ROOT = Path("_meta/mirror-annotations")
REPO_CONFIG = Path("tools/repos.yml")
SOURCE_MANAGED_KEYS = {
    "type",
    "source_id",
    "source",
    "source_manifest",
    "source_format",
    "source_modified",
    "synced",
    "source_sha256",
    "converter",
    "converter_version",
    "updated",
}
REPO_MANAGED_KEYS = {
    "type",
    "repo_id",
    "repo_manifest",
    "repo",
    "repo_url",
    "default_branch",
    "last_commit",
    "last_commit_date",
    "open_issues",
    "synced",
    "updated",
}
DEFAULT_FRONTMATTER_KEYS = {"title", "domain", "owner", "created", "updated"}
LEGACY_PROFILE_CONTEXT_KEYS = {"account", "client", "program", "vendor"}
RESERVED_PARTS = {
    ".git",
    ".githooks",
    ".github",
    ".obsidian",
    "_archive",
    "_fixtures",
    "_templates",
    "_tmp",
    "node_modules",
    "tools",
}
IDENTITY_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def now_iso() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            raw = text[3:end].lstrip("\n")
            body = text[end + 4 :]
            if body.startswith("\n"):
                body = body[1:]
            try:
                loaded = yaml.safe_load(raw) or {}
            except yaml.YAMLError:
                return None, text
            return loaded if isinstance(loaded, dict) else None, body
    return None, text


def dump_frontmatter(data: dict[str, Any]) -> str:
    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{text}---\n"


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def split_body_at_sentinel(body: str) -> tuple[str, bool]:
    lines = body.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.rstrip("\r\n") == SENTINEL:
            return "".join(lines[:index]), True
    if body.rstrip("\r\n") == SENTINEL:
        return "", True
    return body, False


def safe_rel(path: Path, root: Path) -> str:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return ""
    if rel.is_absolute() or ".." in rel.parts:
        return ""
    return rel.as_posix()


def safe_identity(value: str) -> str:
    cleaned = IDENTITY_RE.sub("-", value.strip()).strip(".-")
    return cleaned or sha256_text(value)[:20]


def sidecar_path(kind: str, identity: str) -> Path:
    group = "source" if kind == "source-mirror" else "repo"
    return ANNOTATION_ROOT / group / f"{safe_identity(identity)}.md"


def iter_markdown_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.md"):
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if path.is_symlink() or any(part in RESERVED_PARTS for part in rel.parts):
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def default_preserved_line(line: str) -> bool:
    stripped = line.strip()
    return (
        not stripped
        or stripped == "## Notes"
        or stripped == "> [!info] Source-mirrored document \u2014 auto-generated"
        or stripped == "> [!info] GitHub repo mirror \u2014 auto-generated"
        or stripped.startswith("> Original: ")
        or stripped.startswith("> Source: ")
        or stripped.startswith("> Human annotations were migrated to ")
        or stripped == "> Curate notes below; everything under the line refreshes on each sync."
        or stripped == "> Curate notes below; everything under the line refreshes on sync."
        or stripped == "> This mirror is machine-owned; do not edit it directly."
        or stripped == "> This mirror is machine-owned; keep durable human notes in curated notes or annotation sidecars."
    )


def preserved_body_has_annotation(body: str) -> bool:
    return any(not default_preserved_line(line) for line in body.splitlines())


def managed_keys(kind: str) -> set[str]:
    return SOURCE_MANAGED_KEYS if kind == "source-mirror" else REPO_MANAGED_KEYS


def preserved_frontmatter(fm: dict[str, Any], kind: str) -> dict[str, Any]:
    owned = managed_keys(kind)
    return {str(key): value for key, value in fm.items() if str(key) not in owned}


def active_profile_context_keys(root: Path) -> set[str]:
    try:
        return set(runtime_profile_context_keys(root))
    except Exception:
        return set(LEGACY_PROFILE_CONTEXT_KEYS)


def repo_context_values(entry: dict[str, Any], context_keys: set[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    if "account" in context_keys:
        account = entry.get("account") or entry.get("client")
        if isinstance(account, str) and account.strip():
            values["account"] = account.strip()
    if "client" in context_keys:
        client = entry.get("client") or values.get("account") or entry.get("account")
        if isinstance(client, str) and client.strip():
            values["client"] = client.strip()
    for key in sorted(context_keys - {"account", "client"}):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            values[key] = value.strip()
    return values


def configured_repo_seed(root: Path, mirror_rel: str, context_keys: set[str]) -> dict[str, Any]:
    path = root / REPO_CONFIG
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(data, dict):
        return {}
    settings = data.get("settings", {})
    if settings is None:
        settings = {}
    if not isinstance(settings, dict):
        settings = {}
    notes_dir = settings.get("notes_dir")
    if not isinstance(notes_dir, str) or not notes_dir.strip():
        notes_dir = profile_repo_notes_dir(root)
    repos = data.get("repos", [])
    if not isinstance(repos, list):
        return {}
    for entry in repos:
        if not isinstance(entry, dict):
            continue
        note = entry.get("note")
        if not isinstance(note, str) or not note.strip():
            continue
        rel = Path(notes_dir) / note.strip()
        if rel.as_posix() != mirror_rel:
            continue
        seed: dict[str, Any] = {
            "tags": entry.get("tags", ["repo"]),
            "related": entry.get("related", []),
        }
        seed.update(repo_context_values(entry, context_keys))
        return seed
    return {}


def frontmatter_has_annotation(fm: dict[str, Any], kind: str, root: Path, mirror_rel: str) -> bool:
    preserved = preserved_frontmatter(fm, kind)
    context_keys = active_profile_context_keys(root)
    repo_seed = configured_repo_seed(root, mirror_rel, context_keys) if kind == "repo-mirror" else {}
    for key, value in preserved.items():
        if key in DEFAULT_FRONTMATTER_KEYS:
            continue
        if key == "status" and str(value or "").strip() in {"", "active", "draft"}:
            continue
        if key == "tags":
            tags = value if isinstance(value, list) else []
            clean_tags = {str(item).strip() for item in tags if str(item).strip()}
            seed_tags = repo_seed.get("tags", ["repo"] if kind == "repo-mirror" else [])
            expected = seed_tags if isinstance(seed_tags, list) else []
            expected_tags = {str(item).strip() for item in expected if str(item).strip()}
            if not clean_tags or (kind == "repo-mirror" and clean_tags <= expected_tags):
                continue
            return True
        if key == "related":
            related = value if isinstance(value, list) else []
            clean_related = {str(item).strip() for item in related if str(item).strip()}
            seed_related = repo_seed.get("related", [])
            expected = seed_related if isinstance(seed_related, list) else []
            expected_related = {str(item).strip() for item in expected if str(item).strip()}
            if not clean_related or (kind == "repo-mirror" and clean_related <= expected_related):
                continue
            return True
        if key in context_keys and value in (None, "", []):
            continue
        if kind == "repo-mirror" and key in context_keys and repo_seed.get(key) == str(value or "").strip():
            continue
        return True
    return False


def annotation_identity(fm: dict[str, Any], kind: str) -> str:
    key = "source_id" if kind == "source-mirror" else "repo_id"
    value = str(fm.get(key, "") or "").strip()
    return value


def preserved_payload(
    *,
    kind: str,
    identity: str,
    mirror_path: str,
    fm: dict[str, Any],
    body: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": kind,
        "identity": identity,
        "mirror_path": mirror_path,
        "frontmatter": preserved_frontmatter(fm, kind),
        "body": body.rstrip() + ("\n" if body.strip() else ""),
    }
    if kind == "source-mirror":
        payload["source"] = str(fm.get("source", "") or "")
    else:
        payload["repo"] = str(fm.get("repo", "") or "")
    return payload


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


def preserved_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(json_safe(payload), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_text(encoded)


def sidecar_frontmatter(path: Path) -> dict[str, Any] | None:
    try:
        fm, _body = split_frontmatter(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    return fm if isinstance(fm, dict) else None


def migration_action(
    root: Path,
    path: Path,
    fm: dict[str, Any],
    body: str,
) -> tuple[dict[str, Any] | None, dict[str, str] | None, bool]:
    kind = str(fm.get("type", "") or "").strip()
    identity = annotation_identity(fm, kind)
    mirror_rel = safe_rel(path, root)
    if not identity:
        return (
            None,
            {
                "code": "missing-mirror-identity",
                "path": mirror_rel,
                "detail": f"{kind} is missing a stable ID",
            },
            False,
        )

    has_annotation = preserved_body_has_annotation(body) or frontmatter_has_annotation(fm, kind, root, mirror_rel)
    if not has_annotation:
        return None, None, False

    payload = preserved_payload(kind=kind, identity=identity, mirror_path=mirror_rel, fm=fm, body=body)
    digest = preserved_hash(payload)
    sidecar_rel = sidecar_path(kind, identity)
    sidecar = root / sidecar_rel
    if sidecar.exists():
        existing_fm = sidecar_frontmatter(sidecar)
        if existing_fm and str(existing_fm.get("preserved_sha256", "") or "") == digest:
            return None, None, True
        return (
            None,
            {
                "code": "annotation-sidecar-conflict",
                "path": sidecar_rel.as_posix(),
                "detail": f"existing sidecar does not match preserved mirror annotations for {mirror_rel}",
            },
            False,
        )

    action: dict[str, Any] = {
        "action": "write-annotation-sidecar",
        "kind": kind,
        "identity": identity,
        "mirror_path": mirror_rel,
        "sidecar_path": sidecar_rel.as_posix(),
        "preserved_sha256": digest,
        "preserved_bytes": len(payload["body"].encode("utf-8")),
        "preserved_frontmatter_keys": sorted(payload["frontmatter"]),
        "payload": payload,
    }
    if kind == "source-mirror":
        action["source"] = payload.get("source", "")
    else:
        action["repo"] = payload.get("repo", "")
    return action, None, False


def annotation_migration_plan(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    actions: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []
    migrated = 0
    scanned = 0
    skipped_without_annotations = 0

    for path in iter_markdown_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        fm, body = split_frontmatter(text)
        if not isinstance(fm, dict):
            continue
        kind = str(fm.get("type", "") or "").strip()
        if kind not in {"source-mirror", "repo-mirror"}:
            continue
        preserved, sentinel_found = split_body_at_sentinel(body)
        if not sentinel_found:
            continue
        scanned += 1
        action, blocker, already_migrated = migration_action(root, path, fm, preserved)
        if action:
            actions.append(action)
        elif blocker:
            blockers.append(blocker)
        elif already_migrated:
            migrated += 1
        else:
            skipped_without_annotations += 1

    public_actions = [{key: value for key, value in action.items() if key != "payload"} for action in actions]
    return {
        "schema_version": 1,
        "annotation_root": ANNOTATION_ROOT.as_posix(),
        "actions": public_actions,
        "blockers": blockers,
        "summary": {
            "scanned_mirrors": scanned,
            "actions": len(actions),
            "blockers": len(blockers),
            "already_migrated": migrated,
            "without_annotations": skipped_without_annotations,
            "up_to_date": not actions and not blockers,
        },
        "_actions_with_payload": actions,
    }


def sidecar_content(action: dict[str, Any], migrated_at: str) -> str:
    payload = action["payload"]
    kind = str(action["kind"])
    identity = str(action["identity"])
    fm: dict[str, Any] = {
        "schema_version": 1,
        "type": "mirror-annotation",
        "annotation_kind": kind,
        "identity": identity,
        "mirror_path": action["mirror_path"],
        "preserved_sha256": action["preserved_sha256"],
        "migrated_at": migrated_at,
    }
    if kind == "source-mirror":
        fm["source_id"] = identity
        fm["source"] = action.get("source", "")
    else:
        fm["repo_id"] = identity
        fm["repo"] = action.get("repo", "")

    preserved_fm = payload.get("frontmatter") if isinstance(payload, dict) else {}
    if isinstance(preserved_fm, dict) and preserved_fm:
        preserved_fm_text = yaml.safe_dump(
            preserved_fm,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ).rstrip()
        frontmatter_section = f"```yaml\n{preserved_fm_text}\n```"
    else:
        frontmatter_section = "_No preserved frontmatter._"
    body = str(payload.get("body", "") if isinstance(payload, dict) else "").rstrip()
    body_section = body if body else "_No preserved notes body._"
    title = identity.replace("_", " ")
    return (
        dump_frontmatter(fm)
        + "\n"
        + f"# Mirror Annotation: {title}\n\n"
        + f"> Migrated from `{action['mirror_path']}` so the generated mirror can become machine-owned.\n\n"
        + "## Preserved Frontmatter\n\n"
        + frontmatter_section
        + "\n\n"
        + "## Preserved Notes\n\n"
        + body_section
        + "\n"
    )


def write_annotation_sidecars(root: Path, plan: dict[str, Any] | None = None) -> dict[str, Any]:
    root = root.expanduser().resolve()
    plan = plan or annotation_migration_plan(root)
    if plan.get("blockers"):
        return {
            "schema_version": 1,
            "annotation_root": ANNOTATION_ROOT.as_posix(),
            "written": [],
            "blockers": plan["blockers"],
            "summary": {
                **dict(plan.get("summary", {})),
                "written": 0,
            },
        }
    written: list[dict[str, str]] = []
    migrated_at = now_iso()
    for action in plan.get("_actions_with_payload", []):
        sidecar_rel = Path(str(action["sidecar_path"]))
        write_text_atomic(root / sidecar_rel, sidecar_content(action, migrated_at))
        written.append(
            {
                "mirror_path": str(action["mirror_path"]),
                "sidecar_path": sidecar_rel.as_posix(),
                "preserved_sha256": str(action["preserved_sha256"]),
            }
        )
    return {
        "schema_version": 1,
        "annotation_root": ANNOTATION_ROOT.as_posix(),
        "written": written,
        "blockers": [],
        "summary": {
            **dict(plan.get("summary", {})),
            "written": len(written),
            "up_to_date": not written,
        },
    }


def public_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in plan.items() if key != "_actions_with_payload"}
