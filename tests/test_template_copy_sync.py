# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync_template_copies.py"


def run_sync(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_template_copy_sync_check_passes_repository() -> None:
    result = run_sync(ROOT, "--check")

    assert result.returncode == 0, result.stderr or result.stdout
    assert "template copies: clean" in result.stdout


def test_template_copy_sync_check_reports_drift_without_mutating(tmp_path: Path) -> None:
    write(tmp_path / "template" / "CLAUDE.md", "canonical template\n")
    write(tmp_path / "template" / "_meta" / "lifecycle-states.yml", "canonical lifecycle\n")
    write(tmp_path / "template" / "tools" / "lint_vault.py", "canonical tool\n")
    write(tmp_path / "src" / "vaultwright" / "template" / "CLAUDE.md", "stale template\n")
    write(tmp_path / "src" / "vaultwright" / "template" / "_meta" / "lifecycle-states.yml", "canonical lifecycle\n")
    write(tmp_path / "examples" / "demo-vault" / "_meta" / "lifecycle-states.yml", "stale lifecycle\n")
    write(tmp_path / "examples" / "demo-vault" / "tools" / "lint_vault.py", "stale tool\n")
    write(tmp_path / "examples" / "demo-vault" / "tools" / "repos.yml", "custom repo config\n")

    result = run_sync(tmp_path, "--check")

    assert result.returncode == 1
    assert "src/vaultwright/template: differs: CLAUDE.md" in result.stdout
    assert "examples/demo-vault/tools: differs: lint_vault.py" in result.stdout
    assert "examples/demo-vault/_meta: differs: lifecycle-states.yml" in result.stdout
    assert "Run: python3.11 scripts/sync_template_copies.py --write" in result.stdout
    assert (tmp_path / "src" / "vaultwright" / "template" / "CLAUDE.md").read_text(encoding="utf-8") == (
        "stale template\n"
    )
    assert (tmp_path / "examples" / "demo-vault" / "_meta" / "lifecycle-states.yml").read_text(encoding="utf-8") == (
        "stale lifecycle\n"
    )
    assert (tmp_path / "examples" / "demo-vault" / "tools" / "repos.yml").read_text(encoding="utf-8") == (
        "custom repo config\n"
    )


def test_template_copy_sync_check_reports_executable_mode_drift(tmp_path: Path) -> None:
    write(tmp_path / "template" / "CLAUDE.md", "canonical template\n")
    write(tmp_path / "template" / "tools" / "sync_all.sh", "#!/usr/bin/env bash\n")
    write(tmp_path / "src" / "vaultwright" / "template" / "CLAUDE.md", "canonical template\n")
    write(tmp_path / "src" / "vaultwright" / "template" / "tools" / "sync_all.sh", "#!/usr/bin/env bash\n")
    write(tmp_path / "examples" / "demo-vault" / "tools" / "sync_all.sh", "#!/usr/bin/env bash\n")
    (tmp_path / "template" / "tools" / "sync_all.sh").chmod(0o755)
    (tmp_path / "src" / "vaultwright" / "template" / "tools" / "sync_all.sh").chmod(0o644)
    (tmp_path / "examples" / "demo-vault" / "tools" / "sync_all.sh").chmod(0o644)

    result = run_sync(tmp_path, "--check")

    assert result.returncode == 1
    assert "src/vaultwright/template: mode differs: tools/sync_all.sh" in result.stdout
    assert "examples/demo-vault/tools: mode differs: sync_all.sh" in result.stdout
    assert not (
        (tmp_path / "src" / "vaultwright" / "template" / "tools" / "sync_all.sh").stat().st_mode & 0o111
    )


def test_template_copy_sync_rejects_invalid_root(tmp_path: Path) -> None:
    result = run_sync(tmp_path, "--write")

    assert result.returncode == 2
    assert "missing template/CLAUDE.md" in result.stderr


def test_template_copy_sync_write_repairs_copies_and_preserves_repo_configs(tmp_path: Path) -> None:
    write(tmp_path / "template" / ".gitignore", "_mirrors/\n")
    write(tmp_path / "template" / "CLAUDE.md", "canonical template\n")
    write(tmp_path / "template" / "_meta" / "lifecycle-states.yml", "canonical lifecycle\n")
    write(tmp_path / "template" / "tools" / "lint_vault.py", "canonical tool\n")
    write(tmp_path / "template" / "tools" / "sync_all.sh", "#!/usr/bin/env bash\n")
    write(tmp_path / "src" / "vaultwright" / "template" / "CLAUDE.md", "stale template\n")
    write(tmp_path / "src" / "vaultwright" / "template" / "obsolete.md", "remove me\n")
    write(tmp_path / "src" / "vaultwright" / "template" / "tools" / "sync_all.sh", "#!/usr/bin/env bash\n")
    write(tmp_path / "examples" / "demo-vault" / "_meta" / "custom-example.yml", "keep me\n")
    write(tmp_path / "examples" / "demo-vault" / "_meta" / "lifecycle-states.yml", "stale lifecycle\n")
    write(tmp_path / "examples" / "demo-vault" / "tools" / "lint_vault.py", "stale tool\n")
    write(tmp_path / "examples" / "demo-vault" / "tools" / "sync_all.sh", "#!/usr/bin/env bash\n")
    write(tmp_path / "examples" / "demo-vault" / "tools" / "obsolete.py", "remove me\n")
    write(tmp_path / "examples" / "demo-vault" / "tools" / "repos.yml", "custom repo config\n")
    (tmp_path / "template" / "tools" / "sync_all.sh").chmod(0o755)
    (tmp_path / "src" / "vaultwright" / "template" / "tools" / "sync_all.sh").chmod(0o644)
    (tmp_path / "examples" / "demo-vault" / "tools" / "sync_all.sh").chmod(0o644)

    result = run_sync(tmp_path, "--write")

    assert result.returncode == 0, result.stderr or result.stdout
    assert "template copies: updated" in result.stdout
    assert (tmp_path / "src" / "vaultwright" / "template" / ".gitignore").read_text(encoding="utf-8") == (
        "_mirrors/\n"
    )
    assert (tmp_path / "src" / "vaultwright" / "template" / "CLAUDE.md").read_text(encoding="utf-8") == (
        "canonical template\n"
    )
    assert not (tmp_path / "src" / "vaultwright" / "template" / "obsolete.md").exists()
    assert (tmp_path / "examples" / "demo-vault" / "_meta" / "lifecycle-states.yml").read_text(encoding="utf-8") == (
        "canonical lifecycle\n"
    )
    assert (tmp_path / "examples" / "demo-vault" / "_meta" / "custom-example.yml").read_text(encoding="utf-8") == (
        "keep me\n"
    )
    assert (tmp_path / "examples" / "demo-vault" / "tools" / "lint_vault.py").read_text(encoding="utf-8") == (
        "canonical tool\n"
    )
    assert (tmp_path / "src" / "vaultwright" / "template" / "tools" / "sync_all.sh").stat().st_mode & 0o111
    assert (tmp_path / "examples" / "demo-vault" / "tools" / "sync_all.sh").stat().st_mode & 0o111
    assert not (tmp_path / "examples" / "demo-vault" / "tools" / "obsolete.py").exists()
    assert (tmp_path / "examples" / "demo-vault" / "tools" / "repos.yml").read_text(encoding="utf-8") == (
        "custom repo config\n"
    )

    clean = run_sync(tmp_path, "--check")
    assert clean.returncode == 0, clean.stderr or clean.stdout
