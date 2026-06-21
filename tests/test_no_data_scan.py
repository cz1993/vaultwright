# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
SCAN = ROOT / "scripts" / "no_data_scan.py"


def run_scan(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCAN), "--paths", *map(str, paths)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_no_data_scan_passes_clean_file(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    path.write_text("plain synthetic note\n", encoding="utf-8")

    result = run_scan(path)

    assert result.returncode == 0
    assert "OK" in result.stdout


def test_no_data_scan_flags_private_key(tmp_path: Path) -> None:
    path = tmp_path / "fixture.md"
    header = "-----BEGIN " + "PRIVATE KEY-----"
    path.write_text(f"{header}\nabc\n", encoding="utf-8")

    result = run_scan(path)

    assert result.returncode == 1
    assert "private key" in result.stderr


def test_no_data_scan_flags_openai_project_key(tmp_path: Path) -> None:
    path = tmp_path / "fixture.md"
    fake_key = "sk-" + "proj-" + ("A" * 30)
    path.write_text(f"token = {fake_key}\n", encoding="utf-8")

    result = run_scan(path)

    assert result.returncode == 1
    assert "openai api key" in result.stderr


def test_no_data_scan_flags_generated_python_package_artifacts(tmp_path: Path) -> None:
    artifact = tmp_path / "src" / "vaultwright.egg-info" / "PKG-INFO"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("Metadata-Version: 2.1\nName: vaultwright\n", encoding="utf-8")

    result = run_scan(artifact)

    assert result.returncode == 1
    assert "generated/vendor directory must not be committed" in result.stderr
    assert "vaultwright.egg-info" in result.stderr


def test_no_data_scan_flags_data_file_outside_allowed_dirs(tmp_path: Path) -> None:
    path = tmp_path / "customers.csv"
    path.write_text("name,email\nExample,example@example.com\n", encoding="utf-8")

    result = run_scan(path)

    assert result.returncode == 1
    assert "DATA_PROVENANCE.md" in result.stderr


def test_no_data_scan_flags_agent_readiness_result_packs(tmp_path: Path) -> None:
    path = tmp_path / "vault" / "_meta" / "agent-readiness-results.yml"
    path.parent.mkdir(parents=True)
    path.write_text("schema_version: 1\ncorpus: fixture\nresults: []\n", encoding="utf-8")

    result = run_scan(path)

    assert result.returncode == 1
    assert "benchmark result packs must stay out of the public repo" in result.stderr


def test_no_data_scan_flags_renamed_agent_readiness_result_pack_shape(tmp_path: Path) -> None:
    path = tmp_path / "vault" / "_meta" / "agent-readiness-results-public.yml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "schema_version: 1\n"
        "corpus: fixture\n"
        "results:\n"
        "  - task_id: answer-1\n"
        "    mode: vaultwright_markdown\n"
        "    score: 2\n",
        encoding="utf-8",
    )

    result = run_scan(path)

    assert result.returncode == 1
    assert "benchmark result packs must stay out of the public repo" in result.stderr


def test_no_data_scan_flags_private_agent_readiness_task_packs(tmp_path: Path) -> None:
    path = tmp_path / "vault" / "_meta" / "agent-readiness-tasks.yml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "schema_version: 1\n"
        "corpus: private-client\n"
        "comparison_modes: [raw_source_folder, document_chat_transcript, vaultwright_markdown]\n"
        "scoring:\n"
        "  scale: \"0-2\"\n"
        "tasks:\n"
        "  - id: private-answer\n"
        "    family: answer\n"
        "    prompt: What should the private client do?\n"
        "    source_paths: [40_delivery/private-plan.docx]\n"
        "    generated_mirror_paths: [_mirrors/40_delivery/private-plan.md]\n"
        "    curated_paths: []\n"
        "    success_criteria:\n"
        "      - cites declared evidence\n",
        encoding="utf-8",
    )

    result = run_scan(path)

    assert result.returncode == 1
    assert "private benchmark task packs must stay out of the public repo" in result.stderr


