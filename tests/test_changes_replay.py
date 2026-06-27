# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from vaultwright.changes import journal, replay


ROOT = Path(__file__).resolve().parents[1]


class TextConversion:
    def __init__(self, text: str) -> None:
        self.text_content = text


class CountingConverter:
    def __init__(self, text: str = "Extracted replay source") -> None:
        self.text = text
        self.paths: list[str] = []

    def convert(self, path: str) -> TextConversion:
        self.paths.append(path)
        return TextConversion(self.text)


def converter_kwargs(converter: CountingConverter) -> dict[str, object]:
    return {
        "converter": converter,
        "converter_name": "test-converter",
        "converter_version": "test",
        "append_audit": False,
    }


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


def test_replay_recovers_interrupted_processing_event(tmp_path: Path) -> None:
    source = tmp_path / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source_bytes = b"synthetic replay source"
    source.write_bytes(source_bytes)
    sequence = journal.record_event(tmp_path, "modified", current_path="40_delivery/registration.docx")
    journal.acquire_worker_lease(tmp_path, "worker-a", now="2099-01-01T00:00:00Z", ttl_seconds=5)
    journal.claim_next_event(tmp_path, "worker-a", now="2099-01-01T00:00:01Z")
    converter = CountingConverter()

    result = replay.replay_journal(
        tmp_path,
        "worker-b",
        now="2099-01-01T00:00:06Z",
        materialize_kwargs=converter_kwargs(converter),
    )

    assert result["acquired"] is True
    assert result["lease"]["stale_recovered"] is True
    assert result["recovered_processing"] == [sequence]
    assert result["retried_failed"] == []
    assert result["processed"] == 1
    assert result["finish_counts"] == {"applied": 1, "review-required": 0, "failed": 0}
    assert converter.paths == [str(source)]
    assert source.read_bytes() == source_bytes
    event = journal.get_event(tmp_path, sequence)
    assert event is not None
    assert event["status"] == "applied"
    assert event["retry_count"] == 1
    assert event["source_id"].startswith("src_")
    assert event["source_sha256"]
    assert journal.journal_status(tmp_path)["worker"]["locked"] is False


def test_replay_failed_retry_is_explicit_and_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic replay source")
    sequence = journal.record_event(tmp_path, "modified", current_path="40_delivery/registration.docx")
    journal.transition_event(tmp_path, sequence, "failed", error_summary="converter failed")
    converter = CountingConverter()

    no_retry = replay.replay_journal(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:00Z",
        materialize_kwargs=converter_kwargs(converter),
    )
    assert no_retry["processed"] == 0
    assert no_retry["retried_failed"] == []
    assert converter.paths == []
    assert journal.get_event(tmp_path, sequence)["status"] == "failed"  # type: ignore[index]

    retried = replay.replay_journal(
        tmp_path,
        "worker-a",
        retry_failed=True,
        now="2099-01-01T00:00:01Z",
        materialize_kwargs=converter_kwargs(converter),
    )
    assert retried["retried_failed"] == [sequence]
    assert retried["processed"] == 1
    assert retried["finish_counts"] == {"applied": 1, "review-required": 0, "failed": 0}
    event = journal.get_event(tmp_path, sequence)
    assert event is not None
    assert event["status"] == "applied"
    assert event["retry_count"] == 1

    second = replay.replay_journal(
        tmp_path,
        "worker-a",
        retry_failed=True,
        now="2099-01-01T00:00:02Z",
        materialize_kwargs=converter_kwargs(converter),
    )
    assert second["retried_failed"] == []
    assert second["processed"] == 0
    assert converter.paths == [str(source)]


def test_replay_respects_active_lease_from_another_holder(tmp_path: Path) -> None:
    sequence = journal.record_event(tmp_path, "modified", current_path="40_delivery/registration.docx")
    journal.acquire_worker_lease(tmp_path, "worker-a", now="2099-01-01T00:00:00Z", ttl_seconds=60)
    converter = CountingConverter()

    result = replay.replay_journal(
        tmp_path,
        "worker-b",
        now="2099-01-01T00:00:01Z",
        materialize_kwargs=converter_kwargs(converter),
    )

    assert result["acquired"] is False
    assert result["processed"] == 0
    assert result["lease"]["holder"] == "worker-a"
    assert converter.paths == []
    assert journal.get_event(tmp_path, sequence)["status"] == "queued"  # type: ignore[index]


def test_replay_rejects_non_positive_max_events(tmp_path: Path) -> None:
    with pytest.raises(replay.ReplayError, match="max_events must be positive"):
        replay.replay_journal(tmp_path, "worker-a", max_events=0)


def test_journal_cli_replay_json_processes_review_required_event(tmp_path: Path) -> None:
    sequence = journal.record_event(tmp_path, "modified", current_path="40_delivery/notes.txt")

    result = run_cli(tmp_path, "journal", "replay", "--json", "--holder", "cli-test")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["acquired"] is True
    assert payload["processed"] == 1
    assert payload["finish_counts"] == {"applied": 0, "failed": 0, "review-required": 1}
    assert payload["events"][0]["finish_status"] == "review-required"
    event = journal.get_event(tmp_path, sequence)
    assert event is not None
    assert event["status"] == "review-required"
    assert event["error_summary"] == "skipped:unsupported-source"
