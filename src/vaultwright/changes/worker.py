# SPDX-License-Identifier: AGPL-3.0-or-later
"""Lease-protected changed-source worker primitives."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from vaultwright.changes import journal, materialize

MaterializeFunc = Callable[..., dict[str, Any]]

APPLIED_MATERIALIZATION_STATUSES = ("created", "updated", "unchanged")
REVIEW_MATERIALIZATION_PREFIXES = ("skipped:",)
FAILED_MATERIALIZATION_PREFIXES = ("error:",)


class WorkerError(ValueError):
    """Raised when a worker cannot safely process a journal event."""


def _finish_status(materialization_status: str) -> tuple[str, str]:
    if materialization_status in APPLIED_MATERIALIZATION_STATUSES:
        return "applied", ""
    if materialization_status == "skipped:unstable-source":
        return "failed", "source did not remain stable before materialization"
    if materialization_status.startswith(FAILED_MATERIALIZATION_PREFIXES):
        return "failed", materialization_status
    if materialization_status.startswith(REVIEW_MATERIALIZATION_PREFIXES):
        return "review-required", materialization_status
    return "failed", f"unexpected materialization status: {materialization_status}"


def _record_identity(result: dict[str, Any]) -> tuple[str, str]:
    record = result.get("record")
    if not isinstance(record, dict):
        return "", ""
    return str(record.get("source_id", "") or ""), str(record.get("source_sha256", "") or "")


def _unsupported_event_result(event: dict[str, Any], detail: str) -> dict[str, Any]:
    return {
        "kind": "journal-event",
        "source_path": str(event.get("current_path") or ""),
        "status": "skipped:unsupported-event",
        "action": "review",
        "record": {
            "source_id": str(event.get("source_id") or ""),
            "current_source_path": str(event.get("current_path") or ""),
            "mirror_path": "",
            "source_format": "",
            "source_sha256": str(event.get("source_sha256") or ""),
            "lifecycle_state": "review-required",
            "warnings": [detail],
            "errors": [],
        },
    }


def process_claimed_event(
    root: Path,
    holder: str,
    event: dict[str, Any],
    *,
    workspace_id: str = journal.DEFAULT_WORKSPACE_ID,
    now: str | None = None,
    materialize_func: MaterializeFunc = materialize.materialize_office_source,
    materialize_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sequence = int(event["sequence"])
    current_path = event.get("current_path")
    if not current_path:
        detail = f"{event.get('event_kind', 'unknown')} event has no current path for materialization"
        result = _unsupported_event_result(event, detail)
        journal.finish_claimed_event(
            root,
            holder,
            sequence,
            "review-required",
            error_summary=detail,
            workspace_id=workspace_id,
            now=now,
        )
        return {
            "processed": True,
            "event": event,
            "finish_status": "review-required",
            "error_summary": detail,
            "materialization": result,
        }

    try:
        result = materialize_func(root, current_path, **(materialize_kwargs or {}))
    except Exception as exc:
        summary = f"{exc.__class__.__name__}: {str(exc)[:160]}"
        journal.finish_claimed_event(
            root,
            holder,
            sequence,
            "failed",
            error_summary=summary,
            workspace_id=workspace_id,
            now=now,
        )
        return {
            "processed": True,
            "event": event,
            "finish_status": "failed",
            "error_summary": summary,
            "materialization": None,
        }

    finish_status, error_summary = _finish_status(str(result.get("status", "")))
    source_id, source_sha256 = _record_identity(result)
    journal.finish_claimed_event(
        root,
        holder,
        sequence,
        finish_status,
        error_summary=error_summary,
        source_id=source_id,
        source_sha256=source_sha256,
        workspace_id=workspace_id,
        now=now,
    )
    return {
        "processed": True,
        "event": event,
        "finish_status": finish_status,
        "error_summary": error_summary,
        "materialization": result,
    }


def process_next_event(
    root: Path,
    holder: str,
    *,
    workspace_id: str = journal.DEFAULT_WORKSPACE_ID,
    lease_ttl_seconds: int = 300,
    now: str | None = None,
    release_lease: bool = True,
    materialize_func: MaterializeFunc = materialize.materialize_office_source,
    materialize_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lease = journal.acquire_worker_lease(
        root,
        holder,
        ttl_seconds=lease_ttl_seconds,
        workspace_id=workspace_id,
        now=now,
    )
    if not lease["acquired"]:
        return {"acquired": False, "processed": False, "lease": lease, "event": None}

    try:
        event = journal.claim_next_event(root, holder, workspace_id=workspace_id, now=now)
        if event is None:
            return {"acquired": True, "processed": False, "lease": lease, "event": None}
        processed = process_claimed_event(
            root,
            holder,
            event,
            workspace_id=workspace_id,
            now=now,
            materialize_func=materialize_func,
            materialize_kwargs=materialize_kwargs,
        )
        return {"acquired": True, "lease": lease, **processed}
    finally:
        if release_lease:
            journal.release_worker_lease(root, holder, workspace_id=workspace_id)


def process_ready_events(
    root: Path,
    holder: str,
    *,
    max_events: int | None = None,
    workspace_id: str = journal.DEFAULT_WORKSPACE_ID,
    lease_ttl_seconds: int = 300,
    now: str | None = None,
    materialize_func: MaterializeFunc = materialize.materialize_office_source,
    materialize_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if max_events is not None and max_events < 1:
        raise WorkerError("max_events must be positive when provided")
    lease = journal.acquire_worker_lease(
        root,
        holder,
        ttl_seconds=lease_ttl_seconds,
        workspace_id=workspace_id,
        now=now,
    )
    if not lease["acquired"]:
        return {"acquired": False, "processed": 0, "lease": lease, "events": []}

    processed: list[dict[str, Any]] = []
    try:
        while max_events is None or len(processed) < max_events:
            event = journal.claim_next_event(root, holder, workspace_id=workspace_id, now=now)
            if event is None:
                break
            processed.append(
                process_claimed_event(
                    root,
                    holder,
                    event,
                    workspace_id=workspace_id,
                    now=now,
                    materialize_func=materialize_func,
                    materialize_kwargs=materialize_kwargs,
                )
            )
    finally:
        journal.release_worker_lease(root, holder, workspace_id=workspace_id)

    counts = {"applied": 0, "review-required": 0, "failed": 0}
    for item in processed:
        status = str(item.get("finish_status", ""))
        if status in counts:
            counts[status] += 1
    return {
        "acquired": True,
        "processed": len(processed),
        "lease": lease,
        "events": processed,
        "finish_counts": counts,
    }