def test_no_data_scan_flags_renamed_agent_readiness_task_pack_shape(tmp_path: Path) -> None:
    path = tmp_path / "vault" / "_meta" / "pilot-agent-tasks.yml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "schema_version: 1\n"
        "corpus: private-client\n"
        "tasks:\n"
        "  - id: private-answer\n"
        "    family: answer\n"
        "    prompt: What should the private client do?\n"
        "    success_criteria:\n"
        "      - cites declared evidence\n",
        encoding="utf-8",
    )

    result = run_scan(path)

    assert result.returncode == 1
    assert "private benchmark task packs must stay out of the public repo" in result.stderr


def test_no_data_scan_allows_public_government_agent_readiness_task_pack() -> None:
    path = ROOT / "examples" / "government-services-vault" / "_meta" / "agent-readiness-tasks.yml"

    result = run_scan(path)

    assert result.returncode == 0, result.stderr


def test_no_data_scan_allows_generated_sync_audit_but_scans_text(tmp_path: Path) -> None:
    audit = tmp_path / "vault" / "_meta" / "sync-audit.jsonl"
    audit.parent.mkdir(parents=True)
    audit.write_text('{"tool":"sync_office_md","status":"created"}\n', encoding="utf-8")

    clean = run_scan(audit)

    assert clean.returncode == 0, clean.stderr

    fake_key = "sk-" + "proj-" + ("A" * 30)
    audit.write_text(f'{{"token":"{fake_key}"}}\n', encoding="utf-8")
    dirty = run_scan(audit)

    assert dirty.returncode == 1
    assert "openai api key" in dirty.stderr


