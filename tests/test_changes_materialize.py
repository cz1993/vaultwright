# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from pathlib import Path
import json
import shutil

import yaml

from vaultwright.changes.fingerprint import MetadataFingerprint
from vaultwright.changes.materialize import (
    MaterializationError,
    materialize_office_delete,
    materialize_office_source,
)
from vaultwright.mirrors import office as office_sync


ROOT = Path(__file__).resolve().parents[1]


class TextConversion:
    def __init__(self, text: str) -> None:
        self.text_content = text


class CountingConverter:
    def __init__(self, text: str = "Extracted changed source") -> None:
        self.text = text
        self.paths: list[str] = []

    def convert(self, path: str) -> TextConversion:
        self.paths.append(path)
        return TextConversion(self.text)


class FailingIfConverted:
    def convert(self, path: str) -> TextConversion:
        raise AssertionError(f"unchanged source should not be converted: {path}")


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


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


def stability_fp(path: str, *, size: int, mtime_ns: int) -> MetadataFingerprint:
    return MetadataFingerprint(
        path=path,
        exists=True,
        is_file=True,
        is_symlink=False,
        size=size,
        mtime_ns=mtime_ns,
        identity_hint="1:1",
    )


def test_materialize_office_source_processes_only_requested_source(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    requested = vault / "40_delivery" / "registration.docx"
    other = vault / "50_operations" / "runbook.docx"
    requested.parent.mkdir(parents=True)
    other.parent.mkdir(parents=True)
    requested_bytes = b"synthetic requested source"
    other_bytes = b"synthetic other source"
    requested.write_bytes(requested_bytes)
    other.write_bytes(other_bytes)
    converter = CountingConverter()

    result = materialize_office_source(
        vault,
        "40_delivery/registration.docx",
        converter=converter,
        converter_name="test-converter",
        converter_version="test",
    )

    assert result["status"] == "created"
    assert result["action"] == "create"
    assert result["manifest_written"] is True
    assert result["audit_appended"] is True
    assert converter.paths == [str(requested)]
    assert requested.read_bytes() == requested_bytes
    assert other.read_bytes() == other_bytes
    assert (vault / "_mirrors" / "40_delivery" / "registration.md").exists()
    assert not (vault / "_mirrors" / "50_operations" / "runbook.md").exists()

    manifest = json.loads((vault / "_meta" / "source-manifest.json").read_text(encoding="utf-8"))
    assert [record["current_source_path"] for record in manifest["records"]] == [
        "40_delivery/registration.docx"
    ]
    record = result["record"]
    assert record["current_source_path"] == "40_delivery/registration.docx"
    assert record["mirror_path"] == "_mirrors/40_delivery/registration.md"
    assert record["lifecycle_state"] == "clean"
    audit_lines = (vault / "_meta" / "sync-audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(audit_lines) == 1
    audit = json.loads(audit_lines[0])
    assert audit["source_path"] == "40_delivery/registration.docx"
    assert audit["mirror_path"] == "_mirrors/40_delivery/registration.md"


def test_materialize_office_source_skips_unchanged_conversion(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic source bytes")

    first = materialize_office_source(
        vault,
        "40_delivery/registration.docx",
        converter=CountingConverter("first extract"),
        converter_name="test-converter",
        converter_version="test",
        append_audit=False,
    )
    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    manifest = vault / "_meta" / "source-manifest.json"
    first_mirror = mirror.read_text(encoding="utf-8")
    first_manifest = manifest.read_text(encoding="utf-8")

    second = materialize_office_source(
        vault,
        "40_delivery/registration.docx",
        converter=FailingIfConverted(),
        converter_name="test-converter",
        converter_version="test",
        append_audit=False,
    )

    assert first["status"] == "created"
    assert second["status"] == "unchanged"
    assert second["manifest_written"] is False
    assert mirror.read_text(encoding="utf-8") == first_mirror
    assert manifest.read_text(encoding="utf-8") == first_manifest


def test_materialize_office_delete_marks_source_missing_and_retains_mirror(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic source bytes")
    record = manifest_record(vault, "40_delivery/registration.docx")
    write_manifest(vault, [record])
    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    mirror.parent.mkdir(parents=True)
    mirror.write_text("retained generated evidence\n", encoding="utf-8")
    source.unlink()

    result = materialize_office_delete(
        vault,
        "40_delivery/registration.docx",
        source_id=str(record["source_id"]),
        source_sha256=str(record["source_sha256"]),
    )

    assert result["status"] == "source-missing"
    assert result["record"]["lifecycle_state"] == "source_missing"
    assert result["manifest_written"] is True
    assert result["audit_appended"] is True
    assert mirror.read_text(encoding="utf-8") == "retained generated evidence\n"
    manifest = json.loads((vault / "_meta" / "source-manifest.json").read_text(encoding="utf-8"))
    assert manifest["records"][0]["lifecycle_state"] == "source_missing"
    audit_lines = (vault / "_meta" / "sync-audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(audit_lines) == 1
    audit = json.loads(audit_lines[0])
    assert audit["status"] == "source_missing"
    assert audit["lifecycle_state"] == "source_missing"


def test_materialize_office_delete_requires_matching_source_id_and_path(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic source bytes")
    record = manifest_record(vault, "40_delivery/registration.docx", source_id="src_expected")
    write_manifest(vault, [record])
    source.unlink()

    result = materialize_office_delete(
        vault,
        "40_delivery/registration.docx",
        source_id="src_other",
    )

    assert result["status"] == "skipped:missing-manifest-record"
    assert result["record"]["lifecycle_state"] == "review-required"
    manifest = json.loads((vault / "_meta" / "source-manifest.json").read_text(encoding="utf-8"))
    assert manifest["records"][0]["lifecycle_state"] == "clean"


def test_materialize_office_source_honors_profile_mirror_root(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "mirror-config.yml").unlink()
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["policy_defaults"]["mirror_root"] = "_generated"
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    source = vault / "40_delivery" / "registration.docx"
    source.write_bytes(b"synthetic source bytes")

    result = materialize_office_source(
        vault,
        "40_delivery/registration.docx",
        converter=CountingConverter(),
        converter_name="test-converter",
        converter_version="test",
        append_audit=False,
    )

    assert result["status"] == "created"
    assert result["record"]["mirror_path"] == "_generated/40_delivery/registration.md"
    assert (vault / "_generated" / "40_delivery" / "registration.md").exists()
    assert not (vault / "_mirrors" / "40_delivery" / "registration.md").exists()


def test_materialize_office_source_rejects_unsafe_paths(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()

    try:
        materialize_office_source(vault, "../outside.docx", converter=CountingConverter())
    except MaterializationError as exc:
        assert "parent-directory" in str(exc)
    else:
        raise AssertionError("unsafe source path was accepted")


def test_materialize_office_source_waits_for_stable_candidate(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic source bytes")
    clock = FakeClock()
    first = stability_fp("40_delivery/registration.docx", size=12, mtime_ns=100)
    changed = stability_fp("40_delivery/registration.docx", size=22, mtime_ns=200)
    fingerprints = [first, changed, changed, changed]
    calls: list[str] = []

    def fingerprint_func(_root: Path, path: str | Path) -> MetadataFingerprint:
        calls.append(str(path))
        return fingerprints[min(len(calls) - 1, len(fingerprints) - 1)]

    converter = CountingConverter()

    result = materialize_office_source(
        vault,
        "40_delivery/registration.docx",
        converter=converter,
        converter_name="test-converter",
        converter_version="test",
        settle=True,
        settle_seconds=1.0,
        settle_check_interval_seconds=0.5,
        settle_timeout_seconds=3.0,
        stability_fingerprint_func=fingerprint_func,
        stability_clock=clock,
        stability_sleeper=clock.sleep,
        append_audit=False,
    )

    assert result["status"] == "created"
    assert result["stability"]["stable"] is True
    assert result["stability"]["observations"] == 4
    assert calls == ["40_delivery/registration.docx"] * 4
    assert converter.paths == [str(source)]
    assert (vault / "_mirrors" / "40_delivery" / "registration.md").exists()


def test_materialize_office_source_skips_unstable_candidate_without_conversion(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic source bytes")
    clock = FakeClock()
    first = stability_fp("40_delivery/registration.docx", size=12, mtime_ns=100)
    second = stability_fp("40_delivery/registration.docx", size=18, mtime_ns=200)
    calls: list[str] = []

    def alternating_fingerprint(_root: Path, path: str | Path) -> MetadataFingerprint:
        calls.append(str(path))
        return first if len(calls) % 2 else second

    converter = CountingConverter()

    result = materialize_office_source(
        vault,
        "40_delivery/registration.docx",
        converter=converter,
        converter_name="test-converter",
        converter_version="test",
        settle=True,
        settle_seconds=0.75,
        settle_check_interval_seconds=0.5,
        settle_timeout_seconds=1.0,
        stability_fingerprint_func=alternating_fingerprint,
        stability_clock=clock,
        stability_sleeper=clock.sleep,
    )

    assert result["status"] == "skipped:unstable-source"
    assert result["action"] == "stabilizing"
    assert result["manifest_written"] is False
    assert result["audit_appended"] is False
    assert result["stability"]["stable"] is False
    assert result["stability"]["timed_out"] is True
    assert result["record"]["lifecycle_state"] == "stabilizing"
    assert converter.paths == []
    assert calls == ["40_delivery/registration.docx"] * 3
    assert not (vault / "_mirrors" / "40_delivery" / "registration.md").exists()
    assert not (vault / "_meta" / "source-manifest.json").exists()
