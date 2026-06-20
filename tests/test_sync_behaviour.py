# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]


class FakeConversion:
    text_content = "Extracted fixture content"


class FakeConverter:
    def convert(self, _path: str) -> FakeConversion:
        return FakeConversion()


class SourceChangingConverter:
    def __init__(self, replacement: bytes) -> None:
        self.replacement = replacement

    def convert(self, path: str) -> FakeConversion:
        Path(path).write_bytes(self.replacement)
        return FakeConversion()


class FailingConverter:
    def convert(self, _path: str) -> FakeConversion:
        raise RuntimeError("conversion exploded")


def load_sync_module():
    spec = importlib.util.spec_from_file_location(
        "sync_github_repos_for_test",
        ROOT / "template/tools/sync_github_repos.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_office_sync_module():
    spec = importlib.util.spec_from_file_location(
        "sync_office_md_for_test",
        ROOT / "template/tools/sync_office_md.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_vaultwright_cli_doctor_passes_on_template() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "template/tools/vaultwright.py"), "doctor"],
        cwd=ROOT / "template",
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "vaultwright doctor: OK" in result.stdout
    assert "info: source-manifest.json: not generated yet" in result.stdout
    assert "info: repo-manifest.json: not generated yet" in result.stdout
    assert "info: sync-audit.jsonl: not generated yet" in result.stdout
    assert "info: recovery: no action items" in result.stdout
    assert "info: Obsidian Bases index: Documents.base present" in result.stdout
    assert "info: Obsidian: .obsidian not present" in result.stdout
    assert "backup guard: .gitignore covers high-risk local data patterns" in result.stdout
    assert "GitHub auth:" in result.stdout
    assert (ROOT / "template/tools/benchmark_tasks.py").exists()
    assert (ROOT / "template/tools/conversion_report.py").exists()
    assert (ROOT / "template/tools/migration_report.py").exists()
    assert (ROOT / "template/tools/pilot_report.py").exists()
    assert (ROOT / "template/tools/recovery_report.py").exists()


def test_vaultwright_cli_doctor_reports_manifest_lifecycle_counts(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "source-manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "records": [
                    {"source_id": "src-clean", "lifecycle_state": "clean"},
                    {"source_id": "src-missing", "lifecycle_state": "source_missing"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (vault / "_meta" / "repo-manifest.json").write_text(
        json.dumps({"version": 1, "records": [{"repo_id": "repo-clean", "lifecycle_state": "clean"}]}),
        encoding="utf-8",
    )
    (vault / "_meta" / "sync-audit.jsonl").write_text(
        '{"tool":"sync_office_md","status":"created"}\n'
        '{"tool":"sync_github_repos","status":"updated"}\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "doctor"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "source-manifest.json: 2 records (clean=1, source_missing=1)" in result.stdout
    assert "repo-manifest.json: 1 records (clean=1)" in result.stdout
    assert "sync-audit.jsonl: 2 events" in result.stdout
    assert "warning: recovery: 1 item needs operator action (office=1, repo=0, temp=0)" in result.stdout
    assert "vaultwright doctor: OK" in result.stdout


def test_vaultwright_cli_doctor_reports_obsidian_and_backup_posture(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    obsidian = vault / ".obsidian"
    plugins = obsidian / "plugins" / "sample-plugin"
    plugins.mkdir(parents=True)
    (obsidian / "app.json").write_text("{bad json", encoding="utf-8")
    (obsidian / "core-plugins.json").write_text(
        json.dumps({"file-explorer": True, "graph": False, "backlink": True}),
        encoding="utf-8",
    )
    (obsidian / "community-plugins.json").write_text(
        json.dumps(["sample-plugin", "another-plugin"]),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "doctor"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "info: Obsidian Bases index: Documents.base present" in result.stdout
    assert "info: Obsidian: .obsidian present" in result.stdout
    assert "info: Obsidian core plugins: 2 enabled" in result.stdout
    assert "warning: Obsidian app.json: invalid JSON (JSONDecodeError)" in result.stdout
    assert "warning: Obsidian community plugins: 2 enabled; review plugin trust boundary before pilots." in result.stdout
    assert "warning: Obsidian installed plugin directories: 1 found; review local plugin code before pilots." in result.stdout
    assert "info: backup guard: .gitignore covers high-risk local data patterns" in result.stdout
    assert "warning: Vault root is not inside a git work tree; back up curated notes before production sync." in result.stdout


def test_vaultwright_cli_doctor_does_not_trust_commented_gitignore_patterns(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / ".gitignore").write_text(
        "# data/\n"
        "# secrets/\n"
        "metadata/\n"
        "private/\n"
        ".env\n"
        "*.pem\n"
        ".obsidian/workspace*.json\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "doctor"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "backup guard: .gitignore covers high-risk local data patterns" not in result.stdout
    assert "warning: backup guard: .gitignore unsafe; missing effective ignores: data/, secrets/" in result.stdout


def test_vaultwright_cli_doctor_flags_negated_gitignore_patterns(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / ".gitignore").write_text(
        "data/\n"
        "secrets/\n"
        "private/\n"
        ".env\n"
        "*.pem\n"
        ".obsidian/workspace*.json\n"
        "!data/\n"
        "!data/leak.md\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "doctor"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "backup guard: .gitignore covers high-risk local data patterns" not in result.stdout
    assert "warning: backup guard: .gitignore unsafe;" in result.stdout
    assert "missing effective ignores: data/" in result.stdout
    assert "negated high-risk paths: data/" in result.stdout


def test_vaultwright_cli_doctor_handles_unreadable_obsidian_json(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    obsidian = vault / ".obsidian"
    obsidian.mkdir()
    (obsidian / "app.json").write_bytes(b"\xff\xfe\x00")

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "doctor"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "info: Obsidian: .obsidian present" in result.stdout
    assert "warning: Obsidian app.json: unreadable text" in result.stdout


def test_vaultwright_cli_root_uses_target_vault_tools(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    fixture = vault / "_fixtures" / "repo"
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text("# Fixture\n", encoding="utf-8")
    (vault / "tools" / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos:\n"
        "  - repo: local/fixture\n"
        "    local_path: _fixtures/repo\n"
        "    note: fixture.md\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(ROOT / "template/tools/vaultwright.py"), "--root", str(vault), "plan"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "sync_office_md plan" in result.stdout
    assert "sync_github_repos plan" in result.stdout
    assert "1 create" in result.stdout
    assert not (vault / "80_sources" / "repos" / "fixture.md").exists()


def test_packaged_vaultwright_cli_delegates_to_target_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "plan"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "sync_office_md plan" in result.stdout

    benchmark = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "benchmark"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert benchmark.returncode == 0, benchmark.stderr or benchmark.stdout
    assert "benchmark validation skipped" in benchmark.stdout

    pilot = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "pilot"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert pilot.returncode == 0, pilot.stderr or pilot.stdout
    assert "pilot: read-only evidence report; no source content was printed" in pilot.stdout
    assert "_meta/source-manifest.json: missing" in pilot.stdout

    conversion = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "conversion"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert conversion.returncode == 0, conversion.stderr or conversion.stdout
    assert "_meta/source-manifest.json: missing; run `vaultwright sync` first." in conversion.stdout
    assert "conversion: no source-manifest records available for spot-checking" in conversion.stdout

    conversion_guide = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "conversion", "--guide"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert conversion_guide.returncode == 0, conversion_guide.stderr or conversion_guide.stdout
    assert "conversion guide: operator review checklist; no files were changed" in conversion_guide.stdout

    migration = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "migration"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert migration.returncode == 0, migration.stderr or migration.stdout
    assert "migration: no legacy or unknown top-level folders found" in migration.stdout

    recovery = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "recovery"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert recovery.returncode == 0, recovery.stderr or recovery.stdout
    assert "recovery: no manifest records need operator action" in recovery.stdout

    recovery_json = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "recovery", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert recovery_json.returncode == 0, recovery_json.stderr or recovery_json.stdout
    report = json.loads(recovery_json.stdout)
    assert report["items"] == []
    assert report["summary"]["total"] == 0


def write_agent_benchmark_fixture(vault: Path) -> None:
    source = vault / "40_delivery" / "client-plan.docx"
    mirror = vault / "_mirrors" / "40_delivery" / "client-plan.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    mirror.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"synthetic benchmark source")
    mirror.write_text("---\nsource_path: 40_delivery/client-plan.docx\n---\nSynthetic mirror\n", encoding="utf-8")
    tasks = []
    for family in ("answer", "reconcile", "update", "audit", "consolidate"):
        tasks.append(
            {
                "id": f"{family}-1",
                "family": family,
                "prompt": f"What should the {family} task prove?",
                "source_paths": ["40_delivery/client-plan.docx"],
                "generated_mirror_paths": ["_mirrors/40_delivery/client-plan.md"],
                "curated_paths": [],
                "success_criteria": ["Uses source-backed evidence"],
            }
        )
    (vault / "_meta" / "agent-readiness-tasks.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "corpus": "fixture",
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
    (vault / "_meta" / "agent-readiness-results.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "corpus": "fixture",
                "results": [
                    {
                        "task_id": "answer-1",
                        "mode": "vaultwright_markdown",
                        "score": 2,
                        "reviewer_corrections": 0,
                        "elapsed_seconds": 12.5,
                        "cited_source_paths": ["40_delivery/client-plan.docx"],
                        "cited_generated_mirror_paths": ["_mirrors/40_delivery/client-plan.md"],
                    },
                    {
                        "task_id": "answer-1",
                        "mode": "raw_source_folder",
                        "score": 1,
                        "reviewer_corrections": 1,
                        "cited_source_paths": ["40_delivery/client-plan.docx"],
                    },
                    {
                        "task_id": "audit-1",
                        "mode": "document_chat_transcript",
                        "score": 0,
                        "reviewer_corrections": 2,
                        "privacy_or_provenance_violation": True,
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_vaultwright_benchmark_reports_result_scores_without_answer_content(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    write_agent_benchmark_fixture(vault)

    result = subprocess.run(
        [
            sys.executable,
            str(vault / "tools" / "vaultwright.py"),
            "benchmark",
            "--results",
            "_meta/agent-readiness-results.yml",
        ],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "benchmark_tasks: 5 tasks" in result.stdout
    assert "benchmark_results: 3 results" in result.stdout
    assert "vaultwright_markdown: results=1 score=2/2 avg=2.00 corrections=0 violations=0" in result.stdout
    assert "raw_source_folder: results=1 score=1/2 avg=1.00 corrections=1 violations=0" in result.stdout
    assert "document_chat_transcript: results=1 score=0/2 avg=0.00 corrections=2 violations=1" in result.stdout
    assert "warning: benchmark results incomplete: missing 12 task/mode scores" in result.stdout


def test_vaultwright_benchmark_require_results_fails_on_incomplete_scores(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    write_agent_benchmark_fixture(vault)

    result = subprocess.run(
        [
            sys.executable,
            str(vault / "tools" / "vaultwright.py"),
            "benchmark",
            "--results",
            "_meta/agent-readiness-results.yml",
            "--require-results",
        ],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "benchmark results incomplete: missing 12 task/mode scores" in result.stderr


def test_vaultwright_benchmark_rejects_answer_text_and_reviewer_notes(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    write_agent_benchmark_fixture(vault)
    (vault / "_meta" / "agent-readiness-results.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "corpus": "fixture",
                "results": [
                    {
                        "task_id": "answer-1",
                        "mode": "vaultwright_markdown",
                        "score": 2,
                        "reviewer_corrections": 0,
                        "cited_source_paths": ["40_delivery/client-plan.docx"],
                        "cited_generated_mirror_paths": ["_mirrors/40_delivery/client-plan.md"],
                        "answer_text": "private generated answer should stay hidden",
                        "reviewer_notes": "private reviewer notes should stay hidden",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(vault / "tools" / "vaultwright.py"),
            "benchmark",
            "--results",
            "_meta/agent-readiness-results.yml",
        ],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "unsupported result field answer_text" in result.stderr
    assert "unsupported result field reviewer_notes" in result.stderr
    assert "private generated answer" not in result.stdout
    assert "private generated answer" not in result.stderr
    assert "private reviewer notes" not in result.stdout
    assert "private reviewer notes" not in result.stderr


def test_vaultwright_benchmark_rejects_top_level_private_result_fields(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    write_agent_benchmark_fixture(vault)
    (vault / "_meta" / "agent-readiness-results.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "corpus": "fixture",
                "answer_text": "private top-level answer should stay hidden",
                "reviewer_notes": "private top-level notes should stay hidden",
                "results": [
                    {
                        "task_id": "answer-1",
                        "mode": "vaultwright_markdown",
                        "score": 2,
                        "reviewer_corrections": 0,
                        "cited_source_paths": ["40_delivery/client-plan.docx"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(vault / "tools" / "vaultwright.py"),
            "benchmark",
            "--results",
            "_meta/agent-readiness-results.yml",
        ],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "unsupported top-level field answer_text" in result.stderr
    assert "unsupported top-level field reviewer_notes" in result.stderr
    assert "private top-level answer" not in result.stdout
    assert "private top-level answer" not in result.stderr
    assert "private top-level notes" not in result.stdout
    assert "private top-level notes" not in result.stderr


def test_vaultwright_benchmark_rejects_unrelated_citations(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    write_agent_benchmark_fixture(vault)
    unrelated = vault / "50_operations" / "unrelated.docx"
    unrelated.parent.mkdir(parents=True, exist_ok=True)
    unrelated.write_bytes(b"unrelated source")
    (vault / "_meta" / "agent-readiness-results.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "corpus": "fixture",
                "results": [
                    {
                        "task_id": "answer-1",
                        "mode": "vaultwright_markdown",
                        "score": 2,
                        "reviewer_corrections": 0,
                        "cited_source_paths": ["50_operations/unrelated.docx"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(vault / "tools" / "vaultwright.py"),
            "benchmark",
            "--results",
            "_meta/agent-readiness-results.yml",
        ],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "cited_source_paths must cite a path declared by the task: 50_operations/unrelated.docx" in result.stderr


def test_vaultwright_benchmark_rejects_non_finite_elapsed_seconds(tmp_path: Path) -> None:
    for value in ("-1", ".nan", ".inf"):
        vault = tmp_path / f"vault-{value.replace('.', 'dot').replace('-', 'neg')}"
        shutil.copytree(ROOT / "template", vault)
        write_agent_benchmark_fixture(vault)
        (vault / "_meta" / "agent-readiness-results.yml").write_text(
            "schema_version: 1\n"
            "corpus: fixture\n"
            "results:\n"
            "  - task_id: answer-1\n"
            "    mode: vaultwright_markdown\n"
            "    score: 2\n"
            "    reviewer_corrections: 0\n"
            "    elapsed_seconds: " + value + "\n"
            "    cited_source_paths: [40_delivery/client-plan.docx]\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                str(vault / "tools" / "vaultwright.py"),
                "benchmark",
                "--results",
                "_meta/agent-readiness-results.yml",
                "--json",
            ],
            cwd=vault,
            text=True,
            capture_output=True,
        )

        assert result.returncode == 1
        assert "elapsed_seconds must be a finite non-negative number" in result.stdout
        assert "NaN" not in result.stdout
        assert "Infinity" not in result.stdout


def test_vaultwright_benchmark_require_results_requires_task_pack(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "benchmark", "--require-results"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "benchmark_tasks: missing task pack: _meta/agent-readiness-tasks.yml" in result.stderr


def test_vaultwright_benchmark_default_result_file_requires_task_pack(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    (vault / "_meta" / "agent-readiness-results.yml").write_text(
        "schema_version: 1\ncorpus: fixture\nresults: []\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "benchmark"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "benchmark_tasks: missing task pack: _meta/agent-readiness-tasks.yml" in result.stderr


def test_packaged_vaultwright_cli_delegates_benchmark_result_args(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    write_agent_benchmark_fixture(vault)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vaultwright.cli",
            "--root",
            str(vault),
            "benchmark",
            "--results",
            "_meta/agent-readiness-results.yml",
            "--json",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["summary"]["tasks"] == 5
    assert payload["result_summary"]["results"] == 3
    assert payload["result_summary"]["modes"]["vaultwright_markdown"]["score"] == 2


def test_packaged_vaultwright_cli_init_from_source_checkout(tmp_path: Path) -> None:
    target = tmp_path / "new-vault"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "VAULTWRIGHT_REPO": str(ROOT)}

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "init", str(target)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert (target / "CLAUDE.md").exists()
    assert (target / "tools" / "vaultwright.py").exists()


def test_packaged_vaultwright_cli_init_from_packaged_template(tmp_path: Path) -> None:
    target = tmp_path / "packaged-vault"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    env.pop("VAULTWRIGHT_REPO", None)

    result = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "init", str(target)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert (target / "CLAUDE.md").exists()
    assert (target / ".gitignore").exists()
    assert (target / "tools" / "conversion_report.py").exists()
    assert (target / "tools" / "migration_report.py").exists()
    assert (target / "tools" / "pilot_report.py").exists()
    assert (target / "tools" / "recovery_report.py").exists()
    assert (target / "tools" / "vaultwright.py").exists()


def test_repos_example_has_no_active_placeholder_repo() -> None:
    cfg = yaml.safe_load((ROOT / "template/tools/repos.example.yml").read_text(encoding="utf-8"))

    assert cfg["repos"] == []


def test_vaultwright_conversion_report_prioritizes_spot_checks(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    source_manifest = vault / "_meta" / "source-manifest.json"
    source_manifest.parent.mkdir(parents=True, exist_ok=True)

    simple_source = vault / "40_delivery" / "simple.docx"
    pdf_source = vault / "40_delivery" / "guidance.pdf"
    stale_source = vault / "40_delivery" / "changed.docx"
    legacy_source = vault / "40_delivery" / "legacy.doc"
    sheet_source = vault / "60_finance" / "model.xlsx"
    simple_mirror = vault / "_mirrors" / "40_delivery" / "simple.md"
    pdf_mirror = vault / "_mirrors" / "40_delivery" / "guidance.md"
    stale_mirror = vault / "_mirrors" / "40_delivery" / "changed.md"
    legacy_mirror = vault / "_mirrors" / "40_delivery" / "legacy.md"
    sheet_mirror = vault / "_mirrors" / "60_finance" / "model.md"
    for path in (
        simple_source,
        pdf_source,
        stale_source,
        legacy_source,
        sheet_source,
        simple_mirror,
        pdf_mirror,
        stale_mirror,
        legacy_mirror,
        sheet_mirror,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
    simple_source.write_bytes(b"docx bytes")
    pdf_source.write_bytes(b"pdf bytes")
    stale_source.write_bytes(b"changed docx bytes")
    legacy_source.write_bytes(b"legacy doc bytes")
    sheet_source.write_bytes(b"xlsx bytes")
    simple_mirror.write_text("Simple mirror\n", encoding="utf-8")
    pdf_mirror.write_text("PDF mirror\n", encoding="utf-8")
    stale_mirror.write_text("Changed mirror\n", encoding="utf-8")
    legacy_mirror.write_text("Legacy mirror\n", encoding="utf-8")
    sheet_mirror.write_text("Sheet mirror\n", encoding="utf-8")
    before_sources = {
        path: path.read_bytes()
        for path in (simple_source, pdf_source, stale_source, legacy_source, sheet_source)
    }
    before_mirrors = {
        path: path.read_text(encoding="utf-8")
        for path in (simple_mirror, pdf_mirror, stale_mirror, legacy_mirror, sheet_mirror)
    }

    source_manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "records": [
                    {
                        "source_id": "src-simple",
                        "current_source_path": "40_delivery/simple.docx",
                        "mirror_path": "_mirrors/40_delivery/simple.md",
                        "source_format": "docx",
                        "source_size": len(before_sources[simple_source]),
                        "lifecycle_state": "clean",
                        "warnings": [],
                        "errors": [],
                    },
                    {
                        "source_id": "src-pdf",
                        "current_source_path": "40_delivery/guidance.pdf",
                        "mirror_path": "_mirrors/40_delivery/guidance.md",
                        "source_format": "pdf",
                        "source_size": len(before_sources[pdf_source]),
                        "lifecycle_state": "clean",
                        "warnings": ["Conversion-quality risk: PDF text extraction may omit scanned pages."],
                        "errors": [],
                    },
                    {
                        "source_id": "src-stale",
                        "current_source_path": "40_delivery/changed.docx",
                        "mirror_path": "_mirrors/40_delivery/changed.md",
                        "source_format": "docx",
                        "source_size": len(before_sources[stale_source]),
                        "lifecycle_state": "source_changed",
                        "warnings": [],
                        "errors": [],
                    },
                    {
                        "source_id": "src-legacy",
                        "current_source_path": "40_delivery/legacy.doc",
                        "mirror_path": "_mirrors/40_delivery/legacy.md",
                        "source_format": "doc",
                        "source_size": len(before_sources[legacy_source]),
                        "lifecycle_state": "unsupported",
                        "warnings": ["Legacy .doc files are inventory-only; convert to .docx for reliable mirroring."],
                        "errors": [],
                    },
                    {
                        "source_id": "src-sheet",
                        "current_source_path": "60_finance/model.xlsx",
                        "mirror_path": "_mirrors/60_finance/model.md",
                        "source_format": "xlsx",
                        "source_size": len(before_sources[sheet_source]),
                        "lifecycle_state": "conflict",
                        "warnings": ["Conversion-quality risk: spreadsheet formulas and formatting require review."],
                        "errors": ["Mirror frontmatter belongs to a different source_id."],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "conversion"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    json_result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "conversion", "--json"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    guide_result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "conversion", "--guide"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    guide_json_result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "conversion", "--guide", "--json"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "conversion: read-only spot-check report; no files were changed" in result.stdout
    assert "conversion: 5 manifest records (high=2, medium=2, low=1)" in result.stdout
    assert "[high  ] 40_delivery/legacy.doc -> _mirrors/40_delivery/legacy.md" in result.stdout
    assert "[high  ] 60_finance/model.xlsx -> _mirrors/60_finance/model.md" in result.stdout
    assert "[medium] 40_delivery/changed.docx -> _mirrors/40_delivery/changed.md" in result.stdout
    assert "[medium] 40_delivery/guidance.pdf -> _mirrors/40_delivery/guidance.md" in result.stdout
    assert "[low   ] 40_delivery/simple.docx -> _mirrors/40_delivery/simple.md" in result.stdout
    assert "Resolve lifecycle/recovery item before trusting the generated mirror." in result.stdout
    assert "Refresh or review the mirror before relying on generated content." in result.stdout
    assert "Spot-check headings, tables/slides/pages, omissions, and source links" in result.stdout

    assert json_result.returncode == 0, json_result.stderr or json_result.stdout
    report = json.loads(json_result.stdout)
    assert report["summary"]["total"] == 5
    assert report["summary"]["high"] == 2
    assert report["summary"]["medium"] == 2
    assert report["summary"]["low"] == 1
    assert report["summary"]["formats"] == {"doc": 1, "docx": 2, "pdf": 1, "xlsx": 1}
    by_id = {item["source_id"]: item for item in report["items"]}
    assert by_id["src-sheet"]["priority"] == "high"
    assert by_id["src-sheet"]["state"] == "conflict"
    assert "Mirror frontmatter belongs to a different source_id." in by_id["src-sheet"]["reasons"]
    assert by_id["src-stale"]["priority"] == "medium"
    assert by_id["src-stale"]["state"] == "source_changed"
    assert "state=source_changed" in by_id["src-stale"]["reasons"]
    assert by_id["src-pdf"]["priority"] == "medium"
    assert by_id["src-simple"]["priority"] == "low"
    assert report["warnings"] == []
    assert report["errors"] == []

    assert guide_result.returncode == 0, guide_result.stderr or guide_result.stdout
    assert "conversion guide: operator review checklist; no files were changed" in guide_result.stdout
    assert "Resolve all high-priority items before relying on mirrors" in guide_result.stdout
    assert "doc (1): Treat legacy .doc files as inventory-only" in guide_result.stdout
    assert "pdf (1): Check scanned or image-only pages against the original PDF" in guide_result.stdout
    assert "xlsx (1): Check formulas, hidden sheets" in guide_result.stdout
    assert "Use source-backed citations for durable curated notes" in guide_result.stdout
    assert "PDF mirror" not in guide_result.stdout
    assert "Sheet mirror" not in guide_result.stdout

    assert guide_json_result.returncode == 0, guide_json_result.stderr or guide_json_result.stdout
    guide_payload = json.loads(guide_json_result.stdout)
    assert guide_payload["summary"]["total"] == 5
    assert [section["title"] for section in guide_payload["guide"]["sections"]] == [
        "Preflight",
        "Priority handling",
        "Format checks",
        "Sign-off",
    ]
    format_section = next(section for section in guide_payload["guide"]["sections"] if section["title"] == "Format checks")
    assert any(item.startswith("pdf (1):") for item in format_section["items"])

    assert {path: path.read_bytes() for path in before_sources} == before_sources
    assert {path: path.read_text(encoding="utf-8") for path in before_mirrors} == before_mirrors


def test_vaultwright_pilot_report_summarizes_evidence_without_content(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    source = vault / "40_delivery" / "client-plan.docx"
    mirror = vault / "_mirrors" / "40_delivery" / "client-plan.md"
    repo_note = vault / "80_sources" / "repos" / "fixture.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    mirror.parent.mkdir(parents=True, exist_ok=True)
    repo_note.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"confidential source bytes")
    mirror.write_text("Generated mirror text that should not appear\n", encoding="utf-8")
    repo_note.write_text("Generated repo mirror text that should not appear\n", encoding="utf-8")
    before_source = source.read_bytes()
    before_mirror = mirror.read_text(encoding="utf-8")
    before_repo_note = repo_note.read_text(encoding="utf-8")
    (vault / "_meta" / "source-manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "records": [
                    {
                        "source_id": "src-plan",
                        "current_source_path": "40_delivery/client-plan.docx",
                        "mirror_path": "_mirrors/40_delivery/client-plan.md",
                        "source_format": "docx",
                        "source_size": len(before_source),
                        "lifecycle_state": "clean",
                        "warnings": ["Conversion-quality risk: sample warning"],
                        "errors": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (vault / "_meta" / "repo-manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "records": [
                    {
                        "repo_id": "repo-fixture",
                        "configured_repo": "local/fixture",
                        "note_path": "80_sources/repos/fixture.md",
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
        json.dumps(
            {
                "timestamp": "2026-06-20T00:00:00Z",
                "tool": "sync_office_md",
                "status": "unchanged",
                "lifecycle_state": "clean",
                "source_id": "src-plan",
                "mirror_path": "_mirrors/40_delivery/client-plan.md",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (vault / "_meta" / "agent-readiness-tasks.yml").write_text(
        "schema_version: 1\n"
        "corpus: fixture\n"
        "comparison_modes: [raw_source_folder, document_chat_transcript, vaultwright_markdown]\n"
        "scoring:\n"
        "  scale: 0-2\n"
        "tasks:\n"
        "  - id: answer-1\n"
        "    family: answer\n"
        "    prompt: What is the plan?\n"
        "    source_paths: [40_delivery/client-plan.docx]\n"
        "    generated_mirror_paths: [_mirrors/40_delivery/client-plan.md]\n"
        "    curated_paths: []\n"
        "    success_criteria: [Cites the source]\n"
        "  - id: reconcile-1\n"
        "    family: reconcile\n"
        "    prompt: What differs?\n"
        "    source_paths: [40_delivery/client-plan.docx]\n"
        "    generated_mirror_paths: [_mirrors/40_delivery/client-plan.md]\n"
        "    curated_paths: []\n"
        "    success_criteria: [Names the conflict]\n"
        "  - id: update-1\n"
        "    family: update\n"
        "    prompt: What changed?\n"
        "    source_paths: [40_delivery/client-plan.docx]\n"
        "    generated_mirror_paths: [_mirrors/40_delivery/client-plan.md]\n"
        "    curated_paths: []\n"
        "    success_criteria: [Names refresh action]\n"
        "  - id: audit-1\n"
        "    family: audit\n"
        "    prompt: Is it traceable?\n"
        "    source_paths: [40_delivery/client-plan.docx]\n"
        "    generated_mirror_paths: [_mirrors/40_delivery/client-plan.md]\n"
        "    curated_paths: []\n"
        "    success_criteria: [Finds provenance]\n"
        "  - id: consolidate-1\n"
        "    family: consolidate\n"
        "    prompt: Where should it live?\n"
        "    source_paths: [40_delivery/client-plan.docx]\n"
        "    generated_mirror_paths: [_mirrors/40_delivery/client-plan.md]\n"
        "    curated_paths: []\n"
        "    success_criteria: [Avoids duplicate notes]\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "pilot"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    json_result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "pilot", "--json"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    worksheet_result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "pilot", "--worksheet"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "pilot: read-only evidence report; no source content was printed" in result.stdout
    assert "pilot: source manifest records=1 warnings=1 errors=0" in result.stdout
    assert "pilot: audit events=1" in result.stdout
    assert "pilot: conversion available=True high=0 medium=1 low=0" in result.stdout
    assert "pilot: recovery available=True items=0" in result.stdout
    assert "pilot: benchmark available=True tasks=5" in result.stdout
    assert "confidential source bytes" not in result.stdout
    assert "Generated mirror text" not in result.stdout
    assert "Generated repo mirror text" not in result.stdout
    assert str(vault) not in result.stdout

    assert json_result.returncode == 0, json_result.stderr or json_result.stdout
    report = json.loads(json_result.stdout)
    payload = json_result.stdout
    assert "confidential source bytes" not in payload
    assert "Generated mirror text" not in payload
    assert "Generated repo mirror text" not in payload
    assert str(vault) not in payload
    assert report["report"]["source_manifest"]["records"] == 1
    assert report["report"]["source_manifest"]["states"] == {"clean": 1}
    assert report["report"]["source_manifest"]["formats"] == {"docx": 1}
    assert report["report"]["repo_manifest"]["records"] == 1
    assert report["report"]["audit"]["events"] == 1
    assert report["report"]["conversion"]["summary"]["medium"] == 1
    assert report["report"]["recovery"]["summary"]["total"] == 0
    assert report["report"]["benchmark"]["summary"]["tasks"] == 5

    assert worksheet_result.returncode == 0, worksheet_result.stderr or worksheet_result.stdout
    assert "# Vaultwright Pilot Evidence Summary" in worksheet_result.stdout
    assert "Source manifest records: 1" in worksheet_result.stdout
    assert "Conversion review queue: available=True high=0 medium=1 low=0" in worksheet_result.stdout
    assert "Recovery queue: available=True items=0" in worksheet_result.stdout
    assert "Benchmark tasks: available=True tasks=5" in worksheet_result.stdout
    assert "Baseline time to answer fixed questions" in worksheet_result.stdout
    assert "confidential source bytes" not in worksheet_result.stdout
    assert "Generated mirror text" not in worksheet_result.stdout
    assert "Generated repo mirror text" not in worksheet_result.stdout
    assert "40_delivery/client-plan.docx" not in worksheet_result.stdout
    assert "_mirrors/40_delivery/client-plan.md" not in worksheet_result.stdout
    assert str(vault) not in worksheet_result.stdout

    assert source.read_bytes() == before_source
    assert mirror.read_text(encoding="utf-8") == before_mirror
    assert repo_note.read_text(encoding="utf-8") == before_repo_note


def test_vaultwright_conversion_report_handles_invalid_inputs(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)

    invalid_args = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "conversion", "--low-risk-per-format", "-1"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert invalid_args.returncode == 1
    assert "--low-risk-per-format must be >= 0" in invalid_args.stderr

    manifest = vault / "_meta" / "source-manifest.json"
    manifest.write_text(json.dumps({"records": {}}), encoding="utf-8")
    malformed = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "conversion"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    malformed_json = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "conversion", "--json"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert malformed.returncode == 1
    assert "_meta/source-manifest.json: records must be a list" in malformed.stderr
    assert malformed_json.returncode == 1
    report = json.loads(malformed_json.stdout)
    assert report["items"] == []
    assert report["summary"]["total"] == 0
    assert report["errors"] == ["_meta/source-manifest.json: records must be a list"]

    manifest.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "source_id": "src-unsafe",
                        "current_source_path": "/tmp/outside.docx",
                        "mirror_path": "../outside.md",
                        "source_format": "docx",
                        "source_size": 10,
                        "lifecycle_state": "clean",
                        "warnings": [],
                        "errors": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    unsafe = subprocess.run(
        [
            sys.executable,
            str(vault / "tools" / "vaultwright.py"),
            "conversion",
            "--low-risk-per-format",
            "0",
        ],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    unsafe_json = subprocess.run(
        [
            sys.executable,
            str(vault / "tools" / "vaultwright.py"),
            "conversion",
            "--json",
            "--low-risk-per-format",
            "0",
        ],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert unsafe.returncode == 0, unsafe.stderr or unsafe.stdout
    assert "conversion: 1 manifest records (high=1, medium=0, low=0)" in unsafe.stdout
    assert "source path is unsafe: /tmp/outside.docx" in unsafe.stdout
    assert "mirror path is unsafe: ../outside.md" in unsafe.stdout
    report = json.loads(unsafe_json.stdout)
    assert report["summary"]["high"] == 1
    assert report["items"][0]["priority"] == "high"
    assert "source path is unsafe: /tmp/outside.docx" in report["items"][0]["reasons"]
    assert "mirror path is unsafe: ../outside.md" in report["items"][0]["reasons"]


def test_vaultwright_migration_reports_legacy_and_unknown_folders(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    marketing = vault / "marketing"
    custom = vault / "client_uploads"
    underscored = vault / "_client_uploads"
    hidden = vault / ".imports"
    marketing.mkdir()
    custom.mkdir()
    underscored.mkdir()
    hidden.mkdir()
    (marketing / "campaign.md").write_text("# Campaign\n", encoding="utf-8")
    (custom / "brief.docx").write_bytes(b"office bytes")
    (underscored / "legacy.md").write_text("# Legacy\n", encoding="utf-8")
    (hidden / "import.pdf").write_bytes(b"pdf bytes")

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "migration"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    json_result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "migration", "--json"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "migration: dry-run only; no files were moved" in result.stdout
    assert "warning: .imports: non-reserved hidden/underscore folder reported for review" in result.stdout
    assert "warning: _client_uploads: non-reserved hidden/underscore folder reported for review" in result.stdout
    assert "migration: 4 top-level folders need review (alias=1, unknown=3)" in result.stdout
    assert "[alias_folder  ] marketing -> 20_market" in result.stdout
    assert "domain: market" in result.stdout
    assert "[unknown_folder] .imports -> manual classification" in result.stdout
    assert "[unknown_folder] _client_uploads -> manual classification" in result.stdout
    assert "[unknown_folder] client_uploads -> manual classification" in result.stdout
    assert "[unknown_folder] _meta -> manual classification" not in result.stdout
    assert marketing.exists()
    assert custom.exists()
    assert underscored.exists()
    assert hidden.exists()
    assert (marketing / "campaign.md").exists()
    assert (custom / "brief.docx").exists()
    assert (underscored / "legacy.md").exists()
    assert (hidden / "import.pdf").exists()

    assert json_result.returncode == 0, json_result.stderr or json_result.stdout
    report = json.loads(json_result.stdout)
    assert report["warnings"] == [
        ".imports: non-reserved hidden/underscore folder reported for review",
        "_client_uploads: non-reserved hidden/underscore folder reported for review",
    ]
    assert report["summary"] == {"alias": 1, "total": 4, "unknown": 3}
    by_folder = {item["folder"]: item for item in report["items"]}
    assert by_folder["marketing"]["recommended_folder"] == "20_market"
    assert by_folder["marketing"]["domain"] == "market"
    assert by_folder["marketing"]["counts"]["markdown"] == 1
    assert by_folder[".imports"]["kind"] == "unknown_folder"
    assert by_folder[".imports"]["counts"]["office"] == 1
    assert by_folder["_client_uploads"]["kind"] == "unknown_folder"
    assert by_folder["_client_uploads"]["counts"]["markdown"] == 1
    assert by_folder["client_uploads"]["kind"] == "unknown_folder"
    assert by_folder["client_uploads"]["counts"]["office"] == 1
    assert "_meta" not in by_folder


def test_vaultwright_recovery_reports_manifest_actions(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    source = vault / "40_delivery" / "registration.docx"
    moved_source = vault / "50_operations" / "registration.docx"
    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    note = vault / "80_sources" / "repos" / "fixture.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    moved_source.parent.mkdir(parents=True, exist_ok=True)
    mirror.parent.mkdir(parents=True, exist_ok=True)
    note.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"office bytes")
    moved_source.write_bytes(b"moved office bytes")
    mirror.write_text("Generated mirror\n", encoding="utf-8")
    note.write_text("Generated repo mirror\n", encoding="utf-8")
    (vault / "_meta" / "source-manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "records": [
                    {
                        "source_id": "src-clean",
                        "current_source_path": "40_delivery/registration.docx",
                        "mirror_path": "_mirrors/40_delivery/registration.md",
                        "lifecycle_state": "clean",
                    },
                    {
                        "source_id": "src-missing",
                        "current_source_path": "40_delivery/missing.docx",
                        "mirror_path": "_mirrors/40_delivery/missing.md",
                        "lifecycle_state": "source_missing",
                    },
                    {
                        "source_id": "src-manual",
                        "current_source_path": "40_delivery/registration.docx",
                        "mirror_path": "_mirrors/40_delivery/registration.md",
                        "lifecycle_state": "manual_modification",
                        "warnings": ["Generated region hash changed."],
                    },
                    {
                        "source_id": "src-moved",
                        "current_source_path": "50_operations/registration.docx",
                        "previous_source_paths": ["40_delivery/registration.docx"],
                        "mirror_path": "_mirrors/50_operations/registration.md",
                        "previous_mirror_path": "_mirrors/40_delivery/registration.md",
                        "previous_mirror_reason": "source_moved",
                        "lifecycle_state": "source_moved",
                    },
                    {
                        "source_id": "src-root-conflict",
                        "current_source_path": "40_delivery/registration.docx",
                        "mirror_path": "_generated/40_delivery/registration.md",
                        "previous_mirror_path": "_mirrors/40_delivery/registration.md",
                        "previous_mirror_reason": "mirror_location_changed",
                        "lifecycle_state": "conflict",
                        "errors": ["Configured mirror location changed while the previous generated mirror still exists."],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (vault / "_meta" / "repo-manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "records": [
                    {
                        "repo_id": "repo-conflict",
                        "configured_repo": "local/fixture",
                        "note_path": "80_sources/repos/fixture.md",
                        "lifecycle_state": "conflict",
                        "errors": ["Target note belongs to another repo_id."],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    audit_events = [
        {
            "timestamp": "2026-06-20T00:00:00Z",
            "tool": "sync_office_md",
            "source_id": "src-manual",
            "mirror_path": "_mirrors/40_delivery/registration.md",
            "status": "updated",
            "lifecycle_state": "clean",
            "warnings": [],
            "errors": [],
        },
        {
            "timestamp": "2026-06-20T00:01:00Z",
            "tool": "sync_office_md",
            "source_id": "src-manual",
            "mirror_path": "_mirrors/40_delivery/registration.md",
            "status": "skipped:manual_modification",
            "lifecycle_state": "manual_modification",
            "warnings": ["Generated region hash changed."],
            "errors": [],
        },
        {
            "timestamp": "2026-06-20T00:02:00Z",
            "tool": "sync_github_repos",
            "repo_id": "repo-conflict",
            "note_path": "80_sources/repos/fixture.md",
            "status": "skipped:conflict",
            "lifecycle_state": "conflict",
            "warnings": [],
            "errors": ["Target note belongs to another repo_id."],
        },
    ]
    (vault / "_meta" / "sync-audit.jsonl").write_text(
        "\n".join(json.dumps(event) for event in audit_events) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "recovery"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "recovery: 5 items need operator action (office=4, repo=1, temp=0)" in result.stdout
    assert "[office:source_missing" in result.stdout
    assert "Locate, restore, or intentionally archive the source" in result.stdout
    assert "[office:manual_modification" in result.stdout
    assert "Preserve human edits below the sentinel" in result.stdout
    assert "[office:source_moved" in result.stdout
    assert "preserve/archive any old mirror" in result.stdout
    assert "previous target: _mirrors/40_delivery/registration.md (exists reason=source_moved)" in result.stdout
    assert "previous target: _mirrors/40_delivery/registration.md (exists reason=mirror_location_changed)" in result.stdout
    assert "[repo:conflict" in result.stdout
    assert "Resolve the target note/repo identity conflict" in result.stdout
    assert "latest audit: 2026-06-20T00:01:00Z status=skipped:manual_modification" in result.stdout
    assert "audit warning: Generated region hash changed." in result.stdout
    assert "latest audit: 2026-06-20T00:02:00Z status=skipped:conflict" in result.stdout
    assert "audit error: Target note belongs to another repo_id." in result.stdout

    json_result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "recovery", "--json"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert json_result.returncode == 0, json_result.stderr or json_result.stdout
    report = json.loads(json_result.stdout)
    assert report["summary"] == {"office": 4, "repo": 1, "temp": 0, "total": 5}
    by_id = {item["id"]: item for item in report["items"]}
    assert by_id["src-moved"]["previous_target"] == "_mirrors/40_delivery/registration.md"
    assert by_id["src-moved"]["previous_target_exists"] is True
    assert by_id["src-moved"]["previous_target_reason"] == "source_moved"
    assert by_id["src-root-conflict"]["previous_target"] == "_mirrors/40_delivery/registration.md"
    assert by_id["src-root-conflict"]["previous_target_exists"] is True
    assert by_id["src-root-conflict"]["previous_target_reason"] == "mirror_location_changed"
    assert by_id["src-manual"]["latest_audit"]["timestamp"] == "2026-06-20T00:01:00Z"
    assert by_id["src-manual"]["latest_audit"]["status"] == "skipped:manual_modification"
    assert by_id["repo-conflict"]["latest_audit"]["errors"] == ["Target note belongs to another repo_id."]


def test_vaultwright_recovery_reports_stale_atomic_temp_files(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "template", vault)
    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    temp = mirror.with_name(f".{mirror.name}.12345.tmp")
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_text("Complete generated mirror\n", encoding="utf-8")
    temp.write_text("Interrupted write body\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "recovery"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "recovery: 1 item needs operator action (office=0, repo=0, temp=1)" in result.stdout
    assert "[temp:interrupted_write" in result.stdout
    assert "_mirrors/40_delivery/.registration.md.12345.tmp" in result.stdout
    assert "Rerun status/sync to confirm the canonical generated file is complete" in result.stdout

    json_result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "recovery", "--json"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert json_result.returncode == 0, json_result.stderr or json_result.stdout
    report = json.loads(json_result.stdout)
    assert report["summary"] == {"office": 0, "repo": 0, "temp": 1, "total": 1}
    assert len(report["items"]) == 1
    item = report["items"][0]
    assert item["kind"] == "temp"
    assert item["state"] == "interrupted_write"
    assert item["target"] == "_mirrors/40_delivery/.registration.md.12345.tmp"
    assert item["expected_target"] == "_mirrors/40_delivery/registration.md"
    assert item["expected_target_exists"] is True


def test_github_sync_skips_missing_default_config(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    tools = vault / "tools"
    tools.mkdir(parents=True)
    shutil.copy(ROOT / "template/tools/sync_github_repos.py", tools / "sync_github_repos.py")

    result = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py"), "--quiet"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "no repos.yml found" in result.stdout


def test_github_sync_empty_repo_config_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    tools = vault / "tools"
    tools.mkdir(parents=True)
    shutil.copy(ROOT / "template/tools/sync_github_repos.py", tools / "sync_github_repos.py")
    (tools / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos: []\n",
        encoding="utf-8",
    )

    first = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py"), "--quiet"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    second = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py"), "--quiet"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert first.returncode == 0, first.stderr or first.stdout
    assert second.returncode == 0, second.stderr or second.stdout
    assert "0 created, 0 updated, 0 unchanged, 0 stub, 0 skipped, 0 error" in first.stdout
    assert "0 created, 0 updated, 0 unchanged, 0 stub, 0 skipped, 0 error" in second.stdout
    assert "[manifest updated]" not in first.stdout
    assert "[manifest updated]" not in second.stdout
    assert not (vault / "_meta" / "repo-manifest.json").exists()
    assert not (vault / "_meta" / "sync-audit.jsonl").exists()
    assert not (vault / "80_sources" / "repos").exists()


def test_github_sync_fails_explicit_missing_config(tmp_path: Path) -> None:
    script = ROOT / "template/tools/sync_github_repos.py"
    missing = tmp_path / "missing.yml"

    result = subprocess.run(
        [sys.executable, str(script), "--config", str(missing), "--quiet"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "config not found" in result.stderr


def test_github_sync_fails_malformed_config_without_traceback(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    tools = vault / "tools"
    tools.mkdir(parents=True)
    shutil.copy(ROOT / "template/tools/sync_github_repos.py", tools / "sync_github_repos.py")
    (tools / "repos.yml").write_text(
        "settings: []\n"
        "repos:\n"
        "  - note: missing-repo.md\n"
        "  - not-a-mapping\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "invalid config" in result.stderr
    assert "repos[0].repo is required" in result.stderr
    assert "repos[1] must be a mapping" in result.stderr
    assert "Traceback" not in result.stderr


def test_github_sync_plan_is_non_mutating_for_local_repo(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    tools = vault / "tools"
    fixture = vault / "_fixtures" / "repo"
    tools.mkdir(parents=True)
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text("# Fixture\n", encoding="utf-8")
    shutil.copy(ROOT / "template/tools/sync_github_repos.py", tools / "sync_github_repos.py")
    (tools / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos:\n"
        "  - repo: local/fixture\n"
        "    local_path: _fixtures/repo\n"
        "    note: fixture.md\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py"), "--plan", "--quiet"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "1 create" in result.stdout
    assert not (vault / "80_sources" / "repos" / "fixture.md").exists()
    assert not (vault / "_meta" / "repo-manifest.json").exists()
    assert not (vault / "_meta" / "sync-audit.jsonl").exists()


def test_github_sync_writes_manifest_audit_and_status_for_local_repo(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    tools = vault / "tools"
    fixture = vault / "_fixtures" / "repo"
    tools.mkdir(parents=True)
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text("# Fixture\n", encoding="utf-8")
    shutil.copy(ROOT / "template/tools/sync_github_repos.py", tools / "sync_github_repos.py")
    (tools / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos:\n"
        "  - repo: local/fixture\n"
        "    local_path: _fixtures/repo\n"
        "    note: fixture.md\n",
        encoding="utf-8",
    )

    sync_result = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py"), "--quiet"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    status_result = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py"), "--status", "--quiet"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert sync_result.returncode == 0, sync_result.stderr or sync_result.stdout
    assert status_result.returncode == 0, status_result.stderr or status_result.stdout
    assert (vault / "80_sources" / "repos" / "fixture.md").exists()
    manifest = (vault / "_meta" / "repo-manifest.json").read_text(encoding="utf-8")
    assert '"repo_id": "repo_' in manifest
    assert '"lifecycle_state": "clean"' in manifest
    audit = (vault / "_meta" / "sync-audit.jsonl").read_text(encoding="utf-8")
    assert '"tool": "sync_github_repos"' in audit
    assert "clean=1" in status_result.stdout


def test_github_sync_populates_stub_and_preserves_curation(tmp_path: Path, monkeypatch) -> None:
    sync = load_sync_module()
    vault = tmp_path / "vault"
    monkeypatch.setattr(sync, "ROOT", vault)
    monkeypatch.setattr(sync, "resolve_slug", lambda _entry, _token: (None, None))
    entry = {
        "repo": "example/private-service",
        "note": "private-service.md",
        "tags": ["private"],
        "related": ["[[Source Access]]"],
        "account": "[[Acme Manufacturing]]",
    }
    settings = {"notes_dir": "80_sources/repos"}
    manifest = sync.empty_repo_manifest()

    stub_plan = sync.plan_one(entry, settings, None, manifest)
    stub_status = sync.sync_one(entry, settings, None, False, False)
    sync.update_manifest_after_sync(manifest, stub_plan, stub_status)
    sync.write_repo_manifest(manifest, vault)
    note = vault / "80_sources" / "repos" / "private-service.md"
    stub_text = note.read_text(encoding="utf-8")
    stub_fm, _stub_body = sync.split_fm(stub_text)
    stub_record = sync.load_repo_manifest(vault)["records"][0]

    assert stub_plan["action"] == "create"
    assert stub_status == "stub"
    assert stub_record["lifecycle_state"] == "unreachable"
    assert "Not yet synced" in stub_text
    assert stub_fm["status"] == "draft"
    assert stub_fm["tags"] == ["private"]
    assert stub_fm["related"] == ["[[Source Access]]"]
    assert stub_fm["account"] == "[[Acme Manufacturing]]"
    assert stub_fm["client"] == "[[Acme Manufacturing]]"

    curated_stub = stub_text.replace("## Notes\n\n", "## Notes\n\nCurated triage note.\n\n", 1)
    note.write_text(curated_stub, encoding="utf-8")
    fixture = vault / "_fixtures" / "private-service"
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text("# Private Service\n\nOperational runbook.\n", encoding="utf-8")
    reachable_entry = {**entry, "local_path": "_fixtures/private-service"}
    loaded = sync.load_repo_manifest(vault)

    populate_plan = sync.plan_one(reachable_entry, settings, None, loaded)
    populate_status = sync.sync_one(
        reachable_entry,
        settings,
        None,
        False,
        False,
        trusted_existing_baseline=True,
    )
    sync.update_manifest_after_sync(loaded, populate_plan, populate_status)
    sync.write_repo_manifest(loaded, vault)
    populated_text = note.read_text(encoding="utf-8")
    populated_fm, _populated_body = sync.split_fm(populated_text)
    populated_record = sync.load_repo_manifest(vault)["records"][0]

    assert populate_plan["action"] == "update"
    assert populate_status == "updated"
    assert populated_record["lifecycle_state"] == "clean"
    assert populated_record["errors"] == []
    assert populated_record["last_commit"] == sync.local_tree_sha(fixture)
    assert populated_fm["status"] == "active"
    assert populated_fm["tags"] == ["private"]
    assert populated_fm["related"] == ["[[Source Access]]"]
    assert populated_fm["account"] == "[[Acme Manufacturing]]"
    assert "Curated triage note." in populated_text
    assert "Not yet synced" not in populated_text
    assert "## `README.md`" in populated_text
    assert "Operational runbook." in populated_text


def test_github_sync_preserves_note_and_recovers_after_write_failure(tmp_path: Path, monkeypatch) -> None:
    sync = load_sync_module()
    vault = tmp_path / "vault"
    monkeypatch.setattr(sync, "ROOT", vault)
    fixture = vault / "_fixtures" / "repo"
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text("# Fixture v1\n", encoding="utf-8")
    entry = {
        "repo": "local/fixture",
        "local_path": "_fixtures/repo",
        "note": "fixture.md",
    }
    settings = {"notes_dir": "80_sources/repos"}
    manifest = sync.empty_repo_manifest()

    first_plan = sync.plan_one(entry, settings, None, manifest)
    first_status = sync.sync_one(entry, settings, None, False, False, trusted_existing_baseline=True)
    sync.update_manifest_after_sync(manifest, first_plan, first_status)
    sync.write_repo_manifest(manifest, vault)
    note = vault / "80_sources" / "repos" / "fixture.md"
    first_note = note.read_text(encoding="utf-8")
    first_record = sync.load_repo_manifest(vault)["records"][0]
    original_write_text_atomic = sync.write_text_atomic

    def failing_write(_path: Path, _content: str) -> None:
        raise OSError("disk full")

    (fixture / "README.md").write_text("# Fixture v2\n", encoding="utf-8")
    loaded = sync.load_repo_manifest(vault)
    failed_plan = sync.plan_one(entry, settings, None, loaded)
    monkeypatch.setattr(sync, "write_text_atomic", failing_write)
    failed_status = sync.sync_one(entry, settings, None, False, False, trusted_existing_baseline=True)
    monkeypatch.setattr(sync, "write_text_atomic", original_write_text_atomic)
    sync.update_manifest_after_sync(loaded, failed_plan, failed_status)
    sync.write_repo_manifest(loaded, vault)
    failed_record = sync.load_repo_manifest(vault)["records"][0]

    assert failed_status == "error:repo-write:OSError: disk full"
    assert note.read_text(encoding="utf-8") == first_note
    assert failed_record["lifecycle_state"] == "error"
    assert failed_record["last_successful_sync"] == first_record["last_successful_sync"]
    assert failed_record["generated_region_sha256"] == first_record["generated_region_sha256"]
    assert any("error:repo-write:OSError: disk full" in error for error in failed_record["errors"])
    sync.append_audit(sync.sync_audit_event(failed_plan, loaded, failed_status, entry), vault)
    failed_event = json.loads((vault / "_meta" / "sync-audit.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert failed_event["status"] == failed_status
    assert failed_event["lifecycle_state"] == "error"
    assert failed_event["note_path"] == "80_sources/repos/fixture.md"
    assert any("error:repo-write:OSError: disk full" in error for error in failed_event["errors"])

    recoverable = sync.load_repo_manifest(vault)
    recovery_plan = sync.plan_one(entry, settings, None, recoverable)
    recovered_status = sync.sync_one(entry, settings, None, False, False, trusted_existing_baseline=True)
    sync.update_manifest_after_sync(recoverable, recovery_plan, recovered_status)
    sync.write_repo_manifest(recoverable, vault)
    recovered_record = sync.load_repo_manifest(vault)["records"][0]

    assert recovery_plan["action"] == "update"
    assert recovered_status == "updated"
    assert recovered_record["lifecycle_state"] == "clean"
    assert recovered_record["errors"] == []
    assert recovered_record["last_commit"] == sync.local_tree_sha(fixture)
    assert note.read_text(encoding="utf-8") != first_note


def test_github_sync_reports_manual_generated_region_modification(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    tools = vault / "tools"
    fixture = vault / "_fixtures" / "repo"
    tools.mkdir(parents=True)
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text("# Fixture\n", encoding="utf-8")
    shutil.copy(ROOT / "template/tools/sync_github_repos.py", tools / "sync_github_repos.py")
    (tools / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos:\n"
        "  - repo: local/fixture\n"
        "    local_path: _fixtures/repo\n"
        "    note: fixture.md\n",
        encoding="utf-8",
    )
    first = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py"), "--quiet"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    assert first.returncode == 0, first.stderr or first.stdout

    note = vault / "80_sources" / "repos" / "fixture.md"
    note.write_text(
        note.read_text(encoding="utf-8").replace("# Fixture", "Manual edit below sentinel"),
        encoding="utf-8",
    )
    second = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert second.returncode == 0, second.stderr or second.stdout
    assert "skipped:manual_modification" in second.stdout
    third = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py"), "--status"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    assert third.returncode == 0, third.stderr or third.stdout
    assert "review:manual_modification" in third.stdout
    assert "next actions:" in third.stdout
    assert "manual_modification (1): inspect the repo mirror below the generated sentinel" in third.stdout
    assert "Manual edit below sentinel" in note.read_text(encoding="utf-8")


def test_github_sync_refuses_to_take_over_hand_authored_note(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    tools = vault / "tools"
    fixture = vault / "_fixtures" / "repo"
    note = vault / "80_sources" / "repos" / "fixture.md"
    tools.mkdir(parents=True)
    fixture.mkdir(parents=True)
    note.parent.mkdir(parents=True)
    (fixture / "README.md").write_text("# Fixture\n", encoding="utf-8")
    note.write_text(
        "---\n"
        "title: Hand Authored Fixture\n"
        "type: guide\n"
        "---\n"
        "# Do not overwrite\n",
        encoding="utf-8",
    )
    shutil.copy(ROOT / "template/tools/sync_github_repos.py", tools / "sync_github_repos.py")
    (tools / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos:\n"
        "  - repo: local/fixture\n"
        "    local_path: _fixtures/repo\n"
        "    note: fixture.md\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py")],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "skipped:conflict" in result.stdout
    assert "# Do not overwrite" in note.read_text(encoding="utf-8")
    manifest = (vault / "_meta" / "repo-manifest.json").read_text(encoding="utf-8")
    assert '"lifecycle_state": "conflict"' in manifest


def test_github_sync_force_refuses_altered_generated_sentinel(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    tools = vault / "tools"
    fixture = vault / "_fixtures" / "repo"
    tools.mkdir(parents=True)
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text("# Fixture\n", encoding="utf-8")
    shutil.copy(ROOT / "template/tools/sync_github_repos.py", tools / "sync_github_repos.py")
    (tools / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos:\n"
        "  - repo: local/fixture\n"
        "    local_path: _fixtures/repo\n"
        "    note: fixture.md\n",
        encoding="utf-8",
    )
    first = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py"), "--quiet"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    assert first.returncode == 0, first.stderr or first.stdout

    note = vault / "80_sources" / "repos" / "fixture.md"
    corrupted_text = note.read_text(encoding="utf-8").replace(
        "%% AUTO-GENERATED BELOW — DO NOT EDIT %%",
        "ALTERED %% AUTO-GENERATED BELOW — DO NOT EDIT %%",
    )
    note.write_text(corrupted_text, encoding="utf-8")
    second = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py"), "--force"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert second.returncode == 0, second.stderr or second.stdout
    assert "skipped:conflict" in second.stdout
    assert note.read_text(encoding="utf-8") == corrupted_text


def test_github_sync_force_refuses_existing_note_without_manifest_baseline(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    tools = vault / "tools"
    fixture = vault / "_fixtures" / "repo"
    tools.mkdir(parents=True)
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text("# Fixture\n", encoding="utf-8")
    shutil.copy(ROOT / "template/tools/sync_github_repos.py", tools / "sync_github_repos.py")
    (tools / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos:\n"
        "  - repo: local/fixture\n"
        "    local_path: _fixtures/repo\n"
        "    note: fixture.md\n",
        encoding="utf-8",
    )
    first = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py"), "--quiet"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    assert first.returncode == 0, first.stderr or first.stdout
    (vault / "_meta" / "repo-manifest.json").unlink()
    note = vault / "80_sources" / "repos" / "fixture.md"
    before = note.read_text(encoding="utf-8")

    status = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py"), "--status"],
        cwd=vault,
        text=True,
        capture_output=True,
    )
    forced = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py"), "--force"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert status.returncode == 0, status.stderr or status.stdout
    assert "review:manual_modification" in status.stdout
    assert forced.returncode == 0, forced.stderr or forced.stdout
    assert "skipped:manual_modification" in forced.stdout
    assert note.read_text(encoding="utf-8") == before


def test_github_sync_reviews_unreachable_existing_note_without_manifest_baseline(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sync = load_sync_module()
    vault = tmp_path / "vault"
    monkeypatch.setattr(sync, "ROOT", vault)
    monkeypatch.setattr(sync, "resolve_slug", lambda _entry, _token: (None, None))
    repo = "example/private-service"
    note_name = "private-service.md"
    repo_id = sync.repo_id_for(repo, note_name)
    note = vault / "80_sources" / "repos" / note_name
    note.parent.mkdir(parents=True)
    before = (
        "---\n"
        "title: Existing Private Service\n"
        "type: repo-mirror\n"
        f"repo_id: {repo_id}\n"
        "repo_manifest: _meta/repo-manifest.json\n"
        f"repo: {repo}\n"
        "---\n"
        "## Notes\n\n"
        f"{sync.SENTINEL}\n\n"
        "## Previous generated body\n\n"
        "Existing mirror content that must not be replaced with a stub.\n"
    )
    note.write_text(before, encoding="utf-8")
    entry = {"repo": repo, "note": note_name}
    settings = {"notes_dir": "80_sources/repos"}

    plan = sync.plan_one(entry, settings, None, sync.empty_repo_manifest())
    forced_status = sync.sync_one(entry, settings, None, True, False)

    assert plan["action"] == "review"
    assert plan["record"]["lifecycle_state"] == "manual_modification"
    assert any("no manifest-generated baseline" in warning for warning in plan["record"]["warnings"])
    assert forced_status == "skipped:manual_modification"
    assert note.read_text(encoding="utf-8") == before


def test_github_sync_reviews_generated_edit_even_when_repo_unreachable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sync = load_sync_module()
    vault = tmp_path / "vault"
    monkeypatch.setattr(sync, "ROOT", vault)
    monkeypatch.setattr(sync, "resolve_slug", lambda _entry, _token: (None, None))
    repo = "example/private-service"
    note_name = "private-service.md"
    repo_id = sync.repo_id_for(repo, note_name)
    note = vault / "80_sources" / "repos" / note_name
    note.parent.mkdir(parents=True)
    baseline = (
        "---\n"
        "title: Existing Private Service\n"
        "type: repo-mirror\n"
        f"repo_id: {repo_id}\n"
        "repo_manifest: _meta/repo-manifest.json\n"
        f"repo: {repo}\n"
        "last_commit: abc123\n"
        "---\n"
        "## Notes\n\n"
        f"{sync.SENTINEL}\n\n"
        "## Previous generated body\n\n"
        "Baseline generated content.\n"
    )
    note.write_text(baseline, encoding="utf-8")
    baseline_hash = sync.generated_region_hash(baseline)
    assert baseline_hash
    note.write_text(
        baseline.replace("Baseline generated content.", "Manual edit below sentinel."),
        encoding="utf-8",
    )
    manifest = sync.empty_repo_manifest()
    manifest["records"] = [{
        "repo_id": repo_id,
        "last_commit": "abc123",
        "generated_region_sha256": baseline_hash,
        "config_version": sync.CONFIG_VERSION,
    }]
    entry = {"repo": repo, "note": note_name}
    settings = {"notes_dir": "80_sources/repos"}

    plan = sync.plan_one(entry, settings, None, manifest)

    assert plan["action"] == "review"
    assert plan["record"]["lifecycle_state"] == "manual_modification"
    assert any("Generated region changed" in warning for warning in plan["record"]["warnings"])


def test_sync_all_propagates_required_sync_failure(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    tools = vault / "tools"
    fakebin = tmp_path / "fakebin"
    tools.mkdir(parents=True)
    fakebin.mkdir()
    shutil.copy(ROOT / "template/tools/sync_all.sh", tools / "sync_all.sh")

    fake_python = fakebin / "python3.11"
    fake_python.write_text(
        "#!/usr/bin/env sh\n"
        "if [ \"$1\" = \"-\" ]; then cat >/dev/null; exit 0; fi\n"
        "case \"$1\" in\n"
        "  *sync_office_md.py) exit 7 ;;\n"
        "  *) exit 0 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)
    shutil.copy(fake_python, fakebin / "python3")

    env = {**os.environ, "PATH": f"{fakebin}{os.pathsep}{os.environ['PATH']}"}
    result = subprocess.run(
        ["bash", str(tools / "sync_all.sh")],
        cwd=vault,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 7


def test_office_sync_defaults_to_dedicated_mirror_root(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "30_customers" / "acme" / "brief.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"fixture")
    config = sync.load_mirror_config(vault)

    mirror, collision = sync.mirror_path_for(source, vault, config)

    assert mirror == vault / "_mirrors" / "30_customers" / "acme" / "brief.md"
    assert collision is False


def test_office_sync_routes_domain_aliases_to_canonical_mirror_folder(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    (vault / "_meta").mkdir(parents=True)
    shutil.copy(ROOT / "template/_meta/domain-map.yml", vault / "_meta" / "domain-map.yml")
    source = vault / "clients" / "acme" / "brief.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"fixture")
    config = sync.load_mirror_config(vault)
    routing = sync.load_domain_routing(vault)

    mirror, collision = sync.mirror_path_for(source, vault, config, routing)
    fm = sync.managed_frontmatter({}, source, vault, "abc123", routing)

    assert mirror == vault / "_mirrors" / "30_customers" / "acme" / "brief.md"
    assert collision is False
    assert fm["domain"] == "customers"
    assert fm["source"] == "clients/acme/brief.docx"


def test_office_sync_alias_to_canonical_mirror_is_idempotent(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    (vault / "_meta").mkdir(parents=True)
    shutil.copy(ROOT / "template/_meta/domain-map.yml", vault / "_meta" / "domain-map.yml")
    source = vault / "clients" / "acme" / "brief.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"fixture")
    config = sync.load_mirror_config(vault)
    routing = sync.load_domain_routing(vault)
    manifest = sync.empty_manifest()

    first_status = sync.sync_one(
        source, vault, FakeConverter(), False, False, config, routing, manifest, "markitdown", "test"
    )
    assert sync.write_source_manifest(vault, manifest) is True
    mirror = vault / "_mirrors" / "30_customers" / "acme" / "brief.md"
    manifest_path = vault / "_meta" / "source-manifest.json"
    first_mirror = mirror.read_text(encoding="utf-8")
    first_manifest = manifest_path.read_text(encoding="utf-8")

    loaded = sync.load_source_manifest(vault)
    second_status = sync.sync_one(
        source, vault, FakeConverter(), False, False, config, routing, loaded, "markitdown", "test"
    )
    wrote = sync.write_source_manifest(vault, loaded)

    assert first_status == "created"
    assert second_status == "unchanged"
    assert wrote is False
    assert mirror.read_text(encoding="utf-8") == first_mirror
    assert manifest_path.read_text(encoding="utf-8") == first_manifest
    assert not (vault / "_mirrors" / "clients" / "acme" / "brief.md").exists()


def test_office_sync_supports_legacy_sibling_mode(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    (vault / "_meta").mkdir(parents=True)
    (vault / "_meta" / "mirror-config.yml").write_text(
        "office_mirrors:\n"
        "  mode: sibling\n"
        "  root: _mirrors\n",
        encoding="utf-8",
    )
    source = vault / "30_customers" / "brief.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"fixture")
    config = sync.load_mirror_config(vault)

    mirror, collision = sync.mirror_path_for(source, vault, config)

    assert mirror == vault / "30_customers" / "brief.md"
    assert collision is False


def test_office_sync_frontmatter_uses_source_relative_path(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "2026-q1_readiness.pptx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"fixture")

    fm = sync.managed_frontmatter({}, source, vault, "abc123")

    assert fm["domain"] == "delivery"
    assert fm["source"] == "40_delivery/2026-q1_readiness.pptx"


def test_office_sync_rejects_escaping_mirror_root(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    (vault / "_meta").mkdir(parents=True)
    (vault / "_meta" / "mirror-config.yml").write_text(
        "office_mirrors:\n"
        "  mode: dedicated\n"
        "  root: ../outside\n",
        encoding="utf-8",
    )

    try:
        sync.load_mirror_config(vault)
    except ValueError as exc:
        assert "inside the vault" in str(exc)
    else:
        raise AssertionError("escaping mirror root was accepted")


def test_office_sync_discover_skips_office_lock_files(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "30_customers" / "brief.docx"
    lock = vault / "30_customers" / "~$brief.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"fixture")
    lock.write_bytes(b"temporary office lock")
    config = sync.load_mirror_config(vault)

    discovered = sync.discover(vault, sync.DEFAULT_EXTS, config)

    assert source in discovered
    assert lock not in discovered


def test_office_sync_lock_file_skip_is_idempotent(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "30_customers" / "brief.docx"
    lock = vault / "30_customers" / "~$brief.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"fixture")
    lock.write_bytes(b"temporary office lock")
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()

    assert sync.discover(vault, sync.DEFAULT_EXTS, config) == [source]
    first_status = sync.sync_one(
        source, vault, FakeConverter(), False, False, config, {}, manifest, "markitdown", "test"
    )
    assert sync.write_source_manifest(vault, manifest) is True
    mirror = vault / "_mirrors" / "30_customers" / "brief.md"
    manifest_path = vault / "_meta" / "source-manifest.json"
    first_mirror = mirror.read_text(encoding="utf-8")
    first_manifest = manifest_path.read_text(encoding="utf-8")

    loaded = sync.load_source_manifest(vault)
    assert sync.discover(vault, sync.DEFAULT_EXTS, config) == [source]
    second_status = sync.sync_one(
        source, vault, FakeConverter(), False, False, config, {}, loaded, "markitdown", "test"
    )
    wrote = sync.write_source_manifest(vault, loaded)

    assert first_status == "created"
    assert second_status == "unchanged"
    assert wrote is False
    assert mirror.read_text(encoding="utf-8") == first_mirror
    assert manifest_path.read_text(encoding="utf-8") == first_manifest
    assert lock.read_bytes() == b"temporary office lock"
    assert not (vault / "_mirrors" / "30_customers" / "~$brief.md").exists()


def test_office_sync_rejects_symlinked_source_files(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    outside = tmp_path / "outside.docx"
    source = vault / "40_delivery" / "linked.docx"
    source.parent.mkdir(parents=True)
    outside.write_bytes(b"external private bytes")
    source.symlink_to(outside)
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()

    discovered = sync.discover(vault, sync.DEFAULT_EXTS, config)
    plan = sync.plan_one(source, vault, config, {}, manifest, "markitdown", "test")
    status = sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, manifest, "markitdown", "test")

    assert source not in discovered
    assert plan["action"] == "error"
    assert plan["record"]["lifecycle_state"] == "error"
    assert any("symlink" in error for error in plan["record"]["errors"])
    assert status == "error:plan"
    assert not (vault / "_mirrors" / "40_delivery" / "linked.md").exists()


def test_office_sync_plan_is_non_mutating(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"office bytes")
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()

    plan = sync.plan_one(source, vault, config, {}, manifest, "markitdown", "test")

    assert plan["action"] == "create"
    assert plan["record"]["lifecycle_state"] == "planned"
    assert not (vault / "_mirrors" / "40_delivery" / "registration.md").exists()
    assert not (vault / "_meta" / "source-manifest.json").exists()


def test_office_sync_plan_reports_duplicate_sensitive_and_conversion_risks(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    secret = vault / "60_finance" / "confidential_payroll.xlsx"
    duplicate = vault / "60_finance" / "payroll-copy.xlsx"
    secret.parent.mkdir(parents=True)
    secret.write_bytes(b"same workbook bytes")
    duplicate.write_bytes(b"same workbook bytes")
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()

    plans = [
        sync.plan_one(secret, vault, config, {}, manifest, "markitdown", "test"),
        sync.plan_one(duplicate, vault, config, {}, manifest, "markitdown", "test"),
    ]
    sync.annotate_duplicate_plans(plans)
    warnings = [warning for plan in plans for warning in plan["record"]["warnings"]]

    assert any("Sensitive-name risk" in warning for warning in warnings)
    assert any("Conversion-quality risk" in warning for warning in warnings)
    assert any("Potential duplicate" in warning for warning in warnings)
    assert not (vault / "_meta" / "source-manifest.json").exists()


def test_office_sync_writes_manifest_and_preserves_source_bytes(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    original = b"office bytes"
    source.write_bytes(original)
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()

    status = sync.sync_one(
        source,
        vault,
        FakeConverter(),
        False,
        False,
        config,
        {},
        manifest,
        "markitdown",
        "test",
    )
    wrote = sync.write_source_manifest(vault, manifest)

    assert status == "created"
    assert wrote is True
    assert source.read_bytes() == original
    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    assert mirror.exists()
    saved = sync.load_source_manifest(vault)
    assert saved["records"][0]["current_source_path"] == "40_delivery/registration.docx"
    assert saved["records"][0]["mirror_path"] == "_mirrors/40_delivery/registration.md"
    assert saved["records"][0]["lifecycle_state"] == "clean"
    assert saved["records"][0]["source_id"].startswith("src_")


def test_office_sync_update_preserves_frontmatter_and_curated_notes(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"office bytes v1")
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()
    first_status = sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, manifest, "markitdown", "test")
    sync.write_source_manifest(vault, manifest)
    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    first_text = mirror.read_text(encoding="utf-8")
    first_fm, first_body = sync.split_frontmatter(first_text)
    source_id = first_fm["source_id"]
    first_source_sha = first_fm["source_sha256"]
    first_record = sync.load_source_manifest(vault)["records"][0]

    first_fm["status"] = "reviewed"
    first_fm["owner"] = "operations"
    first_fm["tags"] = ["delivery", "mirror"]
    first_fm["related"] = ["[[CRA Business Registration Hub]]"]
    first_fm["reviewed_by"] = "cz1993"
    curated_body = first_body.replace("## Notes\n\n\n", "## Notes\n\nCurated delivery note.\n\n", 1)
    mirror.write_text(sync.dump_frontmatter(first_fm) + "\n" + curated_body, encoding="utf-8")

    source.write_bytes(b"office bytes v2")
    loaded = sync.load_source_manifest(vault)
    plan = sync.plan_one(source, vault, config, {}, loaded, "markitdown", "test")
    second_status = sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, loaded, "markitdown", "test")
    sync.write_source_manifest(vault, loaded)
    updated_text = mirror.read_text(encoding="utf-8")
    updated_fm, _updated_body = sync.split_frontmatter(updated_text)
    updated_record = sync.load_source_manifest(vault)["records"][0]

    assert first_status == "created"
    assert plan["action"] == "update"
    assert second_status == "updated"
    assert "Curated delivery note." in updated_text
    assert updated_fm["status"] == "reviewed"
    assert updated_fm["owner"] == "operations"
    assert updated_fm["tags"] == ["delivery", "mirror"]
    assert updated_fm["related"] == ["[[CRA Business Registration Hub]]"]
    assert updated_fm["reviewed_by"] == "cz1993"
    assert updated_fm["type"] == "source-mirror"
    assert updated_fm["source_id"] == source_id
    assert updated_fm["source"] == "40_delivery/registration.docx"
    assert updated_fm["source_sha256"] == sync.sha256_of(source)
    assert updated_fm["source_sha256"] != first_source_sha
    assert updated_record["source_id"] == first_record["source_id"]
    assert updated_record["lifecycle_state"] == "clean"


def test_office_sync_second_run_is_manifest_stable(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"office bytes")
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()

    sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, manifest, "markitdown", "test")
    assert sync.write_source_manifest(vault, manifest) is True
    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    first_mirror = mirror.read_text(encoding="utf-8")
    first_manifest = (vault / "_meta" / "source-manifest.json").read_text(encoding="utf-8")

    loaded = sync.load_source_manifest(vault)
    status = sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, loaded, "markitdown", "test")
    wrote = sync.write_source_manifest(vault, loaded)

    assert status == "unchanged"
    assert wrote is False
    assert mirror.read_text(encoding="utf-8") == first_mirror
    assert (vault / "_meta" / "source-manifest.json").read_text(encoding="utf-8") == first_manifest


def test_office_sync_unsupported_source_is_idempotent(tmp_path: Path) -> None:
    class UnsupportedFormatError(Exception):
        pass

    class UnsupportedConverter:
        def convert(self, _path: str) -> FakeConversion:
            raise UnsupportedFormatError("legacy container")

    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "legacy-container.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"legacy bytes")
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()

    first_status = sync.sync_one(
        source,
        vault,
        UnsupportedConverter(),
        False,
        False,
        config,
        {},
        manifest,
        "markitdown",
        "test",
    )
    assert sync.write_source_manifest(vault, manifest) is True
    first_manifest = (vault / "_meta" / "source-manifest.json").read_text(encoding="utf-8")

    loaded = sync.load_source_manifest(vault)
    second_status = sync.sync_one(
        source,
        vault,
        UnsupportedConverter(),
        False,
        False,
        config,
        {},
        loaded,
        "markitdown",
        "test",
    )
    wrote = sync.write_source_manifest(vault, loaded)
    saved = sync.load_source_manifest(vault)["records"][0]

    assert first_status == "skipped:unsupported-format (legacy/no converter)"
    assert second_status == "skipped:unsupported-format (legacy/no converter)"
    assert wrote is False
    assert saved["lifecycle_state"] == "unsupported"
    assert "Converter reported unsupported format." in saved["warnings"]
    assert source.read_bytes() == b"legacy bytes"
    assert not (vault / "_mirrors" / "40_delivery" / "legacy-container.md").exists()
    assert (vault / "_meta" / "source-manifest.json").read_text(encoding="utf-8") == first_manifest


def test_office_sync_aborts_when_source_changes_during_conversion(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"office bytes v1")
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()
    sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, manifest, "markitdown", "test")
    sync.write_source_manifest(vault, manifest)
    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    first_mirror = mirror.read_text(encoding="utf-8")
    first_record = sync.load_source_manifest(vault)["records"][0]

    source.write_bytes(b"office bytes v2")
    loaded = sync.load_source_manifest(vault)
    status = sync.sync_one(
        source,
        vault,
        SourceChangingConverter(b"office bytes v3"),
        False,
        False,
        config,
        {},
        loaded,
        "markitdown",
        "test",
    )
    sync.write_source_manifest(vault, loaded)

    assert status == "error:source-changed-during-conversion"
    assert mirror.read_text(encoding="utf-8") == first_mirror
    saved = sync.load_source_manifest(vault)["records"][0]
    assert saved["lifecycle_state"] == "error"
    assert saved["last_successful_sync"] == first_record["last_successful_sync"]
    assert any("Source bytes changed during conversion" in error for error in saved["errors"])


def test_office_sync_preserves_mirror_and_recovers_after_converter_failure(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"office bytes v1")
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()
    sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, manifest, "markitdown", "test")
    sync.write_source_manifest(vault, manifest)
    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    first_mirror = mirror.read_text(encoding="utf-8")
    first_record = sync.load_source_manifest(vault)["records"][0]

    source.write_bytes(b"office bytes v2")
    loaded = sync.load_source_manifest(vault)
    failed = sync.sync_one(source, vault, FailingConverter(), False, False, config, {}, loaded, "markitdown", "test")
    sync.write_source_manifest(vault, loaded)
    failed_record = sync.load_source_manifest(vault)["records"][0]

    assert failed == "error:RuntimeError: conversion exploded"
    assert mirror.read_text(encoding="utf-8") == first_mirror
    assert failed_record["lifecycle_state"] == "error"
    assert failed_record["last_successful_sync"] == first_record["last_successful_sync"]
    assert failed_record["generated_region_sha256"] == first_record["generated_region_sha256"]
    assert any("RuntimeError: conversion exploded" in error for error in failed_record["errors"])

    recoverable = sync.load_source_manifest(vault)
    plan = sync.plan_one(source, vault, config, {}, recoverable, "markitdown", "test")
    recovered = sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, recoverable, "markitdown", "test")
    sync.write_source_manifest(vault, recoverable)
    recovered_record = sync.load_source_manifest(vault)["records"][0]

    assert plan["action"] == "update"
    assert recovered == "updated"
    assert recovered_record["lifecycle_state"] == "clean"
    assert recovered_record["errors"] == []
    assert recovered_record["source_sha256"] == sync.sha256_of(source)
    assert mirror.read_text(encoding="utf-8") != first_mirror


def test_office_sync_preserves_mirror_and_recovers_after_write_failure(tmp_path: Path, monkeypatch) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"office bytes v1")
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()
    sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, manifest, "markitdown", "test")
    sync.write_source_manifest(vault, manifest)
    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    first_mirror = mirror.read_text(encoding="utf-8")
    first_record = sync.load_source_manifest(vault)["records"][0]
    original_write_text_atomic = sync.write_text_atomic

    def failing_write(_path: Path, _content: str) -> None:
        raise OSError("disk full")

    source.write_bytes(b"office bytes v2")
    monkeypatch.setattr(sync, "write_text_atomic", failing_write)
    loaded = sync.load_source_manifest(vault)
    failed_plan = sync.plan_one(source, vault, config, {}, loaded, "markitdown", "test")
    failed = sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, loaded, "markitdown", "test")
    monkeypatch.setattr(sync, "write_text_atomic", original_write_text_atomic)
    sync.write_source_manifest(vault, loaded)
    failed_record = sync.load_source_manifest(vault)["records"][0]

    assert failed == "error:mirror-write:OSError: disk full"
    assert mirror.read_text(encoding="utf-8") == first_mirror
    assert failed_record["lifecycle_state"] == "error"
    assert failed_record["last_successful_sync"] == first_record["last_successful_sync"]
    assert failed_record["generated_region_sha256"] == first_record["generated_region_sha256"]
    assert any("Mirror write failed: OSError: disk full" in error for error in failed_record["errors"])
    sync.append_audit(vault, sync.sync_audit_event(vault, failed_plan, loaded, failed))
    failed_event = json.loads((vault / "_meta" / "sync-audit.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert failed_event["status"] == failed
    assert failed_event["lifecycle_state"] == "error"
    assert failed_event["mirror_path"] == "_mirrors/40_delivery/registration.md"
    assert any("Mirror write failed: OSError: disk full" in error for error in failed_event["errors"])

    recoverable = sync.load_source_manifest(vault)
    plan = sync.plan_one(source, vault, config, {}, recoverable, "markitdown", "test")
    recovered = sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, recoverable, "markitdown", "test")
    sync.write_source_manifest(vault, recoverable)
    recovered_record = sync.load_source_manifest(vault)["records"][0]

    assert plan["action"] == "update"
    assert recovered == "updated"
    assert recovered_record["lifecycle_state"] == "clean"
    assert recovered_record["errors"] == []
    assert recovered_record["source_sha256"] == sync.sha256_of(source)
    assert mirror.read_text(encoding="utf-8") != first_mirror


def test_office_sync_reports_manual_generated_region_modification(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"office bytes")
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()
    sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, manifest, "markitdown", "test")
    sync.write_source_manifest(vault, manifest)

    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    mirror.write_text(
        mirror.read_text(encoding="utf-8").replace("Extracted fixture content", "Manual edit below sentinel"),
        encoding="utf-8",
    )
    loaded = sync.load_source_manifest(vault)

    plan = sync.plan_one(source, vault, config, {}, loaded, "markitdown", "test")
    status = sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, loaded, "markitdown", "test")
    sync.write_source_manifest(vault, loaded)
    reloaded = sync.load_source_manifest(vault)
    third_plan = sync.plan_one(source, vault, config, {}, reloaded, "markitdown", "test")

    assert plan["action"] == "review"
    assert plan["record"]["lifecycle_state"] == "manual_modification"
    assert status == "skipped:manual_modification"
    assert third_plan["action"] == "review"
    assert third_plan["record"]["lifecycle_state"] == "manual_modification"
    assert "Manual edit below sentinel" in mirror.read_text(encoding="utf-8")


def test_office_sync_reports_missing_generated_sentinel_as_manual_modification(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"office bytes")
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()
    sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, manifest, "markitdown", "test")
    sync.write_source_manifest(vault, manifest)
    baseline_hash = manifest["records"][0]["generated_region_sha256"]

    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    mirror.write_text(
        mirror.read_text(encoding="utf-8").replace(sync.SENTINEL, "%% SENTINEL REMOVED %%"),
        encoding="utf-8",
    )
    loaded = sync.load_source_manifest(vault)

    plan = sync.plan_one(source, vault, config, {}, loaded, "markitdown", "test")
    status = sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, loaded, "markitdown", "test")
    sync.write_source_manifest(vault, loaded)
    reloaded = sync.load_source_manifest(vault)
    third_plan = sync.plan_one(source, vault, config, {}, reloaded, "markitdown", "test")

    assert plan["action"] == "review"
    assert plan["record"]["lifecycle_state"] == "manual_modification"
    assert any("sentinel" in warning for warning in plan["record"]["warnings"])
    assert status == "skipped:manual_modification"
    assert reloaded["records"][0]["generated_region_sha256"] == baseline_hash
    assert third_plan["action"] == "review"
    assert third_plan["record"]["lifecycle_state"] == "manual_modification"


def test_office_sync_requires_exact_generated_sentinel_line(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"office bytes")
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()
    sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, manifest, "markitdown", "test")
    sync.write_source_manifest(vault, manifest)
    baseline_hash = manifest["records"][0]["generated_region_sha256"]

    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    altered = mirror.read_text(encoding="utf-8").replace(
        sync.SENTINEL,
        "ALTERED " + sync.SENTINEL,
    )
    mirror.write_text(altered, encoding="utf-8")
    loaded = sync.load_source_manifest(vault)

    plan = sync.plan_one(source, vault, config, {}, loaded, "markitdown", "test")
    status = sync.sync_one(source, vault, FakeConverter(), True, False, config, {}, loaded, "markitdown", "test")
    sync.write_source_manifest(vault, loaded)
    reloaded = sync.load_source_manifest(vault)

    assert plan["action"] == "review"
    assert plan["record"]["lifecycle_state"] == "manual_modification"
    assert any("sentinel" in warning for warning in plan["record"]["warnings"])
    assert status == "skipped:manual_modification"
    assert mirror.read_text(encoding="utf-8") == altered
    assert reloaded["records"][0]["generated_region_sha256"] == baseline_hash


def test_office_sync_force_does_not_trust_missing_generated_sentinel(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"office bytes")
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()
    sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, manifest, "markitdown", "test")
    sync.write_source_manifest(vault, manifest)

    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    corrupted_text = mirror.read_text(encoding="utf-8").replace(
        sync.SENTINEL,
        "Corrupted generated text without a trusted boundary",
    )
    mirror.write_text(corrupted_text, encoding="utf-8")
    loaded = sync.load_source_manifest(vault)

    status = sync.sync_one(source, vault, FakeConverter(), True, False, config, {}, loaded, "markitdown", "test")

    assert status == "skipped:manual_modification"
    assert mirror.read_text(encoding="utf-8") == corrupted_text


def test_office_sync_treats_existing_mirror_without_manifest_baseline_as_review(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"office bytes")
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()
    sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, manifest, "markitdown", "test")
    sync.write_source_manifest(vault, manifest)
    (vault / "_meta" / "source-manifest.json").unlink()
    empty_manifest = sync.empty_manifest()

    plan = sync.plan_one(source, vault, config, {}, empty_manifest, "markitdown", "test")
    status = sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, empty_manifest, "markitdown", "test")
    force_status = sync.sync_one(source, vault, FakeConverter(), True, False, config, {}, empty_manifest, "markitdown", "test")

    assert plan["action"] == "review"
    assert plan["record"]["lifecycle_state"] == "manual_modification"
    assert plan["record"]["generated_region_sha256"] is None
    assert any("no manifest-generated baseline" in warning for warning in plan["record"]["warnings"])
    assert status == "skipped:manual_modification"
    assert force_status == "skipped:manual_modification"


def test_office_sync_force_does_not_trust_missing_sentinel_without_manifest(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"office bytes")
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()
    sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, manifest, "markitdown", "test")
    sync.write_source_manifest(vault, manifest)

    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    corrupted_text = mirror.read_text(encoding="utf-8").replace(
        sync.SENTINEL,
        "Corrupted generated text without a trusted boundary",
    )
    mirror.write_text(corrupted_text, encoding="utf-8")
    (vault / "_meta" / "source-manifest.json").unlink()
    empty_manifest = sync.empty_manifest()

    plan = sync.plan_one(source, vault, config, {}, empty_manifest, "markitdown", "test")
    status = sync.sync_one(source, vault, FakeConverter(), True, False, config, {}, empty_manifest, "markitdown", "test")

    assert plan["action"] == "review"
    assert any("no manifest-generated baseline" in warning for warning in plan["record"]["warnings"])
    assert status == "skipped:manual_modification"
    assert mirror.read_text(encoding="utf-8") == corrupted_text


def test_office_sync_marks_missing_manifest_sources(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"office bytes")
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()
    sync.sync_one(source, vault, FakeConverter(), False, False, config, {}, manifest, "markitdown", "test")
    source_id = manifest["records"][0]["source_id"]

    source.unlink()
    missing = sync.mark_missing_sources(manifest, vault, set())

    assert missing == 1
    assert manifest["records"][0]["source_id"] == source_id
    assert manifest["records"][0]["lifecycle_state"] == "source_missing"


def test_office_lifecycle_guidance_explains_review_states() -> None:
    sync = load_office_sync_module()

    lines = sync.lifecycle_guidance_lines({
        "clean": 3,
        "manual_modification": 1,
        "source_missing": 2,
        "source_moved": 1,
    })

    assert any("manual_modification (1): inspect the mirror below the generated sentinel" in line for line in lines)
    assert any("source_missing (2): do not delete the retained mirror automatically" in line for line in lines)
    assert any("source_moved (1): confirm the source move is intentional" in line for line in lines)
    assert not any(line.startswith("clean") for line in lines)


def test_repo_lifecycle_guidance_explains_review_states() -> None:
    sync = load_sync_module()

    lines = sync.lifecycle_guidance_lines({
        "clean": 1,
        "manual_modification": 1,
        "repo_changed": 2,
        "unreachable": 1,
    })

    assert any("manual_modification (1): inspect the repo mirror below the generated sentinel" in line for line in lines)
    assert any("repo_changed (2): run sync to refresh README/docs/metadata" in line for line in lines)
    assert any("unreachable (1): check repo spelling, network access, and GitHub auth" in line for line in lines)
    assert not any(line.startswith("clean") for line in lines)


def test_office_sync_detects_moved_source_by_manifest_hash(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    original = vault / "40_delivery" / "registration.docx"
    moved = vault / "50_operations" / "registration.docx"
    original.parent.mkdir(parents=True)
    moved.parent.mkdir(parents=True)
    original.write_bytes(b"office bytes")
    config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()
    sync.sync_one(original, vault, FakeConverter(), False, False, config, {}, manifest, "markitdown", "test")
    sync.write_source_manifest(vault, manifest)
    source_id = manifest["records"][0]["source_id"]
    old_mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    old_mirror_text = old_mirror.read_text(encoding="utf-8")

    moved.write_bytes(original.read_bytes())
    original.unlink()
    loaded = sync.load_source_manifest(vault)
    plan = sync.plan_one(moved, vault, config, {}, loaded, "markitdown", "test")
    skipped = sync.sync_one(moved, vault, FakeConverter(), False, False, config, {}, loaded, "markitdown", "test")
    forced = sync.sync_one(moved, vault, FakeConverter(), True, False, config, {}, loaded, "markitdown", "test")
    sync.write_source_manifest(vault, loaded)
    repeated_plan = sync.plan_one(moved, vault, config, {}, sync.load_source_manifest(vault), "markitdown", "test")

    assert plan["record"]["source_id"] == source_id
    assert plan["action"] == "review"
    assert plan["record"]["lifecycle_state"] == "source_moved"
    assert plan["record"]["previous_source_paths"] == ["40_delivery/registration.docx"]
    assert plan["record"]["previous_mirror_path"] == "_mirrors/40_delivery/registration.md"
    assert plan["record"]["previous_mirror_reason"] == "source_moved"
    assert skipped == "skipped:source_moved"
    assert forced == "skipped:source_moved"
    assert old_mirror.read_text(encoding="utf-8") == old_mirror_text
    assert not (vault / "_mirrors" / "50_operations" / "registration.md").exists()
    assert repeated_plan["action"] == "review"
    assert repeated_plan["record"]["lifecycle_state"] == "source_moved"

    old_mirror.unlink()
    resolvable = sync.load_source_manifest(vault)
    resolved_status = sync.sync_one(moved, vault, FakeConverter(), False, False, config, {}, resolvable, "markitdown", "test")
    sync.write_source_manifest(vault, resolvable)
    resolved = sync.load_source_manifest(vault)["records"][0]

    assert resolved_status == "created"
    assert (vault / "_mirrors" / "50_operations" / "registration.md").exists()
    assert resolved["source_id"] == source_id
    assert resolved["lifecycle_state"] == "clean"
    assert resolved["previous_source_paths"] == ["40_delivery/registration.docx"]
    assert "previous_mirror_path" not in resolved
    assert "previous_mirror_reason" not in resolved


def test_office_sync_conflicts_when_mirror_root_changes_with_old_mirror(tmp_path: Path) -> None:
    sync = load_office_sync_module()
    vault = tmp_path / "vault"
    source = vault / "40_delivery" / "registration.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"office bytes")
    original_config = sync.load_mirror_config(vault)
    manifest = sync.empty_manifest()
    sync.sync_one(source, vault, FakeConverter(), False, False, original_config, {}, manifest, "markitdown", "test")
    sync.write_source_manifest(vault, manifest)
    old_mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    old_mirror_text = old_mirror.read_text(encoding="utf-8")

    new_config = sync.normalized_mirror_config("dedicated", "_generated")
    loaded = sync.load_source_manifest(vault)
    plan = sync.plan_one(source, vault, new_config, {}, loaded, "markitdown", "test")
    status = sync.sync_one(source, vault, FakeConverter(), False, False, new_config, {}, loaded, "markitdown", "test")
    sync.write_source_manifest(vault, loaded)
    reloaded = sync.load_source_manifest(vault)
    repeated_plan = sync.plan_one(source, vault, new_config, {}, reloaded, "markitdown", "test")

    assert plan["action"] == "review"
    assert plan["record"]["lifecycle_state"] == "conflict"
    assert plan["record"]["previous_mirror_path"] == "_mirrors/40_delivery/registration.md"
    assert plan["record"]["previous_mirror_reason"] == "mirror_location_changed"
    assert any("Configured mirror location changed" in error for error in plan["record"]["errors"])
    assert status == "skipped:conflict"
    assert old_mirror.read_text(encoding="utf-8") == old_mirror_text
    assert not (vault / "_generated" / "40_delivery" / "registration.md").exists()
    assert repeated_plan["action"] == "review"
    assert repeated_plan["record"]["lifecycle_state"] == "conflict"
    assert repeated_plan["record"]["previous_mirror_path"] == "_mirrors/40_delivery/registration.md"
    assert repeated_plan["record"]["previous_mirror_reason"] == "mirror_location_changed"

    old_mirror.unlink()
    resolvable = sync.load_source_manifest(vault)
    resolved_status = sync.sync_one(
        source,
        vault,
        FakeConverter(),
        False,
        False,
        new_config,
        {},
        resolvable,
        "markitdown",
        "test",
    )
    sync.write_source_manifest(vault, resolvable)
    resolved_record = sync.load_source_manifest(vault)["records"][0]

    assert resolved_status == "created"
    assert (vault / "_generated" / "40_delivery" / "registration.md").exists()
    assert resolved_record["lifecycle_state"] == "clean"
    assert resolved_record["mirror_path"] == "_generated/40_delivery/registration.md"
    assert "previous_mirror_path" not in resolved_record
    assert "previous_mirror_reason" not in resolved_record


def test_github_token_is_not_embedded_in_git_argv(monkeypatch) -> None:
    sync = load_sync_module()
    seen: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = "abc123\tHEAD\n"
        stderr = ""

    def fake_run(cmd, **kwargs):
        seen.append(cmd)
        return Result()

    monkeypatch.setattr(sync.subprocess, "run", fake_run)

    assert sync.head_sha("owner/repo", "SECRET_TOKEN_VALUE") == "abc123"
    assert seen
    assert all("SECRET_TOKEN_VALUE" not in part for cmd in seen for part in cmd)


def test_repo_frontmatter_prefers_account_and_supports_legacy_client() -> None:
    sync = load_sync_module()

    fm = sync.base_fm({}, {"repo": "local/repo", "note": "repo.md", "account": "[[Acme Manufacturing]]"}, "local/repo")
    assert fm["account"] == "[[Acme Manufacturing]]"

    legacy = sync.base_fm({}, {"repo": "local/repo", "note": "repo.md", "client": "[[Legacy Client]]"}, "local/repo")
    assert legacy["account"] == "[[Legacy Client]]"
    assert legacy["client"] == "[[Legacy Client]]"

    normalized = sync.base_fm({"account": "[[Acme]]", "client": "[[Other]]"}, {"repo": "local/repo", "note": "repo.md"}, "local/repo")
    assert normalized["account"] == "[[Acme]]"
    assert normalized["client"] == "[[Acme]]"


def test_local_path_repo_mirror_rejects_escape(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    tools = vault / "tools"
    tools.mkdir(parents=True)
    shutil.copy(ROOT / "template/tools/sync_github_repos.py", tools / "sync_github_repos.py")
    (tools / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos:\n"
        "  - repo: local/escape\n"
        "    local_path: ../../\n"
        "    note: escape.md\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py"), "--quiet"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "1 error" in result.stdout


def test_repo_mirror_rejects_escaping_note_path(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    tools = vault / "tools"
    fixture = vault / "_fixtures" / "repo"
    tools.mkdir(parents=True)
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text("# Fixture\n", encoding="utf-8")
    shutil.copy(ROOT / "template/tools/sync_github_repos.py", tools / "sync_github_repos.py")
    (tools / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: 80_sources/repos\n"
        "repos:\n"
        "  - repo: local/escape\n"
        "    local_path: _fixtures/repo\n"
        "    note: ../../../escaped.md\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py"), "--quiet"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "1 error" in result.stdout
    assert not (tmp_path / "escaped.md").exists()


def test_repo_mirror_rejects_escaping_notes_dir(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    tools = vault / "tools"
    fixture = vault / "_fixtures" / "repo"
    tools.mkdir(parents=True)
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text("# Fixture\n", encoding="utf-8")
    shutil.copy(ROOT / "template/tools/sync_github_repos.py", tools / "sync_github_repos.py")
    (tools / "repos.yml").write_text(
        "settings:\n"
        "  notes_dir: ../outside\n"
        "repos:\n"
        "  - repo: local/escape\n"
        "    local_path: _fixtures/repo\n"
        "    note: escape.md\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(tools / "sync_github_repos.py"), "--quiet"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "1 error" in result.stdout
    assert not (tmp_path / "outside" / "escape.md").exists()


def test_repo_mirror_output_path_rejects_absolute_values() -> None:
    sync = load_sync_module()

    for notes_dir, note in (("/tmp/outside", "repo.md"), ("80_sources/repos", "/tmp/repo.md")):
        try:
            sync.note_output_path(notes_dir, note)
        except ValueError as exc:
            assert "inside the vault" in str(exc)
        else:
            raise AssertionError("absolute repo mirror output path was accepted")


def test_repo_mirror_output_path_rejects_operational_paths_and_non_markdown() -> None:
    sync = load_sync_module()

    bad_cases = (
        (".git/hooks", "pre-commit"),
        ("80_sources/repos", "pre-commit"),
        ("80_sources/repos", "repo.MD"),
        ("tools/repos", "repo.md"),
        ("80_sources/repos", ".hidden.md"),
    )
    for notes_dir, note in bad_cases:
        try:
            sync.note_output_path(notes_dir, note)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe output path was accepted: {notes_dir}/{note}")


def test_repo_mirror_output_path_rejects_symlinked_reserved_target(tmp_path: Path, monkeypatch) -> None:
    sync = load_sync_module()
    vault = tmp_path / "vault"
    (vault / "80_sources").mkdir(parents=True)
    (vault / ".github" / "workflows").mkdir(parents=True)
    (vault / "80_sources" / "repos").symlink_to(vault / ".github" / "workflows")
    monkeypatch.setattr(sync, "ROOT", vault)

    try:
        sync.note_output_path("80_sources/repos", "injected.md")
    except ValueError as exc:
        assert "symlink" in str(exc) or "reserved" in str(exc)
    else:
        raise AssertionError("symlinked reserved repo mirror output path was accepted")


def test_repo_mirror_output_path_rejects_final_note_symlink(tmp_path: Path, monkeypatch) -> None:
    sync = load_sync_module()
    vault = tmp_path / "vault"
    (vault / "80_sources" / "repos").mkdir(parents=True)
    (vault / "10_governance").mkdir(parents=True)
    target = vault / "10_governance" / "Important.md"
    target.write_text("# Important\n", encoding="utf-8")
    (vault / "80_sources" / "repos" / "repo.md").symlink_to(target)
    monkeypatch.setattr(sync, "ROOT", vault)

    try:
        sync.note_output_path("80_sources/repos", "repo.md")
    except ValueError as exc:
        assert "symlink" in str(exc)
    else:
        raise AssertionError("final note symlink output path was accepted")
