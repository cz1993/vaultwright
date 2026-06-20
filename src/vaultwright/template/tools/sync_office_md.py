#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
sync_office_md.py — keep markdown mirrors of Office files in sync.

For every .docx/.pptx/.xlsx/.doc in the vault, write a markdown mirror under
`_mirrors/<canonical-source-path>.md` by default. The original stays the editable source of
truth; the mirror makes its content searchable, linkable, and visible in Obsidian — and
refreshes when the original changes (detected by content hash, so runs are idempotent and cheap).

Each mirror has two regions:
  • a human-curated region (frontmatter + a `## Notes` section) — PRESERVED across syncs
  • an auto-generated region below the sentinel line — REGENERATED from the original

Usage:
  python3.11 tools/sync_office_md.py                 # sync the whole vault (dir of this script's parent)
  python3.11 tools/sync_office_md.py --root /path    # explicit vault root
  python3.11 tools/sync_office_md.py --plan          # inventory proposed actions, write nothing
  python3.11 tools/sync_office_md.py --status        # report lifecycle state from the manifest
  python3.11 tools/sync_office_md.py --dry-run       # show what would change, write nothing
  python3.11 tools/sync_office_md.py --force         # rebuild mirrors even if unchanged
  python3.11 tools/sync_office_md.py --include-pdf   # also mirror text-based PDFs
  python3.11 tools/sync_office_md.py --mirror-mode sibling  # legacy sibling mirrors
  python3.11 tools/sync_office_md.py --no-log        # don't append a summary line to log.md

Requires:  python3.11 -m pip install markitdown pyyaml
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from importlib import metadata as importlib_metadata
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pip install pyyaml")

try:
    from markitdown import MarkItDown
except ImportError:
    sys.exit("Missing dependency: pip install markitdown")

# --- configuration ---------------------------------------------------------

DEFAULT_EXTS = [".docx", ".pptx", ".xlsx", ".doc"]
PDF_EXTS = [".pdf"]
TEMP_SOURCE_PREFIXES = ("~$",)
SENSITIVE_NAME_PATTERNS = (
    "secret", "credential", "password", "token", "private", "confidential",
    "payroll", "passport", "sin", "ssn", "tax-return", "bank-statement",
)
FORMAT_RISK_MESSAGES = {
    ".xlsx": "Spreadsheet extraction may omit formulas, hidden sheets, formatting, comments, or live calculations.",
    ".pptx": "Slide extraction may omit speaker notes, layout nuance, images, charts, or embedded objects.",
    ".pdf": "PDF extraction may miss scans, tables, images, signatures, or layout-dependent meaning.",
    ".doc": "Legacy .doc files are unsupported by the default converter; convert to .docx for reliable mirroring.",
}

# Skip these directory names (and anything under them).
EXCLUDE_EXACT = {"_mirrors", "_templates", "_tmp", "tools", "node_modules"}
EXCLUDE_PREFIX = ("_archive", "_backup", "_deprecated")

SENTINEL = "%% AUTO-GENERATED BELOW — DO NOT EDIT %%"
DEFAULT_MIRROR_MODE = "dedicated"
DEFAULT_MIRROR_ROOT = "_mirrors"
MANIFEST_REL = Path("_meta/source-manifest.json")
AUDIT_REL = Path("_meta/sync-audit.jsonl")
MANIFEST_SCHEMA_VERSION = 1
CONFIG_VERSION = "office-mirrors:v1"
MIRROR_MODES = {"dedicated", "sibling"}
FORBIDDEN_MIRROR_PARTS = {
    ".git", ".githooks", ".github", ".obsidian", "_archive", "_fixtures",
    "_meta", "_templates", "_tmp", "node_modules", "tools",
}
LIFECYCLE_GUIDANCE = {
    "planned": "review the plan, then run sync to create the generated mirror.",
    "source_changed": "run sync to refresh the generated region, then review linked curated notes.",
    "source_moved": "confirm the source move is intentional, then run sync to update the mirror path.",
    "stale": "run sync before relying on the mirror; the source or configuration is newer.",
    "converter_changed": "review conversion quality, then run sync if the new converter output is acceptable.",
    "unsupported": "keep the original as source of truth; convert the file manually or use a supported format.",
    "source_missing": "do not delete the retained mirror automatically; confirm whether the source was moved, archived, or deleted.",
    "manual_modification": "inspect the mirror below the generated sentinel and preserve human edits before forcing regeneration.",
    "conflict": "resolve the target mirror/source identity conflict before syncing.",
    "error": "fix the reported error, then rerun plan/status before syncing.",
}

# Frontmatter keys the script owns and overwrites on every sync.
MANAGED_KEYS = {
    "type", "source_id", "source", "source_manifest", "source_format", "source_modified",
    "synced", "source_sha256", "converter", "converter_version", "updated",
}
# Canonical key order for tidy, diff-friendly frontmatter.
KEY_ORDER = [
    "title", "type", "status", "domain", "owner", "created", "updated",
    "tags", "related", "account", "client", "program", "vendor",
    "source_id", "source", "source_manifest", "source_format", "source_modified",
    "synced", "source_sha256", "converter", "converter_version",
]

MAX_CHARS = 400_000  # safety cap on extracted text per file


# --- helpers ---------------------------------------------------------------

