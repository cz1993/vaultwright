# SPDX-License-Identifier: AGPL-3.0-or-later
"""Durable local journal state for changed-file materialization."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from typing import Any

from vaultwright.changes.events import (
    COUNTED_STATUSES,
    EVENT_STATUSES,
    JournalEventError,
    normalize_vault_relative_path,
    validate_event_kind,
    validate_event_status,
)

STATE_DIR = Path(".vaultwright")
STATE_DB = STATE_DIR / "state.sqlite"
SCHEMA_VERSION = 1
DEFAULT_WORKSPACE_ID = "default"
CLAIMABLE_STATUSES = ("queued", "ready")
RECOVERABLE_STATUSES = ("processing",)
FINISH_STATUSES = {"applied", "failed", "review-required"}
UNRESOLVED_STATUSES = ("queued", "ready", "stabilizing", "processing", "failed")

META_DEFAULTS = {
    "schema_version": str(SCHEMA_VERSION),
    "last_observed_sequence": "0",
    "last_applied_sequence": "0",
    "last_reconciliation_at": "",
}


class JournalError(ValueError):
    """Raised when local journal state cannot be read or updated safely."""


def utc_now() -> str:
    return utc_text(datetime.now(timezone.utc))


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _now_datetime(now: str | None = None) -> datetime:
    return parse_utc(now) if now else datetime.now(timezone.utc)


def _normalize_holder(holder: str) -> str:
    value = holder.strip()
    if not value:
        raise JournalError("worker holder must be non-empty")
    return value


def _normalize_workspace_id(workspace_id: str) -> str:
    value = workspace_id.strip()
    if not value:
        raise JournalError("workspace_id must be non-empty")
    return value


def state_db_path(root: Path) -> Path:
    return root / STATE_DB


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_root(root: Path) -> None:
    if not root.exists():
        raise JournalError(f"vault root does not exist: {root}")
    if not root.is_dir():
        raise JournalError(f"vault root is not a directory: {root}")


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS journal_meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS journal_events (
          sequence INTEGER PRIMARY KEY AUTOINCREMENT,
          event_kind TEXT NOT NULL,
          source_id TEXT NOT NULL DEFAULT '',
          current_path TEXT,
          previous_path TEXT,
          observed_at TEXT NOT NULL,
          status TEXT NOT NULL,
          retry_count INTEGER NOT NULL DEFAULT 0,
          error_summary TEXT NOT NULL DEFAULT '',
          metadata_fingerprint TEXT NOT NULL DEFAULT '',
          source_sha256 TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS journal_worker_lease (
          workspace_id TEXT PRIMARY KEY,
          holder TEXT NOT NULL,
          acquired_at TEXT NOT NULL,
          expires_at TEXT NOT NULL,
          last_sequence INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    for key, value in META_DEFAULTS.items():
        conn.execute("INSERT OR IGNORE INTO journal_meta(key, value) VALUES (?, ?)", (key, value))
    meta = _read_meta(conn)
    if meta.get("schema_version") != str(SCHEMA_VERSION):
        found = meta.get("schema_version", "missing")
        raise JournalError(f"unsupported journal schema_version {found}; expected {SCHEMA_VERSION}")


def _read_meta(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM journal_meta").fetchall()
    return {str(row["key"]): str(row["value"]) for row in rows}


def _write_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO journal_meta(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _row_to_event(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _lease_row(
    conn: sqlite3.Connection,
    workspace_id: str,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT workspace_id, holder, acquired_at, expires_at, last_sequence
          FROM journal_worker_lease
         WHERE workspace_id = ?
        """,
        (workspace_id,),
    ).fetchone()


def _active_lease_row(
    conn: sqlite3.Connection,
    holder: str,
    workspace_id: str,
    now_text: str,
) -> sqlite3.Row | None:
    row = _lease_row(conn, workspace_id)
    if row is None:
        return None
    if row["holder"] != holder:
        return None
    if str(row["expires_at"]) <= now_text:
        return None
    return row


