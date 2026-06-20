# SPDX-License-Identifier: AGPL-3.0-or-later
import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SENTINEL = "%% AUTO-GENERATED BELOW — DO NOT EDIT %%"
TEST_SHA = "0" * 64


def source_mirror_fields(source: str, source_id: str = "src-test") -> str:
    return (
        f"source: {source}\n"
        f"source_id: {source_id}\n"
        "source_manifest: _meta/source-manifest.json\n"
        f"source_sha256: \"{TEST_SHA}\"\n"
    )


def repo_mirror_fields(repo: str = "local/fixture", repo_id: str = "repo-test") -> str:
    return (
        f"repo: {repo}\n"
        f"repo_id: {repo_id}\n"
        "repo_manifest: _meta/repo-manifest.json\n"
    )


def write_source_manifest(
    vault: Path,
    *records: tuple[str, str, str],
) -> None:
    payload = {
        "schema_version": 1,
        "records": [
            {
                "source_id": source_id,
                "current_source_path": source,
                "mirror_path": mirror,
                "source_sha256": TEST_SHA,
            }
            for source_id, source, mirror in records
        ],
    }
    (vault / "_meta" / "source-manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def write_repo_manifest(vault: Path, *records: tuple[str, str]) -> None:
    payload = {
        "schema_version": 1,
        "records": [
            {
                "repo_id": repo_id,
                "note_path": note_path,
            }
            for repo_id, note_path in records
        ],
    }
    (vault / "_meta" / "repo-manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def test_template_linter_exits_nonzero_for_blocking_issue(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    bad_note = vault / "10_governance" / "bad.md"
    bad_note.write_text("# Missing frontmatter\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Missing/invalid frontmatter: 1" in result.stdout


def test_template_linter_keeps_warning_only_orphans_zero_exit(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    note = vault / "10_governance" / "orphan.md"
    note.write_text(
        "---\n"
        "title: Orphan\n"
        "type: note\n"
        "status: active\n"
        "domain: governance\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Orphan\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Orphan notes (no inbound links): 1" in result.stdout


def test_template_linter_blocks_unknown_domain(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    note = vault / "10_governance" / "bad-domain.md"
    note.write_text(
        "---\n"
        "title: Bad Domain\n"
        "type: note\n"
        "status: active\n"
        "domain: marketing\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Bad Domain\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Invalid domain: 1" in result.stdout
    assert "bad-domain.md  [marketing]" in result.stdout


def test_template_linter_blocks_missing_domain_map(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "domain-map.yml").unlink()

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Domain map errors: 1" in result.stdout
    assert "_meta/domain-map.yml  [missing]" in result.stdout


def test_template_linter_blocks_malformed_domain_map(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "domain-map.yml").write_text("domains: [", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Domain map errors: 1" in result.stdout
    assert "_meta/domain-map.yml  [invalid YAML]" in result.stdout


def test_template_linter_blocks_domain_folder_mismatch(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    legacy = vault / "clients"
    legacy.mkdir()
    note = legacy / "Acme.md"
    note.write_text(
        "---\n"
        "title: Acme\n"
        "type: note\n"
        "status: active\n"
        "domain: customers\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Acme\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Domain/folder mismatch: 1" in result.stdout
    assert "clients/Acme.md  [customers -> 30_customers]" in result.stdout


def test_template_linter_checks_account_frontmatter_links(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    note = vault / "10_governance" / "account-link.md"
    note.write_text(
        "---\n"
        "title: Account Link\n"
        "type: note\n"
        "status: active\n"
        "domain: governance\n"
        "account: \"[[Missing Account]]\"\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Account Link\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Unresolved wikilinks: 1" in result.stdout
    assert "Missing Account" in result.stdout


def test_template_linter_blocks_account_client_mismatch(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    customers = vault / "30_customers"
    (customers / "Acme.md").write_text(
        "---\n"
        "title: Acme\n"
        "type: entity\n"
        "status: active\n"
        "domain: customers\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Acme\n",
        encoding="utf-8",
    )
    (customers / "Other.md").write_text(
        "---\n"
        "title: Other\n"
        "type: entity\n"
        "status: active\n"
        "domain: customers\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Other\n",
        encoding="utf-8",
    )
    note = customers / "mismatch.md"
    note.write_text(
        "---\n"
        "title: Mismatch\n"
        "type: note\n"
        "status: active\n"
        "domain: customers\n"
        "account: \"[[Acme]]\"\n"
        "client: \"[[Other]]\"\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Mismatch\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Account/client mismatch: 1" in result.stdout


def test_template_linter_blocks_client_without_account(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    note = vault / "30_customers" / "client-only.md"
    note.write_text(
        "---\n"
        "title: Client Only\n"
        "type: note\n"
        "status: active\n"
        "domain: customers\n"
        "client: \"[[Acme]]\"\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Client Only\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Account/client mismatch: 1" in result.stdout
    assert "client requires account" in result.stdout


def test_template_linter_blocks_uppercase_markdown_extension(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    note = vault / "10_governance" / "Bad.MD"
    note.write_text("# Missing frontmatter\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Non-lowercase markdown extension: 1" in result.stdout
    assert "Missing/invalid frontmatter: 1" in result.stdout


def test_template_linter_accepts_dedicated_office_mirror_layout(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    source = vault / "30_customers" / "acme" / "brief.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"not a real docx; lint only checks mirror presence")
    mirror = vault / "_mirrors" / "30_customers" / "acme" / "brief.md"
    mirror.parent.mkdir(parents=True)
    mirror.write_text(
        "---\n"
        "title: Brief\n"
        "type: source-mirror\n"
        "status: active\n"
        "domain: customers\n"
        f"{source_mirror_fields('30_customers/acme/brief.docx')}"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Brief\n\n{SENTINEL}\n\n## Extracted content\n",
        encoding="utf-8",
    )
    write_source_manifest(
        vault,
        ("src-test", "30_customers/acme/brief.docx", "_mirrors/30_customers/acme/brief.md"),
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Office files without a mirror: 0" in result.stdout
    assert "Domain/folder mismatch: 0" in result.stdout


def test_template_linter_accepts_alias_source_with_canonical_mirror_layout(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    source = vault / "clients" / "acme" / "brief.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"not a real docx; lint only checks mirror presence")
    mirror = vault / "_mirrors" / "30_customers" / "acme" / "brief.md"
    mirror.parent.mkdir(parents=True)
    mirror.write_text(
        "---\n"
        "title: Brief\n"
        "type: source-mirror\n"
        "status: active\n"
        "domain: customers\n"
        f"{source_mirror_fields('clients/acme/brief.docx')}"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Brief\n\n{SENTINEL}\n\n## Extracted content\n",
        encoding="utf-8",
    )
    write_source_manifest(
        vault,
        ("src-test", "clients/acme/brief.docx", "_mirrors/30_customers/acme/brief.md"),
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Office files without a mirror: 0" in result.stdout
    assert "Domain/folder mismatch: 0" in result.stdout


def test_template_linter_blocks_sibling_office_mirror_by_default(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    source = vault / "30_customers" / "brief.docx"
    source.write_bytes(b"not a real docx; lint only checks mirror presence")
    (vault / "30_customers" / "brief.md").write_text(
        "---\n"
        "title: Brief\n"
        "type: source-mirror\n"
        "status: active\n"
        "domain: customers\n"
        f"{source_mirror_fields('30_customers/brief.docx')}"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Brief\n\n{SENTINEL}\n\n## Extracted content\n",
        encoding="utf-8",
    )
    write_source_manifest(vault, ("src-test", "30_customers/brief.docx", "30_customers/brief.md"))

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Office files without a mirror: 1" in result.stdout


def test_template_linter_requires_generated_sibling_mirror_not_curated_note(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "mirror-config.yml").write_text(
        "office_mirrors:\n"
        "  mode: sibling\n"
        "  root: _mirrors\n",
        encoding="utf-8",
    )
    source = vault / "40_delivery" / "brief.docx"
    source.write_bytes(b"not a real docx; lint only checks mirror presence")
    (vault / "40_delivery" / "brief.md").write_text(
        "---\n"
        "title: Brief\n"
        "type: note\n"
        "status: active\n"
        "domain: delivery\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Brief\n\n"
        "This curated note is not a generated source mirror.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Office files without a mirror: 1" in result.stdout
    assert "40_delivery/brief.docx  (no markdown mirror)" in result.stdout


def test_template_linter_accepts_sibling_office_mirror_in_legacy_mode(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "mirror-config.yml").write_text(
        "office_mirrors:\n"
        "  mode: sibling\n"
        "  root: _mirrors\n",
        encoding="utf-8",
    )
    source = vault / "30_customers" / "brief.docx"
    source.write_bytes(b"not a real docx; lint only checks mirror presence")
    (vault / "30_customers" / "brief.md").write_text(
        "---\n"
        "title: Brief\n"
        "type: source-mirror\n"
        "status: active\n"
        "domain: customers\n"
        f"{source_mirror_fields('30_customers/brief.docx')}"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Brief\n\n{SENTINEL}\n\n## Extracted content\n",
        encoding="utf-8",
    )
    write_source_manifest(vault, ("src-test", "30_customers/brief.docx", "30_customers/brief.md"))

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Office files without a mirror: 0" in result.stdout


def test_template_linter_accepts_alias_source_with_sibling_mirror_in_legacy_mode(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "mirror-config.yml").write_text(
        "office_mirrors:\n"
        "  mode: sibling\n"
        "  root: _mirrors\n",
        encoding="utf-8",
    )
    source = vault / "clients" / "acme" / "brief.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"not a real docx; lint only checks mirror presence")
    (vault / "clients" / "acme" / "brief.md").write_text(
        "---\n"
        "title: Brief\n"
        "type: source-mirror\n"
        "status: active\n"
        "domain: customers\n"
        f"{source_mirror_fields('clients/acme/brief.docx')}"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Brief\n\n{SENTINEL}\n\n## Extracted content\n",
        encoding="utf-8",
    )
    write_source_manifest(
        vault,
        ("src-test", "clients/acme/brief.docx", "clients/acme/brief.md"),
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Domain/folder mismatch: 0" in result.stdout
    assert "Office files without a mirror: 0" in result.stdout


def test_template_linter_blocks_sibling_mirror_from_unmapped_source_root(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "mirror-config.yml").write_text(
        "office_mirrors:\n"
        "  mode: sibling\n"
        "  root: _mirrors\n",
        encoding="utf-8",
    )
    source = vault / "random_folder" / "acme" / "brief.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"not a real docx; lint only checks mirror presence")
    mirror = vault / "random_folder" / "acme" / "brief.md"
    mirror.write_text(
        "---\n"
        "title: Brief\n"
        "type: source-mirror\n"
        "status: active\n"
        "domain: customers\n"
        f"{source_mirror_fields('random_folder/acme/brief.docx')}"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Brief\n\n{SENTINEL}\n\n## Extracted content\n",
        encoding="utf-8",
    )
    write_source_manifest(
        vault,
        ("src-test", "random_folder/acme/brief.docx", "random_folder/acme/brief.md"),
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Domain/folder mismatch: 1" in result.stdout
    assert "random_folder/acme/brief.md  [customers -> 30_customers]" in result.stdout
    assert "Office files without a mirror: 0" in result.stdout


def test_template_linter_blocks_source_mirror_type_with_wrong_sibling_path(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "mirror-config.yml").write_text(
        "office_mirrors:\n"
        "  mode: sibling\n"
        "  root: _mirrors\n",
        encoding="utf-8",
    )
    note = vault / "40_delivery" / "hidden-generated-type.md"
    note.write_text(
        "---\n"
        "title: Hidden Generated Type\n"
        "type: source-mirror\n"
        "status: active\n"
        "domain: delivery\n"
        "source: 40_delivery/real-source.docx\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Hidden Generated Type\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Mirror layout errors: 1" in result.stdout
    assert "source-mirror requires generated sentinel, manifest metadata, and source-derived sibling path" in result.stdout


def test_template_linter_blocks_source_mirror_type_outside_dedicated_mirror_root(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    note = vault / "40_delivery" / "hidden-generated-type.md"
    note.write_text(
        "---\n"
        "title: Hidden Generated Type\n"
        "type: source-mirror\n"
        "status: active\n"
        "domain: delivery\n"
        "source: 40_delivery/hidden-generated-type.docx\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Hidden Generated Type\n\n"
        "Hand-authored content should not hide from orphan or overlap checks by claiming a mirror type.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Mirror layout errors: 1" in result.stdout
    assert "source-mirror notes belong under _mirrors" in result.stdout


def test_template_linter_blocks_source_mirror_under_mirror_root_with_wrong_source_path(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    note = vault / "_mirrors" / "40_delivery" / "hand-authored.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "---\n"
        "title: Hand Authored\n"
        "type: source-mirror\n"
        "status: active\n"
        "domain: delivery\n"
        f"{source_mirror_fields('40_delivery/missing.docx')}"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Hand Authored\n\n"
        f"{SENTINEL}\n\n"
        "Hand-authored content under _mirrors should not be exempt unless the path matches source.\n",
        encoding="utf-8",
    )
    write_source_manifest(
        vault,
        ("src-test", "40_delivery/missing.docx", "_mirrors/40_delivery/hand-authored.md"),
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Mirror layout errors: 1" in result.stdout
    assert "source-mirror requires generated sentinel, manifest metadata, and source-derived path" in result.stdout


def test_template_linter_blocks_source_mirror_without_generated_contract_under_mirror_root(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    note = vault / "_mirrors" / "40_delivery" / "missing.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "---\n"
        "title: Missing\n"
        "type: source-mirror\n"
        "status: active\n"
        "domain: delivery\n"
        "source: 40_delivery/missing.docx\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Missing\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Mirror layout errors: 1" in result.stdout
    assert "source-mirror requires generated sentinel, manifest metadata, and source-derived path" in result.stdout


def test_template_linter_blocks_repo_mirror_type_outside_repo_mirror_root(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    note = vault / "40_delivery" / "hidden-repo-type.md"
    note.write_text(
        "---\n"
        "title: Hidden Repo Type\n"
        "type: repo-mirror\n"
        "status: active\n"
        "domain: delivery\n"
        "repo: local/hidden\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Hidden Repo Type\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Mirror layout errors: 1" in result.stdout
    assert "repo-mirror notes belong under 80_sources/repos" in result.stdout


def test_template_linter_blocks_repo_mirror_without_generated_contract_under_repo_root(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    note = vault / "80_sources" / "repos" / "fixture.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        "---\n"
        "title: Fixture Repo\n"
        "type: repo-mirror\n"
        "status: active\n"
        "domain: sources\n"
        "repo: local/fixture\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Fixture Repo\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Mirror layout errors: 1" in result.stdout
    assert "repo-mirror requires generated sentinel and manifest metadata" in result.stdout


def test_template_linter_reports_overlap_candidates_as_warning_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    first = vault / "40_delivery" / "grant-readiness.md"
    second = vault / "40_delivery" / "funding-readiness.md"
    body = (
        "The intake checklist reviews eligibility, incorporation status, payroll evidence, "
        "tax registration, cashflow runway, milestone plan, owner responsibilities, supporting "
        "documents, application deadline, budget assumptions, reporting cadence, compliance risks, "
        "grant program fit, review notes, approval path, and follow-up actions.\n"
    )
    first.write_text(
        "---\n"
        "title: Grant Readiness Checklist\n"
        "type: guide\n"
        "status: active\n"
        "domain: delivery\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Grant Readiness Checklist\n\n{body}",
        encoding="utf-8",
    )
    second.write_text(
        "---\n"
        "title: Funding Readiness Checklist\n"
        "type: guide\n"
        "status: active\n"
        "domain: delivery\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Funding Readiness Checklist\n\n{body}",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Potential duplicate/overlap notes: 1" in result.stdout
    assert "40_delivery/grant-readiness.md" in result.stdout
    assert "40_delivery/funding-readiness.md" in result.stdout
    assert "content overlap" in result.stdout


def test_template_linter_skips_generated_mirrors_for_overlap_and_orphan_candidates(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    body = (
        "Repeated generated mirror text about eligibility incorporation payroll tax registration "
        "cashflow runway milestones supporting documents application deadline budget assumptions "
        "reporting cadence compliance risks review notes approval path and follow-up actions.\n"
    )
    for name in ("first", "second"):
        mirror = vault / "_mirrors" / "40_delivery" / f"{name}.md"
        mirror.parent.mkdir(parents=True, exist_ok=True)
        mirror.write_text(
            "---\n"
            f"title: {name.title()} Mirror\n"
            "type: source-mirror\n"
            "status: active\n"
            "domain: delivery\n"
            f"{source_mirror_fields(f'40_delivery/{name}.docx', f'src-{name}')}"
            "created: 2026-01-01\n"
            "updated: 2026-01-01\n"
            "---\n"
            f"# {name.title()} Mirror\n\n{SENTINEL}\n\n## Extracted content\n\n{body}",
            encoding="utf-8",
        )
    write_source_manifest(
        vault,
        ("src-first", "40_delivery/first.docx", "_mirrors/40_delivery/first.md"),
        ("src-second", "40_delivery/second.docx", "_mirrors/40_delivery/second.md"),
    )
    repo_note = vault / "80_sources" / "repos" / "fixture.md"
    repo_note.parent.mkdir(parents=True, exist_ok=True)
    repo_note.write_text(
        "---\n"
        "title: Fixture Repo\n"
        "type: repo-mirror\n"
        "status: active\n"
        "domain: sources\n"
        f"{repo_mirror_fields()}"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Fixture Repo\n\n{SENTINEL}\n\n## Repository\n\n"
        "Repeated generated mirror text about eligibility incorporation payroll tax registration "
        "cashflow runway milestones supporting documents application deadline budget assumptions "
        "reporting cadence compliance risks review notes approval path and follow-up actions.\n",
        encoding="utf-8",
    )
    write_repo_manifest(vault, ("repo-test", "80_sources/repos/fixture.md"))

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Orphan notes (no inbound links): 0" in result.stdout
    assert "Potential duplicate/overlap notes: 0" in result.stdout
