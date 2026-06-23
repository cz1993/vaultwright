# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SENTINEL = "%% AUTO-GENERATED BELOW \u2014 DO NOT EDIT %%"


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = src_path if not env.get("PYTHONPATH") else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", *args],
        cwd=cwd or ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def write_source_mirror(vault: Path, *, annotated: bool = True) -> Path:
    mirror = vault / "_mirrors" / "40_delivery" / "registration.md"
    mirror.parent.mkdir(parents=True)
    note = "Human delivery note.\n\n" if annotated else ""
    related = "related:\n  - '[[Business Registration Hub]]'\n" if annotated else "related: []\n"
    mirror.write_text(
        "---\n"
        "title: Registration\n"
        "type: source-mirror\n"
        f"status: {'reviewed' if annotated else 'active'}\n"
        "domain: delivery\n"
        "owner: you\n"
        "created: 2026-06-23\n"
        "updated: 2026-06-23\n"
        f"tags: {['reviewed'] if annotated else []}\n"
        f"{related}"
        "source_id: src_registration\n"
        "source: 40_delivery/registration.docx\n"
        "source_manifest: _meta/source-manifest.json\n"
        "source_format: docx\n"
        "source_modified: 2026-06-23T00:00:00-04:00\n"
        "synced: 2026-06-23T00:00:00-04:00\n"
        "source_sha256: abc123\n"
        "converter: markitdown\n"
        "converter_version: test\n"
        "---\n\n"
        "> [!info] Source-mirrored document \u2014 auto-generated\n"
        "> Original: [[40_delivery/registration.docx|registration.docx]] · edit the **original**, never this mirror.\n"
        "> Curate notes below; everything under the line refreshes on each sync.\n\n"
        "## Notes\n\n"
        f"{note}"
        f"{SENTINEL}\n\n"
        "## Extracted content\n\nGenerated source text.\n",
        encoding="utf-8",
    )
    return mirror


def write_repo_mirror(vault: Path) -> Path:
    mirror = vault / "80_sources" / "repos" / "fixture.md"
    mirror.parent.mkdir(parents=True)
    mirror.write_text(
        "---\n"
        "title: fixture\n"
        "type: repo-mirror\n"
        "status: active\n"
        "domain: sources\n"
        "owner: platform\n"
        "created: 2026-06-23\n"
        "updated: 2026-06-23\n"
        "tags:\n"
        "  - repo\n"
        "repo_id: repo_fixture\n"
        "repo_manifest: _meta/repo-manifest.json\n"
        "repo: example/fixture\n"
        "repo_url: https://example.invalid/fixture\n"
        "default_branch: main\n"
        "last_commit: abc123\n"
        "last_commit_date: 2026-06-23\n"
        "open_issues: ''\n"
        "synced: 2026-06-23T00:00:00-04:00\n"
        "---\n\n"
        "> [!info] GitHub repo mirror \u2014 auto-generated\n"
        "> Source: example/fixture (https://example.invalid/fixture). Edit the source repo, never this note.\n"
        "> Curate notes below; everything under the line refreshes on sync.\n\n"
        "## Notes\n\n"
        "Human repo note.\n\n"
        f"{SENTINEL}\n\n"
        "## Repository\n\nGenerated repo text.\n",
        encoding="utf-8",
    )
    return mirror


def test_annotation_migration_plans_writes_and_becomes_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    original = write_source_mirror(vault).read_text(encoding="utf-8")

    plan = run_cli("--root", str(vault), "migrate", "annotations", "--plan", "--json")

    assert plan.returncode == 0, plan.stderr
    payload = json.loads(plan.stdout)
    assert payload["summary"]["actions"] == 1
    assert payload["summary"]["blockers"] == 0
    assert payload["actions"][0]["mirror_path"] == "_mirrors/40_delivery/registration.md"
    assert payload["actions"][0]["sidecar_path"] == "_meta/mirror-annotations/source/src_registration.md"
    assert "Human delivery note" not in plan.stdout

    write = run_cli("--root", str(vault), "migrate", "annotations", "--write", "--json")

    assert write.returncode == 0, write.stderr
    write_payload = json.loads(write.stdout)
    assert write_payload["summary"]["written"] == 1
    sidecar = vault / "_meta" / "mirror-annotations" / "source" / "src_registration.md"
    assert sidecar.exists()
    sidecar_text = sidecar.read_text(encoding="utf-8")
    assert "Human delivery note." in sidecar_text
    assert "source_id: src_registration" in sidecar_text
    assert "preserved_sha256:" in sidecar_text
    assert (vault / "_mirrors" / "40_delivery" / "registration.md").read_text(encoding="utf-8") == original

    second_plan = run_cli("--root", str(vault), "migrate", "annotations", "--plan", "--json")

    assert second_plan.returncode == 0, second_plan.stderr
    second_payload = json.loads(second_plan.stdout)
    assert second_payload["summary"]["actions"] == 0
    assert second_payload["summary"]["already_migrated"] == 1


def test_annotation_migration_skips_empty_generated_mirror(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    write_source_mirror(vault, annotated=False)

    plan = run_cli("--root", str(vault), "migrate", "annotations", "--plan", "--json")

    assert plan.returncode == 0, plan.stderr
    payload = json.loads(plan.stdout)
    assert payload["summary"]["scanned_mirrors"] == 1
    assert payload["summary"]["actions"] == 0
    assert payload["summary"]["without_annotations"] == 1


def test_annotation_migration_writes_repo_sidecar(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    write_repo_mirror(vault)

    result = run_cli("--root", str(vault), "migrate", "annotations", "--write", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["summary"]["written"] == 1
    sidecar = vault / "_meta" / "mirror-annotations" / "repo" / "repo_fixture.md"
    assert sidecar.exists()
    text = sidecar.read_text(encoding="utf-8")
    assert "repo_id: repo_fixture" in text
    assert "Human repo note." in text


def test_annotation_migration_blocks_conflicting_sidecar(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    write_repo_mirror(vault)
    sidecar = vault / "_meta" / "mirror-annotations" / "repo" / "repo_fixture.md"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text("---\npreserved_sha256: stale\n---\n", encoding="utf-8")

    result = run_cli("--root", str(vault), "migrate", "annotations", "--plan", "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["summary"]["blockers"] == 1
    assert payload["blockers"][0]["code"] == "annotation-sidecar-conflict"
