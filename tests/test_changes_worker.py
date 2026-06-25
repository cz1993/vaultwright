# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

from vaultwright.changes import journal, worker


class TextConversion:
    def __init__(self, text: str) -> None:
        self.text_content = text


class CountingConverter:
    def __init__(self, text: str = "Extracted worker source") -> None:
        self.text = text
        self.paths: list[str] = []

    def convert(self, path: str) -> TextConversion:
        self.paths.append(path)
        return TextConversion(self.text)


class FailingConverter:
    def convert(self, _path: str) -> TextConversion:
        raise RuntimeError("conversion exploded")


def test_worker_processes_next_supported_office_event(tmp_path: Path) -> None:
    source = tmp_path / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source_bytes = b"synthetic source bytes"
    source.write_bytes(source_bytes)
    sequence = journal.record_event(
        tmp_path,
        "modified",
        current_path="40_delivery/registration.docx",
    )
    converter = CountingConverter()

    result = worker.process_next_event(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:00Z",
        materialize_kwargs={
            "converter": converter,
            "converter_name": "test-converter",
            "converter_version": "test",
            "append_audit": False,
        },
    )

    assert result["acquired"] is True
    assert result["processed"] is True
    assert result["finish_status"] == "applied"
    assert result["materialization"]["status"] == "created"
    assert converter.paths == [str(source)]
    assert source.read_bytes() == source_bytes
    assert (tmp_path / "_mirrors" / "40_delivery" / "registration.md").exists()
    event = journal.get_event(tmp_path, sequence)
    assert event is not None
    assert event["status"] == "applied"
    assert event["source_id"].startswith("src_")
    assert event["source_sha256"]
    status = journal.journal_status(tmp_path)
    assert status["last_applied_sequence"] == sequence
    assert status["worker"]["locked"] is False


def test_worker_marks_unsupported_source_for_review(tmp_path: Path) -> None:
    sequence = journal.record_event(
        tmp_path,
        "modified",
        current_path="40_delivery/notes.txt",
    )

    result = worker.process_next_event(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:00Z",
    )

    assert result["finish_status"] == "review-required"
    assert result["materialization"]["status"] == "skipped:unsupported-source"
    event = journal.get_event(tmp_path, sequence)
    assert event is not None
    assert event["status"] == "review-required"
    assert event["error_summary"] == "skipped:unsupported-source"
    assert not (tmp_path / "_meta" / "source-manifest.json").exists()


def test_worker_marks_no_current_path_event_for_review(tmp_path: Path) -> None:
    sequence = journal.record_event(
        tmp_path,
        "deleted",
        previous_path="40_delivery/registration.docx",
    )

    result = worker.process_next_event(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:00Z",
    )

    assert result["finish_status"] == "review-required"
    assert result["materialization"]["status"] == "skipped:unsupported-event"
    event = journal.get_event(tmp_path, sequence)
    assert event is not None
    assert event["status"] == "review-required"
    assert "no current path" in event["error_summary"]


def test_worker_marks_materialization_errors_failed_for_retry(tmp_path: Path) -> None:
    source = tmp_path / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic source bytes")
    sequence = journal.record_event(
        tmp_path,
        "modified",
        current_path="40_delivery/registration.docx",
    )

    result = worker.process_next_event(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:00Z",
        materialize_kwargs={
            "converter": FailingConverter(),
            "converter_name": "test-converter",
            "converter_version": "test",
            "append_audit": False,
        },
    )

    assert result["finish_status"] == "failed"
    assert result["materialization"]["status"] == "error:RuntimeError: conversion exploded"
    event = journal.get_event(tmp_path, sequence)
    assert event is not None
    assert event["status"] == "failed"
    assert "RuntimeError" in event["error_summary"]
    assert journal.retry_failed_event(tmp_path, sequence, now="2099-01-01T00:00:01Z") is True
    assert journal.get_event(tmp_path, sequence)["status"] == "queued"  # type: ignore[index]


def test_worker_respects_active_lease_from_another_holder(tmp_path: Path) -> None:
    sequence = journal.record_event(
        tmp_path,
        "modified",
        current_path="40_delivery/registration.docx",
    )
    journal.acquire_worker_lease(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:00Z",
        ttl_seconds=60,
    )
    converter = CountingConverter()

    result = worker.process_next_event(
        tmp_path,
        "worker-b",
        now="2099-01-01T00:00:01Z",
        materialize_kwargs={"converter": converter},
    )

    assert result["acquired"] is False
    assert result["processed"] is False
    assert result["lease"]["holder"] == "worker-a"
    assert converter.paths == []
    assert journal.get_event(tmp_path, sequence)["status"] == "queued"  # type: ignore[index]


def test_worker_drains_ready_events_under_one_lease(tmp_path: Path) -> None:
    first = tmp_path / "40_delivery" / "first.docx"
    second = tmp_path / "40_delivery" / "second.docx"
    first.parent.mkdir(parents=True)
    first.write_bytes(b"first synthetic source")
    second.write_bytes(b"second synthetic source")
    journal.record_event(tmp_path, "created", current_path="40_delivery/first.docx")
    journal.record_event(tmp_path, "modified", current_path="40_delivery/second.docx")
    converter = CountingConverter()

    result = worker.process_ready_events(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:00Z",
        materialize_kwargs={
            "converter": converter,
            "converter_name": "test-converter",
            "converter_version": "test",
            "append_audit": False,
        },
    )

    assert result["processed"] == 2
    assert result["finish_counts"] == {"applied": 2, "review-required": 0, "failed": 0}
    assert converter.paths == [str(first), str(second)]
    status = journal.journal_status(tmp_path)
    assert status["queued_count"] == 0
    assert status["state_counts"]["applied"] == 2
