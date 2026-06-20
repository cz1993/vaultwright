# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path
import shutil
import subprocess
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
NORTHWIND_GENERATED = [
    Path("_meta/source-manifest.json"),
    Path("_meta/repo-manifest.json"),
    Path("_meta/sync-audit.jsonl"),
    Path("_mirrors/30_customers/acme-manufacturing/2026-01-15_acme_discovery_brief.md"),
    Path("_mirrors/60_finance/2026-01_pipeline_snapshot.md"),
    Path("_mirrors/40_delivery/2026-q1_service_readiness_review.md"),
    Path("80_sources/repos/fieldkit-control.md"),
]
NORTHWIND_RAW_FOLDER_MIRRORS = [
    Path("30_customers/acme-manufacturing/2026-01-15_acme_discovery_brief.md"),
    Path("60_finance/2026-01_pipeline_snapshot.md"),
    Path("40_delivery/2026-q1_service_readiness_review.md"),
]
GOVERNMENT_GENERATED = [
    Path("_meta/source-manifest.json"),
    Path("_meta/sync-audit.jsonl"),
    Path("_mirrors/40_delivery/business-registration/2026-06_cra_business_registration_path.md"),
    Path("_mirrors/60_finance/gst-hst/2026-06_gst_hst_registration_readiness.md"),
    Path("_mirrors/60_finance/2026-06_business_support_and_funding_tracker.md"),
    Path("_mirrors/20_market/2026-06_canadian_business_startup_navigation_brief.md"),
]
GOVERNMENT_RAW_FOLDER_MIRRORS = [
    Path("40_delivery/business-registration/2026-06_cra_business_registration_path.md"),
    Path("60_finance/gst-hst/2026-06_gst_hst_registration_readiness.md"),
    Path("60_finance/2026-06_business_support_and_funding_tracker.md"),
    Path("20_market/2026-06_canadian_business_startup_navigation_brief.md"),
]
GOVERNMENT_BENCHMARK = Path("_meta/agent-readiness-tasks.yml")
OFFICE_SOURCE_EXTS = {".docx", ".pptx", ".xlsx", ".pdf"}
BENCHMARK_FAMILIES = {"answer", "reconcile", "update", "audit", "consolidate"}


def assert_no_generated_residue(src: Path) -> None:
    mirror_files = [
        path.relative_to(src)
        for path in (src / "_mirrors").rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    ]
    assert mirror_files == []

    meta_generated = [
        path.relative_to(src)
        for path in (src / "_meta").glob("*")
        if path.name.endswith("-manifest.json") or path.name == "sync-audit.jsonl"
    ]
    assert meta_generated == []

    repo_mirrors = [
        path.relative_to(src)
        for path in (src / "80_sources" / "repos").glob("*.md")
    ]
    assert repo_mirrors == []

    sibling_mirrors = []
    for source in src.rglob("*"):
        if not source.is_file() or source.suffix.lower() not in OFFICE_SOURCE_EXTS:
            continue
        if "_mirrors" in source.parts or "tools" in source.parts:
            continue
        for mirror in (source.with_suffix(".md"), source.with_name(source.stem + ".mirror.md")):
            if mirror.exists():
                sibling_mirrors.append(mirror.relative_to(src))
    sibling_mirrors.extend(
        path.relative_to(src)
        for path in src.rglob("*.mirror.md")
        if "_mirrors" not in path.parts and "tools" not in path.parts
    )
    assert sibling_mirrors == []


def test_northwind_example_source_tree_has_no_generated_residue() -> None:
    src = ROOT / "examples/northwind-robotics-vault"
    assert_no_generated_residue(src)
    for rel in [*NORTHWIND_GENERATED, *NORTHWIND_RAW_FOLDER_MIRRORS]:
        assert not (src / rel).exists()
    log = (src / "log.md").read_text(encoding="utf-8")
    assert "sync |" not in log


def test_government_services_example_source_tree_has_no_generated_residue() -> None:
    src = ROOT / "examples/government-services-vault"
    assert_no_generated_residue(src)
    for rel in [*GOVERNMENT_GENERATED, *GOVERNMENT_RAW_FOLDER_MIRRORS]:
        assert not (src / rel).exists()
    log = (src / "log.md").read_text(encoding="utf-8")
    assert "sync |" not in log


