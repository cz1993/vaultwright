#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Print a read-only recovery checklist from Vaultwright manifests."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - exercised in installed vaults, not unit env
    yaml = None


DEFAULT_ROOT = Path.cwd()
SOURCE_MANIFEST = Path("_meta/source-manifest.json")
REPO_MANIFEST = Path("_meta/repo-manifest.json")
AUDIT_LOG = Path("_meta/sync-audit.jsonl")
REPO_CONFIG = Path("tools/repos.yml")
LIFECYCLE_CONTRACT = Path("_meta/lifecycle-states.yml")
CLEAN_STATES = {"clean", "reviewed"}
SOURCE_EXTS = {".docx", ".pptx", ".xlsx", ".doc", ".pdf"}
EXCLUDED_PARTS = {"_mirrors", "_templates", "_tmp", "tools", "node_modules", ".git"}
TEMP_EXCLUDED_PARTS = {"_templates", "_tmp", "tools", "node_modules", ".git"}
ATOMIC_TEMP_RE = re.compile(r"^\..+\.\d+\.tmp$")

OFFICE_ACTIONS = {
    "planned": "Run plan review, then sync to create the generated mirror.",
    "source_changed": "Run sync to refresh the generated region, then review linked curated notes.",
    "source_moved": "Confirm the move is intentional, migrate/archive any old mirror annotations, then run sync to update the mirror path.",
    "stale": "Run sync before relying on the mirror; the source or configuration is newer.",
    "converter_changed": "Review conversion quality, then sync if the new converter output is acceptable.",
    "unsupported": "Keep the original as source of truth; convert manually or use a supported format.",
    "source_missing": "Locate, restore, or intentionally archive the source before changing the retained mirror.",
    "manual_modification": "Migrate legacy annotations or preserve human edits in curated notes before forcing regeneration.",
    "conflict": "Resolve the mirror/source identity conflict before syncing.",
    "error": "Fix the reported error, then rerun plan/status before syncing.",
}

REPO_ACTIONS = {
    "planned": "Run plan review, then sync to create the repo mirror.",
    "repo_changed": "Run sync to refresh README/docs/metadata, then review curated notes.",
    "stale": "Run sync before relying on the mirror; the repo or configuration is newer.",
    "unreachable": "Check repo spelling, network access, and GitHub auth; existing mirror content is retained.",
    "repo_unconfigured": "Confirm whether the repo mirror is retired, restore its repos.yml entry, or archive/remove the mirror deliberately.",
    "manual_modification": "Migrate legacy annotations or preserve human edits in curated notes before forcing regeneration.",
    "conflict": "Resolve the target note/repo identity conflict before syncing.",
    "error": "Fix the reported error, then rerun plan/status before syncing.",
}

TEMP_ACTION = (
    "Rerun status/sync to confirm the canonical generated file is complete, then remove the stale "
    "temp file after backup review."
)
AMBIGUOUS_CANDIDATE_DISPLAY_LIMIT = 5
UNCONFIGURED_REPO_WARNING = (
    "Repo config entry is missing; retained repo mirror is no longer governed by tools/repos.yml."
)


