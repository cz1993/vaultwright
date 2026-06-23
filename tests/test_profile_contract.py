# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from vaultwright.profiles import ProfileValidationError, load_profile, validate_profile_mapping


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = (
        src_path if not env.get("PYTHONPATH") else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "vaultwright.cli", *args],
        cwd=cwd or ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_template_business_operations_profile_validates() -> None:
    profile = load_profile(ROOT / "template" / "_meta" / "profile.yml")

    assert profile.schema_version == 1
    assert profile.id == "business-operations"
    assert profile.domains["customers"]["folder"] == "30_customers"
    assert "source-mirror" in profile.note_types
    assert "active" in profile.statuses
    assert "Documents.base" in profile.views


def test_packaged_and_example_profiles_match_template() -> None:
    template_profile = (ROOT / "template" / "_meta" / "profile.yml").read_bytes()

    profile_paths = [
        ROOT / "src" / "vaultwright" / "template" / "_meta" / "profile.yml",
        ROOT / "examples" / "government-services-vault" / "_meta" / "profile.yml",
        ROOT / "examples" / "northwind-robotics-vault" / "_meta" / "profile.yml",
    ]

    for path in profile_paths:
        assert path.read_bytes() == template_profile
        assert load_profile(path).id == "business-operations"


def test_profile_contract_rejects_unknown_fields() -> None:
    data = minimal_profile()
    data["hooks"] = ["python arbitrary.py"]

    with pytest.raises(ProfileValidationError, match="unknown profile fields: hooks"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_non_slug_id() -> None:
    data = minimal_profile()
    data["id"] = "Business Operations"

    with pytest.raises(ProfileValidationError, match="id must be lowercase kebab-case"):
        validate_profile_mapping(data)


def test_profile_contract_requires_domain_folders() -> None:
    data = minimal_profile()
    data["domains"] = {"research": {"purpose": "missing folder"}}

    with pytest.raises(ProfileValidationError, match="domains.research.folder"):
        validate_profile_mapping(data)


def test_profile_cli_lists_built_in_profile() -> None:
    result = run_cli("profile", "list")

    assert result.returncode == 0, result.stderr
    assert "business-operations" in result.stdout
    assert "version" in result.stdout


def test_profile_cli_shows_built_in_profile_json() -> None:
    result = run_cli("profile", "show", "business-operations", "--json")

    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["id"] == "business-operations"
    assert data["schema_version"] == 1
    assert "customers" in data["domains"]


def test_profile_cli_initializes_and_validates_current_profile(tmp_path: Path) -> None:
    vault = tmp_path / "vault"

    init = run_cli("init", "--profile", "business-operations", str(vault))
    assert init.returncode == 0, init.stderr
    assert "Profile: business-operations 0.1.0" in init.stdout

    validation = run_cli("--root", str(vault), "profile", "validate")
    assert validation.returncode == 0, validation.stderr
    assert "profile validate: OK business-operations 0.1.0" in validation.stdout

    current = run_cli("--root", str(vault), "profile", "show", "--json")
    assert current.returncode == 0, current.stderr
    assert json.loads(current.stdout)["id"] == "business-operations"


def test_profile_cli_diff_and_migrate_plan_clean_initialized_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init = run_cli("init", "--profile", "business-operations", str(vault))
    assert init.returncode == 0, init.stderr

    diff = run_cli("--root", str(vault), "profile", "diff", "0.1.0", "--json")
    assert diff.returncode == 0, diff.stderr
    diff_payload = json.loads(diff.stdout)
    assert diff_payload["summary"]["up_to_date"] is True
    assert diff_payload["differences"] == []

    plan = run_cli("--root", str(vault), "profile", "migrate", "--plan", "--json")
    assert plan.returncode == 0, plan.stderr
    plan_payload = json.loads(plan.stdout)
    assert plan_payload["summary"] == {"actions": 0, "blockers": 0, "up_to_date": True}


def test_profile_cli_migrate_plan_reports_missing_profile_file(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init = run_cli("init", "--profile", "business-operations", str(vault))
    assert init.returncode == 0, init.stderr
    (vault / "Documents.base").unlink()

    plan = run_cli("--root", str(vault), "profile", "migrate", "--plan", "--json")

    assert plan.returncode == 0, plan.stderr
    payload = json.loads(plan.stdout)
    assert payload["summary"]["actions"] == 1
    assert payload["summary"]["blockers"] == 0
    assert payload["actions"][0]["action"] == "copy-template-file"
    assert payload["actions"][0]["path"] == "Documents.base"
    assert not (vault / "Documents.base").exists()


def test_profile_cli_migrate_plan_reports_profile_contract_drift(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init = run_cli("init", "--profile", "business-operations", str(vault))
    assert init.returncode == 0, init.stderr
    profile_path = vault / "_meta" / "profile.yml"
    profile_path.write_text(
        profile_path.read_text(encoding="utf-8").replace("profile_version: 0.1.0", "profile_version: 0.0.1"),
        encoding="utf-8",
    )

    diff = run_cli("--root", str(vault), "profile", "diff", "0.1.0", "--json")

    assert diff.returncode == 0, diff.stderr
    payload = json.loads(diff.stdout)
    assert payload["summary"]["actions"] >= 1
    assert {
        "field": "profile_version",
        "kind": "changed",
        "current": "0.0.1",
        "target": "0.1.0",
    } in payload["differences"]


def test_profile_cli_rejects_unavailable_init_profile(tmp_path: Path) -> None:
    result = run_cli("init", "--profile", "research-learning", str(tmp_path / "vault"))

    assert result.returncode == 1
    assert "not available yet" in result.stderr


def test_profile_cli_diff_rejects_unavailable_target_version(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init = run_cli("init", "--profile", "business-operations", str(vault))
    assert init.returncode == 0, init.stderr

    result = run_cli("--root", str(vault), "profile", "diff", "9.9.9")

    assert result.returncode == 1
    assert "target profile version '9.9.9' is not available" in result.stderr


def minimal_profile() -> dict:
    return {
        "schema_version": 1,
        "id": "blank",
        "name": "Blank",
        "profile_version": "0.1.0",
        "domains": {"inbox": {"folder": "00_inbox"}},
        "note_types": {},
        "statuses": {},
        "required_properties": [],
        "optional_properties": [],
        "folder_plan": [],
        "templates": [],
        "views": [],
        "skills": [],
        "benchmark_tasks": [],
        "policy_defaults": {},
    }