def test_no_data_scan_blocks_staged_generated_sync_audit_without_provenance(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    audit = repo / "template" / "_meta" / "sync-audit.jsonl"
    audit.parent.mkdir(parents=True)
    audit.write_text(
        '{"source":"30_customers/RealCo/confidential_board_deck.pptx","status":"created"}\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "template/_meta/sync-audit.jsonl"], cwd=repo, check=True)

    result = subprocess.run(
        [sys.executable, str(SCAN), "--staged"],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "template/_meta/sync-audit.jsonl" in result.stderr
    assert "DATA_PROVENANCE.md" in result.stderr


def test_no_data_scan_default_blocks_generated_sync_audit_without_provenance(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    audit = repo / "template" / "_meta" / "sync-audit.jsonl"
    audit.parent.mkdir(parents=True)
    audit.write_text('{"tool":"sync_office_md","status":"created"}\n', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCAN)],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "template/_meta/sync-audit.jsonl" in result.stderr
    assert "DATA_PROVENANCE.md" in result.stderr


def test_no_data_scan_reads_staged_blob_not_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    path = repo / "fixture.md"
    header = "-----BEGIN " + "PRIVATE KEY-----"
    path.write_text(f"{header}\nabc\n", encoding="utf-8")
    subprocess.run(["git", "add", "fixture.md"], cwd=repo, check=True)
    path.write_text("clean worktree copy\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCAN), "--staged"],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "private key" in result.stderr


def test_no_data_scan_flags_staged_high_risk_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    path = repo / "secrets" / "readme.md"
    path.parent.mkdir()
    path.write_text("plain text\n", encoding="utf-8")
    subprocess.run(["git", "add", "-f", "secrets/readme.md"], cwd=repo, check=True)

    result = subprocess.run(
        [sys.executable, str(SCAN), "--staged"],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "high-risk path component" in result.stderr


def test_no_data_scan_flags_force_staged_generated_artifact(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    artifact = repo / ".DS_Store"
    artifact.write_bytes(b"Mac OS metadata")
    subprocess.run(["git", "add", "-f", ".DS_Store"], cwd=repo, check=True)

    result = subprocess.run(
        [sys.executable, str(SCAN), "--staged"],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "generated/OS artifact" in result.stderr


def test_no_data_scan_default_includes_ignored_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / ".gitignore").write_text("data/\n.env\n.DS_Store\n*.log\n__pycache__/\n", encoding="utf-8")
    data_dir = repo / "data"
    cache_dir = repo / "__pycache__"
    data_dir.mkdir()
    cache_dir.mkdir()
    header = "-----BEGIN " + "PRIVATE KEY-----"
    (data_dir / "secret.md").write_text(f"{header}\nabc\n", encoding="utf-8")
    (repo / ".env").write_text("PLAIN=1\n", encoding="utf-8")
    (repo / ".DS_Store").write_bytes(b"Mac OS metadata")
    (repo / "debug.log").write_text("log output\n", encoding="utf-8")
    (cache_dir / "ignored.md").write_text("ignored cache\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCAN)],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "data/secret.md" in result.stderr
    assert "private key" in result.stderr
    assert ".env" in result.stderr
    assert ".DS_Store" in result.stderr
    assert "debug.log" in result.stderr
    assert "generated/vendor directory" in result.stderr


def test_no_data_scan_scans_force_staged_skipped_dirs(tmp_path: Path) -> None:
    for dirname in ("__pycache__", "node_modules", "venv"):
        repo = tmp_path / dirname / "repo"
        repo.mkdir(parents=True)
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        path = repo / dirname / "secret.md"
        path.parent.mkdir()
        header = "-----BEGIN " + "PRIVATE KEY-----"
        path.write_text(f"{header}\nabc\n", encoding="utf-8")
        subprocess.run(["git", "add", "-f", f"{dirname}/secret.md"], cwd=repo, check=True)

        result = subprocess.run(
            [sys.executable, str(SCAN), "--staged"],
            cwd=repo,
            text=True,
            capture_output=True,
        )

        assert result.returncode == 1
        assert "generated/vendor directory" in result.stderr
        assert "private key" in result.stderr


def test_no_data_scan_flags_unexpected_ooxml_metadata(tmp_path: Path) -> None:
    path = tmp_path / "deck.pptx"
    core = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<cp:coreProperties xmlns:cp='http://schemas.openxmlformats.org/package/2006/metadata/core-properties' "
        "xmlns:dc='http://purl.org/dc/elements/1.1/'>"
        "<dc:creator>Someone Real</dc:creator>"
        "<cp:lastModifiedBy>Someone Real</cp:lastModifiedBy>"
        "</cp:coreProperties>"
    )
    with ZipFile(path, "w") as zf:
        zf.writestr("docProps/core.xml", core)

    result = run_scan(path)

    assert result.returncode == 1
    assert "unexpected OOXML" in result.stderr


def test_no_data_scan_flags_secret_in_ooxml_body(tmp_path: Path) -> None:
    path = tmp_path / "brief.docx"
    header = "-----BEGIN " + "PRIVATE KEY-----"
    core = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<cp:coreProperties xmlns:cp='http://schemas.openxmlformats.org/package/2006/metadata/core-properties' "
        "xmlns:dc='http://purl.org/dc/elements/1.1/'>"
        "<dc:creator>Vaultwright Example</dc:creator>"
        "</cp:coreProperties>"
    )
    document = (
        "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
        f"<w:body><w:p><w:r><w:t>{header}</w:t></w:r></w:p></w:body>"
        "</w:document>"
    )
    with ZipFile(path, "w") as zf:
        zf.writestr("docProps/core.xml", core)
        zf.writestr("word/document.xml", document)

    result = run_scan(path)

    assert result.returncode == 1
    assert "private key" in result.stderr


def test_no_data_scan_flags_secret_in_ooxml_header(tmp_path: Path) -> None:
    path = tmp_path / "brief.docx"
    header = "-----BEGIN " + "PRIVATE KEY-----"
    core = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<cp:coreProperties xmlns:cp='http://schemas.openxmlformats.org/package/2006/metadata/core-properties' "
        "xmlns:dc='http://purl.org/dc/elements/1.1/'>"
        "<dc:creator>Vaultwright Example</dc:creator>"
        "</cp:coreProperties>"
    )
    header_xml = (
        "<w:hdr xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
        f"<w:p><w:r><w:t>{header}</w:t></w:r></w:p>"
        "</w:hdr>"
    )
    with ZipFile(path, "w") as zf:
        zf.writestr("docProps/core.xml", core)
        zf.writestr("word/header1.xml", header_xml)

    result = run_scan(path)

    assert result.returncode == 1
    assert "word/header1.xml" in result.stderr
    assert "private key" in result.stderr


def test_no_data_scan_flags_secret_in_ooxml_relationship_attribute(tmp_path: Path) -> None:
    path = tmp_path / "brief.docx"
    fake_key = "sk-" + "proj-" + ("A" * 30)
    rels = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
        f"<Relationship Id='rId1' Type='external' Target='https://example.invalid/{fake_key}'/>"
        "</Relationships>"
    )
    with ZipFile(path, "w") as zf:
        zf.writestr("word/_rels/document.xml.rels", rels)

    result = run_scan(path)

    assert result.returncode == 1
    assert "word/_rels/document.xml.rels" in result.stderr
    assert "openai api key" in result.stderr


def test_no_data_scan_flags_payment_card_in_ooxml_relationship_attribute(tmp_path: Path) -> None:
    path = tmp_path / "brief.docx"
    card = "-".join(["4111", "1111", "1111", "1111"])
    rels = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
        f"<Relationship Id='rId1' Type='external' Target='https://example.invalid/{card}'/>"
        "</Relationships>"
    )
    with ZipFile(path, "w") as zf:
        zf.writestr("word/_rels/document.xml.rels", rels)

    result = run_scan(path)

    assert result.returncode == 1
    assert "word/_rels/document.xml.rels" in result.stderr
    assert "payment card" in result.stderr


def test_no_data_scan_flags_payment_card_in_ooxml_custom_xml(tmp_path: Path) -> None:
    path = tmp_path / "brief.docx"
    card = " ".join(["4111", "1111", "1111", "1111"])
    custom = f"<root><value>{card}</value></root>"
    with ZipFile(path, "w") as zf:
        zf.writestr("customXml/item1.xml", custom)

    result = run_scan(path)

    assert result.returncode == 1
    assert "customXml/item1.xml" in result.stderr
    assert "payment card" in result.stderr


def test_no_data_scan_flags_unexpected_ooxml_app_metadata(tmp_path: Path) -> None:
    path = tmp_path / "brief.docx"
    app = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<Properties xmlns='http://schemas.openxmlformats.org/officeDocument/2006/extended-properties'>"
        "<Company>RealCo Confidential</Company>"
        "<Manager>Jane Realperson</Manager>"
        "</Properties>"
    )
    with ZipFile(path, "w") as zf:
        zf.writestr("docProps/app.xml", app)

    result = run_scan(path)

    assert result.returncode == 1
    assert "docProps/app.xml" in result.stderr
    assert "Company" in result.stderr or "company" in result.stderr


def test_no_data_scan_flags_unexpected_ooxml_custom_metadata(tmp_path: Path) -> None:
    path = tmp_path / "brief.docx"
    custom = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<Properties xmlns='http://schemas.openxmlformats.org/officeDocument/2006/custom-properties' "
        "xmlns:vt='http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes'>"
        "<property name='MatterName'><vt:lpwstr>RealCo Integration</vt:lpwstr></property>"
        "</Properties>"
    )
    with ZipFile(path, "w") as zf:
        zf.writestr("docProps/custom.xml", custom)

    result = run_scan(path)

    assert result.returncode == 1
    assert "docProps/custom.xml" in result.stderr
    assert "custom metadata" in result.stderr