def load_government_benchmark(vault: Path) -> dict:
    data = yaml.safe_load((vault / GOVERNMENT_BENCHMARK).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_government_services_agent_readiness_tasks_reference_committed_sources() -> None:
    vault = ROOT / "examples/government-services-vault"
    data = load_government_benchmark(vault)
    assert data["schema_version"] == 1
    assert data["corpus"] == "government-services-vault"
    assert set(data["comparison_modes"]) == {
        "raw_source_folder",
        "document_chat_transcript",
        "vaultwright_markdown",
    }
    tasks = data["tasks"]
    assert isinstance(tasks, list)
    assert len(tasks) >= 5
    families = {task["family"] for task in tasks}
    assert BENCHMARK_FAMILIES.issubset(families)
    assert families <= BENCHMARK_FAMILIES

    generated = set(GOVERNMENT_GENERATED)
    for task in tasks:
        assert task["id"]
        assert task["prompt"].endswith("?")
        assert task["success_criteria"]
        for rel in task.get("source_paths", []):
            assert (vault / rel).exists(), rel
            assert "_mirrors" not in Path(rel).parts
        for rel in task.get("curated_paths", []):
            path = vault / rel
            assert path.exists(), rel
            assert path.suffix == ".md"
        for rel in task.get("generated_mirror_paths", []):
            mirror = Path(rel)
            assert mirror in generated, rel
            assert not (vault / mirror).exists(), rel

    benchmark = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "benchmark"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    assert benchmark.returncode == 0, benchmark.stderr or benchmark.stdout
    assert "benchmark_tasks: 6 tasks" in benchmark.stdout
    assert "generated mirror not present yet" in benchmark.stdout


def assert_benchmark_generated_mirrors_exist(vault: Path) -> None:
    data = load_government_benchmark(vault)
    for task in data["tasks"]:
        for rel in task.get("generated_mirror_paths", []):
            assert (vault / rel).exists(), rel


def run_example_regeneration(tmp_path: Path, name: str, generated_rels: list[Path], raw_folder_rels: list[Path]) -> str:
    src = ROOT / f"examples/{name}"
    vault = tmp_path / name
    shutil.copytree(src, vault)

    generated = [vault / rel for rel in generated_rels]
    for path in generated:
        assert not path.exists()

    plan = subprocess.run(
        [sys.executable, str(vault / "tools" / "sync_office_md.py"), "--plan", "--quiet"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    assert plan.returncode == 0, plan.stderr or plan.stdout
    for path in generated:
        assert not path.exists()

    lint_output = ""
    for script in ("sync_office_md.py", "sync_github_repos.py", "lint_vault.py"):
        result = subprocess.run(
            [sys.executable, str(vault / "tools" / script), "--quiet"]
            if script != "lint_vault.py"
            else [sys.executable, str(vault / "tools" / script)],
            cwd=vault,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr or result.stdout
        if script == "lint_vault.py":
            lint_output = result.stdout

    status = subprocess.run(
        [sys.executable, str(vault / "tools" / "sync_office_md.py"), "--status", "--quiet"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    assert status.returncode == 0, status.stderr or status.stdout
    assert "unchanged" in status.stdout
    assert "clean=" in status.stdout

    for path in generated:
        assert path.exists()
    for rel in raw_folder_rels:
        assert not (vault / rel).exists()
    return lint_output


def assert_clean_lint(lint_output: str) -> None:
    assert "Missing/invalid frontmatter: 0" in lint_output
    assert "Invalid type: 0" in lint_output
    assert "Invalid status: 0" in lint_output
    assert "Invalid domain: 0" in lint_output
    assert "Domain map errors: 0" in lint_output
    assert "Mirror config errors: 0" in lint_output
    assert "Domain/folder mismatch: 0" in lint_output
    assert "Account/client mismatch: 0" in lint_output
    assert "Mirror layout errors: 0" in lint_output
    assert "Non-lowercase markdown extension: 0" in lint_output
    assert "Unresolved wikilinks: 0" in lint_output
    assert "Orphan notes (no inbound links): 0" in lint_output
    assert "Potential duplicate/overlap notes: 0" in lint_output
    assert "Office files without a mirror: 0" in lint_output


def run_vaultwright(vault: Path, command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), command],
        cwd=vault,
        text=True,
        capture_output=True,
    )


def test_northwind_example_mirrors_regenerate_from_sources(tmp_path: Path) -> None:
    lint_output = run_example_regeneration(
        tmp_path,
        "northwind-robotics-vault",
        NORTHWIND_GENERATED,
        NORTHWIND_RAW_FOLDER_MIRRORS,
    )
    assert_clean_lint(lint_output)


def test_government_services_example_mirrors_regenerate_from_sources(tmp_path: Path) -> None:
    vault = tmp_path / "government-services-vault"
    lint_output = run_example_regeneration(
        tmp_path,
        "government-services-vault",
        GOVERNMENT_GENERATED,
        GOVERNMENT_RAW_FOLDER_MIRRORS,
    )
    assert_clean_lint(lint_output)
    assert_benchmark_generated_mirrors_exist(vault)
    benchmark = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "benchmark", "--require-generated"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    assert benchmark.returncode == 0, benchmark.stderr or benchmark.stdout
    assert "benchmark_tasks: 6 tasks" in benchmark.stdout


def test_northwind_recovery_gate_regenerates_and_flags_review_states(tmp_path: Path) -> None:
    vault = tmp_path / "northwind-robotics-vault"
    shutil.copytree(ROOT / "examples/northwind-robotics-vault", vault)
    source_rels = [
        Path("30_customers/acme-manufacturing/2026-01-15_acme_discovery_brief.docx"),
        Path("60_finance/2026-01_pipeline_snapshot.xlsx"),
        Path("40_delivery/2026-q1_service_readiness_review.pptx"),
        Path("_fixtures/repos/fieldkit-control/README.md"),
    ]
    source_bytes = {rel: (vault / rel).read_bytes() for rel in source_rels}

    first_sync = run_vaultwright(vault, "sync")
    assert first_sync.returncode == 0, first_sync.stderr or first_sync.stdout
    for rel in NORTHWIND_GENERATED:
        assert (vault / rel).exists()

    shutil.rmtree(vault / "_mirrors")
    for rel in NORTHWIND_GENERATED:
        if rel.as_posix().startswith("80_sources/repos/"):
            (vault / rel).unlink()

    recovery_plan = run_vaultwright(vault, "plan")
    assert recovery_plan.returncode == 0, recovery_plan.stderr or recovery_plan.stdout
    assert "create" in recovery_plan.stdout
    recovery_sync = run_vaultwright(vault, "sync")
    assert recovery_sync.returncode == 0, recovery_sync.stderr or recovery_sync.stdout
    recovery_status = run_vaultwright(vault, "status")
    assert recovery_status.returncode == 0, recovery_status.stderr or recovery_status.stdout
    assert "clean=" in recovery_status.stdout
    lint = run_vaultwright(vault, "lint")
    assert lint.returncode == 0, lint.stderr or lint.stdout
    for rel in NORTHWIND_GENERATED:
        assert (vault / rel).exists()
    for rel, original in source_bytes.items():
        assert (vault / rel).read_bytes() == original

    scan_paths = [
        str(path)
        for path in vault.rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".json", ".jsonl"}
    ]
    scan = subprocess.run(
        [sys.executable, str(ROOT / "scripts/no_data_scan.py"), "--paths", *scan_paths],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert scan.returncode == 0, scan.stderr or scan.stdout

    removed_source = vault / "30_customers/acme-manufacturing/2026-01-15_acme_discovery_brief.docx"
    removed_source.unlink()
    missing_status = run_vaultwright(vault, "status")
    assert missing_status.returncode == 0, missing_status.stderr or missing_status.stdout
    assert "source_missing" in missing_status.stdout

    mirror = vault / "_mirrors/60_finance/2026-01_pipeline_snapshot.md"
    mirror.write_text(
        mirror.read_text(encoding="utf-8").replace("Extracted content", "Manually edited generated content"),
        encoding="utf-8",
    )
    manual_status = run_vaultwright(vault, "status")
    assert manual_status.returncode == 0, manual_status.stderr or manual_status.stdout
    assert "manual_modification" in manual_status.stdout
