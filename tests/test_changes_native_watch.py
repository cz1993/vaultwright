# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

import yaml

from vaultwright.changes import native_watch


class FakeEvent:
    def __init__(
        self,
        event_type: str,
        src_path: Path,
        *,
        dest_path: Path | None = None,
        is_directory: bool = False,
    ) -> None:
        self.event_type = event_type
        self.src_path = str(src_path)
        self.dest_path = str(dest_path) if dest_path else ""
        self.is_directory = is_directory


def test_source_watch_roots_use_existing_legacy_content_roots(tmp_path: Path) -> None:
    (tmp_path / "40_delivery").mkdir()
    (tmp_path / "_mirrors").mkdir()

    roots = native_watch.source_watch_roots(tmp_path)

    assert roots == [(tmp_path / "40_delivery").resolve()]


def test_source_watch_roots_use_existing_profile_content_roots(tmp_path: Path) -> None:
    (tmp_path / "_meta").mkdir()
    (tmp_path / "25_research").mkdir()
    (tmp_path / "40_delivery").mkdir()
    profile = {
        "schema_version": 1,
        "id": "test-profile",
        "name": "Test Profile",
        "profile_version": "0.1.0",
        "domains": {"research": {"folder": "25_research", "purpose": "Research sources."}},
        "note_types": {"source-mirror": {"purpose": "Generated mirror.", "machine_owned": True}},
        "statuses": {"active": {"purpose": "Active material."}},
        "required_properties": ["title", "type", "status", "domain", "created", "updated"],
        "optional_properties": [],
        "folder_plan": [{"path": "25_research", "domain": "research"}],
        "templates": [],
        "views": [],
        "skills": [],
        "benchmark_tasks": [],
        "policy_defaults": {
            "original_sources_authoritative": True,
            "real_data_in_repo": False,
        },
    }
    (tmp_path / "_meta" / "profile.yml").write_text(yaml.safe_dump(profile), encoding="utf-8")

    roots = native_watch.source_watch_roots(tmp_path)

    assert roots == [(tmp_path / "25_research").resolve()]


def test_native_event_mapping_normalizes_file_events(tmp_path: Path) -> None:
    current = tmp_path / "40_delivery" / "registration.docx"
    previous = tmp_path / "40_delivery" / "old-registration.docx"
    current.parent.mkdir(parents=True)

    modified = native_watch.event_to_observed_change(
        tmp_path,
        FakeEvent("modified", current),
    )
    moved = native_watch.event_to_observed_change(
        tmp_path,
        FakeEvent("moved", previous, dest_path=current),
    )
    deleted = native_watch.event_to_observed_change(
        tmp_path,
        FakeEvent("deleted", previous),
    )

    assert modified is not None
    assert modified.event_kind == "modified"
    assert modified.current_path == "40_delivery/registration.docx"
    assert moved is not None
    assert moved.event_kind == "moved"
    assert moved.current_path == "40_delivery/registration.docx"
    assert moved.previous_path == "40_delivery/old-registration.docx"
    assert deleted is not None
    assert deleted.event_kind == "deleted"
    assert deleted.current_path is None
    assert deleted.previous_path == "40_delivery/old-registration.docx"


def test_native_event_mapping_ignores_directories_and_outside_paths(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.docx"

    assert native_watch.event_to_observed_change(
        tmp_path,
        FakeEvent("modified", tmp_path / "40_delivery", is_directory=True),
    ) is None
    assert native_watch.event_to_observed_change(
        tmp_path,
        FakeEvent("modified", outside),
    ) is None


def test_native_event_handler_buffers_and_drains_file_events(tmp_path: Path) -> None:
    current = tmp_path / "40_delivery" / "registration.docx"
    current.parent.mkdir(parents=True)

    class FakeBaseHandler:
        pass

    buffered = native_watch.BufferedNativeEventHandler(tmp_path, FakeBaseHandler)
    buffered.handler.on_any_event(FakeEvent("modified", current))
    buffered.handler.on_any_event(FakeEvent("modified", current.parent, is_directory=True))

    first = buffered.drain()
    second = buffered.drain()

    assert len(first) == 1
    assert first[0].event_kind == "modified"
    assert first[0].current_path == "40_delivery/registration.docx"
    assert second == []
