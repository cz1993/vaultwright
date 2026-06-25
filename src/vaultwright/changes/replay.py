# SPDX-License-Identifier: AGPL-3.0-or-later
"""Idempotent journal replay for changed-source materialization."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from vaultwright.changes import journal, materialize, worker

MaterializeFunc = worker.MaterializeFunc


class ReplayError(ValueError):
    """Raised when a replay request is not safe to execute."""


def _finish_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"applied": 0, "review-required": 0, "failed": 0}
    for item in events:
        status = str(item.get("finish_status", ""))
        if status in counts:
            counts[status] += 1
    return counts


def replay_journal(
    root: Path,
    holder: str,
    *,
    retry_failed: bool = False,
    max_events: int | None = None,
    workspace_id: str = journal.DEFAULT_WORKSPACE_ID,
    lease_ttl_seconds: int = 300,
    now: str | None = None,
    materialize_func: MaterializeFunc = materialize.materialize_office_source,
    materialize_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Replay recoverable journal work under one workspace lease.

    Replay first recovers events left in `processing` after an interrupted worker. Failed events
    are requeued only when the caller explicitly requests `retry_failed`, which keeps repeated
    replay invocations idempotent for already-applied or review-required work.
    """

    if max_events is not None and max_events < 1:
        raise ReplayError("max_events must be positive when provided")

    lease = journal.acquire_worker_lease(
        root,
        holder,
        ttl_seconds=lease_ttl_seconds,
        workspace_id=workspace_id,
        now=now,
    )
    if not lease["acquired"]:
        return {
            "acquired": False,
            "processed": 0,
            "lease": lease,
            "recovered_processing": [],
            "retried_failed": [],
            "events": [],
            "finish_counts": {"applied": 0, "review-required": 0, "failed": 0},
        }

    recovered_processing: list[int] = []
    retried_failed: list[int] = []
    processed: list[dict[str, Any]] = []
    try:
        recovered_processing = journal.recover_processing_events(root, now=now)
        if retry_failed:
            for sequence in journal.failed_event_sequences(root):
                if journal.retry_failed_event(root, sequence, now=now):
                    retried_failed.append(sequence)

        while max_events is None or len(processed) < max_events:
            event = journal.claim_next_event(root, holder, workspace_id=workspace_id, now=now)
            if event is None:
                break
            processed.append(
                worker.process_claimed_event(
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

    return {
        "acquired": True,
        "processed": len(processed),
        "lease": lease,
        "recovered_processing": recovered_processing,
        "retried_failed": retried_failed,
        "events": processed,
        "finish_counts": _finish_counts(processed),
    }
