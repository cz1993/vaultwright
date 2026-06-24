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
