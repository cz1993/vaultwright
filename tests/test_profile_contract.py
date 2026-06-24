# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vaultwright.profile_migration import target_dir_paths
from vaultwright.profiles import ProfileContract, ProfileValidationError, load_profile, validate_profile_mapping
from vaultwright.views import render_documents_base


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
    assert profile.note_types["source-mirror"]["machine_owned"] is True
    assert profile.note_types["repo-mirror"]["machine_owned"] is True
    assert "active" in profile.statuses
    assert profile.statuses["draft"]["attention"] is True
    assert profile.statuses["in-review"]["attention"] is True
    assert profile.statuses["superseded"]["inactive"] is True
    assert profile.statuses["archived"]["inactive"] is True
    assert profile.policy_defaults["mirror_mode"] == "dedicated"
    assert profile.policy_defaults["mirror_root"] == "_mirrors"
    assert profile.policy_defaults["mirror_status"] == "active"
    assert profile.policy_defaults["repo_stub_status"] == "draft"
    assert profile.policy_defaults["context_aliases"] == {"client": "account"}
    assert profile.policy_defaults["original_sources_authoritative"] is True
    assert profile.policy_defaults["real_data_in_repo"] is False
    assert "Documents.base" in profile.views


def test_documents_base_matches_profile_generated_view() -> None:
    vaults = [
        ROOT / "template",
        ROOT / "src" / "vaultwright" / "template",
        ROOT / "examples" / "government-services-vault",
        ROOT / "examples" / "northwind-robotics-vault",
    ]

    for vault in vaults:
        profile = load_profile(vault / "_meta" / "profile.yml")
        assert (vault / "Documents.base").read_text(encoding="utf-8") == render_documents_base(profile)


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