def test_no_data_scan_flags_camelcase_ooxml_core_metadata(tmp_path: Path) -> None:
    path = tmp_path / "brief.docx"
    core = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<cp:coreProperties xmlns:cp='http://schemas.openxmlformats.org/package/2006/metadata/core-properties' "
        "xmlns:dc='http://purl.org/dc/elements/1.1/'>"
        "<cp:lastModifiedBy>Jane Realperson</cp:lastModifiedBy>"
        "<cp:contentStatus>RealCo Confidential</cp:contentStatus>"
        "<cp:hyperlinkBase>https://realco.example/private</cp:hyperlinkBase>"
        "</cp:coreProperties>"
    )
    with ZipFile(path, "w") as zf:
        zf.writestr("docProps/core.xml", core)

    result = run_scan(path)

    assert result.returncode == 1
    assert "lastmodifiedby" in result.stderr
    assert "contentstatus" in result.stderr
    assert "hyperlinkbase" in result.stderr


def test_no_data_scan_matches_ooxml_part_names_case_insensitively(tmp_path: Path) -> None:
    path = tmp_path / "brief.docx"
    card = " ".join(["4111", "1111", "1111", "1111"])
    document = (
        "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
        f"<w:body><w:p><w:r><w:t>{card}</w:t></w:r></w:p></w:body>"
        "</w:document>"
    )
    core = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<cp:coreProperties xmlns:cp='http://schemas.openxmlformats.org/package/2006/metadata/core-properties' "
        "xmlns:dc='http://purl.org/dc/elements/1.1/'>"
        "<dc:creator>Jane Realperson</dc:creator>"
        "</cp:coreProperties>"
    )
    with ZipFile(path, "w") as zf:
        zf.writestr("WORD/DOCUMENT.XML", document)
        zf.writestr("DOCPROPS/CORE.XML", core)

    result = run_scan(path)

    assert result.returncode == 1
    assert "WORD/DOCUMENT.XML" in result.stderr
    assert "payment card" in result.stderr
    assert "DOCPROPS/CORE.XML" in result.stderr
    assert "creator" in result.stderr


