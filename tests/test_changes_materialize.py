# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from pathlib import Path
import json
import shutil

import yaml

from vaultwright.changes.materialize import MaterializationError, materialize_office_source


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
