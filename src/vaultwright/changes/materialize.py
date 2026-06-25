# SPDX-License-Identifier: AGPL-3.0-or-later
"""Source-addressable materialization helpers for journaled changes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from vaultwright.changes.events import JournalEventError, normalize_vault_relative_path
from vaultwright.mirrors import office as office_sync


class MaterializationError(ValueError):
    """Raised when a changed source cannot be materialized safely."""


def _source_record(manifest: dict, source_id: str) -> dict[str, Any] | None:
    for record in manifest.get("records", []):
        if isinstance(record, dict) and record.get("source_id") == source_id:
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
        "record": _public_record(record),
    }