def _require_active_lease(
    conn: sqlite3.Connection,
    holder: str,
    workspace_id: str,
    now_text: str,
) -> sqlite3.Row:
    row = _active_lease_row(conn, holder, workspace_id, now_text)
    if row is None:
        raise JournalError(f"worker lease is not active for holder: {holder}")
    return row


def initialize(root: Path) -> Path:
    root = root.expanduser().resolve()
    _ensure_root(root)
    path = state_db_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        _ensure_schema(conn)
    return path


def _connect_existing(root: Path) -> sqlite3.Connection:
    path = state_db_path(root.expanduser().resolve())
    if not path.exists():
        raise JournalError(f"journal state is not initialized: {STATE_DB.as_posix()}")
    conn = _connect(path)
    try:
        _ensure_schema(conn)
        conn.commit()
    except Exception:
        conn.close()
        raise
    return conn


def acquire_worker_lease(
    root: Path,
    holder: str,
    *,
    ttl_seconds: int = 300,
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    now: str | None = None,
) -> dict[str, Any]:
    holder = _normalize_holder(holder)
    workspace_id = _normalize_workspace_id(workspace_id)
    if ttl_seconds <= 0:
        raise JournalError("ttl_seconds must be positive")
    now_dt = _now_datetime(now)
    now_text = utc_text(now_dt)
    expires_at = utc_text(now_dt + timedelta(seconds=ttl_seconds))
    initialize(root)
    with _connect_existing(root) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing = _lease_row(conn, workspace_id)
            stale_recovered = False
            acquired = False
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO journal_worker_lease(
                      workspace_id, holder, acquired_at, expires_at, last_sequence
                    )
                    VALUES (?, ?, ?, ?, 0)
                    """,
                    (workspace_id, holder, now_text, expires_at),
                )
                acquired = True
            elif existing["holder"] == holder or str(existing["expires_at"]) <= now_text:
                stale_recovered = existing["holder"] != holder and str(existing["expires_at"]) <= now_text
                conn.execute(
                    """
                    UPDATE journal_worker_lease
                       SET holder = ?,
                           acquired_at = ?,
                           expires_at = ?
                     WHERE workspace_id = ?
                    """,
                    (holder, now_text, expires_at, workspace_id),
                )
                acquired = True
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {
        "acquired": acquired,
        "holder": holder if acquired else str(existing["holder"]) if existing else "",
        "workspace_id": workspace_id,
        "expires_at": expires_at if acquired else str(existing["expires_at"]) if existing else "",
        "stale_recovered": stale_recovered if acquired else False,
    }


def release_worker_lease(
    root: Path,
    holder: str,
    *,
    workspace_id: str = DEFAULT_WORKSPACE_ID,
) -> bool:
    holder = _normalize_holder(holder)
    workspace_id = _normalize_workspace_id(workspace_id)
    with _connect_existing(root) as conn:
        cursor = conn.execute(
            "DELETE FROM journal_worker_lease WHERE workspace_id = ? AND holder = ?",
            (workspace_id, holder),
        )
    return cursor.rowcount > 0


def get_event(root: Path, sequence: int) -> dict[str, Any] | None:
    with _connect_existing(root) as conn:
        row = conn.execute(
            """
            SELECT sequence, event_kind, source_id, current_path, previous_path, observed_at,
                   status, retry_count, error_summary, metadata_fingerprint, source_sha256,
                   created_at, updated_at
              FROM journal_events
             WHERE sequence = ?
            """,
            (sequence,),
        ).fetchone()
    return _row_to_event(row)


def _validate_statuses(statuses: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    out: list[str] = []
    for status in statuses:
        try:
            out.append(validate_event_status(status))
        except JournalEventError as exc:
            raise JournalError(str(exc)) from exc
    if not out:
        raise JournalError("at least one status is required")
    return tuple(out)


def claim_next_event(
    root: Path,
    holder: str,
    *,
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    now: str | None = None,
    statuses: tuple[str, ...] | list[str] = CLAIMABLE_STATUSES,
) -> dict[str, Any] | None:
    holder = _normalize_holder(holder)
    workspace_id = _normalize_workspace_id(workspace_id)
    claimable = _validate_statuses(statuses)
    now_text = utc_text(_now_datetime(now))
    placeholders = ", ".join("?" for _status in claimable)
    with _connect_existing(root) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            _require_active_lease(conn, holder, workspace_id, now_text)
            row = conn.execute(
                f"""
                SELECT sequence
                  FROM journal_events
                 WHERE status IN ({placeholders})
              ORDER BY sequence
                 LIMIT 1
                """,
                claimable,
            ).fetchone()
            if row is None:
                conn.commit()
                return None
            sequence = int(row["sequence"])
            conn.execute(
                """
                UPDATE journal_events
                   SET status = 'processing',
                       error_summary = '',
                       updated_at = ?
                 WHERE sequence = ?
                """,
                (now_text, sequence),
            )
            conn.execute(
                """
                UPDATE journal_worker_lease
                   SET last_sequence = ?
                 WHERE workspace_id = ?
                """,
                (sequence, workspace_id),
            )
            claimed = conn.execute(
                """
                SELECT sequence, event_kind, source_id, current_path, previous_path, observed_at,
                       status, retry_count, error_summary, metadata_fingerprint, source_sha256,
                       created_at, updated_at
                  FROM journal_events
                 WHERE sequence = ?
                """,
                (sequence,),
            ).fetchone()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return _row_to_event(claimed)


def finish_claimed_event(
    root: Path,
    holder: str,
    sequence: int,
    status: str,
    *,
    error_summary: str | None = None,
    source_id: str | None = None,
    source_sha256: str | None = None,
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    now: str | None = None,
) -> None:
    holder = _normalize_holder(holder)
    workspace_id = _normalize_workspace_id(workspace_id)
    try:
        status = validate_event_status(status)
    except JournalEventError as exc:
        raise JournalError(str(exc)) from exc
    if status not in FINISH_STATUSES:
        allowed = ", ".join(sorted(FINISH_STATUSES))
        raise JournalError(f"claimed events can finish only as: {allowed}")
    now_text = utc_text(_now_datetime(now))
    with _connect_existing(root) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            _require_active_lease(conn, holder, workspace_id, now_text)
            row = conn.execute(
                "SELECT status, source_id, source_sha256 FROM journal_events WHERE sequence = ?",
                (sequence,),
            ).fetchone()
            if row is None:
                raise JournalError(f"journal event does not exist: {sequence}")
            if row["status"] != "processing":
                raise JournalError(f"journal event is not processing: {sequence}")
            conn.execute(
                """
                UPDATE journal_events
                   SET status = ?,
                       error_summary = ?,
                       source_id = ?,
                       source_sha256 = ?,
                       updated_at = ?
                 WHERE sequence = ?
                """,
                (
                    status,
                    "" if error_summary is None else error_summary,
                    str(row["source_id"] if source_id is None else source_id),
                    str(row["source_sha256"] if source_sha256 is None else source_sha256),
                    now_text,
                    sequence,
                ),
            )
            if status == "applied":
                meta = _read_meta(conn)
                current_last = int(meta.get("last_applied_sequence", "0") or "0")
                _write_meta(conn, "last_applied_sequence", str(max(current_last, sequence)))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def retry_failed_event(
    root: Path,
    sequence: int,
    *,
    now: str | None = None,
) -> bool:
    now_text = utc_text(_now_datetime(now))
    with _connect_existing(root) as conn:
        cursor = conn.execute(
            """
            UPDATE journal_events
               SET status = 'queued',
                   retry_count = retry_count + 1,
                   error_summary = '',
                   updated_at = ?
             WHERE sequence = ?
               AND status = 'failed'
            """,
            (now_text, sequence),
        )
    return cursor.rowcount > 0


def failed_event_sequences(root: Path) -> list[int]:
    with _connect_existing(root) as conn:
        rows = conn.execute(
            """
            SELECT sequence
              FROM journal_events
             WHERE status = 'failed'
          ORDER BY sequence
            """
        ).fetchall()
    return [int(row["sequence"]) for row in rows]


def matching_event_sequences(
    root: Path,
    event_kind: str,
    *,
    current_path: str | Path | None = None,
    previous_path: str | Path | None = None,
    statuses: tuple[str, ...] | list[str] = UNRESOLVED_STATUSES,
) -> list[int]:
    try:
        event_kind = validate_event_kind(event_kind)
        current = normalize_vault_relative_path(current_path, field="current_path")
        previous = normalize_vault_relative_path(previous_path, field="previous_path")
    except JournalEventError as exc:
        raise JournalError(str(exc)) from exc
    checked_statuses = _validate_statuses(statuses)
    placeholders = ", ".join("?" for _status in checked_statuses)
    with _connect_existing(root) as conn:
        rows = conn.execute(
            f"""
            SELECT sequence
              FROM journal_events
             WHERE event_kind = ?
               AND COALESCE(current_path, '') = ?
               AND COALESCE(previous_path, '') = ?
               AND status IN ({placeholders})
          ORDER BY sequence
            """,
            (event_kind, current or "", previous or "", *checked_statuses),
        ).fetchall()
    return [int(row["sequence"]) for row in rows]


def record_reconciliation(root: Path, *, now: str | None = None) -> str:
    reconciled_at = utc_text(_now_datetime(now))
    initialize(root)
    with _connect_existing(root) as conn:
        _write_meta(conn, "last_reconciliation_at", reconciled_at)
    return reconciled_at


def recover_processing_events(
    root: Path,
    *,
    error_summary: str = "worker interrupted before completion",
    now: str | None = None,
) -> list[int]:
    now_text = utc_text(_now_datetime(now))
    with _connect_existing(root) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            rows = conn.execute(
                """
                SELECT sequence
                  FROM journal_events
                 WHERE status = 'processing'
              ORDER BY sequence
                """
            ).fetchall()
            sequences = [int(row["sequence"]) for row in rows]
            if sequences:
                placeholders = ", ".join("?" for _sequence in sequences)
                conn.execute(
                    f"""
                    UPDATE journal_events
                       SET status = 'queued',
                           retry_count = retry_count + 1,
                           error_summary = ?,
                           updated_at = ?
                     WHERE sequence IN ({placeholders})
                    """,
                    (error_summary, now_text, *sequences),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return sequences


def record_event(
    root: Path,
    event_kind: str,
    *,
    current_path: str | Path | None = None,
    previous_path: str | Path | None = None,
    source_id: str = "",
    status: str = "queued",
    metadata_fingerprint: str = "",
    source_sha256: str = "",
    observed_at: str | None = None,
) -> int:
    try:
        event_kind = validate_event_kind(event_kind)
        status = validate_event_status(status)
        current = normalize_vault_relative_path(current_path, field="current_path")
        previous = normalize_vault_relative_path(previous_path, field="previous_path")
    except JournalEventError as exc:
        raise JournalError(str(exc)) from exc
    observed = observed_at or utc_now()
    now = utc_now()
    initialize(root)
    with _connect_existing(root) as conn:
        cursor = conn.execute(
            """
            INSERT INTO journal_events(
              event_kind, source_id, current_path, previous_path, observed_at, status,
              metadata_fingerprint, source_sha256, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_kind,
                source_id,
                current,
                previous,
                observed,
                status,
                metadata_fingerprint,
                source_sha256,
                now,
                now,
            ),
        )
        sequence = int(cursor.lastrowid)
        _write_meta(conn, "last_observed_sequence", str(sequence))
    return sequence


