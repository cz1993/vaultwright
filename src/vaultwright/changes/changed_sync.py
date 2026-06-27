# SPDX-License-Identifier: AGPL-3.0-or-later
"""Changed-file sync orchestration for journaled materialization."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from vaultwright.changes import journal, materialize, reconcile, replay, worker

MaterializeFunc = worker.MaterializeFunc


def sync_changed(
    root: Path,
    holder: str,
    *,
    retry_failed: bool = False,
    max_events: int | None = None,
    lease_ttl_seconds: int = 300,
    now: str | None = None,
    reconcile_first: bool = True,
    materialize_func: MaterializeFunc = materialize.materialize_office_source,
    materialize_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one deterministic changed-file sync pass.

    The pass keeps full sync separate: it optionally reconciles authoritative sources to queue
    missed journal events, then replays claimable journal work through the existing worker and
    source-addressable materialization primitive.
    """

    reconciliation = (
        reconcile.reconcile_workspace(root, now=now)
        if reconcile_first
        else {
            "reconciled_at": None,
            "scanned_sources": 0,
            "manifest_records": 0,
            "events_queued": 0,
            "events_skipped": 0,
            "event_counts": {"created": 0, "modified": 0, "moved": 0, "deleted": 0, "reconcile-required": 0},
            "full_hashes": 0,
            "bytes_hashed": 0,
            "events": [],
        }
    )
    replay_result = replay.replay_journal(
        root,
        holder,
        retry_failed=retry_failed,
        max_events=max_events,
        lease_ttl_seconds=lease_ttl_seconds,
        now=now,
        materialize_func=materialize_func,
        materialize_kwargs=materialize_kwargs,
    )
    return {
        "reconciliation": reconciliation,
        "replay": replay_result,
        "events_queued": reconciliation["events_queued"],
        "events_skipped": reconciliation["events_skipped"],
        "processed": replay_result["processed"],
        "finish_counts": replay_result["finish_counts"],
    }