def now_iso() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def file_mtime_iso(p: Path) -> str:
    return dt.datetime.fromtimestamp(p.stat().st_mtime).astimezone().replace(microsecond=0).isoformat()


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def markitdown_version() -> str:
    try:
        return importlib_metadata.version("markitdown")
    except importlib_metadata.PackageNotFoundError:
        return "unknown"


def unique_list(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        try:
            dir_fd = os.open(str(path.parent), os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if tmp.exists():
            tmp.unlink()


def append_audit(root: Path, event: dict) -> None:
    payload = {"timestamp": now_iso(), **event}
    path = root / AUDIT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")


def is_excluded(rel: Path, mirror_root: Path | None = None) -> bool:
    if mirror_root and rel.parts[:len(mirror_root.parts)] == mirror_root.parts:
        return True
    for part in rel.parts:
        if part.startswith("."):
            return True
        if part in EXCLUDE_EXACT:
            return True
        if part.startswith(EXCLUDE_PREFIX):
            return True
    return False


def humanize(stem: str) -> str:
    return stem.replace("_", " ").replace("-", " ").strip()


def as_posix_rel(path: Path) -> str:
    return path.as_posix()


def load_domain_routing(root: Path) -> dict[str, dict[str, str]]:
    domain_map = root / "_meta" / "domain-map.yml"
    domain_for: dict[str, str] = {}
    canonical_folder_for: dict[str, str] = {}
    if not domain_map.exists():
        return {"domain_for": domain_for, "canonical_folder_for": canonical_folder_for}
    try:
        data = yaml.safe_load(domain_map.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {"domain_for": domain_for, "canonical_folder_for": canonical_folder_for}
    domains = data.get("domains", {})
    if not isinstance(domains, dict):
        return {"domain_for": domain_for, "canonical_folder_for": canonical_folder_for}
    for domain, info in domains.items():
        if not isinstance(info, dict) or not info.get("folder"):
            continue
        folder = str(info["folder"])
        domain_name = str(domain)
        domain_for[folder] = domain_name
        domain_for[domain_name] = domain_name
        canonical_folder_for[folder] = folder
        canonical_folder_for[domain_name] = folder
        for alias in info.get("aliases", []) or []:
            alias_name = str(alias)
            domain_for[alias_name] = domain_name
            canonical_folder_for[alias_name] = folder
    return {"domain_for": domain_for, "canonical_folder_for": canonical_folder_for}


def domain_from_path(src: Path, root: Path, routing: dict[str, dict[str, str]] | None = None) -> str:
    first = src.relative_to(root).parts[0] if len(src.relative_to(root).parts) > 1 else ""
    if routing and first in routing.get("domain_for", {}):
        return routing["domain_for"][first]
    if len(first) > 3 and first[:2].isdigit() and first[2] == "_":
        return first[3:]
    return first


def canonical_source_rel(src: Path, root: Path, routing: dict[str, dict[str, str]] | None = None) -> Path:
    rel = src.relative_to(root)
    if not rel.parts or not routing:
        return rel
    canonical = routing.get("canonical_folder_for", {}).get(rel.parts[0])
    if not canonical:
        return rel
    return Path(canonical, *rel.parts[1:])


def safe_rel_path(value: str, label: str) -> Path:
    path = Path(str(value))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"{label} must stay inside the vault")
    for part in path.parts:
        if part.startswith(".") or part in FORBIDDEN_MIRROR_PARTS:
            raise ValueError(f"{label} contains a reserved path component")
    return path


def normalized_mirror_config(mode: str, mirror_root: str) -> dict[str, Path | str]:
    if mode not in MIRROR_MODES:
        raise ValueError(f"office_mirrors.mode must be one of: {', '.join(sorted(MIRROR_MODES))}")
    return {"mode": mode, "root": safe_rel_path(mirror_root, "office_mirrors.root")}


def load_mirror_config(root: Path, mode_override: str | None = None, root_override: str | None = None) -> dict[str, Path | str]:
    mode = DEFAULT_MIRROR_MODE
    mirror_root = DEFAULT_MIRROR_ROOT
    cfg = root / "_meta" / "mirror-config.yml"
    if cfg.exists():
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError("_meta/mirror-config.yml must be a mapping")
        office = data.get("office_mirrors", data)
        if not isinstance(office, dict):
            raise ValueError("office_mirrors must be a mapping")
        mode = str(office.get("mode", mode))
        mirror_root = str(office.get("root", mirror_root))
    if mode_override:
        mode = mode_override
    if root_override:
        mirror_root = root_override
    return normalized_mirror_config(mode, mirror_root)


def assert_output_safe(root: Path, output_path: Path) -> None:
    resolved = output_path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("mirror output path must stay inside the vault")
    rel = resolved.relative_to(root)
    for part in rel.parts:
        if part.startswith(".") or part in FORBIDDEN_MIRROR_PARTS:
            raise ValueError("mirror output path resolves through a reserved path component")
    cursor = root
    for part in rel.parent.parts:
        cursor = cursor / part
        if cursor.exists() and cursor.is_symlink():
            raise ValueError("mirror output path must not contain symlink components")
    if output_path.exists() and output_path.is_symlink():
        raise ValueError("mirror output path must not be a symlink")


def source_path_error(root: Path, source_path: Path) -> str | None:
    try:
        rel = source_path.relative_to(root)
    except ValueError:
        return "Source path must stay inside the vault"
    cursor = root
    for part in rel.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            return "Source path must not contain symlink components"
    return None


def split_frontmatter(text: str):
    """Return (frontmatter_dict_or_None, body_str)."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm_raw = text[3:end].lstrip("\n")
            body = text[end + 4:]
            if body.startswith("\n"):
                body = body[1:]
            try:
                return (yaml.safe_load(fm_raw) or {}), body
            except yaml.YAMLError:
                return None, text
    return None, text


def dump_frontmatter(data: dict) -> str:
    ordered = {k: data[k] for k in KEY_ORDER if k in data}
    for k, v in data.items():
        if k not in ordered:
            ordered[k] = v
    text = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{text}---\n"


def managed_frontmatter(
    existing: dict | None,
    src: Path,
    root: Path,
    sha: str,
    routing: dict[str, dict[str, str]] | None = None,
    source_id: str | None = None,
    converter_name: str | None = None,
    converter_version: str | None = None,
) -> dict:
    fm = dict(existing or {})
    domain = domain_from_path(src, root, routing)
    source_rel = as_posix_rel(src.relative_to(root))
    fm.setdefault("title", humanize(src.stem))
    fm.setdefault("status", "active")
    fm.setdefault("domain", domain)
    fm.setdefault("owner", "you")
    fm.setdefault("tags", [])
    fm.setdefault("related", [])
    fm.setdefault("created", dt.date.today().isoformat())
    # managed (always overwritten):
    fm["type"] = "source-mirror"
    if source_id:
        fm["source_id"] = source_id
        fm["source_manifest"] = MANIFEST_REL.as_posix()
    fm["source"] = source_rel
    fm["source_format"] = src.suffix.lstrip(".").lower()
    fm["source_modified"] = file_mtime_iso(src)
    fm["synced"] = now_iso()
    fm["source_sha256"] = sha
    if converter_name:
        fm["converter"] = converter_name
    if converter_version:
        fm["converter_version"] = converter_version
    fm["updated"] = dt.date.today().isoformat()
    return fm


def fresh_preserved_region(src: Path, root: Path) -> str:
    source_rel = as_posix_rel(src.relative_to(root))
    return (
        f"> [!info] Source-mirrored document — auto-generated\n"
        f"> Original: [[{source_rel}|{src.name}]] · edit the **original**, never this mirror.\n"
        f"> Curate notes below; everything under the line refreshes on each sync.\n\n"
        f"## Notes\n\n\n"
    )


def auto_region(extracted: str) -> str:
    body = extracted.strip() if extracted else "_(no extractable text found in the source)_"
    if len(body) > MAX_CHARS:
        body = body[:MAX_CHARS] + "\n\n> _…truncated; see the original for full content._"
    return f"{SENTINEL}\n\n## Extracted content\n\n{body}\n"


def generated_region_hash(markdown: str) -> str | None:
    _fm, body = split_frontmatter(markdown)
    lines = body.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.rstrip("\r\n") == SENTINEL:
            return sha256_text(line + "".join(lines[index + 1:]))
    if body.rstrip("\r\n") == SENTINEL:
        return sha256_text(SENTINEL)
    return None


def split_body_at_sentinel(body: str) -> tuple[str, bool]:
    lines = body.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.rstrip("\r\n") == SENTINEL:
            return "".join(lines[:index]), True
    if body.rstrip("\r\n") == SENTINEL:
        return "", True
    return body, False


def source_manifest_path(root: Path) -> Path:
    return root / MANIFEST_REL


def empty_manifest() -> dict:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "updated": None,
        "records": [],
    }


def load_source_manifest(root: Path) -> dict:
    path = source_manifest_path(root)
    if not path.exists():
        return empty_manifest()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{MANIFEST_REL.as_posix()} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{MANIFEST_REL.as_posix()} must be a JSON object")
    records = data.get("records", [])
    if not isinstance(records, list):
        raise ValueError(f"{MANIFEST_REL.as_posix()} records must be a list")
    normalized = empty_manifest()
    normalized["updated"] = data.get("updated")
    normalized["records"] = [dict(r) for r in records if isinstance(r, dict)]
    return normalized


def comparable_manifest(manifest: dict) -> dict:
    records = []
    for record in manifest.get("records", []):
        clean = dict(record)
        clean["previous_source_paths"] = sorted(clean.get("previous_source_paths") or [])
        clean["warnings"] = sorted(clean.get("warnings") or [])
        clean["errors"] = sorted(clean.get("errors") or [])
        records.append(clean)
    records.sort(key=lambda r: str(r.get("source_id", "")))
    return {"schema_version": MANIFEST_SCHEMA_VERSION, "records": records}


def manifest_text(manifest: dict) -> str:
    records = list(manifest.get("records", []))
    records.sort(key=lambda r: str(r.get("source_id", "")))
    data = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "updated": manifest.get("updated"),
        "records": records,
    }
    return json.dumps(data, indent=2, sort_keys=False) + "\n"


def write_source_manifest(root: Path, manifest: dict) -> bool:
    path = source_manifest_path(root)
    existing = load_source_manifest(root) if path.exists() else empty_manifest()
    if comparable_manifest(existing) == comparable_manifest(manifest):
        return False
    manifest["updated"] = now_iso()
    write_text_atomic(path, manifest_text(manifest))
    return True


def source_id_for(source_rel: str, source_sha256: str) -> str:
    digest = hashlib.sha256(f"{source_rel}\0{source_sha256}".encode("utf-8")).hexdigest()[:20]
    return f"src_{digest}"


def manifest_record_for_source(manifest: dict, root: Path, source_rel: str, source_sha256: str, source_size: int) -> tuple[dict | None, list[str]]:
    records = [r for r in manifest.get("records", []) if isinstance(r, dict)]
    for record in records:
        if record.get("current_source_path") == source_rel:
            return record, []
    candidates = []
    for record in records:
        if record.get("source_sha256") != source_sha256 or record.get("source_size") != source_size:
            continue
        old_path = record.get("current_source_path")
        if isinstance(old_path, str) and old_path and not (root / old_path).exists():
            candidates.append(record)
    if len(candidates) == 1:
        previous = candidates[0].get("current_source_path")
        return candidates[0], [previous] if isinstance(previous, str) else []
    return None, []


def upsert_manifest_record(manifest: dict, record: dict) -> None:
    records = [r for r in manifest.get("records", []) if isinstance(r, dict)]
    for i, existing in enumerate(records):
        if existing.get("source_id") == record.get("source_id"):
            records[i] = record
            break
    else:
        records.append(record)
    records.sort(key=lambda r: str(r.get("source_id", "")))
    manifest["records"] = records


def mark_missing_sources(manifest: dict, root: Path, seen_source_ids: set[str]) -> int:
    missing = 0
    for record in list(manifest.get("records", [])):
        source_id = record.get("source_id")
        if not source_id or source_id in seen_source_ids:
            continue
        current = record.get("current_source_path")
        if not isinstance(current, str) or (root / current).exists():
            continue
        updated = dict(record)
        updated["lifecycle_state"] = "source_missing"
        updated["warnings"] = unique_list((updated.get("warnings") or []) + [
            "Source file is missing; mirror was retained for review.",
        ])
        updated["errors"] = []
        upsert_manifest_record(manifest, updated)
        missing += 1
    return missing


def source_risk_warnings(src: Path, source_size: int) -> list[str]:
    rel_text = src.as_posix().lower()
    warnings: list[str] = []
    for pattern in SENSITIVE_NAME_PATTERNS:
        if pattern in rel_text:
            warnings.append(f"Sensitive-name risk: path contains '{pattern}'. Review before mirroring.")
            break
    format_warning = FORMAT_RISK_MESSAGES.get(src.suffix.lower())
    if format_warning:
        warnings.append(f"Conversion-quality risk: {format_warning}")
    if source_size > 25_000_000:
        warnings.append("Large-file risk: conversion may be slow or truncated; review extracted output.")
    return warnings


def annotate_duplicate_plans(plans: list[dict]) -> None:
    by_hash: dict[str, list[dict]] = {}
    for plan in plans:
        sha = plan["record"].get("source_sha256")
        if sha:
            by_hash.setdefault(str(sha), []).append(plan)
    for dupes in by_hash.values():
        if len(dupes) < 2:
            continue
        paths = [p["record"]["current_source_path"] for p in dupes]
        for plan in dupes:
            others = [p for p in paths if p != plan["record"]["current_source_path"]]
            plan["record"]["warnings"] = unique_list(plan["record"].get("warnings", []) + [
                "Potential duplicate: source bytes match " + ", ".join(others[:5])
            ])


# --- core ------------------------------------------------------------------

def collision_safe_path(preferred: Path) -> tuple[Path, bool]:
    """Return (mirror_path, is_collision). If the preferred path exists and is not a managed
    source mirror, fall back to `<stem>.mirror.md` so a hand-authored note is never clobbered."""
    if preferred.exists():
        head = preferred.read_text(encoding="utf-8", errors="ignore")[:400]
        fm, _ = split_frontmatter(head + "\n---\n") if "---" in head else (None, "")
        is_mirror = "type: source-mirror" in head or (isinstance(fm, dict) and fm.get("type") == "source-mirror")
        if not is_mirror:
            return preferred.with_name(preferred.stem + ".mirror.md"), True
    return preferred, False


def mirror_path_for(src: Path, root: Path, mirror_config: dict[str, Path | str], routing: dict[str, dict[str, str]] | None = None) -> tuple[Path, bool]:
    if mirror_config["mode"] == "sibling":
        return collision_safe_path(src.with_suffix(".md"))
    mirror_root = mirror_config["root"]
    assert isinstance(mirror_root, Path)
    preferred = root / mirror_root / canonical_source_rel(src, root, routing).with_suffix(".md")
    return collision_safe_path(preferred)


def plan_one(
    src: Path,
    root: Path,
    mirror_config: dict[str, Path | str],
    routing: dict[str, dict[str, str]] | None,
    manifest: dict,
    converter_name: str,
    converter_version: str,
) -> dict:
    source_rel = as_posix_rel(src.relative_to(root))
    warnings: list[str] = []
    errors: list[str] = []
    source_size = 0
    source_sha256 = ""
    source_mtime = None
    try:
        symlink_error = source_path_error(root, src)
        if symlink_error:
            raise ValueError(symlink_error)
        source_size = src.stat().st_size
        source_sha256 = sha256_of(src)
        source_mtime = file_mtime_iso(src)
    except Exception as exc:
        detail = f": {exc}" if str(exc) else ""
        errors.append(f"Source is unreadable: {exc.__class__.__name__}{detail}")

    try:
        mirror, collision = mirror_path_for(src, root, mirror_config, routing)
        assert_output_safe(root, mirror)
    except ValueError as exc:
        mirror = root / "_mirrors" / src.relative_to(root).with_suffix(".md")
        collision = False
        errors.append(f"Mirror path is unsafe: {exc}")

    existing_record, moved_from = (None, [])
    if source_sha256:
        existing_record, moved_from = manifest_record_for_source(
            manifest, root, source_rel, source_sha256, source_size,
        )
    source_id = (
        str(existing_record.get("source_id"))
        if existing_record and existing_record.get("source_id")
        else source_id_for(source_rel, source_sha256 or "unreadable")
    )
    previous_paths = existing_record.get("previous_source_paths") if existing_record else []
    if not isinstance(previous_paths, list):
        previous_paths = []
    previous_paths = unique_list([*previous_paths, *moved_from])

    mirror_rel = as_posix_rel(mirror.relative_to(root)) if mirror.is_relative_to(root) else str(mirror)
    mirror_mode = str(mirror_config["mode"])
    mirror_root = mirror_config["root"].as_posix() if isinstance(mirror_config["root"], Path) else str(mirror_config["root"])
    previous_mirror_rel = None
    for candidate in (
        (existing_record or {}).get("mirror_path"),
        (existing_record or {}).get("previous_mirror_path"),
    ):
        if not isinstance(candidate, str) or not candidate or candidate == mirror_rel:
            continue
        previous_path = Path(candidate)
        if previous_path.is_absolute() or ".." in previous_path.parts:
            continue
        if (root / previous_path).exists():
            previous_mirror_rel = candidate
            break
    mirror_location_changed = bool(
        existing_record
        and previous_mirror_rel
        and (
            existing_record.get("mirror_mode") != mirror_mode
            or existing_record.get("mirror_root") != mirror_root
            or existing_record.get("previous_mirror_path")
        )
    )
    existing_fm = None
    existing_generated_hash = None
    if mirror.exists():
        mirror_text = mirror.read_text(encoding="utf-8", errors="ignore")
        existing_fm, _body = split_frontmatter(mirror_text)
        existing_generated_hash = generated_region_hash(mirror_text)
    stored_generated_hash = (existing_record or {}).get("generated_region_sha256")
    missing_generated_baseline = bool(mirror.exists() and not stored_generated_hash)

    action = "unchanged"
    lifecycle_state = "clean"
    if errors:
        action = "error"
        lifecycle_state = "error"
    elif src.suffix.lower() == ".doc":
        action = "skip"
        lifecycle_state = "unsupported"
        warnings.append("Legacy .doc files are inventory-only; convert to .docx for reliable mirroring.")
    elif collision:
        warnings.append("Preferred mirror path is hand-authored; using .mirror.md fallback.")
    warnings = unique_list(warnings + source_risk_warnings(src.relative_to(root), source_size))

    if not errors and action != "skip":
        if mirror_location_changed:
            action = "review"
            lifecycle_state = "conflict"
            errors.append(
                "Configured mirror location changed while the previous generated mirror still exists."
            )
            warnings.append(
                "Archive or remove the previous mirror before syncing the new mirror path."
            )
        elif moved_from:
            action = "update"
            lifecycle_state = "source_moved"
            warnings.append("Source path changed; stable source ID was reused from the manifest.")
        elif (
            isinstance(existing_fm, dict)
            and existing_fm.get("source_id")
            and existing_fm.get("source_id") != source_id
        ):
            action = "review"
            lifecycle_state = "conflict"
            errors.append("Mirror frontmatter belongs to a different source_id.")
        elif (
            existing_record
            and stored_generated_hash
            and mirror.exists()
            and not existing_generated_hash
        ):
            action = "review"
            lifecycle_state = "manual_modification"
            warnings.append("Generated region sentinel is missing or altered since the last successful sync.")
        elif (
            existing_record
            and stored_generated_hash
            and existing_generated_hash
            and stored_generated_hash != existing_generated_hash
        ):
            action = "review"
            lifecycle_state = "manual_modification"
            warnings.append("Generated region changed since the last successful sync.")
        elif missing_generated_baseline:
            action = "review"
            lifecycle_state = "manual_modification"
            warnings.append("Existing mirror has no manifest-generated baseline; review or force-regenerate before trusting it.")
        elif existing_record and existing_record.get("converter_version") != converter_version:
            action = "update"
            lifecycle_state = "converter_changed"
            warnings.append("Converter version changed; mirror should be regenerated.")
        elif (
            existing_record
            and (
                existing_record.get("config_version") != CONFIG_VERSION
                or existing_record.get("mirror_mode") != mirror_mode
                or existing_record.get("mirror_root") != mirror_root
                or existing_record.get("mirror_path") != mirror_rel
            )
        ):
            action = "update"
            lifecycle_state = "stale"
            warnings.append("Mirror configuration changed; mirror should be regenerated.")
        elif existing_record and existing_record.get("source_sha256") != source_sha256:
            action = "update"
            lifecycle_state = "source_changed"
        elif not mirror.exists():
            action = "create"
            lifecycle_state = "planned"
        elif isinstance(existing_fm, dict) and existing_fm.get("source_sha256") == source_sha256:
            action = "unchanged"
            lifecycle_state = "clean"
        else:
            action = "update"
            lifecycle_state = "source_changed"

    record = {
        "source_id": source_id,
        "current_source_path": source_rel,
        "previous_source_paths": previous_paths,
        "mirror_path": mirror_rel,
        "previous_mirror_path": previous_mirror_rel if mirror_location_changed else None,
        "source_format": src.suffix.lstrip(".").lower(),
        "source_size": source_size,
        "source_modified": source_mtime,
        "source_sha256": source_sha256,
        "normalized_content_sha256": (existing_record or {}).get("normalized_content_sha256"),
        "generated_region_sha256": stored_generated_hash or (None if missing_generated_baseline else existing_generated_hash),
        "observed_generated_region_sha256": (
            existing_generated_hash
            if existing_record
            and stored_generated_hash
            and existing_generated_hash
            and stored_generated_hash != existing_generated_hash
            else (existing_record or {}).get("observed_generated_region_sha256")
        ),
        "converter": converter_name,
        "converter_version": converter_version,
        "config_version": CONFIG_VERSION,
        "mirror_mode": mirror_mode,
        "mirror_root": mirror_root,
        "lifecycle_state": lifecycle_state,
        "last_successful_sync": (existing_record or {}).get("last_successful_sync"),
        "warnings": unique_list(warnings),
        "errors": unique_list(errors),
    }
    if not record.get("previous_mirror_path"):
        record.pop("previous_mirror_path", None)
    return {
        "source": src,
        "mirror": mirror,
        "collision": collision,
        "action": action,
        "record": record,
        "existing_fm": existing_fm,
    }


def status_for_plan(plan: dict) -> str:
    action = plan["action"]
    state = plan["record"]["lifecycle_state"]
    if action == "create":
        return "planned:create"
    if action == "update":
        return f"planned:update ({state})"
    if action == "review":
        return f"review:{state}"
    if action == "skip":
        return f"skipped:{state}"
    if action == "error":
        return "error:plan"
    return state


def lifecycle_guidance_lines(state_counts: dict[str, int]) -> list[str]:
    lines: list[str] = []
    for state in sorted(state_counts):
        count = state_counts.get(state, 0)
        if count <= 0 or state == "clean":
            continue
        guidance = LIFECYCLE_GUIDANCE.get(state)
        if guidance:
            lines.append(f"{state} ({count}): {guidance}")
    return lines


def print_lifecycle_guidance(state_counts: dict[str, int]) -> None:
    lines = lifecycle_guidance_lines(state_counts)
    if not lines:
        return
    print("next actions:")
    for line in lines:
        print(f"  - {line}")


def review_blocks_force(record: dict) -> bool:
    if record.get("lifecycle_state") == "conflict":
        return True
    if record.get("lifecycle_state") != "manual_modification":
        return False
    warnings = record.get("warnings") or []
    force_blockers = (
        "Generated region sentinel is missing",
        "no manifest-generated baseline",
    )
    return any(any(blocker in str(warning) for blocker in force_blockers) for warning in warnings)


def sync_one(
    src: Path,
    root: Path,
    converter: MarkItDown,
    force: bool,
    dry: bool,
    mirror_config: dict[str, Path | str],
    routing: dict[str, dict[str, str]] | None = None,
    manifest: dict | None = None,
    converter_name: str = "markitdown",
    converter_version: str = "unknown",
):
    """Return status string: created | updated | unchanged | skipped:<reason> | error:<msg>."""
    active_manifest = manifest if manifest is not None else empty_manifest()
    plan = plan_one(src, root, mirror_config, routing, active_manifest, converter_name, converter_version)
    record = dict(plan["record"])
    mirror = plan["mirror"]
    source_id = record["source_id"]
    sha = record["source_sha256"]

    if plan["action"] == "error":
        if manifest is not None and not dry:
            upsert_manifest_record(manifest, record)
        return "error:plan"
    if plan["action"] == "skip":
        if manifest is not None and not dry:
            upsert_manifest_record(manifest, record)
        return "skipped:unsupported-format (legacy/no converter)"
    if plan["action"] == "review" and (not force or review_blocks_force(record)):
        if manifest is not None and not dry:
            upsert_manifest_record(manifest, record)
        return f"skipped:{record['lifecycle_state']}"

    existing_fm, existing_body = (None, "")
    if mirror.exists():
        existing_fm, existing_body = split_frontmatter(mirror.read_text(encoding="utf-8"))
        if plan["action"] == "unchanged" and not force:
            record["lifecycle_state"] = "clean"
            current_generated_hash = generated_region_hash(mirror.read_text(encoding="utf-8", errors="ignore"))
            if current_generated_hash:
                record["generated_region_sha256"] = current_generated_hash
            if manifest is not None and not dry:
                upsert_manifest_record(manifest, record)
            return "unchanged"

    try:
        extracted = converter.convert(str(src)).text_content
    except Exception as e:
        name = e.__class__.__name__
        if "UnsupportedFormat" in name:
            record["lifecycle_state"] = "unsupported"
            record["warnings"] = unique_list(record.get("warnings", []) + ["Converter reported unsupported format."])
            if manifest is not None and not dry:
                upsert_manifest_record(manifest, record)
            return "skipped:unsupported-format (legacy/no converter)"
        record["lifecycle_state"] = "error"
        record["errors"] = unique_list(record.get("errors", []) + [f"{name}: {str(e)[:120]}"])
        if manifest is not None and not dry:
            upsert_manifest_record(manifest, record)
        return f"error:{name}: {str(e)[:120]}"

    try:
        post_convert_sha = sha256_of(src)
    except Exception as e:
        name = e.__class__.__name__
        record["lifecycle_state"] = "error"
        record["errors"] = unique_list(record.get("errors", []) + [
            f"Source became unreadable during conversion: {name}: {str(e)[:120]}"
        ])
        if manifest is not None and not dry:
            upsert_manifest_record(manifest, record)
        return f"error:source-unreadable-after-conversion:{name}"
    if post_convert_sha != sha:
        record["lifecycle_state"] = "error"
        record["errors"] = unique_list(record.get("errors", []) + [
            "Source bytes changed during conversion; mirror was not written.",
        ])
        if manifest is not None and not dry:
            upsert_manifest_record(manifest, record)
        return "error:source-changed-during-conversion"

    # preserve the curated region (above the sentinel) if the mirror already exists
    preserved_prefix, sentinel_found = split_body_at_sentinel(existing_body)
    if existing_body and sentinel_found:
        preserved = preserved_prefix.rstrip() + "\n\n"
    elif existing_body:
        preserved = existing_body.rstrip() + "\n\n"
    else:
        preserved = fresh_preserved_region(src, root)

    fm = managed_frontmatter(
        existing_fm if isinstance(existing_fm, dict) else None,
        src,
        root,
        sha,
        routing,
        source_id,
        converter_name,
        converter_version,
    )
    generated = auto_region(extracted)
    content = dump_frontmatter(fm) + "\n" + preserved + generated

    status = "updated" if mirror.exists() else "created"
    if plan["collision"] and status == "created":
        status = "created(.mirror.md — preferred mirror path was hand-authored)"
    if not dry:
        write_text_atomic(mirror, content)
        record["normalized_content_sha256"] = sha256_text(extracted.strip())
        record["generated_region_sha256"] = sha256_text(generated)
        record["lifecycle_state"] = "clean"
        record["last_successful_sync"] = fm["synced"]
        record["warnings"] = unique_list(record.get("warnings", []))
        record["errors"] = []
        if manifest is not None:
            upsert_manifest_record(manifest, record)
    return status


def discover(root: Path, exts: list[str], mirror_config: dict[str, Path | str]) -> list[Path]:
    out = []
    mirror_root = mirror_config["root"] if isinstance(mirror_config["root"], Path) else None
    for p in sorted(root.rglob("*")):
        if p.is_symlink() or not p.is_file():
            continue
        if p.name.startswith(TEMP_SOURCE_PREFIXES):
            continue
        if p.suffix.lower() not in exts:
            continue
        if is_excluded(p.relative_to(root).parent, mirror_root):
            continue
        if source_path_error(root, p):
            continue
        out.append(p)
    return out


def count_status(status: str, counts: dict[str, int]) -> None:
    if status.startswith("created"):
        counts["created"] += 1
    elif status.startswith("updated"):
        counts["updated"] += 1
    elif status.startswith("unchanged"):
        counts["unchanged"] += 1
    elif status.startswith("skipped"):
        counts["skipped"] += 1
    elif status.startswith("error"):
        counts["error"] += 1
    else:
        counts["skipped"] += 1


def print_plan_or_status(
    root: Path,
    files: list[Path],
    mirror_config: dict[str, Path | str],
    routing: dict[str, dict[str, str]],
    manifest: dict,
    converter_name: str,
    converter_version: str,
    *,
    mode: str,
    quiet: bool,
) -> int:
    action_counts = {"create": 0, "update": 0, "unchanged": 0, "skip": 0, "review": 0, "error": 0}
    state_counts: dict[str, int] = {}
    seen_source_ids: set[str] = set()
    plans = [plan_one(src, root, mirror_config, routing, manifest, converter_name, converter_version) for src in files]
    annotate_duplicate_plans(plans)

    for plan in plans:
        src = plan["source"]
        action = plan["action"]
        state = plan["record"]["lifecycle_state"]
        action_counts[action] = action_counts.get(action, 0) + 1
        state_counts[state] = state_counts.get(state, 0) + 1
        seen_source_ids.add(plan["record"]["source_id"])
        if not quiet:
            source_rel = src.relative_to(root)
            mirror_rel = plan["record"]["mirror_path"]
            warning_count = len(plan["record"].get("warnings", []))
            suffix = f"  warnings={warning_count}" if warning_count else ""
            print(f"  [{status_for_plan(plan):<28}] {source_rel} -> {mirror_rel}{suffix}")

    missing = 0
    for record in manifest.get("records", []):
        source_id = record.get("source_id")
        current = record.get("current_source_path")
        if not source_id or source_id in seen_source_ids or not isinstance(current, str):
            continue
        if (root / current).exists():
            continue
        missing += 1
        state_counts["source_missing"] = state_counts.get("source_missing", 0) + 1
        action_counts["review"] = action_counts.get("review", 0) + 1
        if not quiet:
            print(f"  [{'review:source_missing':<28}] {current} -> {record.get('mirror_path', '')}")

    action_summary = (
        f"{action_counts.get('create', 0)} create, {action_counts.get('update', 0)} update, "
        f"{action_counts.get('unchanged', 0)} unchanged, {action_counts.get('skip', 0)} skip, "
        f"{action_counts.get('review', 0)} review, {action_counts.get('error', 0)} error"
    )
    state_summary = ", ".join(f"{state}={count}" for state, count in sorted(state_counts.items())) or "no states"
    warning_total = sum(len(plan["record"].get("warnings", [])) for plan in plans)
    print(f"\nsync_office_md {mode}: {len(files)} current sources, {missing} missing manifest sources -> {action_summary}")
    print(f"lifecycle: {state_summary}")
    print(f"warnings: {warning_total}")
    print_lifecycle_guidance(state_counts)
    return 1 if action_counts.get("error", 0) else 0


def main():
    ap = argparse.ArgumentParser(description="Sync markdown mirrors of Office files.")
    ap.add_argument("--root", type=Path, default=None, help="Vault root (default: parent of this script).")
    ap.add_argument("--include-pdf", action="store_true", help="Also mirror text-based PDFs.")
    ap.add_argument("--force", action="store_true", help="Rebuild even if the source is unchanged.")
    ap.add_argument("--dry-run", action="store_true", help="Report only; write nothing.")
    ap.add_argument("--plan", action="store_true", help="Inventory sources and proposed mirror actions without writing.")
    ap.add_argument("--status", action="store_true", help="Report lifecycle status from the source manifest without writing.")
    ap.add_argument("--mirror-mode", choices=sorted(MIRROR_MODES), default=None, help="Mirror layout: dedicated (default) or sibling (legacy).")
    ap.add_argument("--mirror-root", default=None, help="Dedicated mirror root, relative to the vault root (default: _mirrors).")
    ap.add_argument("--no-log", action="store_true", help="Do not append a summary line to log.md.")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.plan and args.status:
        sys.exit("--plan and --status are mutually exclusive")

    root = (args.root or Path(__file__).resolve().parent.parent).resolve()
    exts = DEFAULT_EXTS + (PDF_EXTS if args.include_pdf else [])
    try:
        mirror_config = load_mirror_config(root, args.mirror_mode, args.mirror_root)
        manifest = load_source_manifest(root)
    except (OSError, yaml.YAMLError, ValueError) as e:
        sys.exit(f"Invalid sync metadata/config: {e}")
    routing = load_domain_routing(root)
    converter_name = "markitdown"
    converter_version = markitdown_version()

    files = discover(root, exts, mirror_config)
    if args.plan:
        return print_plan_or_status(
            root,
            files,
            mirror_config,
            routing,
            manifest,
            converter_name,
            converter_version,
            mode="plan",
            quiet=args.quiet,
        )
    if args.status:
        return print_plan_or_status(
            root,
            files,
            mirror_config,
            routing,
            manifest,
            converter_name,
            converter_version,
            mode="status",
            quiet=args.quiet,
        )

    converter = MarkItDown()

    counts = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0, "error": 0}
    changed = []
    seen_source_ids: set[str] = set()
    for src in files:
        plan = plan_one(src, root, mirror_config, routing, manifest, converter_name, converter_version)
        seen_source_ids.add(plan["record"]["source_id"])
        status = sync_one(
            src,
            root,
            converter,
            args.force,
            args.dry_run,
            mirror_config,
            routing,
            manifest,
            converter_name,
            converter_version,
        )
        count_status(status, counts)
        if not args.quiet:
            rel = src.relative_to(root)
            print(f"  [{status:<10}] {rel}")
        if status.startswith(("created", "updated")):
            changed.append(src.relative_to(root))
        if not args.dry_run:
            append_audit(root, {
                "tool": "sync_office_md",
                "source_id": plan["record"].get("source_id"),
                "source_path": plan["record"].get("current_source_path"),
                "mirror_path": plan["record"].get("mirror_path"),
                "status": status,
                "lifecycle_state": (manifest_record_for_source(
                    manifest,
                    root,
                    plan["record"].get("current_source_path", ""),
                    plan["record"].get("source_sha256", ""),
                    int(plan["record"].get("source_size") or 0),
                )[0] or plan["record"]).get("lifecycle_state"),
            })

    missing = 0
    manifest_changed = False
    if not args.dry_run:
        missing = mark_missing_sources(manifest, root, seen_source_ids)
        manifest_changed = write_source_manifest(root, manifest)

    summary = (f"{counts['created']} created, {counts['updated']} updated, "
               f"{counts['unchanged']} unchanged, {counts['skipped']} skipped, "
               f"{counts['error']} error, {missing} missing")
    print(f"\nsync_office_md: {len(files)} sources → {summary}"
          + (" [dry-run]" if args.dry_run else "")
          + (" [manifest updated]" if manifest_changed else ""))

    if changed and not args.dry_run and not args.no_log:
        log = root / "log.md"
        line = f"## [{dt.date.today().isoformat()}] sync | office mirrors: {summary}\n"
        with log.open("a", encoding="utf-8") as f:
            f.write(line)

    return 1 if counts["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
