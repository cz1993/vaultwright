# SPDX-License-Identifier: AGPL-3.0-or-later
"""Deterministic change-feed primitives for journaled materialization."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Protocol

from vaultwright.changes import fingerprint, journal
from vaultwright.changes.events import JournalEventError, normalize_vault_relative_path, validate_event_kind
from vaultwright.runtime_profile import configured_office_mirror_root, rel_is_under, repo_notes_dirs

LOCAL_STATE_DIR = Path(".vaultwright")
OPERATIONAL_DIRS = {
    ".git",
    ".githooks",
    ".github",
    ".obsidian",
    "_meta",
    "_templates",
    "_tmp",
    "node_modules",
    "template",
    "templates",
    "tools",
}
OPERATIONAL_PREFIXES = ("_archive", "_backup", "_deprecated")
TEMP_FILE_PREFIXES = ("~$", ".~", ".#")
TEMP_FILE_SUFFIXES = (".tmp", ".swp", ".swx")


class ChangeFeed(Protocol):
    def events(self) -> Iterator["ObservedChange"]:
        """Yield observed source-change hints."""


@dataclass(frozen=True)
class ObservedChange:
    event_kind: str
    current_path: str | None = None
    previous_path: str | None = None
    observed_at: str | None = None

    def __post_init__(self) -> None:
        validate_event_kind(self.event_kind)
        if self.current_path is None and self.previous_path is None:
            raise ValueError("observed changes require a current_path or previous_path")


class StaticChangeFeed:
    """Deterministic feed for tests and one-shot orchestration."""

    def __init__(self, changes: Iterable[ObservedChange]):
        self._changes = list(changes)

    def events(self) -> Iterator[ObservedChange]:
        yield from self._changes


def _normalize_path_for_filter(root: Path, value: str | Path | None) -> str | None:
    if value is None:
        return None
    path = Path(value)
    if path.is_absolute():
        try:
            return path.resolve(strict=False).relative_to(root.expanduser().resolve()).as_posix()
        except ValueError:
            return None
    try:
        return normalize_vault_relative_path(path, field="path")
    except JournalEventError:
        return None


def ignored_reason(root: Path, value: str | Path | None) -> str | None:
    rel_text = _normalize_path_for_filter(root, value)
    if rel_text is None:
        return "outside-vault-or-unsafe"
    rel = Path(rel_text)
    if rel == LOCAL_STATE_DIR or rel_is_under(rel, LOCAL_STATE_DIR):
        return "local-state"
    mirror_root = configured_office_mirror_root(root)
    if rel == mirror_root or rel_is_under(rel, mirror_root):
        return "generated-office-mirror"
    for repo_dir in repo_notes_dirs(root):
        repo_path = Path(repo_dir)
        if rel == repo_path or rel_is_under(rel, repo_path):
            return "generated-repo-mirror"
    if any(part in OPERATIONAL_DIRS or part.startswith(OPERATIONAL_PREFIXES) for part in rel.parts):
        return "operational-directory"
    name = rel.name
    if name.startswith(TEMP_FILE_PREFIXES) or name.endswith(TEMP_FILE_SUFFIXES):
        return "temporary-file"
    if name.startswith(".") and name.endswith(".tmp"):
        return "temporary-file"
    return None


def is_ignored(root: Path, value: str | Path | None) -> bool:
    return ignored_reason(root, value) is not None


def normalize_observed_change(root: Path, change: ObservedChange) -> ObservedChange | None:
    current = _normalize_path_for_filter(root, change.current_path)
    previous = _normalize_path_for_filter(root, change.previous_path)
    if current and ignored_reason(root, current):
        return None
    if previous and ignored_reason(root, previous):
        return None
    if current is None and previous is None:
        return None
    return ObservedChange(
        event_kind=change.event_kind,
        current_path=current,
        previous_path=previous,
        observed_at=change.observed_at,
    )


def coalesce_changes(changes: Iterable[ObservedChange]) -> list[ObservedChange]:
    coalesced: dict[tuple[str | None, str | None], ObservedChange] = {}
    order: list[tuple[str | None, str | None]] = []
    for change in changes:
        key = (change.current_path, change.previous_path if change.event_kind == "moved" else None)
        if key not in coalesced:
            order.append(key)
        coalesced[key] = change
    return [coalesced[key] for key in order]


def queue_feed_events(root: Path, feed: ChangeFeed) -> list[int]:
    normalized = [
        change
        for change in (normalize_observed_change(root, event) for event in feed.events())
        if change is not None
    ]
    sequences: list[int] = []
    for change in coalesce_changes(normalized):
        fingerprint_token = ""
        if change.current_path:
            fingerprint_token = fingerprint.fingerprint_token(root, change.current_path)
        sequences.append(
            journal.record_event(
                root,
                change.event_kind,
                current_path=change.current_path,
                previous_path=change.previous_path,
                metadata_fingerprint=fingerprint_token,
                observed_at=change.observed_at,
            )
        )
    return sequences
