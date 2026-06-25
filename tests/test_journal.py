# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from vaultwright.changes import journal


ROOT = Path(__file__).resolve().parents[1]


def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = src_path if not env.get("PYTHONPATH") else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(root), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_journal_status_reports_uninitialized_without_creating_state(tmp_path: Path) -> None:
    payload = journal.journal_status(tmp_path)

    assert payload["initialized"] is False
    assert payload["state_path"] == ".vaultwright/state.sqlite"
    assert payload["last_event_sequence"] == 0
    assert payload["queued_count"] == 0
    assert not (tmp_path / ".vaultwright").exists()


def test_journal_initializes_sqlite_state_in_derived_directory(tmp_path: Path) -> None:
    path = journal.initialize(tmp_path)

    assert path == tmp_path / ".vaultwright" / "state.sqlite"
    assert path.exists()
    payload = journal.journal_status(tmp_path)
    assert payload["initialized"] is True
    assert payload["schema_version"] == 1
    assert payload["last_reconciliation"] is None


def test_journal_records_and_transitions_event_persistently(tmp_path: Path) -> None:
    sequence = journal.record_event(
        tmp_path,
        "created",
        source_id="source-001",
        current_path="10_sources/source-001.docx",
        metadata_fingerprint="mtime=1:size=20",
    )

    queued = journal.journal_status(tmp_path)
    assert sequence == 1
    assert queued["last_event_sequence"] == 1
    assert queued["last_observed_sequence"] == 1
    assert queued["last_applied_sequence"] == 0
    assert queued["queued_count"] == 1

    journal.transition_event(tmp_path, sequence, "applied")

    applied = journal.journal_status(tmp_path)
    assert applied["last_event_sequence"] == 1
    assert applied["last_applied_sequence"] == 1
    assert applied["queued_count"] == 0
    assert applied["state_counts"]["applied"] == 1


def test_journal_rejects_invalid_event_values_and_unsafe_paths(tmp_path: Path) -> None:
    with pytest.raises(journal.JournalError, match="invalid journal event kind"):
        journal.record_event(tmp_path, "renamed", current_path="10_sources/source-001.docx")
    with pytest.raises(journal.JournalError, match="invalid journal event status"):
        journal.record_event(tmp_path, "modified", status="done", current_path="10_sources/source-001.docx")
    with pytest.raises(journal.JournalError, match="vault-relative"):
        journal.record_event(tmp_path, "modified", current_path="/private/source-001.docx")
    with pytest.raises(journal.JournalError, match="parent-directory"):
        journal.record_event(tmp_path, "modified", current_path="../source-001.docx")
    with pytest.raises(journal.JournalError, match="derived state"):
        journal.record_event(tmp_path, "modified", current_path=".vaultwright/state.sqlite")


