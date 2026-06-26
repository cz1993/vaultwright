# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from vaultwright.changes import changed_sync, journal


ROOT = Path(__file__).resolve().parents[1]


class TextConversion:
    def __init__(self, text: str) -> None:
        self.text_content = text


class CountingConverter:
    def __init__(self, text: str = "Extracted changed-sync source") -> None:
        self.text = text
        self.paths: list[str] = []

    def convert(self, path: str) -> TextConversion:
        self.paths.append(path)
        return TextConversion(self.text)


class FailingIfConverted:
    def convert(self, path: str) -> TextConversion:
        raise AssertionError(f"unchanged changed-sync pass should not convert: {path}")


def converter_kwargs(converter: object) -> dict[str, object]:
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


def test_sync_changed_reconciles_replays_and_preserves_source_bytes(tmp_path: Path) -> None:
    source = tmp_path / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source_bytes = b"synthetic changed-sync source"
    source.write_bytes(source_bytes)
    converter = CountingConverter()

    result = changed_sync.sync_changed(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:00Z",
        materialize_kwargs=converter_kwargs(converter),
    )

    assert result["events_queued"] == 1
    assert result["processed"] == 1
    assert result["finish_counts"] == {"applied": 1, "review-required": 0, "failed": 0}
    assert result["reconciliation"]["event_counts"]["created"] == 1
    assert result["replay"]["acquired"] is True
    assert converter.paths == [str(source)]
    assert source.read_bytes() == source_bytes
    assert (tmp_path / "_mirrors" / "40_delivery" / "registration.md").exists()
    status = journal.journal_status(tmp_path)
    assert status["last_applied_sequence"] == 1
    assert status["last_reconciliation"] == "2099-01-01T00:00:00Z"


def test_sync_changed_second_unchanged_pass_does_not_convert(tmp_path: Path) -> None:
    source = tmp_path / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic changed-sync source")
    first_converter = CountingConverter()
    first = changed_sync.sync_changed(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:00Z",
        materialize_kwargs=converter_kwargs(first_converter),
    )

    second = changed_sync.sync_changed(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:01Z",
        materialize_kwargs=converter_kwargs(FailingIfConverted()),
    )

    assert first["processed"] == 1
    assert second["events_queued"] == 0
    assert second["processed"] == 0
    assert second["reconciliation"]["full_hashes"] == 0
    assert first_converter.paths == [str(source)]


def test_sync_changed_delete_marks_manifest_source_missing_and_retains_mirror(tmp_path: Path) -> None:
    source = tmp_path / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic changed-sync source")
    first_converter = CountingConverter()
    first = changed_sync.sync_changed(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:00Z",
        materialize_kwargs=converter_kwargs(first_converter),
    )
    mirror = tmp_path / "_mirrors" / "40_delivery" / "registration.md"
    source.unlink()

    second = changed_sync.sync_changed(
        tmp_path,
        "worker-a",
        now="2099-01-01T00:00:01Z",
    )

    assert first["processed"] == 1
    assert second["reconciliation"]["event_counts"]["deleted"] == 1
    assert second["processed"] == 1
    assert second["finish_counts"] == {"applied": 1, "review-required": 0, "failed": 0}
    assert mirror.exists()
    status = json.loads((tmp_path / "_meta" / "source-manifest.json").read_text(encoding="utf-8"))
    assert status["records"][0]["lifecycle_state"] == "source_missing"


def test_sync_changed_cli_json_processes_review_required_legacy_doc(tmp_path: Path) -> None:
    source = tmp_path / "40_delivery" / "legacy.doc"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic legacy source")

    result = run_cli(tmp_path, "sync", "--changed", "--json", "--holder", "cli-test")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["events_queued"] == 1
    assert payload["processed"] == 1
    assert payload["finish_counts"] == {"applied": 0, "failed": 0, "review-required": 1}
    assert payload["reconciliation"]["event_counts"]["created"] == 1
    assert payload["replay"]["events"][0]["finish_status"] == "review-required"


def test_sync_changed_only_options_require_changed_mode(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "sync", "--json")

    assert result.returncode == 2
    assert "require --changed" in result.stderr