def test_profile_contract_rejects_unknown_domain_definition_fields() -> None:
    data = minimal_profile()
    data["domains"]["inbox"]["script"] = "python arbitrary.py"

    with pytest.raises(ProfileValidationError, match="domains.inbox has unknown fields: script"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_empty_domain_purpose() -> None:
    data = minimal_profile()
    data["domains"]["inbox"]["purpose"] = ""

    with pytest.raises(ProfileValidationError, match=r"domains\.inbox\.purpose must be a non-empty string"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_non_slug_domain_keys() -> None:
    data = minimal_profile()
    data["domains"] = {"Research Area": {"folder": "00_inbox"}}

    with pytest.raises(ProfileValidationError, match="domain key must be lowercase kebab-case"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_non_slug_note_type_keys() -> None:
    data = minimal_profile()
    data["note_types"] = {"Research Note": {"purpose": "bad key"}}

    with pytest.raises(ProfileValidationError, match="note_types key must be lowercase kebab-case"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_unknown_note_type_definition_fields() -> None:
    data = minimal_profile()
    data["note_types"] = {"machine-note": {"purpose": "generated note", "hook": "python arbitrary.py"}}

    with pytest.raises(ProfileValidationError, match="note_types.machine-note has unknown fields: hook"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_empty_note_type_purpose() -> None:
    data = minimal_profile()
    data["note_types"] = {"machine-note": {"purpose": ""}}

    with pytest.raises(ProfileValidationError, match=r"note_types\.machine-note\.purpose must be a non-empty string"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_non_slug_status_keys() -> None:
    data = minimal_profile()
    data["statuses"] = {"Needs Review": {"purpose": "bad key"}}

    with pytest.raises(ProfileValidationError, match="status key must be lowercase kebab-case"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_unknown_status_definition_fields() -> None:
    data = minimal_profile()
    data["statuses"] = {"queued": {"purpose": "pending", "handler": "python arbitrary.py"}}

    with pytest.raises(ProfileValidationError, match="statuses.queued has unknown fields: handler"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_empty_status_purpose() -> None:
    data = minimal_profile()
    data["statuses"] = {"queued": {"purpose": ""}}

    with pytest.raises(ProfileValidationError, match=r"statuses\.queued\.purpose must be a non-empty string"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_invalid_frontmatter_property_keys() -> None:
    data = minimal_profile()
    data["required_properties"] = ["title", "Research Project"]

    with pytest.raises(ProfileValidationError, match="required_properties entries must be a lowercase frontmatter key"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_duplicate_frontmatter_property_keys() -> None:
    data = minimal_profile()
    data["optional_properties"] = ["owner", "owner"]

    with pytest.raises(ProfileValidationError, match="optional_properties entries must not contain duplicates"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_overlapping_frontmatter_properties() -> None:
    data = minimal_profile()
    data["required_properties"] = ["title", "domain"]
    data["optional_properties"] = ["domain", "title"]

    with pytest.raises(
        ProfileValidationError,
        match="required_properties and optional_properties must not overlap: domain, title",
    ):
        validate_profile_mapping(data)


def test_profile_contract_requires_folder_plan_entries() -> None:
    data = minimal_profile()
    data["folder_plan"] = []

    with pytest.raises(ProfileValidationError, match="folder_plan must contain at least one starter folder"):
        validate_profile_mapping(data)


def test_profile_contract_requires_folder_plan_mapping_entries() -> None:
    data = minimal_profile()
    data["folder_plan"] = ["00_inbox"]

    with pytest.raises(ProfileValidationError, match=r"folder_plan\[0\] must be a mapping"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_unknown_folder_plan_fields() -> None:
    data = minimal_profile()
    data["folder_plan"] = [{"path": "00_inbox", "domain": "inbox", "hook": "python arbitrary.py"}]

    with pytest.raises(ProfileValidationError, match=r"folder_plan\[0\] has unknown fields: hook"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_non_boolean_status_roles() -> None:
    data = minimal_profile()
    data["statuses"] = {"queued": {"purpose": "pending", "attention": "yes"}}

    with pytest.raises(ProfileValidationError, match=r"statuses\.queued\.attention must be true or false"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_non_boolean_note_type_roles() -> None:
    data = minimal_profile()
    data["note_types"] = {"machine-note": {"purpose": "generated note", "machine_owned": "yes"}}

    with pytest.raises(ProfileValidationError, match=r"note_types\.machine-note\.machine_owned must be true or false"):
        validate_profile_mapping(data)


def test_profile_contract_requires_policy_default_statuses_to_be_declared() -> None:
    data = minimal_profile()
    data["statuses"] = {"queued": {"purpose": "pending"}}
    data["policy_defaults"] = {"mirror_status": "current"}

    with pytest.raises(ProfileValidationError, match=r"policy_defaults\.mirror_status must reference a declared status"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_unknown_policy_default_fields() -> None:
    data = minimal_profile()
    data["policy_defaults"] = {"startup_hook": "python arbitrary.py"}

    with pytest.raises(ProfileValidationError, match="policy_defaults has unknown fields: startup_hook"):
        validate_profile_mapping(data)


def test_profile_contract_accepts_context_aliases_for_optional_properties() -> None:
    data = minimal_profile()
    data["optional_properties"] = ["account", "client"]
    data["policy_defaults"] = {"context_aliases": {"client": "account"}}

    validate_profile_mapping(data)


def test_profile_contract_rejects_non_mapping_context_aliases() -> None:
    data = minimal_profile()
    data["optional_properties"] = ["account", "client"]
    data["policy_defaults"] = {"context_aliases": ["client", "account"]}

    with pytest.raises(ProfileValidationError, match=r"policy_defaults\.context_aliases must be a mapping"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_context_alias_self_reference() -> None:
    data = minimal_profile()
    data["optional_properties"] = ["client"]
    data["policy_defaults"] = {"context_aliases": {"client": "client"}}

    with pytest.raises(ProfileValidationError, match=r"policy_defaults\.context_aliases\.client must not reference itself"):
        validate_profile_mapping(data)


def test_profile_contract_requires_context_alias_keys_to_be_optional_properties() -> None:
    data = minimal_profile()
    data["optional_properties"] = ["account"]
    data["policy_defaults"] = {"context_aliases": {"client": "account"}}

    with pytest.raises(
        ProfileValidationError,
        match=r"policy_defaults\.context_aliases\.client must reference optional_properties",
    ):
        validate_profile_mapping(data)


def test_profile_contract_requires_context_alias_targets_to_be_optional_properties() -> None:
    data = minimal_profile()
    data["optional_properties"] = ["client"]
    data["policy_defaults"] = {"context_aliases": {"client": "account"}}

    with pytest.raises(
        ProfileValidationError,
        match=r"policy_defaults\.context_aliases\.client target must reference optional_properties",
    ):
        validate_profile_mapping(data)


def test_profile_contract_rejects_non_boolean_source_policy_defaults() -> None:
    data = minimal_profile()
    data["policy_defaults"] = {"original_sources_authoritative": "yes"}

    with pytest.raises(
        ProfileValidationError,
        match=r"policy_defaults\.original_sources_authoritative must be true or false",
    ):
        validate_profile_mapping(data)


def test_profile_contract_requires_original_sources_authoritative() -> None:
    data = minimal_profile()
    data["policy_defaults"] = {"original_sources_authoritative": False}

    with pytest.raises(
        ProfileValidationError,
        match=r"policy_defaults\.original_sources_authoritative must be true",
    ):
        validate_profile_mapping(data)


def test_profile_contract_rejects_non_boolean_real_data_policy_default() -> None:
    data = minimal_profile()
    data["policy_defaults"] = {"real_data_in_repo": "no"}

    with pytest.raises(
        ProfileValidationError,
        match=r"policy_defaults\.real_data_in_repo must be true or false",
    ):
        validate_profile_mapping(data)


def test_profile_contract_requires_real_data_out_of_repo() -> None:
    data = minimal_profile()
    data["policy_defaults"] = {"real_data_in_repo": True}

    with pytest.raises(
        ProfileValidationError,
        match=r"policy_defaults\.real_data_in_repo must be false",
    ):
        validate_profile_mapping(data)


def test_profile_contract_rejects_invalid_mirror_mode_default() -> None:
    data = minimal_profile()
    data["policy_defaults"] = {"mirror_mode": "inline"}

    with pytest.raises(ProfileValidationError, match=r"policy_defaults\.mirror_mode must be one of: dedicated, sibling"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_unsafe_mirror_root_default() -> None:
    data = minimal_profile()
    data["policy_defaults"] = {"mirror_root": "_meta/generated"}

    with pytest.raises(ProfileValidationError, match=r"policy_defaults\.mirror_root contains a reserved path component"):
        validate_profile_mapping(data)


def test_profile_contract_accepts_profile_repo_notes_dir_inside_domain_folder() -> None:
    data = minimal_profile()
    data["domains"]["research"] = {"folder": "25_research"}
    data["folder_plan"].append({"path": "25_research", "domain": "research"})
    data["policy_defaults"] = {"repo_notes_dir": "25_research/repos"}

    validate_profile_mapping(data)


def test_profile_contract_rejects_unsafe_repo_notes_dir_default() -> None:
    data = minimal_profile()
    data["policy_defaults"] = {"repo_notes_dir": "_meta/repos"}

    with pytest.raises(ProfileValidationError, match=r"policy_defaults\.repo_notes_dir contains a reserved path component"):
        validate_profile_mapping(data)


def test_profile_contract_requires_repo_notes_dir_inside_domain_folder() -> None:
    data = minimal_profile()
    data["policy_defaults"] = {"repo_notes_dir": "90_repos"}

    with pytest.raises(ProfileValidationError, match=r"policy_defaults\.repo_notes_dir must be inside a declared domain folder"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_repo_notes_dir_mirror_root_overlap() -> None:
    data = minimal_profile()
    data["domains"]["sources"] = {"folder": "80_sources"}
    data["folder_plan"].append({"path": "80_sources", "domain": "sources"})
    data["policy_defaults"] = {
        "mirror_root": "80_sources/repos",
        "repo_notes_dir": "80_sources/repos",
    }

    with pytest.raises(ProfileValidationError, match=r"policy_defaults\.repo_notes_dir must not overlap"):
        validate_profile_mapping(data)


def test_profile_contract_requires_folder_plan_declared_domain() -> None:
    data = minimal_profile()
    data["folder_plan"] = [{"path": "00_inbox", "domain": "missing"}]

    with pytest.raises(ProfileValidationError, match=r"folder_plan\[0\]\.domain must reference"):
        validate_profile_mapping(data)


def test_profile_contract_requires_folder_plan_paths_under_domain_folder() -> None:
    data = minimal_profile()
    data["folder_plan"] = [{"path": "90_archive", "domain": "inbox"}]

    with pytest.raises(ProfileValidationError, match=r"folder_plan\[0\]\.path must be inside domains.inbox.folder"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_unsafe_domain_folder_paths() -> None:
    data = minimal_profile()
    data["domains"]["inbox"]["folder"] = "../outside"

    with pytest.raises(ProfileValidationError, match="domains.inbox.folder must stay inside the vault"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_duplicate_domain_folders() -> None:
    data = minimal_profile()
    data["domains"]["triage"] = {"folder": "00_inbox"}

    with pytest.raises(
        ProfileValidationError,
        match=r"domains\.triage\.folder duplicates domains\.inbox\.folder",
    ):
        validate_profile_mapping(data)


def test_profile_contract_rejects_nested_domain_folders() -> None:
    data = minimal_profile()
    data["domains"]["questions"] = {"folder": "00_inbox/questions"}

    with pytest.raises(
        ProfileValidationError,
        match=r"domains\.inbox\.folder must not overlap domains\.questions\.folder",
    ):
        validate_profile_mapping(data)


def test_profile_contract_rejects_unsafe_benchmark_task_paths() -> None:
    data = minimal_profile()
    data["benchmark_tasks"] = ["../private/tasks.yml"]

    with pytest.raises(ProfileValidationError, match="benchmark_tasks entry must stay inside the vault"):
        validate_profile_mapping(data)


def test_profile_contract_requires_benchmark_task_yaml_paths() -> None:
    data = minimal_profile()
    data["benchmark_tasks"] = ["_meta/tasks.json"]

    with pytest.raises(ProfileValidationError, match="benchmark_tasks entries must be .yml or .yaml"):
        validate_profile_mapping(data)


def test_profile_contract_accepts_safe_profile_artifact_paths() -> None:
    data = minimal_profile()
    data["templates"] = ["_templates/base-note.md"]
    data["views"] = ["Documents.base"]
    data["skills"] = ["skills/review.md"]

    validate_profile_mapping(data)


def test_profile_contract_rejects_unsafe_template_paths() -> None:
    data = minimal_profile()
    data["templates"] = ["../private/template.md"]

    with pytest.raises(ProfileValidationError, match="templates entry must stay inside the vault"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_reserved_view_paths() -> None:
    data = minimal_profile()
    data["views"] = ["_meta/private.base"]

    with pytest.raises(ProfileValidationError, match="views entry contains a reserved path component"):
        validate_profile_mapping(data)


def test_profile_contract_rejects_duplicate_skill_paths() -> None:
    data = minimal_profile()
    data["skills"] = ["skills/review.md", "skills/review.md"]

    with pytest.raises(ProfileValidationError, match="skills entries must not contain duplicates"):
        validate_profile_mapping(data)


@pytest.mark.parametrize(
    ("field", "path"),
    [
        ("templates", "_generated/templates/base-note.md"),
        ("views", "_generated/Documents.base"),
        ("skills", "_generated/skills/review.md"),
        ("benchmark_tasks", "_generated/benchmarks/tasks.yml"),
    ],
)
def test_profile_contract_rejects_artifacts_under_profile_mirror_root(field: str, path: str) -> None:
    data = minimal_profile()
    data["policy_defaults"]["mirror_root"] = "_generated"
    data[field] = [path]

    with pytest.raises(
        ProfileValidationError,
        match=rf"{field} entry must not overlap policy_defaults\.mirror_root",
    ):
        validate_profile_mapping(data)


def test_profile_migration_directory_plan_uses_folder_plan_paths() -> None:
    data = minimal_profile()
    data["domains"]["archive"] = {"folder": "90_archive"}
    data["folder_plan"].append({"path": "00_inbox/questions", "domain": "inbox"})
    profile = ProfileContract.from_mapping(data)

    paths = {path.as_posix() for path in target_dir_paths(profile)}

    assert "00_inbox" in paths
    assert "00_inbox/questions" in paths
    assert "90_archive" not in paths
    assert "_meta" in paths


def test_profile_migration_directory_plan_uses_profile_mirror_root_default() -> None:
    data = minimal_profile()
    data["policy_defaults"] = {"mirror_root": "_generated"}
    profile = ProfileContract.from_mapping(data)

    paths = {path.as_posix() for path in target_dir_paths(profile)}

    assert "_generated" in paths
    assert "_mirrors" not in paths


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


def test_profile_cli_views_check_current_initialized_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init = run_cli("init", "--profile", "business-operations", str(vault))
    assert init.returncode == 0, init.stderr

    check = run_cli("--root", str(vault), "profile", "views", "--check", "--json")

    assert check.returncode == 0, check.stderr
    payload = json.loads(check.stdout)
    assert payload["summary"] == {"actions": 0, "blockers": 0, "up_to_date": True, "views": 1}
    assert payload["views"][0]["path"] == "Documents.base"
    assert payload["views"][0]["state"] == "current"


def test_profile_cli_views_write_regenerates_stale_documents_base(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init = run_cli("init", "--profile", "business-operations", str(vault))
    assert init.returncode == 0, init.stderr
    documents_base = vault / "Documents.base"
    documents_base.write_text("views: []\n", encoding="utf-8")

    check = run_cli("--root", str(vault), "profile", "views", "--check", "--json")
    assert check.returncode == 1
    check_payload = json.loads(check.stdout)
    assert check_payload["actions"][0]["action"] == "write-view"
    assert check_payload["actions"][0]["path"] == "Documents.base"
    assert check_payload["views"][0]["state"] == "stale"

    write = run_cli("--root", str(vault), "profile", "views", "--write", "--json")

    assert write.returncode == 0, write.stderr
    payload = json.loads(write.stdout)
    assert payload["write"]["summary"]["written"] == 1
    assert payload["plan"]["summary"]["up_to_date"] is True
    profile = load_profile(vault / "_meta" / "profile.yml")
    assert documents_base.read_text(encoding="utf-8") == render_documents_base(profile)


def test_profile_view_generation_omits_absent_mirror_views() -> None:
    data = minimal_profile()
    data["required_properties"] = ["title", "type", "status", "domain", "updated"]
    data["optional_properties"] = ["owner"]
    data["note_types"] = {"note": {"purpose": "general note"}}
    data["statuses"] = {"queued": {"purpose": "pending"}, "done": {"purpose": "complete"}}
    data["views"] = ["Documents.base"]
    profile = ProfileContract.from_mapping(data)

    rendered = render_documents_base(profile)

    assert "By domain" in rendered
    assert "Office mirrors" not in rendered
    assert "Repos" not in rendered
    assert "queued" not in rendered


def test_profile_view_generation_uses_status_attention_flags() -> None:
    data = minimal_profile()
    data["required_properties"] = ["title", "type", "status", "domain", "updated"]
    data["note_types"] = {"note": {"purpose": "general note"}}
    data["statuses"] = {
        "queued": {"purpose": "pending review", "attention": True},
        "draft": {"purpose": "ordinary draft, not an attention state"},
        "done": {"purpose": "complete", "inactive": True},
    }
    data["views"] = ["Documents.base"]
    profile = ProfileContract.from_mapping(data)

    rendered = render_documents_base(profile)

    assert "Needs attention" in rendered
    assert 'status == "queued"' in rendered
    assert 'status == "draft"' not in rendered
    assert 'status == "done"' not in rendered


def test_profile_contract_rejects_unsafe_view_paths() -> None:
    data = minimal_profile()
    data["views"] = ["../Documents.base"]

    with pytest.raises(ProfileValidationError, match="views entry must stay inside the vault"):
        validate_profile_mapping(data)


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


def test_profile_cli_migrate_plan_bootstraps_missing_profile_contract(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init = run_cli("init", "--profile", "business-operations", str(vault))
    assert init.returncode == 0, init.stderr
    (vault / "_meta" / "profile.yml").unlink()

    plan = run_cli("--root", str(vault), "profile", "migrate", "--plan", "--json")

    assert plan.returncode == 0, plan.stderr
    payload = json.loads(plan.stdout)
    assert payload["profile_id"] == "business-operations"
    assert payload["current_version"] is None
    assert payload["target_version"] == "0.1.0"
    assert {
        "field": "_meta/profile.yml",
        "kind": "missing",
        "target": "0.1.0",
    } in payload["differences"]
    assert any(
        action["action"] == "copy-template-file" and action["path"] == "_meta/profile.yml"
        for action in payload["actions"]
    )
    assert not (vault / "_meta" / "profile.yml").exists()


def test_profile_cli_migrate_write_bootstraps_missing_profile_without_overwrites(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    init = run_cli("init", "--profile", "business-operations", str(vault))
    assert init.returncode == 0, init.stderr
    source = vault / "40_delivery" / "private-plan.docx"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"private source bytes must not change")
    index = vault / "INDEX.md"
    custom_index = "# Custom operator index\n\nKeep this local note.\n"
    index.write_text(custom_index, encoding="utf-8")
    (vault / "_meta" / "profile.yml").unlink()
    (vault / "Documents.base").unlink()
    shutil.rmtree(vault / "70_people")

    write = run_cli("--root", str(vault), "profile", "migrate", "--write", "--json")

    assert write.returncode == 0, write.stderr
    payload = json.loads(write.stdout)
    written_paths = {item["path"] for item in payload["write"]["written"]}
    skipped = {(item["action"], item["path"]) for item in payload["write"]["skipped"]}
    assert "_meta/profile.yml" in written_paths
    assert "Documents.base" in written_paths
    assert "70_people" in written_paths
    assert ("review-template-drift", "INDEX.md") in skipped
    assert payload["write"]["summary"]["errors"] == 0
    assert load_profile(vault / "_meta" / "profile.yml").id == "business-operations"
    assert (vault / "Documents.base").exists()
    assert (vault / "70_people").is_dir()
    assert index.read_text(encoding="utf-8") == custom_index
    assert source.read_bytes() == b"private source bytes must not change"

    validation = run_cli("--root", str(vault), "profile", "validate")
    assert validation.returncode == 0, validation.stderr


def test_profile_cli_migrate_write_skips_template_drift(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init = run_cli("init", "--profile", "business-operations", str(vault))
    assert init.returncode == 0, init.stderr
    index = vault / "INDEX.md"
    custom_index = "# Custom operator index\n"
    index.write_text(custom_index, encoding="utf-8")

    write = run_cli("--root", str(vault), "profile", "migrate", "--write", "--json")

    assert write.returncode == 0, write.stderr
    payload = json.loads(write.stdout)
    assert payload["write"]["summary"]["written"] == 0
    assert payload["write"]["summary"]["errors"] == 0
    assert {
        "action": "review-template-drift",
        "path": "INDEX.md",
        "detail": "manual review required; existing files are not overwritten",
    } in payload["write"]["skipped"]
    assert index.read_text(encoding="utf-8") == custom_index


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
        "folder_plan": [{"path": "00_inbox", "domain": "inbox"}],
        "templates": [],
        "views": [],
        "skills": [],
        "benchmark_tasks": [],
        "policy_defaults": {},
    }
