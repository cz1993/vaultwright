# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path
import importlib.util

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "template" / "_meta" / "lifecycle-states.yml"
REQUIRED_FIELDS = {
    "entry_condition",
    "explanation",
    "permitted_next_actions",
    "exit_condition",
}
TRANSITION_STATES = {"regenerated", "reviewed"}


def load_tool_module(filename: str):
    spec = importlib.util.spec_from_file_location(
        f"{Path(filename).stem}_for_lifecycle_contract_test",
        ROOT / "template" / "tools" / filename,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_contract() -> dict:
    data = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def assert_state_contract(section: str, states: dict) -> None:
    assert states, section
    for state, contract in states.items():
        assert isinstance(contract, dict), f"{section}.{state}"
        assert REQUIRED_FIELDS.issubset(contract), f"{section}.{state}"
        for field in REQUIRED_FIELDS.difference({"permitted_next_actions"}):
            assert isinstance(contract[field], str) and contract[field].strip(), (
                f"{section}.{state}.{field}"
            )
        actions = contract["permitted_next_actions"]
        assert isinstance(actions, list) and actions, f"{section}.{state}.permitted_next_actions"
        assert all(isinstance(action, str) and action.strip() for action in actions), (
            f"{section}.{state}.permitted_next_actions"
        )
        assert isinstance(contract.get("manifest_state"), bool), f"{section}.{state}.manifest_state"


def test_lifecycle_contract_covers_sync_and_report_states() -> None:
    office_sync = load_tool_module("sync_office_md.py")
    repo_sync = load_tool_module("sync_github_repos.py")
    conversion = load_tool_module("conversion_report.py")
    m365 = load_tool_module("m365_report.py")

    data = load_contract()
    assert data["schema_version"] == 1
    office_states = data["office"]
    repo_states = data["repo"]
    assert_state_contract("office", office_states)
    assert_state_contract("repo", repo_states)

    expected_office = (
        set(office_sync.LIFECYCLE_GUIDANCE)
        | set(conversion.CLEAN_STATES)
        | set(conversion.HIGH_RISK_STATES)
        | {"source_changed", "converter_changed", "stale"}
        | TRANSITION_STATES
    )
    expected_repo = (
        set(repo_sync.LIFECYCLE_GUIDANCE)
        | {"clean", "stale"}
        | {
            state
            for state in m365.REVIEW_STATES
            if state.startswith("repo_")
            or state in {"conflict", "error", "manual_modification", "stale", "unreachable"}
        }
        | TRANSITION_STATES
    )

    assert expected_office <= set(office_states), sorted(expected_office.difference(office_states))
    assert expected_repo <= set(repo_states), sorted(expected_repo.difference(repo_states))

    manifest_office = {state for state, contract in office_states.items() if contract["manifest_state"]}
    manifest_repo = {state for state, contract in repo_states.items() if contract["manifest_state"]}
    assert TRANSITION_STATES.isdisjoint(manifest_office)
    assert TRANSITION_STATES.isdisjoint(manifest_repo)
