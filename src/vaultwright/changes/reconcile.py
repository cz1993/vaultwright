# SPDX-License-Identifier: AGPL-3.0-or-later
"""Explicit reconciliation for journaled changed-file materialization."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from vaultwright.changes import fingerprint, journal
from vaultwright.mirrors import office as office_sync

HashFunc = Callable[[Path], str]


class ReconciliationError(ValueError):
    """Raised when reconciliation cannot safely inspect workspace state."""


def _record_path(record: dict[str, Any]) -> str | None:
    value = record.get("current_source_path")
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path.as_posix()


def _record_size(record: dict[str, Any]) -> int | None:
    value = record.get("source_size")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _record_modified(record: dict[str, Any]) -> str:
    value = record.get("source_modified")
    return value if isinstance(value, str) else ""


def _source_rel(root: Path, source: Path) -> str:
    return source.relative_to(root).as_posix()


def _source_modified(source: Path) -> str:
    try:
        return office_sync.file_mtime_iso(source)
    except OSError as exc:
        raise ReconciliationError(f"source is not readable for reconciliation: {source}: {exc}") from exc


def _queue_once(
    root: Path,
    event_kind: str,
    *,
    current_path: str | None = None,
    previous_path: str | None = None,
    source_id: str = "",
    metadata_fingerprint: str = "",
    source_sha256: str = "",
    observed_at: str | None = None,
) -> dict[str, Any]:
    existing = journal.matching_event_sequences(
        root,
        event_kind,
        current_path=current_path,
        previous_path=previous_path,
    )
    if existing:
        return {
            "sequence": existing[0],
            "event_kind": event_kind,
            "current_path": current_path,
            "previous_path": previous_path,
            "source_id": source_id,
            "queued": False,
            "reason": "unresolved-event-exists",
        }
    sequence = journal.record_event(
        root,
        event_kind,
        current_path=current_path,
        previous_path=previous_path,
        source_id=source_id,
        metadata_fingerprint=metadata_fingerprint,
        source_sha256=source_sha256,
        observed_at=observed_at,
    )
    return {
        "sequence": sequence,
        "event_kind": event_kind,
        "current_path": current_path,
        "previous_path": previous_path,
        "source_id": source_id,
        "queued": True,
        "reason": "queued",
    }


def _record_event_count(events: list[dict[str, Any]], event_kind: str) -> int:
    return sum(1 for event in events if event["event_kind"] == event_kind and event["queued"])


def reconcile_workspace(
    root: Path,
    *,
    include_pdf: bool | None = None,
    mirror_mode: str | None = None,
    mirror_root: str | None = None,
    now: str | None = None,
    hash_func: HashFunc = office_sync.sha256_of,
) -> dict[str, Any]:
    """Queue missed journal events by comparing authoritative sources with the manifest.

    The pass is metadata-first. Full source hashing is limited to new paths that may correspond to
    a missing manifest record with the same stored size, which is the suspicious case needed for
    safe move detection.
    """

    root = root.expanduser().resolve()
    try:
        mirror_config = office_sync.load_mirror_config(root, mirror_mode, mirror_root)
        exts = office_sync.source_extensions(mirror_config, include_pdf)
        sources = office_sync.discover(root, exts, mirror_config)
        manifest = office_sync.load_source_manifest(root)
    except (OSError, ValueError) as exc:
        raise ReconciliationError(str(exc)) from exc

    journal.initialize(root)
    records = [record for record in manifest.get("records", []) if isinstance(record, dict)]
    records_by_path = {
        path: record
        for record in records
        if (path := _record_path(record)) is not None
    }
    current_by_path = {_source_rel(root, source): source for source in sources}

    missing_records = [
        record
        for path, record in records_by_path.items()
        if path not in current_by_path
    ]
    missing_by_size: dict[int, list[dict[str, Any]]] = {}
    for record in missing_records:
        size = _record_size(record)
        source_hash = record.get("source_sha256")
        if size is None or not isinstance(source_hash, str) or not source_hash:
            continue
        missing_by_size.setdefault(size, []).append(record)

    events: list[dict[str, Any]] = []
    moved_previous_paths: set[str] = set()
    full_hashes = 0
    bytes_hashed = 0

    for rel, source in sorted(current_by_path.items()):
        token = fingerprint.fingerprint_token(root, rel)
        record = records_by_path.get(rel)
        if record is not None:
            current_size = source.stat().st_size
            if _record_size(record) != current_size or _record_modified(record) != _source_modified(source):
                events.append(
                    _queue_once(
                        root,
                        "modified",
                        current_path=rel,
                        source_id=str(record.get("source_id") or ""),
                        metadata_fingerprint=token,
                        observed_at=now,
                    )
                )
            continue

        size = source.stat().st_size
        candidates = missing_by_size.get(size, [])
        if candidates:
            source_hash = hash_func(source)
            full_hashes += 1
            bytes_hashed += size
            matches = [
                candidate
                for candidate in candidates
                if candidate.get("source_sha256") == source_hash
            ]
            if len(matches) == 1:
                previous = _record_path(matches[0])
                if previous:
                    moved_previous_paths.add(previous)
                    events.append(
                        _queue_once(
                            root,
                            "moved",
                            current_path=rel,
                            previous_path=previous,
                            source_id=str(matches[0].get("source_id") or ""),
                            metadata_fingerprint=token,
                            source_sha256=source_hash,
                            observed_at=now,
                        )
                    )
                    continue
            elif len(matches) > 1:
                events.append(
                    _queue_once(
                        root,
                        "reconcile-required",
                        current_path=rel,
                        metadata_fingerprint=token,
                        source_sha256=source_hash,
                        observed_at=now,
                    )
                )
                continue

        events.append(
            _queue_once(
                root,
                "created",
                current_path=rel,
                metadata_fingerprint=token,
                observed_at=now,
            )
        )

    for record in missing_records:
        previous = _record_path(record)
        if previous is None or previous in moved_previous_paths:
            continue
        events.append(
            _queue_once(
                root,
                "deleted",
                previous_path=previous,
                source_id=str(record.get("source_id") or ""),
                source_sha256=str(record.get("source_sha256") or ""),
                observed_at=now,
            )
        )

    reconciled_at = journal.record_reconciliation(root, now=now)
    event_counts = {
        "created": _record_event_count(events, "created"),
        "modified": _record_event_count(events, "modified"),
        "moved": _record_event_count(events, "moved"),
        "deleted": _record_event_count(events, "deleted"),
        "reconcile-required": _record_event_count(events, "reconcile-required"),
    }
    queued = [event for event in events if event["queued"]]
    skipped = [event for event in events if not event["queued"]]
    return {
        "reconciled_at": reconciled_at,
        "scanned_sources": len(sources),
        "manifest_records": len(records_by_path),
        "events_queued": len(queued),
        "events_skipped": len(skipped),
        "event_counts": event_counts,
        "full_hashes": full_hashes,
        "bytes_hashed": bytes_hashed,
        "events": events,
    }
