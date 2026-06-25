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
