# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from vaultwright.changes import journal, reconcile
from vaultwright.mirrors import office as office_sync


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


def write_manifest(root: Path, records: list[dict[str, object]]) -> None:
    manifest = office_sync.empty_manifest()
    manifest["records"] = records
    office_sync.write_source_manifest(root, manifest)


def manifest_record(root: Path, rel: str, source_id: str = "src_existing") -> dict[str, object]:
    source = root / rel
    return {
        "source_id": source_id,
        "current_source_path": rel,
        "previous_source_paths": [],
        "mirror_path": f"_mirrors/{Path(rel).with_suffix('.md').as_posix()}",
        "source_format": source.suffix.lstrip(".").lower(),
        "source_size": source.stat().st_size,
        "source_modified": office_sync.file_mtime_iso(source),
        "source_sha256": office_sync.sha256_of(source),
        "lifecycle_state": "clean",
        "warnings": [],
        "errors": [],
    }


def failing_hash(path: Path) -> str:
    raise AssertionError(f"unexpected full hash: {path}")


def test_reconcile_noops_for_manifest_current_source_without_hashing(tmp_path: Path) -> None:
    source = tmp_path / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic source bytes")
    write_manifest(tmp_path, [manifest_record(tmp_path, "40_delivery/registration.docx")])

    result = reconcile.reconcile_workspace(
        tmp_path,
        now="2099-01-01T00:00:00Z",
        hash_func=failing_hash,
    )

    assert result["events_queued"] == 0
    assert result["full_hashes"] == 0
    status = journal.journal_status(tmp_path)
    assert status["last_event_sequence"] == 0
    assert status["last_reconciliation"] == "2099-01-01T00:00:00Z"


def test_reconcile_queues_missed_create_without_full_hash(tmp_path: Path) -> None:
    source = tmp_path / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic source bytes")

    result = reconcile.reconcile_workspace(
        tmp_path,
        now="2099-01-01T00:00:00Z",
        hash_func=failing_hash,
    )

    assert result["event_counts"]["created"] == 1
    assert result["full_hashes"] == 0
    event = journal.get_event(tmp_path, result["events"][0]["sequence"])
    assert event is not None
    assert event["event_kind"] == "created"
    assert event["current_path"] == "40_delivery/registration.docx"
    assert event["metadata_fingerprint"]


def test_reconcile_queues_missed_modify_by_metadata_without_full_hash(tmp_path: Path) -> None:
    source = tmp_path / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"original synthetic source")
    write_manifest(tmp_path, [manifest_record(tmp_path, "40_delivery/registration.docx")])
    original_bytes = source.read_bytes()
    source.write_bytes(b"changed synthetic source with a different size")

    result = reconcile.reconcile_workspace(
        tmp_path,
        now="2099-01-01T00:00:00Z",
        hash_func=failing_hash,
    )

    assert result["event_counts"]["modified"] == 1
    assert result["full_hashes"] == 0
    assert source.read_bytes() != original_bytes
    event = journal.get_event(tmp_path, result["events"][0]["sequence"])
    assert event is not None
    assert event["event_kind"] == "modified"
    assert event["current_path"] == "40_delivery/registration.docx"
    assert event["source_id"] == "src_existing"


def test_reconcile_queues_missed_delete_for_missing_manifest_source(tmp_path: Path) -> None:
    source = tmp_path / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic source bytes")
    record = manifest_record(tmp_path, "40_delivery/registration.docx")
    source.unlink()
    write_manifest(tmp_path, [record])

    result = reconcile.reconcile_workspace(
        tmp_path,
        now="2099-01-01T00:00:00Z",
        hash_func=failing_hash,
    )

    assert result["event_counts"]["deleted"] == 1
    assert result["full_hashes"] == 0
    event = journal.get_event(tmp_path, result["events"][0]["sequence"])
    assert event is not None
    assert event["event_kind"] == "deleted"
    assert event["current_path"] is None
    assert event["previous_path"] == "40_delivery/registration.docx"
    assert event["source_id"] == "src_existing"


def test_reconcile_detects_move_with_candidate_only_hash(tmp_path: Path) -> None:
    old_source = tmp_path / "40_delivery" / "registration.docx"
    new_source = tmp_path / "40_delivery" / "renamed.docx"
    old_source.parent.mkdir(parents=True)
    old_source.write_bytes(b"synthetic source bytes")
    write_manifest(tmp_path, [manifest_record(tmp_path, "40_delivery/registration.docx")])
    old_source.rename(new_source)
    hashed: list[str] = []

    def counted_hash(path: Path) -> str:
        hashed.append(path.relative_to(tmp_path).as_posix())
        return office_sync.sha256_of(path)

    result = reconcile.reconcile_workspace(
        tmp_path,
        now="2099-01-01T00:00:00Z",
        hash_func=counted_hash,
    )

    assert result["event_counts"]["moved"] == 1
    assert result["event_counts"]["deleted"] == 0
    assert result["full_hashes"] == 1
    assert result["bytes_hashed"] == new_source.stat().st_size
    assert hashed == ["40_delivery/renamed.docx"]
    event = journal.get_event(tmp_path, result["events"][0]["sequence"])
    assert event is not None
    assert event["event_kind"] == "moved"
    assert event["current_path"] == "40_delivery/renamed.docx"
    assert event["previous_path"] == "40_delivery/registration.docx"
    assert event["source_id"] == "src_existing"


def test_reconcile_does_not_duplicate_existing_unresolved_event(tmp_path: Path) -> None:
    source = tmp_path / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic source bytes")

    first = reconcile.reconcile_workspace(tmp_path, now="2099-01-01T00:00:00Z")
    second = reconcile.reconcile_workspace(tmp_path, now="2099-01-01T00:00:01Z")

    assert first["events_queued"] == 1
    assert second["events_queued"] == 0
    assert second["events_skipped"] == 1
    assert journal.journal_status(tmp_path)["queued_count"] == 1


def test_reconcile_cli_json_queues_missed_create(tmp_path: Path) -> None:
    source = tmp_path / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic source bytes")

    result = run_cli(tmp_path, "reconcile", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["events_queued"] == 1
    assert payload["event_counts"]["created"] == 1
    assert payload["full_hashes"] == 0
    assert journal.journal_status(tmp_path)["last_reconciliation"]
