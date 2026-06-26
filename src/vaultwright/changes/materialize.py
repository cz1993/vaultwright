# SPDX-License-Identifier: AGPL-3.0-or-later
"""Source-addressable materialization helpers for journaled changes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from vaultwright.changes.events import JournalEventError, normalize_vault_relative_path
from vaultwright.changes import stability
from vaultwright.mirrors import office as office_sync


class MaterializationError(ValueError):
    """Raised when a changed source cannot be materialized safely."""


def _source_record(manifest: dict, source_id: str) -> dict[str, Any] | None:
    for record in manifest.get("records", []):
        if isinstance(record, dict) and record.get("source_id") == source_id:
            return record
    return None


def _source_record_for_path(manifest: dict, source_path: str, source_id: str = "") -> dict[str, Any] | None:
    records = [record for record in manifest.get("records", []) if isinstance(record, dict)]
    if source_id:
        for record in records:
            if (
                record.get("source_id") == source_id
                and record.get("current_source_path") == source_path
            ):
                return record
        return None
    for record in records:
        if record.get("current_source_path") == source_path:
            return record
    return None


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": str(record.get("source_id", "") or ""),
        "current_source_path": str(record.get("current_source_path", "") or ""),
        "mirror_path": str(record.get("mirror_path", "") or ""),
        "source_format": str(record.get("source_format", "") or ""),
        "source_sha256": str(record.get("source_sha256", "") or ""),
        "lifecycle_state": str(record.get("lifecycle_state", "") or ""),
        "warnings": list(record.get("warnings", []) or []),
        "errors": list(record.get("errors", []) or []),
    }


def materialize_office_source(
    root: Path,
    source_path: str | Path,
    *,
    converter: Any | None = None,
    force: bool = False,
    dry_run: bool = False,
    include_pdf: bool | None = None,
    mirror_mode: str | None = None,
    mirror_root: str | None = None,
    converter_name: str = "markitdown",
    converter_version: str | None = None,
    append_audit: bool = True,
    settle: bool = False,
    settle_seconds: float = stability.DEFAULT_SETTLE_SECONDS,
    settle_check_interval_seconds: float = stability.DEFAULT_CHECK_INTERVAL_SECONDS,
    settle_timeout_seconds: float = stability.DEFAULT_TIMEOUT_SECONDS,
    stability_fingerprint_func: stability.FingerprintFunc | None = None,
    stability_clock: stability.ClockFunc | None = None,
    stability_sleeper: stability.SleepFunc | None = None,
) -> dict[str, Any]:
    """Materialize one Office/PDF source through the existing mirror engine.

    This is the Stage 1B worker-facing primitive: it accepts a vault-relative source path and
    delegates source identity, routing, lifecycle, atomic writes, annotation policy, and manifest
    updates to the package-owned Office mirror implementation.
    """

    root = root.expanduser().resolve()
    try:
        rel = normalize_vault_relative_path(source_path, field="source_path")
    except JournalEventError as exc:
        raise MaterializationError(str(exc)) from exc
    assert rel is not None

    try:
        mirror_config = office_sync.load_mirror_config(root, mirror_mode, mirror_root)
    except (OSError, ValueError) as exc:
        raise MaterializationError(f"invalid Office mirror configuration: {exc}") from exc

    source = root / rel
    supported_exts = set(office_sync.source_extensions(mirror_config, include_pdf))
    if source.suffix.lower() not in supported_exts:
        return {
            "kind": "office-source",
            "source_path": rel,
            "status": "skipped:unsupported-source",
            "action": "skip",
            "dry_run": dry_run,
            "manifest_written": False,
            "audit_appended": False,
            "record": {
                "source_id": "",
                "current_source_path": rel,
                "mirror_path": "",
                "source_format": source.suffix.lstrip(".").lower(),
                "source_sha256": "",
                "lifecycle_state": "unsupported",
                "warnings": ["Source extension is not handled by Office mirror materialization."],
                "errors": [],
            },
        }

    stability_result = None
    if settle:
        stability_result = stability.wait_for_file_stability(
            root,
            rel,
            settle_seconds=settle_seconds,
            check_interval_seconds=settle_check_interval_seconds,
            timeout_seconds=settle_timeout_seconds,
            **({"fingerprint_func": stability_fingerprint_func} if stability_fingerprint_func else {}),
            **({"clock": stability_clock} if stability_clock else {}),
            **({"sleeper": stability_sleeper} if stability_sleeper else {}),
        )
        if not stability_result.stable:
            return {
                "kind": "office-source",
                "source_path": rel,
                "status": "skipped:unstable-source",
                "action": "stabilizing",
                "dry_run": dry_run,
                "manifest_written": False,
                "audit_appended": False,
                "stability": stability_result.as_dict(),
                "record": {
                    "source_id": "",
                    "current_source_path": rel,
                    "mirror_path": "",
                    "source_format": source.suffix.lstrip(".").lower(),
                    "source_sha256": "",
                    "lifecycle_state": "stabilizing",
                    "warnings": ["Source did not remain metadata-stable before the settle timeout."],
                    "errors": [],
                },
            }

    manifest = office_sync.load_source_manifest(root)
    routing = office_sync.load_domain_routing(root)
    active_converter = converter if converter is not None else office_sync.MarkItDown()
    active_converter_version = converter_version or office_sync.markitdown_version()
    plan = office_sync.plan_one(
        source,
        root,
        mirror_config,
        routing,
        manifest,
        converter_name,
        active_converter_version,
    )
    source_id = str(plan["record"]["source_id"])
    status = office_sync.sync_one(
        source,
        root,
        active_converter,
        force,
        dry_run,
        mirror_config,
        routing,
        manifest,
        converter_name,
        active_converter_version,
        plan=plan,
    )
    record = _source_record(manifest, source_id) or plan["record"]
    manifest_written = False
    audit_appended = False
    if not dry_run:
        manifest_written = office_sync.write_source_manifest(root, manifest)
        if append_audit:
            office_sync.append_audit(root, office_sync.sync_audit_event(root, plan, manifest, status))
            audit_appended = True

    return {
        "kind": "office-source",
        "source_path": rel,
        "status": status,
        "action": str(plan.get("action", "")),
        "dry_run": dry_run,
        "manifest_written": manifest_written,
        "audit_appended": audit_appended,
        "stability": stability_result.as_dict() if stability_result else None,
        "record": _public_record(record),
    }


def materialize_office_delete(
    root: Path,
    previous_path: str | Path,
    *,
    source_id: str = "",
    source_sha256: str = "",
    append_audit: bool = True,
) -> dict[str, Any]:
    """Apply one missing-source journal event without deleting retained mirrors."""

    root = root.expanduser().resolve()
    try:
        rel = normalize_vault_relative_path(previous_path, field="previous_path")
    except JournalEventError as exc:
        raise MaterializationError(str(exc)) from exc
    assert rel is not None

    manifest = office_sync.load_source_manifest(root)
    record = _source_record_for_path(manifest, rel, source_id=source_id)
    if record is None:
        return {
            "kind": "office-source-delete",
            "source_path": rel,
            "status": "skipped:missing-manifest-record",
            "action": "review",
            "manifest_written": False,
            "audit_appended": False,
            "record": {
                "source_id": source_id,
                "current_source_path": rel,
                "mirror_path": "",
                "source_format": Path(rel).suffix.lstrip(".").lower(),
                "source_sha256": source_sha256,
                "lifecycle_state": "review-required",
                "warnings": ["Deleted source event has no matching source manifest record."],
                "errors": [],
            },
        }
    if (root / rel).exists():
        return {
            "kind": "office-source-delete",
            "source_path": rel,
            "status": "skipped:source-present",
            "action": "review",
            "manifest_written": False,
            "audit_appended": False,
            "record": _public_record(record),
        }

    updated = dict(record)
    updated["lifecycle_state"] = "source_missing"
    updated.update(office_sync.lifecycle_record_metadata(root))
    updated["warnings"] = office_sync.unique_list(
        (updated.get("warnings") or [])
        + ["Source file is missing; mirror was retained for review."]
    )
    updated["errors"] = []
    office_sync.upsert_manifest_record(manifest, updated)
    manifest_written = office_sync.write_source_manifest(root, manifest)
    audit_appended = False
    if append_audit:
        office_sync.append_audit(
            root,
            office_sync.sync_audit_event(root, {"record": updated}, manifest, "source_missing"),
        )
        audit_appended = True

    return {
        "kind": "office-source-delete",
        "source_path": rel,
        "status": "source-missing",
        "action": "source_missing",
        "manifest_written": manifest_written,
        "audit_appended": audit_appended,
        "record": _public_record(updated),
    }
