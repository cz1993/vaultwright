# SPDX-License-Identifier: AGPL-3.0-or-later
"""Durable local journal state for changed-file materialization."""
from __future__ import annotations

from datetime import datetime, timezone
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

META_DEFAULTS = {
    "schema_version": str(SCHEMA_VERSION),
    "last_observed_sequence": "0",
    "last_applied_sequence": "0",
    "last_reconciliation_at": "",
}


class JournalError(ValueError):
    """Raised when local journal state cannot be read or updated safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    except Exception:
        conn.close()
        raise
    return conn


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
        "worker": {"locked": False, "holder": "", "expires_at": "", "last_sequence": 0},
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
            "locked": lease is not None,
            "holder": str(lease["holder"]) if lease else "",
            "expires_at": str(lease["expires_at"]) if lease else "",
            "last_sequence": int(lease["last_sequence"]) if lease else 0,
        },
    }
    for status in COUNTED_STATUSES:
        payload[f"{status.replace('-', '_')}_count"] = counts[status]
    return payload
