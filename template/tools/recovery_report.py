#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Print a read-only recovery checklist from Vaultwright manifests."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_MANIFEST = Path("_meta/source-manifest.json")
REPO_MANIFEST = Path("_meta/repo-manifest.json")
AUDIT_LOG = Path("_meta/sync-audit.jsonl")
CLEAN_STATES = {"clean", "reviewed"}
SOURCE_EXTS = {".docx", ".pptx", ".xlsx", ".doc", ".pdf"}
EXCLUDED_PARTS = {"_mirrors", "_templates", "_tmp", "tools", "node_modules", ".git"}
TEMP_EXCLUDED_PARTS = {"_templates", "_tmp", "tools", "node_modules", ".git"}
ATOMIC_TEMP_RE = re.compile(r"^\..+\.\d+\.tmp$")

OFFICE_ACTIONS = {
    "planned": "Run plan review, then sync to create the generated mirror.",
    "source_changed": "Run sync to refresh the generated region, then review linked curated notes.",
    "source_moved": "Confirm the move is intentional, preserve/archive any old mirror, then run sync to update the mirror path.",
    "stale": "Run sync before relying on the mirror; the source or configuration is newer.",
    "converter_changed": "Review conversion quality, then sync if the new converter output is acceptable.",
    "unsupported": "Keep the original as source of truth; convert manually or use a supported format.",
    "source_missing": "Locate, restore, or intentionally archive the source before changing the retained mirror.",
    "manual_modification": "Preserve human edits below the sentinel before forcing regeneration.",
    "conflict": "Resolve the mirror/source identity conflict before syncing.",
    "error": "Fix the reported error, then rerun plan/status before syncing.",
}

REPO_ACTIONS = {
    "planned": "Run plan review, then sync to create the repo mirror.",
    "repo_changed": "Run sync to refresh README/docs/metadata, then review curated notes.",
    "stale": "Run sync before relying on the mirror; the repo or configuration is newer.",
    "unreachable": "Check repo spelling, network access, and GitHub auth; existing mirror content is retained.",
    "manual_modification": "Preserve human edits below the sentinel before forcing regeneration.",
    "conflict": "Resolve the target note/repo identity conflict before syncing.",
    "error": "Fix the reported error, then rerun plan/status before syncing.",
}

TEMP_ACTION = (
    "Rerun status/sync to confirm the canonical generated file is complete, then remove the stale "
    "temp file after backup review."
)


def rel_exists(root: Path, value: object) -> bool | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return None
    return (root / path).exists()


def load_manifest(root: Path, rel: Path) -> tuple[list[dict], list[str]]:
    path = root / rel
    if not path.exists():
        return [], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], [f"{rel.as_posix()}: invalid JSON ({exc.__class__.__name__})"]
    records = data.get("records", [])
    if not isinstance(records, list):
        return [], [f"{rel.as_posix()}: records must be a list"]
    bad = sum(1 for record in records if not isinstance(record, dict))
    errors = [f"{rel.as_posix()}: {bad} records are not objects"] if bad else []
    return [record for record in records if isinstance(record, dict)], errors


