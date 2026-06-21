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
COPIED_TOOL_FILES = [
    "README.md",
    "benchmark_tasks.py",
    "catalog_report.py",
    "conversion_report.py",
    "lint_vault.py",
    "m365_report.py",
    "pilot_report.py",
    "recovery_report.py",
    "review_ledger.py",
    "sandbox_report.py",
    "repos.example.yml",
    "requirements.txt",
    "sync_all.sh",
    "sync_github_repos.py",
    "sync_office_md.py",
    "vaultwright.py",
]


def source_payloads(vault: Path) -> dict[Path, bytes]:
    payloads: dict[Path, bytes] = {}
    for path in vault.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(vault)
        if path.suffix.lower() in OFFICE_SOURCE_EXTS and "_mirrors" not in rel.parts:
            payloads[rel] = path.read_bytes()
        elif rel.parts[:2] == ("_fixtures", "repos"):
            payloads[rel] = path.read_bytes()
    return payloads


def assert_source_payloads_unchanged(vault: Path, before: dict[Path, bytes]) -> None:
    after = source_payloads(vault)
    assert after.keys() == before.keys()
    for rel, payload in before.items():
        assert after[rel] == payload, rel


def stable_generated_payloads(vault: Path, generated_rels: list[Path]) -> dict[Path, bytes]:
    payloads: dict[Path, bytes] = {}
    for rel in generated_rels:
        if rel.name == "sync-audit.jsonl":
            continue
        path = vault / rel
        assert path.exists(), rel
        payloads[rel] = path.read_bytes()
    return payloads


def assert_stable_generated_payloads_unchanged(vault: Path, before: dict[Path, bytes]) -> None:
    for rel, payload in before.items():
        assert (vault / rel).read_bytes() == payload, rel


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


def test_example_vault_tool_copies_match_template() -> None:
    for example in ("northwind-robotics-vault", "government-services-vault"):
        tools = ROOT / "examples" / example / "tools"
        for filename in COPIED_TOOL_FILES:
            assert (tools / filename).read_bytes() == (ROOT / "template" / "tools" / filename).read_bytes(), (
                example,
                filename,
            )


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
    original_sources = source_payloads(vault)

    generated = [vault / rel for rel in generated_rels]
    for path in generated:
        assert not path.exists()

    cli_plan = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "plan"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    assert cli_plan.returncode == 0, cli_plan.stderr or cli_plan.stdout
    for path in generated:
        assert not path.exists()
    assert_source_payloads_unchanged(vault, original_sources)

    plan = subprocess.run(
        [sys.executable, str(vault / "tools" / "sync_office_md.py"), "--plan", "--quiet"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    assert plan.returncode == 0, plan.stderr or plan.stdout
    for path in generated:
        assert not path.exists()
    assert_source_payloads_unchanged(vault, original_sources)

    for script in ("sync_office_md.py", "sync_github_repos.py"):
        dry_run = subprocess.run(
            [sys.executable, str(vault / "tools" / script), "--dry-run", "--quiet"],
            cwd=vault,
            text=True,
            capture_output=True,
        )
        assert dry_run.returncode == 0, dry_run.stderr or dry_run.stdout
        for path in generated:
            assert not path.exists()
        assert_source_payloads_unchanged(vault, original_sources)

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

    conversion = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "conversion"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    assert conversion.returncode == 0, conversion.stderr or conversion.stdout
    assert "conversion: read-only spot-check report; no files were changed" in conversion.stdout
    assert "spot-check items" in conversion.stdout
    assert_source_payloads_unchanged(vault, original_sources)

    pilot = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "pilot"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    assert pilot.returncode == 0, pilot.stderr or pilot.stdout
    assert "pilot: read-only evidence report; no source content was printed" in pilot.stdout
    assert "pilot: source manifest" in pilot.stdout
    assert_source_payloads_unchanged(vault, original_sources)

    for path in generated:
        assert path.exists()
    for rel in raw_folder_rels:
        assert not (vault / rel).exists()
    assert_source_payloads_unchanged(vault, original_sources)

    stable_generated = stable_generated_payloads(vault, generated_rels)
    second_sync = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "sync"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    assert second_sync.returncode == 0, second_sync.stderr or second_sync.stdout
    assert "unchanged" in second_sync.stdout
    assert_stable_generated_payloads_unchanged(vault, stable_generated)
    assert_source_payloads_unchanged(vault, original_sources)
    return lint_output


def assert_clean_lint(lint_output: str) -> None:
    assert "Missing/invalid frontmatter: 0" in lint_output
    assert "Invalid type: 0" in lint_output
    assert "Invalid status: 0" in lint_output
    assert "Invalid domain: 0" in lint_output
    assert "Domain map errors: 0" in lint_output
    assert "Mirror config errors: 0" in lint_output
    assert "Repo config errors: 0" in lint_output
    assert "Domain/folder mismatch: 0" in lint_output
    assert "Account/client mismatch: 0" in lint_output
    assert "Mirror layout errors: 0" in lint_output
    assert "Non-lowercase markdown extension: 0" in lint_output
    assert "Unresolved wikilinks: 0" in lint_output
    assert "Orphan notes (no inbound links): 0" in lint_output
    assert "Potential duplicate/overlap notes: 0" in lint_output
    assert "Office files without a mirror: 0" in lint_output
    assert "Configured repos without a mirror: 0" in lint_output


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