def transition_event(
    root: Path,
    sequence: int,
    status: str,
    *,
    error_summary: str | None = None,
    retry: bool = False,
) -> None:
    try:
        status = validate_event_status(status)
    except JournalEventError as exc:
        raise JournalError(str(exc)) from exc
    with _connect_existing(root) as conn:
        row = conn.execute("SELECT sequence FROM journal_events WHERE sequence = ?", (sequence,)).fetchone()
        if row is None:
            raise JournalError(f"journal event does not exist: {sequence}")
        now = utc_now()
        retry_sql = ", retry_count = retry_count + 1" if retry else ""
        error_value = "" if error_summary is None else error_summary
        conn.execute(
            f"""
            UPDATE journal_events
               SET status = ?,
                   error_summary = ?,
                   updated_at = ?
                   {retry_sql}
             WHERE sequence = ?
            """,
            (status, error_value, now, sequence),
        )
        if status == "applied":
            meta = _read_meta(conn)
            current_last = int(meta.get("last_applied_sequence", "0") or "0")
            _write_meta(conn, "last_applied_sequence", str(max(current_last, sequence)))


def _empty_status(root: Path) -> dict[str, Any]:
    counts = {status: 0 for status in EVENT_STATUSES}
    payload = {
        "state_path": STATE_DB.as_posix(),
        "initialized": False,
        "schema_version": None,
        "last_event_sequence": 0,
        "last_observed_sequence": 0,
        "last_applied_sequence": 0,
        "last_reconciliation": None,
        "state_counts": counts,
        "worker": {"locked": False, "stale": False, "holder": "", "expires_at": "", "last_sequence": 0},
    }
    for status in COUNTED_STATUSES:
        payload[f"{status.replace('-', '_')}_count"] = 0
    return payload


