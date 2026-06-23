# SPDX-License-Identifier: AGPL-3.0-or-later
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
