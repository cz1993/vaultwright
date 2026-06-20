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
    assert "GitHub auth:" in result.stdout
    assert (ROOT / "template/tools/benchmark_tasks.py").exists()
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
    assert "vaultwright doctor: OK" in result.stdout


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

    recovery = subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", "--root", str(vault), "recovery"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert recovery.returncode == 0, recovery.stderr or recovery.stdout
    assert "recovery: no manifest records need operator action" in recovery.stdout


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
    assert (target / "tools" / "recovery_report.py").exists()
    assert (target / "tools" / "vaultwright.py").exists()


def test_repos_example_has_no_active_placeholder_repo() -> None:
    cfg = yaml.safe_load((ROOT / "template/tools/repos.example.yml").read_text(encoding="utf-8"))

    assert cfg["repos"] == []


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

    result = subprocess.run(
        [sys.executable, str(vault / "tools" / "vaultwright.py"), "recovery"],
        cwd=vault,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "recovery: 4 items need operator action (office=3, repo=1)" in result.stdout
    assert "[office:source_missing" in result.stdout
    assert "Locate, restore, or intentionally archive the source" in result.stdout
    assert "[office:manual_modification" in result.stdout
    assert "Preserve human edits below the sentinel" in result.stdout
    assert "[office:source_moved" in result.stdout
    assert "preserve/archive any old mirror" in result.stdout
    assert "[repo:conflict" in result.stdout
    assert "Resolve the target note/repo identity conflict" in result.stdout


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