def test_no_data_scan_staged_uses_staged_provenance_not_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "examples").mkdir()
    (repo / "examples" / "DATA_PROVENANCE.md").write_text(
        "# Data Provenance\n",
        encoding="utf-8",
    )
    data = repo / "fixture.csv"
    data.write_text("name,email\nExample,example@example.com\n", encoding="utf-8")
    subprocess.run(["git", "add", "examples/DATA_PROVENANCE.md", "fixture.csv"], cwd=repo, check=True)
    (repo / "examples" / "DATA_PROVENANCE.md").write_text(
        "# Data Provenance\n\n`fixture.csv`\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCAN), "--staged"],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "fixture.csv" in result.stderr
    assert "DATA_PROVENANCE.md" in result.stderr


def test_no_data_scan_blocks_staged_symlink(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    link = repo / "innocent-link"
    link.symlink_to("/Users/cz/private/customer.csv")
    subprocess.run(["git", "add", "innocent-link"], cwd=repo, check=True)

    result = subprocess.run(
        [sys.executable, str(SCAN), "--staged"],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "symlink must not be committed" in result.stderr


def test_no_data_scan_blocks_staged_symlink_typechange(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.invalid"], cwd=repo, check=True)
    note = repo / "note.md"
    note.write_text("clean\n", encoding="utf-8")
    subprocess.run(["git", "add", "note.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    note.unlink()
    note.symlink_to("/Users/cz/private/customer.csv")
    subprocess.run(["git", "add", "note.md"], cwd=repo, check=True)

    result = subprocess.run(
        [sys.executable, str(SCAN), "--staged"],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "symlink must not be committed" in result.stderr


def test_no_data_scan_allows_provenance_listed_example_office_files() -> None:
    path = ROOT / "examples/northwind-robotics-vault/40_delivery/2026-q1_service_readiness_review.pptx"

    result = run_scan(path)

    assert result.returncode == 0
