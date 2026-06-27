# SPDX-License-Identifier: AGPL-3.0-or-later
"""Journal event vocabulary for changed-file materialization."""
from __future__ import annotations

from pathlib import PurePosixPath

EVENT_KINDS = frozenset(
    {
        "created",
        "modified",
        "moved",
        "deleted",
        "reconcile-required",
    }
)

EVENT_STATUSES = frozenset(
    {
        "queued",
        "stabilizing",
        "ready",
        "processing",
        "applied",
        "review-required",
        "failed",
    }
)

COUNTED_STATUSES = ("queued", "processing", "failed", "review-required")


class JournalEventError(ValueError):
    """Raised when a journal event cannot be represented safely."""


def validate_event_kind(event_kind: str) -> str:
    if event_kind not in EVENT_KINDS:
        allowed = ", ".join(sorted(EVENT_KINDS))
        raise JournalEventError(f"invalid journal event kind '{event_kind}'; expected one of: {allowed}")
    return event_kind


def validate_event_status(status: str) -> str:
    if status not in EVENT_STATUSES:
        allowed = ", ".join(sorted(EVENT_STATUSES))
        raise JournalEventError(f"invalid journal event status '{status}'; expected one of: {allowed}")
    return status


def normalize_vault_relative_path(value: str | PurePosixPath | None, *, field: str) -> str | None:
    if value is None:
        return None
    raw = str(value).replace("\\", "/").strip()
    if not raw:
        raise JournalEventError(f"{field} must be a non-empty vault-relative path")
    path = PurePosixPath(raw)
    if path.is_absolute():
        raise JournalEventError(f"{field} must be vault-relative, not absolute: {raw}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise JournalEventError(f"{field} must not contain empty, current, or parent-directory parts: {raw}")
    if path.parts and path.parts[0] == ".vaultwright":
        raise JournalEventError(f"{field} must not point at local Vaultwright derived state: {raw}")
    return path.as_posix()