def unique_list(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def repo_id_for(repo: str, note: str) -> str:
    digest = hashlib.sha256(f"{repo}\0{note}".encode("utf-8")).hexdigest()[:20]
    return f"repo_{digest}"


def rel_exists(root: Path, value: object) -> bool | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return None
    return (root / path).exists()


def ambiguous_candidate_summary(candidates: list[str], limit: int = AMBIGUOUS_CANDIDATE_DISPLAY_LIMIT) -> str:
    shown = candidates[:limit]
    suffix = f" (+{len(candidates) - len(shown)} more; use --json for full list)" if len(candidates) > len(shown) else ""
    return f"{len(candidates)} candidate(s): " + ", ".join(shown) + suffix


def source_id_summary(source_ids: list[str], limit: int = AMBIGUOUS_CANDIDATE_DISPLAY_LIMIT) -> str:
    shown = source_ids[:limit]
    suffix = f" (+{len(source_ids) - len(shown)} more; use --json for full list)" if len(source_ids) > len(shown) else ""
    return f"{len(source_ids)} source_id(s): " + ", ".join(shown) + suffix


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


def load_lifecycle_contract(root: Path) -> tuple[dict[str, dict[str, dict]], list[str]]:
    path = root / LIFECYCLE_CONTRACT
    if not path.exists():
        return {}, [f"{LIFECYCLE_CONTRACT.as_posix()} not found; recovery will use fallback action text only."]
    if yaml is None:
        return {}, ["PyYAML unavailable; lifecycle contract guidance skipped."]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return {}, [f"{LIFECYCLE_CONTRACT.as_posix()}: invalid YAML; lifecycle guidance skipped ({exc.__class__.__name__})."]
    except UnicodeDecodeError:
        return {}, [f"{LIFECYCLE_CONTRACT.as_posix()}: unreadable text; lifecycle guidance skipped."]
    if not isinstance(data, dict):
        return {}, [f"{LIFECYCLE_CONTRACT.as_posix()}: contract must be a mapping; lifecycle guidance skipped."]
    contract: dict[str, dict[str, dict]] = {}
    warnings: list[str] = []
    for section in ("office", "repo"):
        states = data.get(section)
        if not isinstance(states, dict):
            warnings.append(f"{LIFECYCLE_CONTRACT.as_posix()}: missing {section} lifecycle states.")
            continue
        contract[section] = {str(state): spec for state, spec in states.items() if isinstance(spec, dict)}
    return contract, warnings


def lifecycle_contract_for(item: dict, contract: dict[str, dict[str, dict]]) -> dict | None:
    kind = str(item.get("kind", ""))
    if kind not in {"office", "repo"}:
        return None
    state = str(item.get("state", ""))
    spec = contract.get(kind, {}).get(state)
    if not isinstance(spec, dict):
        return None
    actions = spec.get("permitted_next_actions")
    if not isinstance(actions, list):
        actions = []
    return {
        "entry_condition": str(spec.get("entry_condition", "") or ""),
        "explanation": str(spec.get("explanation", "") or ""),
        "permitted_next_actions": [str(action) for action in actions if str(action).strip()],
        "exit_condition": str(spec.get("exit_condition", "") or ""),
        "manifest_state": bool(spec.get("manifest_state", False)),
    }


def enrich_lifecycle_items(items: list[dict], contract: dict[str, dict[str, dict]]) -> None:
    for item in items:
        lifecycle = lifecycle_contract_for(item, contract)
        if lifecycle:
            item["lifecycle"] = lifecycle


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
    repos_yml = root / REPO_CONFIG
    if not repos_yml.exists():
        return False
    for line in repos_yml.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if stripped.startswith("- repo:"):
            return True
    return False


def configured_repo_ids(root: Path) -> tuple[set[str] | None, list[str]]:
    config_path = root / REPO_CONFIG
    if not config_path.exists():
        return set(), []
    if yaml is None:
        return None, ["PyYAML unavailable; repo config comparison skipped."]
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return None, [f"{REPO_CONFIG.as_posix()}: invalid YAML; repo config comparison skipped ({exc.__class__.__name__})."]
    if not isinstance(data, dict):
        return None, [f"{REPO_CONFIG.as_posix()}: config must be a mapping; repo config comparison skipped."]
    repos = data.get("repos", [])
    if repos is None:
        repos = []
    if not isinstance(repos, list):
        return None, [f"{REPO_CONFIG.as_posix()}: repos must be a list; repo config comparison skipped."]
    repo_ids: set[str] = set()
    warnings: list[str] = []
    for index, entry in enumerate(repos):
        if not isinstance(entry, dict):
            warnings.append(f"{REPO_CONFIG.as_posix()}: repos[{index}] is not a mapping; skipped for config comparison.")
            continue
        repo = entry.get("repo")
        note = entry.get("note")
        if not isinstance(repo, str) or not repo.strip() or not isinstance(note, str) or not note.strip():
            warnings.append(
                f"{REPO_CONFIG.as_posix()}: repos[{index}] needs repo and note for config comparison; skipped."
            )
            continue
        repo_ids.add(repo_id_for(repo.strip(), note.strip()))
    return repo_ids, warnings


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
    ambiguous_move_candidates = record.get("ambiguous_move_candidates")
    if not isinstance(ambiguous_move_candidates, list):
        ambiguous_move_candidates = []
    ambiguous_move_candidates = [str(candidate) for candidate in ambiguous_move_candidates if str(candidate)]
    duplicate_source_ids = record.get("duplicate_source_ids")
    if not isinstance(duplicate_source_ids, list):
        duplicate_source_ids = []
    duplicate_source_ids = [str(source_id) for source_id in duplicate_source_ids if str(source_id)]
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
        "ambiguous_move_candidates": ambiguous_move_candidates,
        "duplicate_source_ids": duplicate_source_ids,
        "reasons": reasons,
        "action": OFFICE_ACTIONS.get(state, "Review the manifest record, then rerun plan/status before syncing."),
        "warnings": record.get("warnings") if isinstance(record.get("warnings"), list) else [],
        "errors": record.get("errors") if isinstance(record.get("errors"), list) else [],
    }