def journal_status(root: Path, *, initialize_state: bool = False) -> dict[str, Any]:
    root = root.expanduser().resolve()
    path = state_db_path(root)
    if not path.exists() and not initialize_state:
        return _empty_status(root)
    if initialize_state:
        initialize(root)
    with _connect_existing(root) as conn:
        meta = _read_meta(conn)
        counts = {status: 0 for status in EVENT_STATUSES}
        for row in conn.execute("SELECT status, COUNT(*) AS count FROM journal_events GROUP BY status"):
            counts[str(row["status"])] = int(row["count"])
        row = conn.execute("SELECT COALESCE(MAX(sequence), 0) AS sequence FROM journal_events").fetchone()
        last_event_sequence = int(row["sequence"]) if row else 0
        lease = conn.execute(
            """
            SELECT holder, expires_at, last_sequence
              FROM journal_worker_lease
          ORDER BY expires_at DESC
             LIMIT 1
            """
        ).fetchone()
    last_reconciliation = meta.get("last_reconciliation_at") or None
    now_text = utc_now()
    lease_locked = lease is not None and str(lease["expires_at"]) > now_text
    payload = {
        "state_path": STATE_DB.as_posix(),
        "initialized": True,
        "schema_version": int(meta["schema_version"]),
        "last_event_sequence": last_event_sequence,
        "last_observed_sequence": int(meta.get("last_observed_sequence", "0") or "0"),
        "last_applied_sequence": int(meta.get("last_applied_sequence", "0") or "0"),
        "last_reconciliation": last_reconciliation,
        "state_counts": counts,
        "worker": {
            "locked": lease_locked,
            "stale": lease is not None and not lease_locked,
            "holder": str(lease["holder"]) if lease else "",
            "expires_at": str(lease["expires_at"]) if lease else "",
            "last_sequence": int(lease["last_sequence"]) if lease else 0,
        },
    }
    for status in COUNTED_STATUSES:
        payload[f"{status.replace('-', '_')}_count"] = counts[status]
    return payload
