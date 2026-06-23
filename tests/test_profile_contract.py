# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path

import pytest

from vaultwright.profiles import ProfileValidationError, load_profile, validate_profile_mapping


ROOT = Path(__file__).resolve().parents[1]


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