def repo_item(root: Path, record: dict, configured_ids: set[str] | None = None) -> dict | None:
    manifest_state = str(record.get("lifecycle_state", "unknown"))
    state = manifest_state
    repo_id = record.get("repo_id")
    config_missing = (
        configured_ids is not None
        and isinstance(repo_id, str)
        and bool(repo_id)
        and repo_id not in configured_ids
    )
    if config_missing:
        state = "repo_unconfigured"
    note_path = record.get("note_path")
    note_exists = rel_exists(root, note_path)
    reasons: list[str] = []
    if state not in CLEAN_STATES:
        reasons.append(f"state={state}")
    if config_missing:
        reasons.append("repo config entry missing")
        if manifest_state != state:
            reasons.append(f"manifest_state={manifest_state}")
    if note_exists is False and state != "planned":
        reasons.append("repo mirror note missing")
    if not reasons:
        return None
    warnings = record.get("warnings") if isinstance(record.get("warnings"), list) else []
    if config_missing:
        warnings = unique_list([*warnings, UNCONFIGURED_REPO_WARNING])
    return {
        "kind": "repo",
        "id": repo_id or "",
        "state": state,
        "manifest_state": manifest_state,
        "source": record.get("configured_repo") or record.get("resolved_repo") or "",
        "target": note_path or "",
        "source_exists": None,
        "target_exists": note_exists,
        "reasons": reasons,
        "action": REPO_ACTIONS.get(state, "Review the manifest record, then rerun plan/status before syncing."),
        "warnings": warnings,
        "errors": record.get("errors") if isinstance(record.get("errors"), list) else [],
    }


