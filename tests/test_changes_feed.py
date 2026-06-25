# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path
import sqlite3

from vaultwright.changes import feed, fingerprint, journal


def journal_rows(root: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(root / ".vaultwright" / "state.sqlite")
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT event_kind, current_path, previous_path, metadata_fingerprint, observed_at "
            "FROM journal_events ORDER BY sequence"
        ).fetchall()
    finally:
        conn.close()


def test_metadata_fingerprint_skips_full_hash_when_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "10_sources" / "brief.docx"
    source.parent.mkdir()
    source.write_text("synthetic source\n", encoding="utf-8")
    previous = fingerprint.fingerprint_token(tmp_path, "10_sources/brief.docx")
    calls: list[str] = []

    def counted_hash(root: Path, path: str | Path) -> str:
        calls.append(str(path))
        return "fake-sha"

    current, sha = fingerprint.hash_candidate_if_fingerprint_changed(
        tmp_path,
        "10_sources/brief.docx",
        previous,
        hash_func=counted_hash,
    )

    assert current.token() == previous
    assert sha is None
    assert calls == []

    source.write_text("synthetic source changed enough\n", encoding="utf-8")
    changed, sha = fingerprint.hash_candidate_if_fingerprint_changed(
        tmp_path,
        "10_sources/brief.docx",
        previous,
        hash_func=counted_hash,
    )

    assert changed.token() != previous
    assert sha == "fake-sha"
    assert calls == ["10_sources/brief.docx"]


def test_missing_fingerprint_candidate_does_not_hash(tmp_path: Path) -> None:
    calls: list[str] = []

    current, sha = fingerprint.hash_candidate_if_fingerprint_changed(
        tmp_path,
        "10_sources/missing.docx",
        None,
        hash_func=lambda root, path: calls.append(str(path)) or "sha",
    )

    assert current.exists is False
    assert sha is None
    assert calls == []


def test_feed_filters_generated_state_operational_and_temporary_paths(tmp_path: Path) -> None:
    meta = tmp_path / "_meta"
    meta.mkdir()
    (meta / "mirror-config.yml").write_text("office_mirrors:\n  root: generated\n", encoding="utf-8")
    changes = [
        feed.ObservedChange("modified", "generated/source.md"),
        feed.ObservedChange("modified", "80_sources/repos/example.md"),
        feed.ObservedChange("modified", ".vaultwright/state.sqlite"),
        feed.ObservedChange("modified", "tools"),
        feed.ObservedChange("modified", "tools/sync.py"),
        feed.ObservedChange("modified", "template/source.docx"),
        feed.ObservedChange("modified", "10_sources/~$locked.docx"),
        feed.ObservedChange("modified", "10_sources/.brief.docx.123.tmp"),
        feed.ObservedChange("modified", "10_sources/brief.docx"),
    ]

    kept = [feed.normalize_observed_change(tmp_path, change) for change in changes]

    assert [change.current_path for change in kept if change is not None] == ["10_sources/brief.docx"]


def test_feed_queues_coalesced_events_with_metadata_fingerprint(tmp_path: Path) -> None:
    source = tmp_path / "10_sources" / "brief.docx"
    source.parent.mkdir()
    source.write_text("synthetic source\n", encoding="utf-8")
    static = feed.StaticChangeFeed(
        [
            feed.ObservedChange("modified", "10_sources/brief.docx", observed_at="2026-06-25T10:00:00Z"),
            feed.ObservedChange("modified", "10_sources/brief.docx", observed_at="2026-06-25T10:00:01Z"),
            feed.ObservedChange("modified", ".vaultwright/state.sqlite"),
        ]
    )

    sequences = feed.queue_feed_events(tmp_path, static)

    assert sequences == [1]
    status = journal.journal_status(tmp_path)
    assert status["queued_count"] == 1
    rows = journal_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["event_kind"] == "modified"
    assert rows[0]["current_path"] == "10_sources/brief.docx"
    assert rows[0]["previous_path"] is None
    assert rows[0]["metadata_fingerprint"]
    assert rows[0]["observed_at"] == "2026-06-25T10:00:01Z"


def test_feed_does_not_initialize_journal_for_ignored_only_events(tmp_path: Path) -> None:
    static = feed.StaticChangeFeed(
        [
            feed.ObservedChange("modified", ".vaultwright/state.sqlite"),
            feed.ObservedChange("modified", "tools/sync.py"),
        ]
    )

    sequences = feed.queue_feed_events(tmp_path, static)

    assert sequences == []
    assert not (tmp_path / ".vaultwright").exists()


def test_move_event_preserves_previous_path(tmp_path: Path) -> None:
    source = tmp_path / "10_sources" / "renamed.docx"
    source.parent.mkdir()
    source.write_text("synthetic source\n", encoding="utf-8")
    static = feed.StaticChangeFeed(
        [
            feed.ObservedChange(
                "moved",
                current_path="10_sources/renamed.docx",
                previous_path="10_sources/original.docx",
            )
        ]
    )

    sequences = feed.queue_feed_events(tmp_path, static)

    assert sequences == [1]
    rows = journal_rows(tmp_path)
    assert rows[0]["event_kind"] == "moved"
    assert rows[0]["current_path"] == "10_sources/renamed.docx"
    assert rows[0]["previous_path"] == "10_sources/original.docx"
