# SPDX-License-Identifier: AGPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import yaml

from vaultwright.annotation_migration import annotation_migration_plan, write_annotation_sidecars


ROOT = Path(__file__).resolve().parents[1]
SENTINEL = "%% AUTO-GENERATED BELOW — DO NOT EDIT %%"
TEST_SHA = "0" * 64


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_sha_for(vault: Path, source: str) -> str:
    path = vault / source
    return sha256_bytes(path.read_bytes()) if path.exists() else TEST_SHA


def source_mirror_fields(source: str, source_id: str = "src-test", source_sha256: str = TEST_SHA) -> str:
    return (
        f"source: {source}\n"
        f"source_id: {source_id}\n"
        "source_manifest: _meta/source-manifest.json\n"
        f"source_sha256: \"{source_sha256}\"\n"
    )


def repo_mirror_fields(repo: str = "local/fixture", repo_id: str = "repo-test") -> str:
    return (
        f"repo: {repo}\n"
        f"repo_id: {repo_id}\n"
        "repo_manifest: _meta/repo-manifest.json\n"
    )


def repo_id_for(repo: str, note: str) -> str:
    digest = hashlib.sha256(f"{repo}\0{note}".encode("utf-8")).hexdigest()[:20]
    return f"repo_{digest}"


def write_source_manifest(
    vault: Path,
    *records: tuple[str, str, str] | tuple[str, str, str, str],
) -> None:
    payload = {
        "schema_version": 1,
        "records": [
            {
                "source_id": record[0],
                "current_source_path": record[1],
                "mirror_path": record[2],
                "source_sha256": record[3] if len(record) > 3 else source_sha_for(vault, record[1]),
                "lifecycle_state": "clean",
            }
            for record in records
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


def load_profile(vault: Path) -> dict:
    return yaml.safe_load((vault / "_meta" / "profile.yml").read_text(encoding="utf-8"))


def write_profile(vault: Path, profile: dict) -> None:
    (vault / "_meta" / "profile.yml").write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")


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


def test_template_linter_skips_generated_meta_markdown_reports(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    report = vault / "_meta" / "migration-review-worksheet.md"
    report.write_text("# Vaultwright Migration Review Worksheet\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Missing/invalid frontmatter: 0" in result.stdout
    assert "_meta/migration-review-worksheet.md" not in result.stdout


def test_template_linter_skips_catalog_gateway_for_orphan_warnings(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    catalog = vault / "CATALOG.md"
    catalog.write_text("# Documentation Catalog\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Orphan notes (no inbound links): 0" in result.stdout
    assert "CATALOG.md" not in result.stdout


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


def test_template_linter_reports_domain_alias_recommendation(tmp_path: Path) -> None:
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
    assert "bad-domain.md  [marketing -> market (20_market/)]" in result.stdout


def test_template_linter_blocks_unknown_domain(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    note = vault / "10_governance" / "bad-domain.md"
    note.write_text(
        "---\n"
        "title: Bad Domain\n"
        "type: note\n"
        "status: active\n"
        "domain: special-projects\n"
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
    assert "bad-domain.md  [special-projects]" in result.stdout


def test_template_linter_reads_profile_contract_for_allowed_values(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    profile = load_profile(vault)
    profile["domains"]["research"] = {
        "folder": "25_research",
        "purpose": "Profile-defined research material.",
    }
    profile["note_types"]["brief"] = {"purpose": "Profile-defined brief."}
    profile["statuses"]["queued"] = {"purpose": "Profile-defined queue state."}
    profile["required_properties"].append("evidence_level")
    write_profile(vault, profile)
    folder = vault / "25_research"
    folder.mkdir()
    note = folder / "brief.md"
    note.write_text(
        "---\n"
        "title: Research Brief\n"
        "type: brief\n"
        "status: queued\n"
        "domain: research\n"
        "evidence_level: public\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Research Brief\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout
    assert "Profile errors: 0" in result.stdout
    assert "Invalid type: 0" in result.stdout
    assert "Invalid status: 0" in result.stdout
    assert "Invalid domain: 0" in result.stdout
    assert "Domain/folder mismatch: 0" in result.stdout


def test_template_linter_blocks_full_profile_validator_errors(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    profile = load_profile(vault)
    profile["policy_defaults"]["repo_notes_dir"] = "90_repos"
    write_profile(vault, profile)

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Profile errors: 1" in result.stdout
    assert (
        "_meta/profile.yml  [policy_defaults.repo_notes_dir must be inside a declared domain folder]"
        in result.stdout
    )


def test_template_linter_blocks_missing_profile_contract(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "profile.yml").unlink()

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Profile errors: 1" in result.stdout
    assert "_meta/profile.yml  [missing]" in result.stdout


def test_template_linter_uses_profileless_legacy_context_aliases(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "profile.yml").unlink()
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
    assert "Profile errors: 1" in result.stdout
    assert "_meta/profile.yml  [missing]" in result.stdout
    assert "Context alias mismatch: 1" in result.stdout
    assert "client requires account" in result.stdout


def test_template_linter_warns_missing_domain_map_when_profile_valid(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "domain-map.yml").unlink()

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout
    assert "Domain map warnings: 1" in result.stdout
    assert "_meta/domain-map.yml  [missing; legacy aliases unavailable]" in result.stdout
    assert "Domain map errors: 0" in result.stdout
    assert "\nOK" in result.stdout


def test_template_linter_blocks_missing_domain_map_without_profile(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "profile.yml").unlink()
    (vault / "_meta" / "domain-map.yml").unlink()

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Profile errors: 1" in result.stdout
    assert "_meta/profile.yml  [missing]" in result.stdout
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
    assert "Context alias mismatch: 1" in result.stdout


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
    assert "Context alias mismatch: 1" in result.stdout
    assert "client requires account" in result.stdout


def test_template_linter_does_not_infer_context_aliases_when_profile_omits_policy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    profile = load_profile(vault)
    profile["policy_defaults"].pop("context_aliases")
    write_profile(vault, profile)
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
    note = customers / "independent-context.md"
    note.write_text(
        "---\n"
        "title: Independent Context\n"
        "type: note\n"
        "status: active\n"
        "domain: customers\n"
        "account: \"[[Acme]]\"\n"
        "client: \"[[Other]]\"\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Independent Context\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Context alias mismatch: 0" in result.stdout
    assert "client must match account" not in result.stdout


def test_template_linter_does_not_infer_context_aliases_for_other_profiles(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    profile = load_profile(vault)
    profile["id"] = "research-learning"
    profile["policy_defaults"].pop("context_aliases")
    write_profile(vault, profile)
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
    note = customers / "independent-context.md"
    note.write_text(
        "---\n"
        "title: Independent Context\n"
        "type: note\n"
        "status: active\n"
        "domain: customers\n"
        "account: \"[[Acme]]\"\n"
        "client: \"[[Other]]\"\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Independent Context\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Context alias mismatch: 0" in result.stdout
    assert "client must match account" not in result.stdout


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
        f"{source_mirror_fields('30_customers/acme/brief.docx', source_sha256=source_sha_for(vault, '30_customers/acme/brief.docx'))}"
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


def test_template_linter_blocks_unmigrated_source_mirror_annotations(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"not a real docx; lint only checks mirror presence")
    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    mirror.parent.mkdir(parents=True)
    mirror.write_text(
        "---\n"
        "title: Registration\n"
        "type: source-mirror\n"
        "status: active\n"
        "domain: delivery\n"
        f"{source_mirror_fields('40_delivery/registration.docx', source_sha256=source_sha_for(vault, '40_delivery/registration.docx'))}"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Registration\n\nHuman migration note.\n\n{SENTINEL}\n\n## Extracted content\n",
        encoding="utf-8",
    )
    write_source_manifest(
        vault,
        ("src-test", "40_delivery/registration.docx", "_mirrors/40_delivery/registration.md"),
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Mirror annotations needing migration: 1" in result.stdout
    assert "above-sentinel annotations need sidecar migration; run vaultwright migrate annotations --write" in result.stdout
    assert "Human migration note" not in result.stdout


def test_template_linter_accepts_source_mirror_annotations_with_matching_sidecar(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"not a real docx; lint only checks mirror presence")
    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    mirror.parent.mkdir(parents=True)
    mirror.write_text(
        "---\n"
        "title: Registration\n"
        "type: source-mirror\n"
        "status: active\n"
        "domain: delivery\n"
        f"{source_mirror_fields('40_delivery/registration.docx', source_sha256=source_sha_for(vault, '40_delivery/registration.docx'))}"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Registration\n\nHuman migration note.\n\n{SENTINEL}\n\n## Extracted content\n",
        encoding="utf-8",
    )
    write_source_manifest(
        vault,
        ("src-test", "40_delivery/registration.docx", "_mirrors/40_delivery/registration.md"),
    )
    migration = write_annotation_sidecars(vault, annotation_migration_plan(vault))

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert migration["summary"]["written"] == 1
    assert result.returncode == 0
    assert "Mirror annotations needing migration: 0" in result.stdout


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
        f"{source_mirror_fields('clients/acme/brief.docx', source_sha256=source_sha_for(vault, 'clients/acme/brief.docx'))}"
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
        f"{source_mirror_fields('30_customers/brief.docx', source_sha256=source_sha_for(vault, '30_customers/brief.docx'))}"
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
        f"{source_mirror_fields('30_customers/brief.docx', source_sha256=source_sha_for(vault, '30_customers/brief.docx'))}"
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
        f"{source_mirror_fields('clients/acme/brief.docx', source_sha256=source_sha_for(vault, 'clients/acme/brief.docx'))}"
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
        f"{source_mirror_fields('random_folder/acme/brief.docx', source_sha256=source_sha_for(vault, 'random_folder/acme/brief.docx'))}"
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


def test_template_linter_uses_profile_mirror_root_when_config_missing(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "mirror-config.yml").unlink()
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["policy_defaults"]["mirror_root"] = "_generated"
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    source_rel = "40_delivery/brief.docx"
    source = vault / source_rel
    source.write_bytes(b"source bytes")
    source_sha = source_sha_for(vault, source_rel)
    mirror = vault / "_generated" / "40_delivery" / "brief.md"
    mirror.parent.mkdir(parents=True)
    mirror.write_text(
        "---\n"
        "title: Brief\n"
        "type: source-mirror\n"
        "status: active\n"
        "domain: delivery\n"
        f"{source_mirror_fields(source_rel, source_sha256=source_sha)}"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Brief\n\n{SENTINEL}\n\nExtracted content.\n",
        encoding="utf-8",
    )
    write_source_manifest(vault, ("src-test", source_rel, "_generated/40_delivery/brief.md", source_sha))

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout


def test_template_linter_reports_profile_mirror_root_for_misplaced_source_mirror(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "mirror-config.yml").unlink()
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["policy_defaults"]["mirror_root"] = "_generated"
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
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
    assert "source-mirror notes belong under _generated" in result.stdout


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


def test_template_linter_blocks_stale_source_mirror_when_source_hash_changed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    source_rel = "40_delivery/brief.docx"
    source = vault / source_rel
    source.write_bytes(b"original source bytes")
    original_sha = source_sha_for(vault, source_rel)
    mirror = vault / "_mirrors" / "40_delivery" / "brief.md"
    mirror.parent.mkdir(parents=True)
    mirror.write_text(
        "---\n"
        "title: Brief\n"
        "type: source-mirror\n"
        "status: active\n"
        "domain: delivery\n"
        f"{source_mirror_fields(source_rel, source_sha256=original_sha)}"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Brief\n\n{SENTINEL}\n\n## Extracted content\n",
        encoding="utf-8",
    )
    write_source_manifest(vault, ("src-test", source_rel, "_mirrors/40_delivery/brief.md", original_sha))
    source.write_bytes(b"updated source bytes")

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Stale Office mirrors: 1" in result.stdout
    assert "_mirrors/40_delivery/brief.md  [source hash changed; run vaultwright sync before relying on mirror]" in result.stdout


def test_template_linter_blocks_source_mirror_with_noncurrent_manifest_state(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    source_rel = "40_delivery/brief.docx"
    source = vault / source_rel
    source.write_bytes(b"source bytes")
    source_sha = source_sha_for(vault, source_rel)
    mirror = vault / "_mirrors" / "40_delivery" / "brief.md"
    mirror.parent.mkdir(parents=True)
    mirror.write_text(
        "---\n"
        "title: Brief\n"
        "type: source-mirror\n"
        "status: active\n"
        "domain: delivery\n"
        f"{source_mirror_fields(source_rel, source_sha256=source_sha)}"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Brief\n\n{SENTINEL}\n\n## Extracted content\n",
        encoding="utf-8",
    )
    write_source_manifest(vault, ("src-test", source_rel, "_mirrors/40_delivery/brief.md", source_sha))
    manifest_path = vault / "_meta" / "source-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["records"][0]["lifecycle_state"] = "source_changed"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Stale Office mirrors: 1" in result.stdout
    assert "source-manifest lifecycle_state=source_changed; run vaultwright sync/status before relying on mirror" in result.stdout


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
    assert "repo-mirror notes belong under configured tools/repos.yml notes_dir or profile policy_defaults.repo_notes_dir" in result.stdout


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


def test_template_linter_blocks_configured_repo_without_generated_mirror(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "tools" / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos:\n"
        "  - repo: local/fixture\n"
        "    note: fixture.md\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Repo config errors: 0" in result.stdout
    assert "Configured repos without a mirror: 1" in result.stdout
    assert "80_sources/repos/fixture.md  (configured repo mirror missing or unmanaged)" in result.stdout


def test_template_linter_uses_profile_default_repo_notes_dir(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    profile = load_profile(vault)
    profile["domains"]["research"] = {
        "folder": "25_research",
        "purpose": "Profile-defined research material.",
    }
    profile["folder_plan"].append({"path": "25_research", "domain": "research"})
    profile["policy_defaults"]["repo_notes_dir"] = "25_research/repos"
    write_profile(vault, profile)
    (vault / "tools" / "repos.yml").write_text(
        "repos:\n"
        "  - repo: local/fixture\n"
        "    note: fixture.md\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Repo config errors: 0" in result.stdout
    assert "Configured repos without a mirror: 1" in result.stdout
    assert "25_research/repos/fixture.md  (configured repo mirror missing or unmanaged)" in result.stdout


def test_template_linter_uses_configured_repo_notes_dir_for_layout_checks(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "tools" / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/custom-repos\n"
        "repos: []\n",
        encoding="utf-8",
    )
    note = vault / "80_sources" / "custom-repos" / "fixture.md"
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
    assert "Repo config errors: 0" in result.stdout
    assert "Mirror layout errors: 1" in result.stdout
    assert "repo-mirror requires generated sentinel and manifest metadata" in result.stdout
    assert (
        "repo-mirror notes belong under configured tools/repos.yml notes_dir or profile policy_defaults.repo_notes_dir"
        not in result.stdout
    )


def test_template_linter_accepts_configured_repo_with_generated_mirror(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    repo_id = repo_id_for("local/fixture", "fixture.md")
    (vault / "tools" / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos:\n"
        "  - repo: local/fixture\n"
        "    note: fixture.md\n",
        encoding="utf-8",
    )
    repo_note = vault / "80_sources" / "repos" / "fixture.md"
    repo_note.parent.mkdir(parents=True, exist_ok=True)
    repo_note.write_text(
        "---\n"
        "title: Fixture Repo\n"
        "type: repo-mirror\n"
        "status: active\n"
        "domain: sources\n"
        f"{repo_mirror_fields(repo_id=repo_id)}"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Fixture Repo\n\n{SENTINEL}\n\n## Repository\n",
        encoding="utf-8",
    )
    write_repo_manifest(vault, (repo_id, "80_sources/repos/fixture.md"))

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Repo config errors: 0" in result.stdout
    assert "Configured repos without a mirror: 0" in result.stdout


def test_template_linter_accepts_configured_repo_seed_frontmatter(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    repo_id = repo_id_for("local/fixture", "fixture.md")
    (vault / "tools" / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos:\n"
        "  - repo: local/fixture\n"
        "    note: fixture.md\n"
        "    tags: [repo, sample, synthetic]\n"
        "    related: [\"[[Repositories]]\"]\n",
        encoding="utf-8",
    )
    repo_note = vault / "80_sources" / "repos" / "fixture.md"
    repo_note.parent.mkdir(parents=True, exist_ok=True)
    repo_note.write_text(
        "---\n"
        "title: Fixture Repo\n"
        "type: repo-mirror\n"
        "status: active\n"
        "domain: sources\n"
        f"{repo_mirror_fields(repo_id=repo_id)}"
        "tags: [repo, sample, synthetic]\n"
        "related: [\"[[Repositories]]\"]\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Fixture Repo\n\n{SENTINEL}\n\n## Repository\n",
        encoding="utf-8",
    )
    write_repo_manifest(vault, (repo_id, "80_sources/repos/fixture.md"))

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout
    assert "Mirror annotations needing migration: 0" in result.stdout
    assert "Configured repos without a mirror: 0" in result.stdout


def test_template_linter_accepts_configured_repo_with_custom_notes_dir(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    repo_id = repo_id_for("local/fixture", "fixture.md")
    (vault / "tools" / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 40_delivery/repos\n"
        "repos:\n"
        "  - repo: local/fixture\n"
        "    note: fixture.md\n",
        encoding="utf-8",
    )
    repo_note = vault / "40_delivery" / "repos" / "fixture.md"
    repo_note.parent.mkdir(parents=True, exist_ok=True)
    repo_note.write_text(
        "---\n"
        "title: Fixture Repo\n"
        "type: repo-mirror\n"
        "status: active\n"
        "domain: delivery\n"
        f"{repo_mirror_fields(repo_id=repo_id)}"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Fixture Repo\n\n{SENTINEL}\n\n## Repository\n",
        encoding="utf-8",
    )
    write_repo_manifest(vault, (repo_id, "40_delivery/repos/fixture.md"))

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Repo config errors: 0" in result.stdout
    assert "Mirror layout errors: 0" in result.stdout
    assert "Domain/folder mismatch: 0" in result.stdout
    assert "Configured repos without a mirror: 0" in result.stdout


def test_template_linter_blocks_configured_repo_identity_mismatch(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    old_repo_id = repo_id_for("old/fixture", "fixture.md")
    (vault / "tools" / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos:\n"
        "  - repo: new/fixture\n"
        "    note: fixture.md\n",
        encoding="utf-8",
    )
    repo_note = vault / "80_sources" / "repos" / "fixture.md"
    repo_note.parent.mkdir(parents=True, exist_ok=True)
    repo_note.write_text(
        "---\n"
        "title: Fixture Repo\n"
        "type: repo-mirror\n"
        "status: active\n"
        "domain: sources\n"
        f"{repo_mirror_fields(repo='old/fixture', repo_id=old_repo_id)}"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Fixture Repo\n\n{SENTINEL}\n\n## Repository\n",
        encoding="utf-8",
    )
    write_repo_manifest(vault, (old_repo_id, "80_sources/repos/fixture.md"))

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Repo config errors: 0" in result.stdout
    assert "Configured repos without a mirror: 1" in result.stdout
    assert "80_sources/repos/fixture.md  (configured repo mirror repo_id mismatch; run vaultwright sync)" in result.stdout


def test_template_linter_blocks_invalid_repo_mirror_config_path(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "tools" / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: _meta/repos\n"
        "repos:\n"
        "  - repo: local/fixture\n"
        "    note: fixture.md\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Repo config errors: 1" in result.stdout
    assert "tools/repos.yml:repos[0].note  [notes_dir contains a reserved path component]" in result.stdout


def test_template_linter_blocks_duplicate_repo_mirror_config_target(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "tools" / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos:\n"
        "  - repo: local/first\n"
        "    note: shared.md\n"
        "  - repo: local/second\n"
        "    note: shared.md\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Repo config errors: 1" in result.stdout
    assert (
        "tools/repos.yml:repos[1].note  [duplicates output path 80_sources/repos/shared.md from tools/repos.yml:repos[0]]"
        in result.stdout
    )


def test_template_linter_blocks_case_only_duplicate_repo_mirror_config_target(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "tools" / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos:\n"
        "  - repo: local/first\n"
        "    note: Shared.md\n"
        "  - repo: local/second\n"
        "    note: shared.md\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Repo config errors: 1" in result.stdout
    assert (
        "tools/repos.yml:repos[1].note  [duplicates output path 80_sources/repos/shared.md from tools/repos.yml:repos[0]]"
        in result.stdout
    )


def test_template_linter_blocks_repo_mirror_with_noncurrent_manifest_state(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    repo_note = vault / "80_sources" / "repos" / "fixture.md"
    repo_note.parent.mkdir(parents=True, exist_ok=True)
    repo_note.write_text(
        "---\n"
        "title: Fixture Repo\n"
        "type: repo-mirror\n"
        "status: active\n"
        "domain: sources\n"
        f"{repo_mirror_fields()}"
        "last_commit: abc123\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Fixture Repo\n\n{SENTINEL}\n\n## Repository\n",
        encoding="utf-8",
    )
    (vault / "_meta" / "repo-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": [
                    {
                        "repo_id": "repo-test",
                        "note_path": "80_sources/repos/fixture.md",
                        "last_commit": "abc123",
                        "lifecycle_state": "repo_changed",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Stale repo mirrors: 1" in result.stdout
    assert "repo-manifest lifecycle_state=repo_changed; run vaultwright sync/status before relying on mirror" in result.stdout


def test_template_linter_blocks_unconfigured_repo_manifest_record(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    repo_id = repo_id_for("local/fixture", "fixture.md")
    repo_note = vault / "80_sources" / "repos" / "fixture.md"
    repo_note.parent.mkdir(parents=True, exist_ok=True)
    repo_note.write_text(
        "---\n"
        "title: Fixture Repo\n"
        "type: repo-mirror\n"
        "status: active\n"
        "domain: sources\n"
        f"{repo_mirror_fields(repo_id=repo_id)}"
        "last_commit: abc123\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Fixture Repo\n\n{SENTINEL}\n\n## Repository\n",
        encoding="utf-8",
    )
    (vault / "tools" / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos: []\n",
        encoding="utf-8",
    )
    (vault / "_meta" / "repo-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": [
                    {
                        "repo_id": repo_id,
                        "configured_repo": "local/fixture",
                        "note_path": "80_sources/repos/fixture.md",
                        "last_commit": "abc123",
                        "lifecycle_state": "clean",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Stale repo mirrors: 0" in result.stdout
    assert "Unconfigured repo mirrors: 1" in result.stdout
    assert (
        "80_sources/repos/fixture.md  "
        "(repo manifest record not governed by tools/repos.yml; restore config or retire mirror)"
    ) in result.stdout


def test_template_linter_blocks_repo_mirror_frontmatter_repo_drift(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    repo_note = vault / "80_sources" / "repos" / "fixture.md"
    repo_note.parent.mkdir(parents=True, exist_ok=True)
    repo_note.write_text(
        "---\n"
        "title: Fixture Repo\n"
        "type: repo-mirror\n"
        "status: active\n"
        "domain: sources\n"
        f"{repo_mirror_fields(repo='old/fixture')}"
        "last_commit: abc123\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Fixture Repo\n\n{SENTINEL}\n\n## Repository\n",
        encoding="utf-8",
    )
    (vault / "_meta" / "repo-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": [
                    {
                        "repo_id": "repo-test",
                        "configured_repo": "local/fixture",
                        "resolved_repo": "local/fixture",
                        "note_path": "80_sources/repos/fixture.md",
                        "last_commit": "abc123",
                        "lifecycle_state": "clean",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Stale repo mirrors: 1" in result.stdout
    assert "repo frontmatter repo differs from repo manifest; run vaultwright sync before relying on mirror" in result.stdout


def test_template_linter_accepts_resolved_repo_identity_for_aliased_repo(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    repo_id = repo_id_for("old/fixture", "fixture.md")
    (vault / "tools" / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos:\n"
        "  - repo: old/fixture\n"
        "    note: fixture.md\n",
        encoding="utf-8",
    )
    repo_note = vault / "80_sources" / "repos" / "fixture.md"
    repo_note.parent.mkdir(parents=True, exist_ok=True)
    repo_note.write_text(
        "---\n"
        "title: Fixture Repo\n"
        "type: repo-mirror\n"
        "status: active\n"
        "domain: sources\n"
        f"{repo_mirror_fields(repo='new/fixture', repo_id=repo_id)}"
        "last_commit: abc123\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Fixture Repo\n\n{SENTINEL}\n\n## Repository\n",
        encoding="utf-8",
    )
    (vault / "_meta" / "repo-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": [
                    {
                        "repo_id": repo_id,
                        "configured_repo": "old/fixture",
                        "resolved_repo": "new/fixture",
                        "note_path": "80_sources/repos/fixture.md",
                        "last_commit": "abc123",
                        "lifecycle_state": "clean",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Stale repo mirrors: 0" in result.stdout


def test_template_linter_blocks_local_repo_mirror_when_tree_changed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    fixture = vault / "_fixtures" / "repos" / "fixture"
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text("# Changed fixture\n", encoding="utf-8")
    repo_note = vault / "80_sources" / "repos" / "fixture.md"
    repo_note.parent.mkdir(parents=True, exist_ok=True)
    repo_note.write_text(
        "---\n"
        "title: Fixture Repo\n"
        "type: repo-mirror\n"
        "status: active\n"
        "domain: sources\n"
        f"{repo_mirror_fields()}"
        "last_commit: local-old\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Fixture Repo\n\n{SENTINEL}\n\n## Repository\n",
        encoding="utf-8",
    )
    (vault / "_meta" / "repo-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": [
                    {
                        "repo_id": "repo-test",
                        "note_path": "80_sources/repos/fixture.md",
                        "source_type": "local",
                        "source_ref": "_fixtures/repos/fixture",
                        "last_commit": "local-old",
                        "lifecycle_state": "clean",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Stale repo mirrors: 1" in result.stdout
    assert "80_sources/repos/fixture.md  [local repo tree changed; run vaultwright sync before relying on mirror]" in result.stdout


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


def test_template_linter_overlap_suggests_inbound_canonical_note(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    first = vault / "40_delivery" / "grant-readiness.md"
    second = vault / "40_delivery" / "funding-readiness.md"
    index = vault / "40_delivery" / "delivery-index.md"
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
    index.write_text(
        "---\n"
        "title: Delivery Index\n"
        "type: moc\n"
        "status: active\n"
        "domain: delivery\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Delivery Index\n\nUse [[grant-readiness]] as the current checklist.\n",
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
    assert "suggestion: keep 40_delivery/grant-readiness.md (1 inbound link vs 0)" in result.stdout
    assert "merge unique details from 40_delivery/funding-readiness.md" in result.stdout
    assert "mark the duplicate superseded/archived after review" in result.stdout
    assert "shared terms:" not in result.stdout
    assert "payroll evidence" not in result.stdout


def test_template_linter_overlap_uses_inbound_signal_across_note_types(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    guide = vault / "40_delivery" / "grant-readiness.md"
    note = vault / "40_delivery" / "funding-readiness-note.md"
    index = vault / "40_delivery" / "delivery-index.md"
    body = (
        "The intake checklist reviews eligibility, incorporation status, payroll evidence, "
        "tax registration, cashflow runway, milestone plan, owner responsibilities, supporting "
        "documents, application deadline, budget assumptions, reporting cadence, compliance risks, "
        "grant program fit, review notes, approval path, and follow-up actions.\n"
    )
    guide.write_text(
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
    note.write_text(
        "---\n"
        "title: Funding Readiness Working Note\n"
        "type: note\n"
        "status: active\n"
        "domain: delivery\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Funding Readiness Working Note\n\n{body}",
        encoding="utf-8",
    )
    index.write_text(
        "---\n"
        "title: Delivery Index\n"
        "type: moc\n"
        "status: active\n"
        "domain: delivery\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Delivery Index\n\nUse [[grant-readiness]] as the canonical checklist.\n",
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
    assert "suggestion: keep 40_delivery/grant-readiness.md (1 inbound link vs 0)" in result.stdout
    assert "review boundaries (guide vs note)" not in result.stdout


def test_template_linter_path_qualified_links_count_only_exact_overlap_target(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    delivery = vault / "40_delivery" / "grant-readiness.md"
    operations = vault / "50_operations" / "grant-readiness.md"
    index = vault / "40_delivery" / "delivery-index.md"
    body = (
        "The intake checklist reviews eligibility, incorporation status, payroll evidence, "
        "tax registration, cashflow runway, milestone plan, owner responsibilities, supporting "
        "documents, application deadline, budget assumptions, reporting cadence, compliance risks, "
        "grant program fit, review notes, approval path, and follow-up actions.\n"
    )
    delivery.write_text(
        "---\n"
        "title: Delivery Grant Readiness\n"
        "type: guide\n"
        "status: active\n"
        "domain: delivery\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Delivery Grant Readiness\n\n{body}",
        encoding="utf-8",
    )
    operations.write_text(
        "---\n"
        "title: Operations Grant Readiness\n"
        "type: guide\n"
        "status: active\n"
        "domain: operations\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Operations Grant Readiness\n\n{body}",
        encoding="utf-8",
    )
    index.write_text(
        "---\n"
        "title: Delivery Index\n"
        "type: moc\n"
        "status: active\n"
        "domain: delivery\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Delivery Index\n\nUse [[40_delivery/grant-readiness]] as the current checklist.\n",
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
    assert "40_delivery/grant-readiness.md <-> 50_operations/grant-readiness.md" in result.stdout
    assert "suggestion: keep 40_delivery/grant-readiness.md (1 inbound link vs 0)" in result.stdout
    assert "suggestion: choose one canonical note" not in result.stdout


def test_template_linter_broken_path_qualified_link_does_not_fallback_to_same_stem(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    delivery = vault / "40_delivery" / "grant-readiness.md"
    operations = vault / "50_operations" / "grant-readiness.md"
    index = vault / "40_delivery" / "delivery-index.md"
    body = (
        "The intake checklist reviews eligibility, incorporation status, payroll evidence, "
        "tax registration, cashflow runway, milestone plan, owner responsibilities, supporting "
        "documents, application deadline, budget assumptions, reporting cadence, compliance risks, "
        "grant program fit, review notes, approval path, and follow-up actions.\n"
    )
    delivery.write_text(
        "---\n"
        "title: Delivery Grant Readiness\n"
        "type: guide\n"
        "status: active\n"
        "domain: delivery\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Delivery Grant Readiness\n\n{body}",
        encoding="utf-8",
    )
    operations.write_text(
        "---\n"
        "title: Operations Grant Readiness\n"
        "type: guide\n"
        "status: active\n"
        "domain: operations\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Operations Grant Readiness\n\n{body}",
        encoding="utf-8",
    )
    index.write_text(
        "---\n"
        "title: Delivery Index\n"
        "type: moc\n"
        "status: active\n"
        "domain: delivery\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Delivery Index\n\n"
        "The old pointer [[20_market/grant-readiness]] needs repair.\n"
        "The unsafe pointer [[../50_operations/grant-readiness]] needs repair too.\n"
        "The absolute pointer [[/50_operations/grant-readiness]] must not fall back either.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Unresolved wikilinks: 3" in result.stdout
    assert "40_delivery/delivery-index.md  [20_market/grant-readiness]" in result.stdout
    assert "40_delivery/delivery-index.md  [../50_operations/grant-readiness]" in result.stdout
    assert "40_delivery/delivery-index.md  [/50_operations/grant-readiness]" in result.stdout
    assert "Potential duplicate/overlap notes: 1" in result.stdout
    assert "40_delivery/grant-readiness.md <-> 50_operations/grant-readiness.md" in result.stdout
    assert "suggestion: choose one canonical note" in result.stdout
    assert "suggestion: keep 50_operations/grant-readiness.md" not in result.stdout


def test_template_linter_allows_overlap_threshold_calibration(tmp_path: Path) -> None:
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
    for path, title in ((first, "Grant Readiness Checklist"), (second, "Funding Readiness Checklist")):
        path.write_text(
            "---\n"
            f"title: {title}\n"
            "type: guide\n"
            "status: active\n"
            "domain: delivery\n"
            "created: 2026-01-01\n"
            "updated: 2026-01-01\n"
            "---\n"
            f"# {title}\n\n{body}",
            encoding="utf-8",
        )
    (vault / "_meta" / "lint-config.yml").write_text(
        "overlap:\n"
        "  min_shared_terms: 30\n"
        "  content_threshold: 0.99\n"
        "  title_threshold: 0.95\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Lint config errors: 0" in result.stdout
    assert "Potential duplicate/overlap notes: 0" in result.stdout


def test_template_linter_blocks_invalid_lint_config(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "lint-config.yml").write_text(
        "overlap:\n"
        "  min_shared_terms: one\n"
        "  content_threshold: 2\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Lint config errors: 2" in result.stdout
    assert "_meta/lint-config.yml:overlap.min_shared_terms" in result.stdout
    assert "_meta/lint-config.yml:overlap.content_threshold" in result.stdout


def test_template_linter_skips_generated_mirrors_for_overlap_and_orphan_candidates(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    body = (
        "Repeated generated mirror text about eligibility incorporation payroll tax registration "
        "cashflow runway milestones supporting documents application deadline budget assumptions "
        "reporting cadence compliance risks review notes approval path and follow-up actions.\n"
    )
    for name in ("first", "second"):
        source_rel = f"40_delivery/{name}.docx"
        source = vault / source_rel
        source.write_bytes(f"{name} source bytes".encode("utf-8"))
        mirror = vault / "_mirrors" / "40_delivery" / f"{name}.md"
        mirror.parent.mkdir(parents=True, exist_ok=True)
        mirror.write_text(
            "---\n"
            f"title: {name.title()} Mirror\n"
            "type: source-mirror\n"
            "status: active\n"
            "domain: delivery\n"
            f"{source_mirror_fields(source_rel, f'src-{name}', source_sha_for(vault, source_rel))}"
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
    repo_id = repo_id_for("local/fixture", "fixture.md")
    (vault / "tools" / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos:\n"
        "  - repo: local/fixture\n"
        "    note: fixture.md\n",
        encoding="utf-8",
    )
    repo_note = vault / "80_sources" / "repos" / "fixture.md"
    repo_note.parent.mkdir(parents=True, exist_ok=True)
    repo_note.write_text(
        "---\n"
        "title: Fixture Repo\n"
        "type: repo-mirror\n"
        "status: active\n"
        "domain: sources\n"
        f"{repo_mirror_fields(repo_id=repo_id)}"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        f"# Fixture Repo\n\n{SENTINEL}\n\n## Repository\n\n"
        "Repeated generated mirror text about eligibility incorporation payroll tax registration "
        "cashflow runway milestones supporting documents application deadline budget assumptions "
        "reporting cadence compliance risks review notes approval path and follow-up actions.\n",
        encoding="utf-8",
    )
    write_repo_manifest(vault, (repo_id, "80_sources/repos/fixture.md"))

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "lint_vault.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Orphan notes (no inbound links): 0" in result.stdout
    assert "Potential duplicate/overlap notes: 0" in result.stdout