def build_report(root: Path) -> tuple[list[dict], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    items: list[dict] = []
    source_records, source_errors = load_manifest(root, SOURCE_MANIFEST)
    repo_records, repo_errors = load_manifest(root, REPO_MANIFEST)
    lifecycle_contract, lifecycle_warnings = load_lifecycle_contract(root)
    latest_audit, audit_warnings = load_latest_audit_events(root)
    configured_ids, config_warnings = configured_repo_ids(root)
    errors.extend(source_errors)
    errors.extend(repo_errors)
    warnings.extend(lifecycle_warnings)
    warnings.extend(audit_warnings)
    warnings.extend(config_warnings)
    if not source_records and not (root / SOURCE_MANIFEST).exists() and has_source_evidence(root):
        warnings.append(f"{SOURCE_MANIFEST.as_posix()} not found; run sync/status or restore it from backup.")
    if not repo_records and not (root / REPO_MANIFEST).exists() and has_repo_evidence(root):
        warnings.append(f"{REPO_MANIFEST.as_posix()} not found; repo recovery has no manifest evidence yet.")
    if repo_records and configured_ids is not None and not (root / REPO_CONFIG).exists():
        warnings.append(f"{REPO_CONFIG.as_posix()} not found; manifest-backed repo mirrors need config review.")
    for record in source_records:
        item = office_item(root, record)
        if item:
            items.append(item)
    for record in repo_records:
        item = repo_item(root, record, configured_ids)
        if item:
            items.append(item)
    items.extend(stale_atomic_temp_items(root))
    enrich_lifecycle_items(items, lifecycle_contract)
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


def md_escape(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def lifecycle_text(item: dict, key: str) -> str:
    lifecycle = item.get("lifecycle")
    if not isinstance(lifecycle, dict):
        return ""
    value = lifecycle.get(key)
    return value if isinstance(value, str) else ""


def lifecycle_actions(item: dict) -> list[str]:
    lifecycle = item.get("lifecycle")
    if not isinstance(lifecycle, dict):
        return []
    actions = lifecycle.get("permitted_next_actions")
    if not isinstance(actions, list):
        return []
    return [str(action) for action in actions if str(action).strip()]


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
    item_word = "item" if len(items) == 1 else "items"
    verb = "needs" if len(items) == 1 else "need"
    print(f"recovery: {len(items)} {item_word} {verb} operator action (office={office_count}, repo={repo_count}, temp={temp_count})")
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
        candidates = item.get("ambiguous_move_candidates")
        if isinstance(candidates, list) and candidates:
            print(f"    ambiguous move candidates: {ambiguous_candidate_summary([str(candidate) for candidate in candidates])}")
        duplicate_source_ids = item.get("duplicate_source_ids")
        if isinstance(duplicate_source_ids, list) and duplicate_source_ids:
            print(f"    duplicate source IDs: {source_id_summary([str(source_id) for source_id in duplicate_source_ids])}")
        print(f"    reasons: {', '.join(item['reasons'])}")
        print(f"    action: {item['action']}")
        explanation = lifecycle_text(item, "explanation")
        if explanation:
            print(f"    state explanation: {explanation}")
        exit_condition = lifecycle_text(item, "exit_condition")
        if exit_condition:
            print(f"    exit condition: {exit_condition}")
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


def print_worksheet(root: Path, items: list[dict], warnings: list[str], errors: list[str]) -> None:
    summary = summary_counts(items)
    print("# Vaultwright Recovery Worksheet")
    print()
    print("Generated by `vaultwright recovery --worksheet`. Read-only; no files were changed.")
    print()
    print("## Summary")
    print()
    print(f"- Vault root: `{md_escape(root)}`")
    print(
        "- Recovery items needing operator action: "
        f"{summary['total']} (office={summary['office']}, repo={summary['repo']}, temp={summary['temp']})"
    )
    print()
    if warnings or errors:
        print("## Preflight Notes")
        print()
        for warning in warnings:
            print(f"- Warning: {md_escape(warning)}")
        for error in errors:
            print(f"- Error: {md_escape(error)}")
        print()
    print("## Review Protocol")
    print()
    print("- Confirm the copied vault is backed up before changing files.")
    print("- Resolve one item at a time, then rerun `vaultwright status` and `vaultwright recovery`.")
    print("- Preserve or archive retained generated mirrors before regenerating moved or conflicted paths.")
    print("- For manual modifications, migrate legacy annotations or preserve human edits in curated notes before forcing regeneration.")
    print("- For unreachable repos, verify repo identity, network access, and GitHub auth before editing mirrors.")
    print("- For unconfigured repos, confirm retirement before archiving mirrors or removing manifest records.")
    print("- Run `vaultwright catalog` and `vaultwright lint` after recovery work is complete.")
    print()
    print("## Recovery Item Checklist")
    print()
    if not items:
        print("- [ ] No manifest records need operator action.")
        print()
        return
    for item in items:
        label = f"{item['kind']}:{item['state']}"
        source = item.get("source") or ""
        target = item.get("target") or ""
        print(f"- [ ] `{md_escape(label)}` `{md_escape(item.get('id') or target or 'untracked-temp')}`")
        if source:
            print(f"  - Source: `{md_escape(source)}`")
        if target:
            print(f"  - Target: `{md_escape(target)}`")
        previous_target = item.get("previous_target")
        if isinstance(previous_target, str) and previous_target:
            previous_exists = item.get("previous_target_exists")
            exists_label = "exists" if previous_exists is True else "missing" if previous_exists is False else "unknown"
            reason = item.get("previous_target_reason")
            reason_suffix = f"; reason={reason}" if isinstance(reason, str) and reason else ""
            print(f"  - Previous target: `{md_escape(previous_target)}` ({exists_label}{md_escape(reason_suffix)})")
        candidates = item.get("ambiguous_move_candidates")
        if isinstance(candidates, list) and candidates:
            print(
                "  - Ambiguous move candidates: "
                f"{md_escape(ambiguous_candidate_summary([str(candidate) for candidate in candidates]))}"
            )
        duplicate_source_ids = item.get("duplicate_source_ids")
        if isinstance(duplicate_source_ids, list) and duplicate_source_ids:
            print(
                "  - Duplicate source IDs: "
                f"{md_escape(source_id_summary([str(source_id) for source_id in duplicate_source_ids]))}"
            )
        print(f"  - Reasons: {md_escape(', '.join(item['reasons']))}")
        print(f"  - Action: {md_escape(item['action'])}")
        explanation = lifecycle_text(item, "explanation")
        if explanation:
            print(f"  - State explanation: {md_escape(explanation)}")
        next_actions = lifecycle_actions(item)
        if next_actions:
            print("  - Contract next actions:")
            for action in next_actions:
                print(f"    - {md_escape(action)}")
        exit_condition = lifecycle_text(item, "exit_condition")
        if exit_condition:
            print(f"  - Exit condition: {md_escape(exit_condition)}")
        for warning in item["warnings"][:3]:
            print(f"  - Warning: {md_escape(warning)}")
        for error in item["errors"][:3]:
            print(f"  - Error: {md_escape(error)}")
        audit = item.get("latest_audit")
        if isinstance(audit, dict):
            timestamp = audit.get("timestamp", "unknown-time")
            status = audit.get("status", "unknown-status")
            lifecycle = audit.get("lifecycle_state", "unknown-state")
            print(
                "  - Latest audit: "
                f"{md_escape(timestamp)} status={md_escape(status)} lifecycle={md_escape(lifecycle)}"
            )
            for warning in audit.get("warnings", [])[:3]:
                print(f"  - Audit warning: {md_escape(warning)}")
            for error in audit.get("errors", [])[:3]:
                print(f"  - Audit error: {md_escape(error)}")
    print()


def items_with_state(items: list[dict], *, kind: str | None = None, states: set[str] | None = None) -> list[dict]:
    selected: list[dict] = []
    for item in items:
        if kind and item.get("kind") != kind:
            continue
        if states and item.get("state") not in states:
            continue
        selected.append(item)
    return selected


def print_runbook_item(item: dict, *, mode: str) -> None:
    item_id = md_escape(item.get("id") or item.get("target") or "untracked-temp")
    source = md_escape(item.get("source") or "")
    target = md_escape(item.get("target") or "")
    previous = item.get("previous_target")
    if mode == "source_missing":
        print(f"- [ ] `{item_id}`: restore or retire `{source}`")
        if target:
            print(f"  - Retained mirror: `{target}`")
    elif mode == "source_moved":
        previous_text = md_escape(previous or "previous generated mirror")
        print(f"- [ ] `{item_id}`: review previous mirror `{previous_text}` before regenerating `{target}`")
        if source:
            print(f"  - Current source path: `{source}`")
    elif mode == "repo_unconfigured":
        print(f"- [ ] `{item_id}`: restore config or retire `{target}`")
        if source:
            print(f"  - Repo identity: `{source}`")
    elif mode == "manual_modification":
        print(f"- [ ] `{item_id}`: preserve human edits before regenerating `{target}`")
        if source:
            print(f"  - Source: `{source}`")
    elif mode == "temp":
        expected = md_escape(item.get("expected_target") or "")
        print(f"- [ ] `{target}`: verify canonical target `{expected}` before removing temp file")
    else:
        label = md_escape(f"{item.get('kind')}:{item.get('state')}")
        print(f"- [ ] `{label}` `{item_id}`: resolve blockers for `{target}`")
        if source:
            print(f"  - Source: `{source}`")
    reasons = item.get("reasons")
    if isinstance(reasons, list) and reasons:
        print(f"  - Reasons: {md_escape(', '.join(str(reason) for reason in reasons))}")
    action = item.get("action")
    if isinstance(action, str) and action:
        print(f"  - Fallback action: {md_escape(action)}")
    candidates = item.get("ambiguous_move_candidates")
    if isinstance(candidates, list) and candidates:
        print(
            "  - Ambiguous candidates: "
            f"{md_escape(ambiguous_candidate_summary([str(candidate) for candidate in candidates]))}"
        )
    duplicate_source_ids = item.get("duplicate_source_ids")
    if isinstance(duplicate_source_ids, list) and duplicate_source_ids:
        print(
            "  - Duplicate source IDs: "
            f"{md_escape(source_id_summary([str(source_id) for source_id in duplicate_source_ids]))}"
        )
    audit = item.get("latest_audit")
    if isinstance(audit, dict):
        timestamp = audit.get("timestamp", "unknown-time")
        status = audit.get("status", "unknown-status")
        print(f"  - Latest audit: {md_escape(timestamp)} status={md_escape(status)}")


def print_runbook_section(
    title: str,
    items: list[dict],
    *,
    mode: str,
    protocol: list[str],
    empty: str,
) -> None:
    print(f"## {title}")
    print()
    for step in protocol:
        print(f"- {step}")
    print()
    if not items:
        print(f"- [ ] {empty}")
        print()
        return
    for item in items:
        print_runbook_item(item, mode=mode)
    print()


def print_runbook(root: Path, items: list[dict], warnings: list[str], errors: list[str]) -> None:
    summary = summary_counts(items)
    source_missing = items_with_state(items, kind="office", states={"source_missing"})
    source_moved = items_with_state(items, kind="office", states={"source_moved"})
    repo_unconfigured = items_with_state(items, kind="repo", states={"repo_unconfigured"})
    manual_modification = items_with_state(items, states={"manual_modification"})
    conflicts = items_with_state(items, states={"conflict", "error"})
    temp_items = items_with_state(items, kind="temp", states={"interrupted_write"})

    print("# Vaultwright Recovery Runbook")
    print()
    print("Generated by `vaultwright recovery --runbook`. Read-only; no files were changed.")
    print()
    print("## Summary")
    print()
    print(f"- Vault root: `{md_escape(root)}`")
    print(
        "- Recovery items needing operator action: "
        f"{summary['total']} (office={summary['office']}, repo={summary['repo']}, temp={summary['temp']})"
    )
    print(f"- Source missing queue: {len(source_missing)}")
    print(f"- Source move queue: {len(source_moved)}")
    print(f"- Repo config queue: {len(repo_unconfigured)}")
    print(f"- Manual/generated-region review queue: {len(manual_modification)}")
    print(f"- Conflict/error queue: {len(conflicts)}")
    print(f"- Interrupted-write temp queue: {len(temp_items)}")
    print()
    if warnings or errors:
        print("## Preflight Notes")
        print()
        for warning in warnings:
            print(f"- Warning: {md_escape(warning)}")
        for error in errors:
            print(f"- Error: {md_escape(error)}")
        print()
    print("## Execution Rules")
    print()
    print("- Work in a copied vault or verified backup before changing mirrors, manifests, or config.")
    print("- Resolve one recovery class at a time; do not combine source moves, repo retirements, and manual edits in one batch.")
    print("- Treat original Office files and source repos as authoritative; generated markdown is replaceable evidence.")
    print("- Migrate legacy mirror annotations before deleting, moving, or regenerating mirrors.")
    print("- After every batch, rerun `vaultwright status`, `vaultwright recovery`, `vaultwright catalog`, and `vaultwright lint`.")
    print()

    print_runbook_section(
        "Source Missing Resolution",
        source_missing,
        mode="source_missing",
        protocol=[
            "Locate the original source in the source collection, cloud version history, Git history, or backup.",
            "If the source still belongs in the vault, restore it to the manifest path and rerun sync/status.",
            "If the source was intentionally retired, migrate any legacy mirror annotations before archiving the mirror and retiring manifest state.",
        ],
        empty="No source_missing Office records in the current recovery queue.",
    )
    print_runbook_section(
        "Source Move Resolution",
        source_moved,
        mode="source_moved",
        protocol=[
            "Confirm the current source path is the intended successor for the prior manifest source path.",
            "Open the previous generated mirror and migrate any legacy annotations before archive, move, or removal.",
            "Rerun status after the previous mirror is resolved; sync only after the move is no longer blocked.",
        ],
        empty="No source_moved Office records in the current recovery queue.",
    )
    print_runbook_section(
        "Repo Config Resolution",
        repo_unconfigured,
        mode="repo_unconfigured",
        protocol=[
            "Decide whether each retained repo mirror remains governed or is intentionally retired.",
            "If governed, restore the matching `tools/repos.yml` entry and rerun repo sync/status.",
            "If retired, migrate legacy annotations before archiving/removing the mirror and retiring manifest state.",
        ],
        empty="No repo_unconfigured records in the current recovery queue.",
    )
    print_runbook_section(
        "Manual Generated Region Resolution",
        manual_modification,
        mode="manual_modification",
        protocol=[
            "Inspect content below the generated sentinel without assuming it is safe to keep.",
            "Move real human notes into a curated note or run `vaultwright migrate annotations --write` before regeneration.",
            "Only force regeneration after the generated region is backed up or confirmed disposable.",
        ],
        empty="No manual_modification records in the current recovery queue.",
    )
    print_runbook_section(
        "Conflict And Error Resolution",
        conflicts,
        mode="conflict",
        protocol=[
            "Read the manifest reasons, warnings, errors, duplicate source IDs, and ambiguous move candidates.",
            "Resolve ownership or identity evidence manually before rerunning sync.",
            "Do not use `--force` for ambiguous source moves, duplicate source IDs, missing sentinels, or write/conversion errors.",
        ],
        empty="No conflict or error records in the current recovery queue.",
    )
    print_runbook_section(
        "Interrupted Write Cleanup",
        temp_items,
        mode="temp",
        protocol=[
            "Rerun status/sync first so the canonical generated file and manifest are current.",
            "Compare the temp file only as diagnostic evidence; do not treat it as authoritative.",
            "Remove the temp file after backup review and a clean recovery report.",
        ],
        empty="No stale atomic temp files in the current recovery queue.",
    )
    print("## Verification Gate")
    print()
    print("- [ ] `vaultwright status` shows no unexpected review-blocking states.")
    print("- [ ] `vaultwright recovery` reports no remaining operator-action items or only accepted deferrals.")
    print("- [ ] `vaultwright catalog --check` passes after catalog regeneration.")
    print("- [ ] `vaultwright lint` passes.")
    print("- [ ] Private pilot notes record what was restored, archived, retired, or regenerated.")
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print a read-only Vaultwright recovery checklist.")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Print machine-readable recovery JSON.")
    output.add_argument("--worksheet", action="store_true", help="Print a Markdown recovery review worksheet.")
    output.add_argument("--runbook", action="store_true", help="Print a Markdown recovery resolution runbook.")
    return parser


def main(argv: list[str] | None = None, root: Path | None = None) -> int:
    args = build_parser().parse_args(argv)
    active_root = (root or DEFAULT_ROOT).expanduser().resolve()
    items, warnings, errors = build_report(active_root)
    if args.json:
        print(json.dumps({
            "root": str(active_root),
            "summary": summary_counts(items),
            "items": items,
            "warnings": warnings,
            "errors": errors,
        }, indent=2, sort_keys=True))
    elif args.worksheet:
        print_worksheet(active_root, items, warnings, errors)
    elif args.runbook:
        print_runbook(active_root, items, warnings, errors)
    else:
        print_human(active_root, items, warnings, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