def test_journal_cli_status_json_reports_counts(tmp_path: Path) -> None:
    journal.record_event(tmp_path, "created", current_path="10_sources/source-001.docx")
    sequence = journal.record_event(tmp_path, "modified", current_path="10_sources/source-002.docx")
    journal.transition_event(tmp_path, sequence, "failed", error_summary="conversion timeout", retry=True)

    result = run_cli(tmp_path, "journal", "status", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["initialized"] is True
    assert payload["queued_count"] == 1
    assert payload["failed_count"] == 1
    assert payload["last_event_sequence"] == 2
    assert payload["state_path"] == ".vaultwright/state.sqlite"


def test_journal_cli_status_init_creates_state(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "journal", "status", "--init", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["initialized"] is True
    assert payload["schema_version"] == 1
    assert (tmp_path / ".vaultwright" / "state.sqlite").exists()


def test_worker_lease_allows_one_active_holder_and_release(tmp_path: Path) -> None:
    first = journal.acquire_worker_lease(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:00Z",
        ttl_seconds=60,
    )
    second = journal.acquire_worker_lease(
        tmp_path,
        "worker-b",
        now="2099-01-01T00:00:01Z",
        ttl_seconds=60,
    )

    assert first["acquired"] is True
    assert second["acquired"] is False
    assert second["holder"] == "worker-a"
    status = journal.journal_status(tmp_path)
    assert status["worker"]["locked"] is True
    assert status["worker"]["stale"] is False
    assert status["worker"]["holder"] == "worker-a"

    assert journal.release_worker_lease(tmp_path, "worker-b") is False
    assert journal.release_worker_lease(tmp_path, "worker-a") is True
    assert journal.journal_status(tmp_path)["worker"]["locked"] is False


def test_worker_lease_can_recover_stale_holder(tmp_path: Path) -> None:
    journal.acquire_worker_lease(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:00Z",
        ttl_seconds=5,
    )

    recovered = journal.acquire_worker_lease(
        tmp_path,
        "worker-b",
        now="2099-01-01T00:00:06Z",
        ttl_seconds=60,
    )

    assert recovered["acquired"] is True
    assert recovered["stale_recovered"] is True
    status = journal.journal_status(tmp_path)
    assert status["worker"]["locked"] is True
    assert status["worker"]["holder"] == "worker-b"


def test_claim_next_event_requires_active_lease_and_claims_once(tmp_path: Path) -> None:
    first = journal.record_event(tmp_path, "created", current_path="10_sources/first.docx")
    second = journal.record_event(tmp_path, "modified", current_path="10_sources/second.docx")
    journal.acquire_worker_lease(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:00Z",
        ttl_seconds=60,
    )

    with pytest.raises(journal.JournalError, match="worker lease is not active"):
        journal.claim_next_event(tmp_path, "worker-b", now="2099-01-01T00:00:01Z")

    claimed = journal.claim_next_event(tmp_path, "worker-a", now="2099-01-01T00:00:02Z")

    assert claimed is not None
    assert claimed["sequence"] == first
    assert claimed["status"] == "processing"
    assert journal.get_event(tmp_path, first)["status"] == "processing"  # type: ignore[index]
    assert journal.get_event(tmp_path, second)["status"] == "queued"  # type: ignore[index]
    status = journal.journal_status(tmp_path)
    assert status["processing_count"] == 1
    assert status["queued_count"] == 1
    assert status["worker"]["last_sequence"] == first


def test_finish_claimed_event_updates_checkpoint_once(tmp_path: Path) -> None:
    sequence = journal.record_event(tmp_path, "modified", current_path="10_sources/brief.docx")
    journal.acquire_worker_lease(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:00Z",
        ttl_seconds=60,
    )
    journal.claim_next_event(tmp_path, "worker-a", now="2099-01-01T00:00:01Z")

    journal.finish_claimed_event(
        tmp_path,
        "worker-a",
        sequence,
        "applied",
        now="2099-01-01T00:00:02Z",
    )

    event = journal.get_event(tmp_path, sequence)
    assert event is not None
    assert event["status"] == "applied"
    assert journal.journal_status(tmp_path)["last_applied_sequence"] == sequence
    with pytest.raises(journal.JournalError, match="not processing"):
        journal.finish_claimed_event(
            tmp_path,
            "worker-a",
            sequence,
            "applied",
            now="2099-01-01T00:00:03Z",
        )


def test_failed_event_retry_returns_to_queue(tmp_path: Path) -> None:
    sequence = journal.record_event(tmp_path, "modified", current_path="10_sources/brief.docx")
    journal.acquire_worker_lease(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:00Z",
        ttl_seconds=60,
    )
    journal.claim_next_event(tmp_path, "worker-a", now="2099-01-01T00:00:01Z")
    journal.finish_claimed_event(
        tmp_path,
        "worker-a",
        sequence,
        "failed",
        error_summary="converter failed",
        now="2099-01-01T00:00:02Z",
    )

    assert journal.retry_failed_event(tmp_path, sequence, now="2099-01-01T00:00:03Z") is True
    assert journal.retry_failed_event(tmp_path, sequence, now="2099-01-01T00:00:04Z") is False
    event = journal.get_event(tmp_path, sequence)
    assert event is not None
    assert event["status"] == "queued"
    assert event["retry_count"] == 1
    assert event["error_summary"] == ""


def test_processing_event_recovery_prevents_permanent_queue_loss(tmp_path: Path) -> None:
    sequence = journal.record_event(tmp_path, "modified", current_path="10_sources/brief.docx")
    journal.acquire_worker_lease(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:00Z",
        ttl_seconds=5,
    )
    journal.claim_next_event(tmp_path, "worker-a", now="2099-01-01T00:00:01Z")
    recovered_lease = journal.acquire_worker_lease(
        tmp_path,
        "worker-b",
        now="2099-01-01T00:00:06Z",
        ttl_seconds=60,
    )

    recovered = journal.recover_processing_events(
        tmp_path,
        error_summary="worker-a interrupted",
        now="2099-01-01T00:00:07Z",
    )
    claimed = journal.claim_next_event(tmp_path, "worker-b", now="2099-01-01T00:00:08Z")

    assert recovered_lease["stale_recovered"] is True
    assert recovered == [sequence]
    event = journal.get_event(tmp_path, sequence)
    assert event is not None
    assert event["retry_count"] == 1
    assert claimed is not None
    assert claimed["sequence"] == sequence
    assert claimed["status"] == "processing"


def test_journal_cli_status_reports_stale_lease(tmp_path: Path) -> None:
    journal.acquire_worker_lease(
        tmp_path,
        "worker-a",
        now="2000-01-01T00:00:00Z",
        ttl_seconds=1,
    )

    result = run_cli(tmp_path, "journal", "status")

    assert result.returncode == 0, result.stderr
    assert "worker: stale lease from worker-a expired at 2000-01-01T00:00:01Z" in result.stdout
