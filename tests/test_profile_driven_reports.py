# SPDX-License-Identifier: AGPL-3.0-or-later
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]


def package_cli_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = (
        src_path if not env.get("PYTHONPATH") else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def repo_id_for(repo: str, note: str) -> str:
    digest = hashlib.sha256(f"{repo}\0{note}".encode("utf-8")).hexdigest()[:20]
    return f"repo_{digest}"


def add_research_repo_profile(vault: Path) -> None:
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["domains"]["research"] = {
        "folder": "25_research",
        "purpose": "Profile-defined research material.",
    }
    profile["folder_plan"].append({"path": "25_research", "domain": "research"})
    profile["policy_defaults"]["repo_notes_dir"] = "25_research/repos"
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")


def invalidate_profile_repo_notes_dir(vault: Path) -> None:
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["policy_defaults"]["repo_notes_dir"] = "90_repos"
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")


def add_invalid_research_repo_profile(vault: Path) -> None:
    add_research_repo_profile(vault)
    invalidate_profile_repo_notes_dir(vault)


def add_research_context_profile(vault: Path) -> None:
    add_research_repo_profile(vault)
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    optional = list(profile.get("optional_properties", []))
    for value in ("research_project", "literature_collection"):
        if value not in optional:
            optional.append(value)
    profile["optional_properties"] = optional
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")


def write_minimal_research_learning_profile(vault: Path) -> None:
    (vault / "_meta").mkdir(parents=True, exist_ok=True)
    profile = {
        "schema_version": 1,
        "id": "research-learning",
        "name": "Research and Learning",
        "profile_version": "1.0.0",
        "description": "Minimal test profile for profile-aware migration guidance.",
        "domains": {
            "research": {
                "folder": "25_research",
                "purpose": "Research notes and synthesized source evidence.",
            }
        },
        "note_types": {
            "note": {"purpose": "Curated human note."},
            "source-mirror": {
                "purpose": "Generated source mirror.",
                "machine_owned": True,
            },
        },
        "statuses": {
            "draft": {"purpose": "Draft material."},
            "current": {"purpose": "Current material."},
            "retired": {"purpose": "Retired material.", "inactive": True},
        },
        "required_properties": ["title", "type", "status", "domain", "created", "updated"],
        "optional_properties": ["related", "research_project"],
        "folder_plan": [{"path": "25_research", "domain": "research"}],
        "templates": [],
        "views": [],
        "skills": [],
        "benchmark_tasks": [],
        "policy_defaults": {
            "mirror_mode": "dedicated",
            "mirror_root": "_mirrors",
            "mirror_status": "current",
            "repo_stub_status": "draft",
            "original_sources_authoritative": True,
            "real_data_in_repo": False,
        },
    }
    (vault / "_meta" / "profile.yml").write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    domain_map = {
        "domains": {
            "research": {
                "folder": "25_research",
                "aliases": ["papers", "literature"],
            }
        }
    }
    (vault / "_meta" / "domain-map.yml").write_text(
        yaml.safe_dump(domain_map, sort_keys=False),
        encoding="utf-8",
    )


def set_profile_mirror_status_defaults(vault: Path, *, mirror_status: str = "current", repo_stub_status: str = "queued") -> None:
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["statuses"][mirror_status] = {"purpose": "Profile-defined generated mirror status."}
    profile["statuses"][repo_stub_status] = {"purpose": "Profile-defined repo stub status."}
    profile["policy_defaults"]["mirror_status"] = mirror_status
    profile["policy_defaults"]["repo_stub_status"] = repo_stub_status
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")


def set_office_mirror_root(vault: Path, mirror_root: str = "_generated") -> None:
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["policy_defaults"]["mirror_root"] = mirror_root
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    (vault / "_meta" / "mirror-config.yml").write_text(
        "office_mirrors:\n"
        "  mode: dedicated\n"
        f"  root: {mirror_root}\n"
        "  include_pdf: false\n",
        encoding="utf-8",
    )


def write_profile_benchmark_task_pack(vault: Path) -> Path:
    add_research_repo_profile(vault)
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    task_pack = Path("_meta/research-agent-readiness-tasks.yml")
    profile["benchmark_tasks"] = [task_pack.as_posix()]
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")

    source = vault / "25_research" / "research-plan.docx"
    mirror = vault / "_mirrors" / "25_research" / "research-plan.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    mirror.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"synthetic research benchmark source bytes")
    mirror.write_text(
        "---\nsource_path: 25_research/research-plan.docx\n---\nSynthetic research mirror body\n",
        encoding="utf-8",
    )
    tasks = []
    for family in ("answer", "reconcile", "update", "audit", "consolidate"):
        tasks.append(
            {
                "id": f"research-{family}",
                "family": family,
                "prompt": f"What should the research {family} task prove?",
                "source_paths": ["25_research/research-plan.docx"],
                "generated_mirror_paths": ["_mirrors/25_research/research-plan.md"],
                "curated_paths": [],
                "success_criteria": ["Uses declared profile benchmark evidence only"],
            }
        )
    (vault / task_pack).write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "corpus": "profile-research-fixture",
                "comparison_modes": [
                    "raw_source_folder",
                    "document_chat_transcript",
                    "vaultwright_markdown",
                ],
                "scoring": {"scale": "0-2"},
                "tasks": tasks,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return task_pack


def test_catalog_reads_profile_domains_for_canonical_folders(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["domains"]["research"] = {
        "folder": "25_research",
        "purpose": "Profile-defined research material.",
    }
    profile["folder_plan"].append({"path": "25_research", "domain": "research"})
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    research = vault / "25_research"
    research.mkdir()
    (research / "brief.md").write_text(
        "---\n"
        "title: Research Brief\n"
        "type: note\n"
        "status: active\n"
        "domain: research\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Research Brief\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "catalog_report.py"), "--json"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    report = json.loads(result.stdout)["report"]
    domains = {item["domain"]: item for item in report["domains"]}
    assert domains["research"]["folder"] == "25_research"
    assert domains["research"]["markdown_files"] == 1
    assert "25_research" in report["canonical_folders"]
    assert {"folder": "25_research"} not in report["legacy_folders"]


def test_package_cli_catalog_separates_profile_machine_owned_markdown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    add_research_repo_profile(vault)
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["note_types"]["research-synthesis"] = {
        "purpose": "Generated research synthesis artifact.",
        "machine_owned": True,
    }
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")

    research = vault / "25_research"
    research.mkdir()
    for filename, note_type in (
        ("curated-brief.md", "note"),
        ("generated-synthesis.md", "research-synthesis"),
    ):
        (research / filename).write_text(
            "---\n"
            f"title: {filename.removesuffix('.md').replace('-', ' ').title()}\n"
            f"type: {note_type}\n"
            "status: active\n"
            "domain: research\n"
            "created: 2026-06-24\n"
            "updated: 2026-06-24\n"
            "---\n"
            f"# {filename}\n",
            encoding="utf-8",
        )

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "catalog", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    report = json.loads(result.stdout)["report"]
    domains = {item["domain"]: item for item in report["domains"]}
    assert domains["research"]["markdown_files"] == 1
    assert domains["research"]["machine_owned_markdown"] == 1
    assert report["summary"]["machine_owned_markdown"] == 1


def test_package_cli_catalog_blocks_invalid_profile_contract_before_domain_routing(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    add_invalid_research_repo_profile(vault)
    (vault / "25_research").mkdir()

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "catalog", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert any(
        "invalid profile contract" in error and "policy_defaults.repo_notes_dir" in error
        for error in payload["errors"]
    )
    domains = {item["domain"]: item for item in payload["report"]["domains"]}
    assert "research" not in domains
    assert "25_research" not in payload["report"]["canonical_folders"]
    assert {"folder": "25_research"} in payload["report"]["legacy_folders"]


def test_package_cli_m365_separates_profile_machine_owned_markdown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    add_research_repo_profile(vault)
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["note_types"]["research-synthesis"] = {
        "purpose": "Generated research synthesis artifact.",
        "machine_owned": True,
    }
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")

    baseline = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "m365", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    assert baseline.returncode == 0, baseline.stderr or baseline.stdout
    baseline_inventory = json.loads(baseline.stdout)["report"]["inventory"]

    target = vault / "25_research" / "generated-synthesis.md"
    target.parent.mkdir()
    target.write_text(
        "---\n"
        "title: Generated Synthesis\n"
        "type: research-synthesis\n"
        "status: active\n"
        "domain: research\n"
        "created: 2026-06-24\n"
        "updated: 2026-06-24\n"
        "---\n"
        "Generated research synthesis body that must not appear in handoff output.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "m365"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    json_result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "m365", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "machine-owned markdown files: 1" in result.stdout
    assert "Generated research synthesis body" not in result.stdout

    assert json_result.returncode == 0, json_result.stderr or json_result.stdout
    inventory = json.loads(json_result.stdout)["report"]["inventory"]
    assert inventory["markdown_files"] == baseline_inventory["markdown_files"]
    assert inventory["machine_owned_markdown"] == baseline_inventory["machine_owned_markdown"] + 1
    assert "Generated research synthesis body" not in json_result.stdout


def test_package_cli_sandbox_separates_profile_machine_owned_markdown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    source_root = tmp_path / "source-root"
    source_root.mkdir()
    shutil.copytree(ROOT / "template", vault)
    add_research_repo_profile(vault)
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["note_types"]["research-synthesis"] = {
        "purpose": "Generated research synthesis artifact.",
        "machine_owned": True,
    }
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")

    baseline = subprocess.run(
        [
            sys.executable,
            "-m",
            "vaultwright.cli",
            "--root",
            str(vault),
            "sandbox",
            "--source-root",
            str(source_root),
            "--json",
        ],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    assert baseline.returncode == 0, baseline.stderr or baseline.stdout
    baseline_inventory = json.loads(baseline.stdout)["report"]["inventory"]

    target = vault / "25_research" / "generated-synthesis.md"
    target.parent.mkdir()
    target.write_text(
        "---\n"
        "title: Generated Synthesis\n"
        "type: research-synthesis\n"
        "status: active\n"
        "domain: research\n"
        "created: 2026-06-24\n"
        "updated: 2026-06-24\n"
        "---\n"
        "Generated research synthesis body that must not appear in sandbox output.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vaultwright.cli",
            "--root",
            str(vault),
            "sandbox",
            "--source-root",
            str(source_root),
        ],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    json_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vaultwright.cli",
            "--root",
            str(vault),
            "sandbox",
            "--source-root",
            str(source_root),
            "--json",
        ],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "sandbox: markdown" in result.stdout
    assert "machine_owned=1" in result.stdout
    assert "Generated research synthesis body" not in result.stdout

    assert json_result.returncode == 0, json_result.stderr or json_result.stdout
    inventory = json.loads(json_result.stdout)["report"]["inventory"]
    assert inventory["curated_markdown"] == baseline_inventory["curated_markdown"]
    assert inventory["machine_owned_markdown"] == baseline_inventory["machine_owned_markdown"] + 1
    assert "Generated research synthesis body" not in json_result.stdout


def test_package_cli_catalog_does_not_delegate_to_vault_local_script(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "tools" / "catalog_report.py").write_text(
        "raise SystemExit('vault-local catalog script should not run')\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "catalog", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["report"]["summary"]["generated_mirrors"] == 0
    assert "vault-local catalog script should not run" not in result.stderr


def test_migration_reads_profile_domains_for_canonical_folders(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["domains"]["research"] = {
        "folder": "25_research",
        "purpose": "Profile-defined research material.",
    }
    profile["folder_plan"].append({"path": "25_research", "domain": "research"})
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    research = vault / "25_research"
    research.mkdir()
    (research / "brief.md").write_text(
        "---\n"
        "title: Research Brief\n"
        "type: note\n"
        "status: active\n"
        "domain: research\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "---\n"
        "# Research Brief\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "migration", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["summary"] == {"alias": 0, "total": 0, "unknown": 0}
    assert payload["frontmatter_summary"] == {"alias": 0, "total": 0, "unknown": 0}
    assert payload["warnings"] == []
    assert payload["errors"] == []


def test_migration_uses_profile_when_domain_map_missing(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "domain-map.yml").unlink()

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "migration", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["summary"] == {"alias": 0, "total": 0, "unknown": 0}
    assert payload["warnings"] == ["_meta/domain-map.yml: missing; legacy aliases unavailable"]
    assert payload["errors"] == []


def test_migration_blocks_domain_map_folder_drift_from_profile(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    domain_map_path = vault / "_meta" / "domain-map.yml"
    domain_map = yaml.safe_load(domain_map_path.read_text(encoding="utf-8"))
    domain_map["domains"]["market"]["folder"] = "99_market"
    domain_map_path.write_text(yaml.safe_dump(domain_map, sort_keys=False), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "migration", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["errors"] == ["_meta/domain-map.yml:market: folder differs from _meta/profile.yml"]


def test_package_cli_migration_blocks_invalid_profile_contract_before_domain_routing(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    add_invalid_research_repo_profile(vault)
    (vault / "25_research").mkdir()

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "migration", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["summary"] == {"alias": 0, "total": 0, "unknown": 0}
    assert payload["frontmatter_summary"] == {"alias": 0, "total": 0, "unknown": 0}
    assert any(
        "invalid profile contract" in error and "policy_defaults.repo_notes_dir" in error
        for error in payload["errors"]
    )


def test_package_cli_migration_guidance_uses_active_profile_vocabulary(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    write_minimal_research_learning_profile(vault)
    papers = vault / "papers"
    field_notes = vault / "field_notes"
    papers.mkdir()
    field_notes.mkdir()
    (papers / "legacy-literature.md").write_text(
        "---\n"
        "title: Legacy Literature Note\n"
        "type: note\n"
        "status: current\n"
        "domain: literature\n"
        "created: 2026-06-24\n"
        "updated: 2026-06-24\n"
        "---\n"
        "# Legacy Literature Note\n",
        encoding="utf-8",
    )
    (field_notes / "unknown-domain.md").write_text(
        "---\n"
        "title: Unknown Domain Note\n"
        "type: note\n"
        "status: current\n"
        "domain: lab\n"
        "created: 2026-06-24\n"
        "updated: 2026-06-24\n"
        "---\n"
        "# Unknown Domain Note\n",
        encoding="utf-8",
    )

    runbook = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "migration", "--runbook"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    worksheet = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "migration", "--worksheet"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    normalize_worksheet = subprocess.run(
        [
            sys.executable,
            "-m",
            "vaultwright.cli",
            "--root",
            str(vault),
            "migration",
            "--normalize-frontmatter-domains",
            "--worksheet",
        ],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert runbook.returncode == 0, runbook.stderr or runbook.stdout
    assert "Profile: `research-learning 1.0.0`" in runbook.stdout
    assert "Canonical domain folders: `research -> 25_research`" in runbook.stdout
    assert "_meta/profile.yml` is authoritative" in runbook.stdout
    assert "_meta/domain-map.yml` is only the legacy alias" in runbook.stdout
    assert "- [ ] `papers/` -> `25_research/` (domain=`research`" in runbook.stdout
    assert "- [ ] Folder `field_notes/`: classify before moving" in runbook.stdout
    assert "customer, finance, people, or governance" not in runbook.stdout
    assert "business functions" not in runbook.stdout

    assert worksheet.returncode == 0, worksheet.stderr or worksheet.stdout
    assert "Profile: `research-learning 1.0.0`" in worksheet.stdout
    assert "active profile domain in _meta/profile.yml" in worksheet.stdout
    assert "requires a profile contract change" in worksheet.stdout
    assert "documented in _meta/domain-map.yml before ingestion" not in worksheet.stdout

    assert normalize_worksheet.returncode == 0, normalize_worksheet.stderr or normalize_worksheet.stdout
    assert "Profile: `research-learning 1.0.0`" in normalize_worksheet.stdout
    assert "Classify unknown domains against `_meta/profile.yml`" in normalize_worksheet.stdout


def test_package_cli_repo_sync_uses_profile_repo_notes_dir(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["domains"]["research"] = {
        "folder": "25_research",
        "purpose": "Profile-defined research material.",
    }
    profile["folder_plan"].append({"path": "25_research", "domain": "research"})
    profile["policy_defaults"]["repo_notes_dir"] = "25_research/repos"
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    fixture = vault / "_fixtures" / "repo"
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text("# Research Fixture\n", encoding="utf-8")
    (vault / "tools" / "repos.yml").write_text(
        "repos:\n"
        "  - repo: local/research-fixture\n"
        "    local_path: _fixtures/repo\n"
        "    note: research-fixture.md\n",
        encoding="utf-8",
    )

    plan = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "plan"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    sync = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "sync"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    repo_note = vault / "25_research" / "repos" / "research-fixture.md"
    assert plan.returncode == 0, plan.stderr or plan.stdout
    assert "local/research-fixture -> 25_research/repos/research-fixture.md" in plan.stdout
    assert sync.returncode == 0, sync.stderr or sync.stdout
    assert repo_note.exists()
    note_text = repo_note.read_text(encoding="utf-8")
    assert "domain: research\n" in note_text
    manifest = json.loads((vault / "_meta" / "repo-manifest.json").read_text(encoding="utf-8"))
    assert manifest["records"][0]["note_path"] == "25_research/repos/research-fixture.md"


def test_package_cli_repo_sync_uses_profile_context_fields(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    add_research_context_profile(vault)
    fixture = vault / "_fixtures" / "repo"
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text("# Research Context Fixture\n", encoding="utf-8")
    (vault / "tools" / "repos.yml").write_text(
        "repos:\n"
        "  - repo: local/research-context-fixture\n"
        "    local_path: _fixtures/repo\n"
        "    note: research-context-fixture.md\n"
        "    research_project: \"[[Concept Retrieval Study]]\"\n"
        "    literature_collection: \"[[Source-Backed Notes]]\"\n",
        encoding="utf-8",
    )

    sync = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "sync"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    lint = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "lint"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    annotations = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "migrate", "annotations", "--plan", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    repo_note = vault / "25_research" / "repos" / "research-context-fixture.md"
    assert sync.returncode == 0, sync.stderr or sync.stdout
    fm = yaml.safe_load(repo_note.read_text(encoding="utf-8").split("---", 2)[1])
    assert fm["domain"] == "research"
    assert fm["research_project"] == "[[Concept Retrieval Study]]"
    assert fm["literature_collection"] == "[[Source-Backed Notes]]"
    assert "account" not in fm
    assert "client" not in fm
    assert lint.returncode == 0, lint.stderr or lint.stdout
    assert "Mirror annotations needing migration: 0" in lint.stdout
    assert "Unresolved wikilinks: 2" in lint.stdout
    assert "Concept Retrieval Study" in lint.stdout
    assert "Source-Backed Notes" in lint.stdout
    assert annotations.returncode == 0, annotations.stderr or annotations.stdout
    payload = json.loads(annotations.stdout)
    assert payload["summary"]["actions"] == 0
    assert payload["summary"]["without_annotations"] >= 1
    assert "Concept Retrieval Study" not in annotations.stdout
    assert "Source-Backed Notes" not in annotations.stdout


def test_package_cli_sync_lint_and_annotations_use_profile_mirror_status_defaults(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    add_research_repo_profile(vault)
    set_profile_mirror_status_defaults(vault, mirror_status="current", repo_stub_status="queued")
    fixture = vault / "_fixtures" / "repo"
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text("# Research Status Fixture\n", encoding="utf-8")
    (vault / "tools" / "repos.yml").write_text(
        "repos:\n"
        "  - repo: local/research-status-fixture\n"
        "    local_path: _fixtures/repo\n"
        "    note: research-status-fixture.md\n",
        encoding="utf-8",
    )

    sync = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "sync"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    lint = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "lint"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    annotations = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "migrate", "annotations", "--plan", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    repo_note = vault / "25_research" / "repos" / "research-status-fixture.md"
    assert sync.returncode == 0, sync.stderr or sync.stdout
    fm = yaml.safe_load(repo_note.read_text(encoding="utf-8").split("---", 2)[1])
    assert fm["status"] == "current"
    assert lint.returncode == 0, lint.stderr or lint.stdout
    assert "Invalid status: 0" in lint.stdout
    assert "Mirror annotations needing migration: 0" in lint.stdout
    assert annotations.returncode == 0, annotations.stderr or annotations.stdout
    payload = json.loads(annotations.stdout)
    assert payload["summary"]["actions"] == 0
    assert payload["summary"]["without_annotations"] >= 1


def test_package_cli_overlap_reads_profile_content_roots(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    add_research_repo_profile(vault)
    research = vault / "25_research"
    research.mkdir()
    body = (
        "Research calibration synthesis source-backed citation provenance lifecycle review "
        "question concept experiment literature method evidence archive context retrieval "
        "profile workspace governance refresh agent handoff."
    )
    for filename, title in (
        ("question-map.md", "Research Question Map"),
        ("concept-map.md", "Research Concept Map"),
    ):
        (research / filename).write_text(
            "---\n"
            f"title: {title}\n"
            "type: note\n"
            "status: active\n"
            "domain: research\n"
            "created: 2026-06-24\n"
            "updated: 2026-06-24\n"
            "---\n"
            f"# {title}\n\n{body}\n",
            encoding="utf-8",
        )

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "overlap", "--json", "--max-pairs", "1"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["report"]["summary"]["curated_notes"] >= 2
    assert payload["report"]["summary"]["current_candidates"] == 1
    candidate = payload["report"]["current_candidates"][0]
    assert candidate["left_path"] == "25_research/concept-map.md"
    assert candidate["right_path"] == "25_research/question-map.md"
    assert candidate["same_domain"] is True
    assert "Research calibration synthesis" not in result.stdout


def test_package_cli_overlap_reads_profile_context_links(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    add_research_context_profile(vault)
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["optional_properties"] = [
        value
        for value in profile["optional_properties"]
        if value not in {"account", "client", "program", "vendor"}
    ]
    profile["policy_defaults"].pop("context_aliases", None)
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")

    research = vault / "25_research"
    research.mkdir()
    body = (
        "Research calibration synthesis source-backed citation provenance lifecycle review "
        "question concept experiment literature method evidence archive context retrieval "
        "profile workspace governance refresh agent handoff."
    )
    (research / "canonical.md").write_text(
        "---\n"
        "title: Canonical Concept\n"
        "type: note\n"
        "status: active\n"
        "domain: research\n"
        "created: 2026-06-24\n"
        "updated: 2026-06-24\n"
        "---\n"
        f"# Canonical Concept\n\n{body}\n",
        encoding="utf-8",
    )
    (research / "duplicate.md").write_text(
        "---\n"
        "title: Duplicate Concept\n"
        "type: note\n"
        "status: active\n"
        "domain: research\n"
        "created: 2026-06-24\n"
        "updated: 2026-06-24\n"
        "---\n"
        f"# Duplicate Concept\n\n{body}\n",
        encoding="utf-8",
    )
    (research / "linker.md").write_text(
        "---\n"
        "title: Linker Note\n"
        "type: note\n"
        "status: active\n"
        "domain: research\n"
        "created: 2026-06-24\n"
        "updated: 2026-06-24\n"
        "research_project: \"[[canonical]]\"\n"
        "account: \"[[duplicate]]\"\n"
        "---\n"
        "# Linker Note\n\nUnique profile context link evidence.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "overlap", "--json", "--max-pairs", "1"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    candidate = payload["report"]["current_candidates"][0]
    assert candidate["left_path"] == "25_research/canonical.md"
    assert candidate["right_path"] == "25_research/duplicate.md"
    assert candidate["left_inbound_links"] == 1
    assert candidate["right_inbound_links"] == 0
    assert "Research calibration synthesis" not in result.stdout


def test_package_cli_overlap_uses_profile_inactive_status_flags(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    add_research_repo_profile(vault)
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["statuses"] = {
        "draft": {"purpose": "Generated repo stubs."},
        "active": {"purpose": "current"},
        "archived": {"purpose": "archive name without inactive role"},
        "retired": {"purpose": "profile-defined inactive status", "inactive": True},
    }
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")

    research = vault / "25_research"
    research.mkdir()
    body = (
        "Research calibration synthesis source-backed citation provenance lifecycle review "
        "question concept experiment literature method evidence archive context retrieval "
        "profile workspace governance refresh agent handoff."
    )
    for filename, status in (
        ("active-note.md", "active"),
        ("archived-note.md", "archived"),
        ("retired-note.md", "retired"),
    ):
        (research / filename).write_text(
            "---\n"
            f"title: {filename.removesuffix('.md').replace('-', ' ').title()}\n"
            "type: note\n"
            f"status: {status}\n"
            "domain: research\n"
            "created: 2026-06-24\n"
            "updated: 2026-06-24\n"
            "---\n"
            f"# {filename}\n\n{body}\n",
            encoding="utf-8",
        )

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "overlap", "--json", "--max-pairs", "3"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["report"]["summary"]["curated_notes"] == 2
    candidate_paths = {
        payload["report"]["current_candidates"][0]["left_path"],
        payload["report"]["current_candidates"][0]["right_path"],
    }
    assert candidate_paths == {"25_research/active-note.md", "25_research/archived-note.md"}
    assert "retired-note.md" not in result.stdout
    assert "Research calibration synthesis" not in result.stdout


def test_package_cli_overlap_uses_profile_machine_owned_note_type_flags(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    add_research_repo_profile(vault)
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["note_types"]["research-mirror"] = {
        "purpose": "Profile-defined generated research mirror.",
        "machine_owned": True,
    }
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")

    research = vault / "25_research"
    research.mkdir()
    body = (
        "Research calibration synthesis source-backed citation provenance lifecycle review "
        "question concept experiment literature method evidence archive context retrieval "
        "profile workspace governance refresh agent handoff."
    )
    for filename, note_type in (
        ("curated-alpha.md", "note"),
        ("curated-beta.md", "note"),
        ("machine-mirror.md", "research-mirror"),
    ):
        (research / filename).write_text(
            "---\n"
            f"title: {filename.removesuffix('.md').replace('-', ' ').title()}\n"
            f"type: {note_type}\n"
            "status: active\n"
            "domain: research\n"
            "created: 2026-06-24\n"
            "updated: 2026-06-24\n"
            "---\n"
            f"# {filename}\n\n{body}\n",
            encoding="utf-8",
        )

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "overlap", "--json", "--max-pairs", "3"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["report"]["summary"]["curated_notes"] == 2
    candidate_paths = {
        payload["report"]["current_candidates"][0]["left_path"],
        payload["report"]["current_candidates"][0]["right_path"],
    }
    assert candidate_paths == {"25_research/curated-alpha.md", "25_research/curated-beta.md"}
    assert "machine-mirror.md" not in result.stdout
    assert "Research calibration synthesis" not in result.stdout


def test_package_cli_migration_skips_profile_machine_owned_frontmatter_domains(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    add_research_repo_profile(vault)
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["note_types"]["research-mirror"] = {
        "purpose": "Profile-defined generated research mirror.",
        "machine_owned": True,
    }
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")

    research = vault / "25_research"
    research.mkdir()
    for filename, note_type in (
        ("human-note.md", "note"),
        ("machine-mirror.md", "research-mirror"),
    ):
        (research / filename).write_text(
            "---\n"
            f"title: {filename.removesuffix('.md').replace('-', ' ').title()}\n"
            f"type: {note_type}\n"
            "status: active\n"
            "domain: marketing\n"
            "created: 2026-06-24\n"
            "updated: 2026-06-24\n"
            "---\n"
            f"# {filename}\n",
            encoding="utf-8",
        )

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "migration", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["frontmatter_summary"] == {"alias": 1, "total": 1, "unknown": 0}
    assert [item["path"] for item in payload["frontmatter_items"]] == ["25_research/human-note.md"]
    assert "machine-mirror.md" not in result.stdout


def test_package_cli_benchmark_reads_profile_task_pack(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    task_pack = write_profile_benchmark_task_pack(vault)

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "benchmark", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["summary"]["path"] == task_pack.as_posix()
    assert payload["summary"]["tasks"] == 5
    assert payload["summary"]["families"] == ["answer", "audit", "consolidate", "reconcile", "update"]
    assert payload["warnings"] == []
    assert payload["errors"] == []
    assert "synthetic research benchmark source bytes" not in result.stdout
    assert "Synthetic research mirror body" not in result.stdout


def test_package_cli_benchmark_blocks_invalid_profile_contract_before_task_discovery(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    write_profile_benchmark_task_pack(vault)
    invalidate_profile_repo_notes_dir(vault)

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "benchmark", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["summary"] == {}
    assert payload["result_summary"] == {}
    assert any(
        "invalid profile contract" in error and "policy_defaults.repo_notes_dir" in error
        for error in payload["errors"]
    )


def test_package_cli_pilot_reads_profile_benchmark_task_pack(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    task_pack = write_profile_benchmark_task_pack(vault)

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "pilot", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    benchmark = payload["report"]["benchmark"]
    assert benchmark["available"] is True
    assert benchmark["summary"]["path"] == task_pack.as_posix()
    assert benchmark["summary"]["tasks"] == 5
    assert benchmark["summary"]["results"] == {"available": False}
    assert "synthetic research benchmark source bytes" not in result.stdout
    assert "Synthetic research mirror body" not in result.stdout
    assert "25_research/research-plan.docx" not in result.stdout
    assert "_mirrors/25_research/research-plan.md" not in result.stdout


def test_package_cli_pilot_blocks_invalid_profile_contract_before_benchmark_discovery(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    write_profile_benchmark_task_pack(vault)
    invalidate_profile_repo_notes_dir(vault)

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "pilot", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    benchmark = payload["report"]["benchmark"]
    assert benchmark == {"available": False, "summary": {}}
    assert any(
        "invalid profile contract" in error and "policy_defaults.repo_notes_dir" in error
        for error in payload["errors"]
    )


def test_package_cli_benchmark_uses_configured_office_mirror_root(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    set_office_mirror_root(vault)
    source = vault / "40_delivery" / "brief.docx"
    mirror = vault / "_generated" / "40_delivery" / "brief.md"
    source.write_bytes(b"synthetic configured-root source bytes")
    mirror.parent.mkdir(parents=True)
    mirror.write_text(
        "---\nsource_path: 40_delivery/brief.docx\n---\nSynthetic configured-root mirror body\n",
        encoding="utf-8",
    )
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    task_pack = Path("_meta/configured-root-agent-readiness-tasks.yml")
    profile["benchmark_tasks"] = [task_pack.as_posix()]
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    tasks = [
        {
            "id": f"configured-root-{family}",
            "family": family,
            "prompt": f"What should the configured-root {family} task prove?",
            "source_paths": ["40_delivery/brief.docx"],
            "generated_mirror_paths": ["_generated/40_delivery/brief.md"],
            "curated_paths": [],
            "success_criteria": ["Uses configured mirror-root evidence only"],
        }
        for family in ("answer", "reconcile", "update", "audit", "consolidate")
    ]
    (vault / task_pack).write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "corpus": "configured-root-fixture",
                "comparison_modes": [
                    "raw_source_folder",
                    "document_chat_transcript",
                    "vaultwright_markdown",
                ],
                "scoring": {"scale": "0-2"},
                "tasks": tasks,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (vault / "_meta" / "configured-root-results.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "corpus": "configured-root-fixture",
                "results": [
                    {
                        "task_id": "configured-root-answer",
                        "mode": "vaultwright_markdown",
                        "score": 2,
                        "reviewer_corrections": 0,
                        "cited_source_paths": ["40_delivery/brief.docx"],
                        "cited_generated_mirror_paths": ["_generated/40_delivery/brief.md"],
                        "prompt_safety_reviewed": True,
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (vault / "_meta" / "source-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": [
                    {
                        "source_id": "src_brief",
                        "current_source_path": "40_delivery/brief.docx",
                        "mirror_path": "_generated/40_delivery/brief.md",
                        "lifecycle_state": "clean",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    benchmark = subprocess.run(
        [
            sys.executable,
            "-m",
            "vaultwright.cli",
            "--root",
            str(vault),
            "benchmark",
            "--json",
            "--require-generated",
            "--results",
            "_meta/configured-root-results.yml",
        ],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    scaffold = subprocess.run(
        [
            sys.executable,
            "-m",
            "vaultwright.cli",
            "--root",
            str(vault),
            "benchmark",
            "--init-tasks",
            "--tasks",
            "_meta/scaffolded-configured-root-tasks.yml",
            "--scaffold-sources",
            "1",
            "--scaffold-curated",
            "0",
        ],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert benchmark.returncode == 0, benchmark.stderr or benchmark.stdout
    payload = json.loads(benchmark.stdout)
    assert payload["summary"]["path"] == task_pack.as_posix()
    assert payload["summary"]["generated_mirror_paths"] == 5
    assert payload["result_summary"]["modes"]["vaultwright_markdown"]["generated_mirror_citations"] == 1
    assert payload["errors"] == []
    assert "must point into _mirrors" not in benchmark.stdout
    assert "must point into _mirrors" not in benchmark.stderr
    assert "synthetic configured-root source bytes" not in benchmark.stdout
    assert "Synthetic configured-root mirror body" not in benchmark.stdout

    assert scaffold.returncode == 0, scaffold.stderr or scaffold.stdout
    scaffold_tasks = yaml.safe_load((vault / "_meta" / "scaffolded-configured-root-tasks.yml").read_text(encoding="utf-8"))
    assert all(
        task["generated_mirror_paths"] == ["_generated/40_delivery/brief.md"]
        for task in scaffold_tasks["tasks"]
    )


def test_package_cli_reports_use_profile_repo_notes_dir(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    source_root = tmp_path / "source-root"
    shutil.copytree(ROOT / "template", vault)
    source_root.mkdir()
    add_research_repo_profile(vault)
    repo = "local/research-fixture"
    note = "research-fixture.md"
    repo_id = repo_id_for(repo, note)
    repo_notes = vault / "25_research" / "repos"
    repo_notes.mkdir(parents=True)
    (repo_notes / note).write_text(
        "---\n"
        "title: Research Fixture\n"
        "type: repo-mirror\n"
        f"repo_id: {repo_id}\n"
        f"repo: {repo}\n"
        "domain: research\n"
        "---\n"
        "Synthetic repo mirror body.\n",
        encoding="utf-8",
    )
    (repo_notes / "untyped-review-target.md").write_text(
        "# Review Target\n\nSynthetic generated metadata fixture.\n",
        encoding="utf-8",
    )
    (vault / "tools" / "repos.yml").write_text(
        "repos:\n"
        f"  - repo: {repo}\n"
        f"    note: {note}\n",
        encoding="utf-8",
    )
    (vault / "_meta" / "source-manifest.json").write_text(
        json.dumps({"version": 1, "records": []}),
        encoding="utf-8",
    )
    (vault / "_meta" / "repo-manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "records": [
                    {
                        "repo_id": repo_id,
                        "configured_repo": repo,
                        "note_path": f"25_research/repos/{note}",
                        "lifecycle_state": "clean",
                        "warnings": [],
                        "errors": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (vault / "_meta" / "sync-audit.jsonl").write_text(
        json.dumps({"tool": "sync_github_repos", "status": "unchanged", "lifecycle_state": "clean"}) + "\n",
        encoding="utf-8",
    )

    m365 = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "m365", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    sandbox = subprocess.run(
        [
            sys.executable,
            "-m",
            "vaultwright.cli",
            "--root",
            str(vault),
            "sandbox",
            "--source-root",
            str(source_root),
            "--json",
        ],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    review = subprocess.run(
        [
            sys.executable,
            "-m",
            "vaultwright.cli",
            "--root",
            str(vault),
            "review",
            "--artifact",
            "25_research/repos/untyped-review-target.md",
            "--status",
            "approved",
            "--reviewer",
            "CodeX",
            "--json",
        ],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert m365.returncode == 0, m365.stderr or m365.stdout
    m365_report = json.loads(m365.stdout)["report"]
    assert m365_report["inventory"]["repo_mirrors"] == 1
    assert "25_research/repos/" in m365_report["handoff_bundle"]
    assert "80_sources/repos/" not in m365_report["handoff_bundle"]

    assert sandbox.returncode == 0, sandbox.stderr or sandbox.stdout
    sandbox_report = json.loads(sandbox.stdout)["report"]
    assert sandbox_report["inventory"]["repo_mirrors"] == 1

    assert review.returncode == 0, review.stderr or review.stdout
    review_event = json.loads(review.stdout)["recorded"]
    assert review_event["artifact_kind"] == "repo-mirror"
    assert review_event["artifact_path"] == "25_research/repos/untyped-review-target.md"


def test_package_cli_review_accepts_profile_machine_owned_note_type(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    add_research_repo_profile(vault)
    profile_path = vault / "_meta" / "profile.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["note_types"]["research-synthesis"] = {
        "purpose": "Generated research synthesis artifact.",
        "machine_owned": True,
    }
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    target = vault / "25_research" / "generated-synthesis.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\n"
        "title: Generated Synthesis\n"
        "type: research-synthesis\n"
        "status: active\n"
        "domain: research\n"
        "---\n"
        "Generated research synthesis body that must not be copied into the ledger.\n",
        encoding="utf-8",
    )

    review = subprocess.run(
        [
            sys.executable,
            "-m",
            "vaultwright.cli",
            "--root",
            str(vault),
            "review",
            "--artifact",
            "25_research/generated-synthesis.md",
            "--status",
            "approved",
            "--reviewer",
            "CodeX",
            "--json",
        ],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert review.returncode == 0, review.stderr or review.stdout
    event = json.loads(review.stdout)["recorded"]
    assert event["artifact_kind"] == "research-synthesis"
    assert event["artifact_path"] == "25_research/generated-synthesis.md"
    assert event["metadata"]["type"] == "research-synthesis"
    assert "Generated research synthesis body" not in json.dumps(event)
    ledger_text = (vault / "_meta" / "review-ledger.jsonl").read_text(encoding="utf-8")
    assert "Generated research synthesis body" not in ledger_text


def test_package_cli_reports_use_configured_office_mirror_root(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    source_root = tmp_path / "source-root"
    shutil.copytree(ROOT / "template", vault)
    source_root.mkdir()
    set_office_mirror_root(vault)
    source = vault / "40_delivery" / "brief.docx"
    mirror = vault / "_generated" / "40_delivery" / "brief.md"
    generated_probe = vault / "_generated" / "40_delivery" / "generated-output.docx"
    source.write_bytes(b"synthetic source bytes")
    mirror.parent.mkdir(parents=True)
    mirror.write_text(
        "---\n"
        "type: source-mirror\n"
        "source_id: src-brief\n"
        "source: 40_delivery/brief.docx\n"
        "---\n"
        "Synthetic generated mirror body.\n",
        encoding="utf-8",
    )
    generated_probe.write_bytes(b"synthetic generated-root bytes")
    (vault / "CATALOG.md").write_text("# Documentation Catalog\n", encoding="utf-8")
    (vault / "CATALOG.html").write_text("<!doctype html><title>Documentation Catalog</title>\n", encoding="utf-8")
    (vault / "_meta" / "source-manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "records": [
                    {
                        "source_id": "src-brief",
                        "current_source_path": "40_delivery/brief.docx",
                        "mirror_path": "_generated/40_delivery/brief.md",
                        "source_format": "docx",
                        "lifecycle_state": "clean",
                        "warnings": [],
                        "errors": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (vault / "_meta" / "repo-manifest.json").write_text(
        json.dumps({"version": 1, "records": []}),
        encoding="utf-8",
    )
    (vault / "_meta" / "sync-audit.jsonl").write_text(
        json.dumps({"tool": "sync_office_md", "status": "unchanged", "lifecycle_state": "clean"}) + "\n",
        encoding="utf-8",
    )

    catalog = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "catalog", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    m365 = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "m365", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    sandbox = subprocess.run(
        [
            sys.executable,
            "-m",
            "vaultwright.cli",
            "--root",
            str(vault),
            "sandbox",
            "--source-root",
            str(source_root),
            "--json",
        ],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    doctor = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "doctor"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    pilot = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "pilot", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )
    review_target = vault / "_generated" / "review-target.md"
    review_target.write_text("# Review Target\n\nSynthetic generated metadata fixture.\n", encoding="utf-8")
    review = subprocess.run(
        [
            sys.executable,
            "-m",
            "vaultwright.cli",
            "--root",
            str(vault),
            "review",
            "--artifact",
            "_generated/review-target.md",
            "--status",
            "approved",
            "--reviewer",
            "CodeX",
            "--json",
        ],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert catalog.returncode == 0, catalog.stderr or catalog.stdout
    catalog_report = json.loads(catalog.stdout)["report"]
    assert catalog_report["summary"]["generated_mirrors"] == 1
    assert {"folder": "_generated"} not in catalog_report["legacy_folders"]

    assert m365.returncode == 0, m365.stderr or m365.stdout
    m365_report = json.loads(m365.stdout)["report"]
    assert m365_report["inventory"]["source_mirrors"] == 1
    assert "_generated/" in m365_report["handoff_bundle"]
    assert "_mirrors/" not in m365_report["handoff_bundle"]

    assert sandbox.returncode == 0, sandbox.stderr or sandbox.stdout
    sandbox_report = json.loads(sandbox.stdout)["report"]
    assert sandbox_report["inventory"]["dedicated_generated_mirrors"] == 1
    assert sandbox_report["inventory"]["raw_folder_generated_mirrors"] == 0

    assert doctor.returncode == 0, doctor.stderr or doctor.stdout
    assert "info: Office mirror root: _generated" in doctor.stdout

    assert pilot.returncode == 0, pilot.stderr or pilot.stdout
    pilot_report = json.loads(pilot.stdout)["report"]
    assert pilot_report["inventory"]["office_source_candidates"] == 1
    assert pilot_report["inventory"]["extensions"].get(".docx") == 1

    assert review.returncode == 0, review.stderr or review.stdout
    review_event = json.loads(review.stdout)["recorded"]
    assert review_event["artifact_kind"] == "generated-source-mirror"
    assert review_event["artifact_path"] == "_generated/review-target.md"


def test_recovery_warns_for_profile_repo_notes_dir_without_manifest(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    add_research_repo_profile(vault)
    repo_notes = vault / "25_research" / "repos"
    repo_notes.mkdir(parents=True)
    (repo_notes / "orphan.md").write_text(
        "---\n"
        "title: Orphan Repo Mirror\n"
        "type: repo-mirror\n"
        "repo_id: repo_orphan\n"
        "domain: research\n"
        "---\n"
        "Synthetic repo mirror body.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "recovery", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert (
        "_meta/repo-manifest.json not found; repo recovery has no manifest evidence yet."
        in payload["warnings"]
    )


def test_recovery_excludes_configured_office_mirror_root_from_source_evidence(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    set_office_mirror_root(vault)
    (vault / "_meta" / "source-manifest.json").unlink(missing_ok=True)
    generated = vault / "_generated" / "40_delivery" / "generated-export.docx"
    generated.parent.mkdir(parents=True)
    generated.write_bytes(b"synthetic generated-root artifact")

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "recovery", "--json"],
        cwd=ROOT,
        env=package_cli_env(),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert (
        "_meta/source-manifest.json not found; run sync/status or restore it from backup."
        not in payload["warnings"]
    )