def compact_audit_event(event: dict) -> dict:
    compact: dict = {}
    for key in ("timestamp", "tool", "status", "lifecycle_state", "source_path", "mirror_path", "note_path"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            compact[key] = value
    for key in ("warnings", "errors"):
        value = event.get(key)
        if isinstance(value, list):
            compact[key] = [str(item) for item in value if str(item).strip()]
        else:
            compact[key] = []
    return compact


def load_latest_audit_events(root: Path) -> tuple[dict[str, dict], list[str]]:
    path = root / AUDIT_LOG
    if not path.exists():
        return {}, []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return {}, [f"{AUDIT_LOG.as_posix()}: unreadable text; latest audit context unavailable."]

    latest: dict[str, dict] = {}
    warnings: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            warnings.append(f"{AUDIT_LOG.as_posix()}: line {line_number} invalid JSON; skipped.")
            continue
        if not isinstance(event, dict):
            warnings.append(f"{AUDIT_LOG.as_posix()}: line {line_number} is not an object; skipped.")
            continue
        source_id = event.get("source_id")
        if isinstance(source_id, str) and source_id.strip():
            latest[f"office:{source_id}"] = compact_audit_event(event)
        repo_id = event.get("repo_id")
        if isinstance(repo_id, str) and repo_id.strip():
            latest[f"repo:{repo_id}"] = compact_audit_event(event)
    return latest, warnings


def has_source_evidence(root: Path) -> bool:
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        if path.suffix.lower() in SOURCE_EXTS:
            return True
    return False


def has_repo_evidence(root: Path) -> bool:
    repo_notes = root / "80_sources" / "repos"
    if repo_notes.exists() and any(repo_notes.glob("*.md")):
        return True
    repos_yml = root / "tools" / "repos.yml"
    if not repos_yml.exists():
        return False
    for line in repos_yml.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if stripped.startswith("- repo:"):
            return True
    return False


def stale_atomic_temp_items(root: Path) -> list[dict]:
    items: list[dict] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if any(part in TEMP_EXCLUDED_PARTS for part in rel.parts):
            continue
        if not ATOMIC_TEMP_RE.match(path.name):
            continue
        target_name = path.name.rsplit(".", 2)[0].lstrip(".")
        target = path.with_name(target_name)
        try:
            target_rel = target.relative_to(root).as_posix()
        except ValueError:
            target_rel = ""
        items.append({
            "kind": "temp",
            "id": "",
            "state": "interrupted_write",
            "source": "",
            "target": rel.as_posix(),
            "expected_target": target_rel,
            "source_exists": None,
            "target_exists": True,
            "expected_target_exists": target.exists(),
            "reasons": ["stale atomic temp file"],
            "action": TEMP_ACTION,
            "warnings": [],
            "errors": [],
        })
    return items


def office_item(root: Path, record: dict) -> dict | None:
    state = str(record.get("lifecycle_state", "unknown"))
    source_path = record.get("current_source_path") or record.get("source_path") or record.get("source")
    mirror_path = record.get("mirror_path")
    previous_mirror_path = record.get("previous_mirror_path")
    previous_mirror_reason = record.get("previous_mirror_reason")
    source_exists = rel_exists(root, source_path)
    mirror_exists = rel_exists(root, mirror_path)
    previous_mirror_exists = rel_exists(root, previous_mirror_path)
    reasons: list[str] = []
    if state not in CLEAN_STATES:
        reasons.append(f"state={state}")
    if source_exists is False:
        reasons.append("source path missing")
    if mirror_exists is False and state != "planned":
        reasons.append("mirror path missing")
    if not reasons:
        return None
    return {
        "kind": "office",
        "id": record.get("source_id", ""),
        "state": state,
        "source": source_path or "",
        "target": mirror_path or "",
        "source_exists": source_exists,
        "target_exists": mirror_exists,
        "previous_target": previous_mirror_path if isinstance(previous_mirror_path, str) else "",
        "previous_target_exists": previous_mirror_exists,
        "previous_target_reason": previous_mirror_reason if isinstance(previous_mirror_reason, str) else "",
        "reasons": reasons,
        "action": OFFICE_ACTIONS.get(state, "Review the manifest record, then rerun plan/status before syncing."),
        "warnings": record.get("warnings") if isinstance(record.get("warnings"), list) else [],
        "errors": record.get("errors") if isinstance(record.get("errors"), list) else [],
    }


def repo_item(root: Path, record: dict) -> dict | None:
    state = str(record.get("lifecycle_state", "unknown"))
    note_path = record.get("note_path")
    note_exists = rel_exists(root, note_path)
    reasons: list[str] = []
    if state not in CLEAN_STATES:
        reasons.append(f"state={state}")
    if note_exists is False and state != "planned":
        reasons.append("repo mirror note missing")
    if not reasons:
        return None
    return {
        "kind": "repo",
        "id": record.get("repo_id", ""),
        "state": state,
        "source": record.get("configured_repo") or record.get("resolved_repo") or "",
        "target": note_path or "",
        "source_exists": None,
        "target_exists": note_exists,
        "reasons": reasons,
        "action": REPO_ACTIONS.get(state, "Review the manifest record, then rerun plan/status before syncing."),
        "warnings": record.get("warnings") if isinstance(record.get("warnings"), list) else [],
        "errors": record.get("errors") if isinstance(record.get("errors"), list) else [],
    }


def build_report(root: Path) -> tuple[list[dict], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    items: list[dict] = []
    source_records, source_errors = load_manifest(root, SOURCE_MANIFEST)
    repo_records, repo_errors = load_manifest(root, REPO_MANIFEST)
    latest_audit, audit_warnings = load_latest_audit_events(root)
    errors.extend(source_errors)
    errors.extend(repo_errors)
    warnings.extend(audit_warnings)
    if not source_records and not (root / SOURCE_MANIFEST).exists() and has_source_evidence(root):
        warnings.append(f"{SOURCE_MANIFEST.as_posix()} not found; run sync/status or restore it from backup.")
    if not repo_records and not (root / REPO_MANIFEST).exists() and has_repo_evidence(root):
        warnings.append(f"{REPO_MANIFEST.as_posix()} not found; repo recovery has no manifest evidence yet.")
    for record in source_records:
        item = office_item(root, record)
        if item:
            items.append(item)
    for record in repo_records:
        item = repo_item(root, record)
        if item:
            items.append(item)
    items.extend(stale_atomic_temp_items(root))
    for item in items:
        item["latest_audit"] = latest_audit.get(f"{item['kind']}:{item['id']}")
    return items, warnings, errors


def summary_counts(items: list[dict]) -> dict[str, int]:
    return {
        "total": len(items),
        "office": sum(1 for item in items if item["kind"] == "office"),
        "repo": sum(1 for item in items if item["kind"] == "repo"),
        "temp": sum(1 for item in items if item["kind"] == "temp"),
    }


def print_human(root: Path, items: list[dict], warnings: list[str], errors: list[str]) -> None:
    print(f"vaultwright recovery: {root}")
    for warning in warnings:
        print(f"  warning: {warning}")
    for error in errors:
        print(f"  error: {error}", file=sys.stderr)
    if errors:
        return
    if not items:
        print("recovery: no manifest records need operator action")
        return
    office_count = sum(1 for item in items if item["kind"] == "office")
    repo_count = sum(1 for item in items if item["kind"] == "repo")
    temp_count = sum(1 for item in items if item["kind"] == "temp")
    print(f"recovery: {len(items)} items need operator action (office={office_count}, repo={repo_count}, temp={temp_count})")
    for item in items:
        label = f"{item['kind']}:{item['state']}"
        print(f"  [{label:<28}] {item['source']} -> {item['target']}")
        previous_target = item.get("previous_target")
        if isinstance(previous_target, str) and previous_target:
            previous_exists = item.get("previous_target_exists")
            exists_label = "exists" if previous_exists is True else "missing" if previous_exists is False else "unknown"
            reason = item.get("previous_target_reason")
            reason_suffix = f" reason={reason}" if isinstance(reason, str) and reason else ""
            print(f"    previous target: {previous_target} ({exists_label}{reason_suffix})")
        print(f"    reasons: {', '.join(item['reasons'])}")
        print(f"    action: {item['action']}")
        for warning in item["warnings"][:3]:
            print(f"    warning: {warning}")
        for error in item["errors"][:3]:
            print(f"    error: {error}")
        audit = item.get("latest_audit")
        if isinstance(audit, dict):
            timestamp = audit.get("timestamp", "unknown-time")
            status = audit.get("status", "unknown-status")
            lifecycle = audit.get("lifecycle_state", "unknown-state")
            print(f"    latest audit: {timestamp} status={status} lifecycle={lifecycle}")
            for warning in audit.get("warnings", [])[:3]:
                print(f"    audit warning: {warning}")
            for error in audit.get("errors", [])[:3]:
                print(f"    audit error: {error}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print a read-only Vaultwright recovery checklist.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable recovery JSON.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    items, warnings, errors = build_report(ROOT)
    if args.json:
        print(json.dumps({
            "root": str(ROOT),
            "summary": summary_counts(items),
            "items": items,
            "warnings": warnings,
            "errors": errors,
        }, indent=2, sort_keys=True))
    else:
        print_human(ROOT, items, warnings, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
