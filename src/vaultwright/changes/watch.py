# SPDX-License-Identifier: AGPL-3.0-or-later
"""Watch orchestration for journaled materialization."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from vaultwright.changes import feed as feed_module
from vaultwright.changes import journal, materialize, reconcile, replay, worker

MaterializeFunc = worker.MaterializeFunc


class WatchError(ValueError):
    """Raised when watch orchestration cannot run safely."""


def _empty_reconciliation() -> dict[str, Any]:
    return {
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


def watch_once(
    root: Path,
    holder: str,
    *,
    observed_feed: feed_module.ChangeFeed | None = None,
    retry_failed: bool = False,
    max_events: int | None = None,
    lease_ttl_seconds: int = 300,
    now: str | None = None,
    reconcile_on_start: bool = True,
    materialize_func: MaterializeFunc = materialize.materialize_office_source,
    materialize_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one watch cycle: startup reconciliation, observed-event queueing, replay.

    Continuous native watching is intentionally outside this primitive. Keeping this cycle
    feed-injected lets tests exercise watcher semantics without treating native delivery as
    authoritative or required for correctness.
    """

    reconciliation = (
        reconcile.reconcile_workspace(root, now=now) if reconcile_on_start else _empty_reconciliation()
    )
    feed_sequences = feed_module.queue_feed_events(root, observed_feed) if observed_feed is not None else []
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
        "mode": "once",
        "reconcile_on_start": reconcile_on_start,
        "reconciliation": reconciliation,
        "feed_events_queued": len(feed_sequences),
        "feed_sequences": feed_sequences,
        "events_queued": int(reconciliation["events_queued"]) + len(feed_sequences),
        "events_skipped": reconciliation["events_skipped"],
        "processed": replay_result["processed"],
        "finish_counts": replay_result["finish_counts"],
        "replay": replay_result,
    }
