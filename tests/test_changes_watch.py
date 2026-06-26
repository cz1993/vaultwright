# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from vaultwright.changes import feed, journal, watch


ROOT = Path(__file__).resolve().parents[1]


class TextConversion:
    def __init__(self, text: str) -> None:
        self.text_content = text


class CountingConverter:
    def __init__(self, text: str = "Extracted watch source") -> None:
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


def test_watch_once_reconciles_on_start_and_replays_missed_source(tmp_path: Path) -> None:
    source = tmp_path / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source_bytes = b"synthetic watch source"
    source.write_bytes(source_bytes)
    converter = CountingConverter()

    result = watch.watch_once(
        tmp_path,
        "watcher-a",
        now="2099-01-01T00:00:00Z",
        materialize_kwargs=converter_kwargs(converter),
    )

    assert result["mode"] == "once"
    assert result["reconcile_on_start"] is True
    assert result["reconciliation"]["events_queued"] == 1
    assert result["feed_events_queued"] == 0
    assert result["processed"] == 1
    assert result["finish_counts"] == {"applied": 1, "review-required": 0, "failed": 0}
    assert converter.paths == [str(source)]
    assert source.read_bytes() == source_bytes
    assert journal.journal_status(tmp_path)["last_reconciliation"] == "2099-01-01T00:00:00Z"


def test_watch_once_queues_feed_events_coalesces_and_replays(tmp_path: Path) -> None:
    source = tmp_path / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic watch source")
    converter = CountingConverter()
    observed = feed.StaticChangeFeed(
        [
            feed.ObservedChange("modified", "40_delivery/registration.docx", observed_at="2099-01-01T00:00:00Z"),
            feed.ObservedChange("modified", "40_delivery/registration.docx", observed_at="2099-01-01T00:00:01Z"),
            feed.ObservedChange("modified", "40_delivery/~$registration.docx"),
        ]
    )

    result = watch.watch_once(
        tmp_path,
        "watcher-a",
        observed_feed=observed,
        reconcile_on_start=False,
        now="2099-01-01T00:00:02Z",
        materialize_kwargs=converter_kwargs(converter),
    )

    assert result["reconcile_on_start"] is False
    assert result["reconciliation"]["events_queued"] == 0
    assert result["feed_events_queued"] == 1
    assert result["feed_sequences"] == [1]
    assert result["events_queued"] == 1
    assert result["processed"] == 1
    assert result["finish_counts"] == {"applied": 1, "review-required": 0, "failed": 0}
    assert converter.paths == [str(source)]
    event = journal.get_event(tmp_path, 1)
    assert event is not None
    assert event["observed_at"] == "2099-01-01T00:00:01Z"
    assert event["status"] == "applied"


def test_watch_once_cli_json_reconciles_review_required_legacy_doc(tmp_path: Path) -> None:
    source = tmp_path / "40_delivery" / "legacy.doc"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic legacy source")

    result = run_cli(tmp_path, "watch", "--once", "--json", "--holder", "cli-test")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "once"
    assert payload["events_queued"] == 1
    assert payload["reconciliation"]["event_counts"]["created"] == 1
    assert payload["feed_events_queued"] == 0
    assert payload["processed"] == 1
    assert payload["finish_counts"] == {"applied": 0, "failed": 0, "review-required": 1}


def test_plain_watch_explains_continuous_native_watch_is_not_ready(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "watch")

    assert result.returncode == 2
    assert "continuous native watching is not implemented yet" in result.stderr
