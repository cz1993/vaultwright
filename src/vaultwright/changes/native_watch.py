# SPDX-License-Identifier: AGPL-3.0-or-later
"""Optional native filesystem watch adapter for journaled materialization."""
from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any

from vaultwright.changes import feed
from vaultwright.runtime_profile import profile_content_roots


class NativeWatchError(ValueError):
    """Raised when native watch capture cannot be started."""


class WatchdogUnavailable(NativeWatchError):
    """Raised when the optional watchdog dependency is not installed."""


def source_watch_roots(root: Path) -> list[Path]:
    """Return existing configured source roots to observe."""

    root = root.expanduser().resolve()
    roots: list[Path] = []
    for rel in sorted(profile_content_roots(root)):
        path = root / rel
        if path.exists() and path.is_dir():
            roots.append(path)
    return roots


def _rel(root: Path, path: str | Path | None) -> str | None:
    if path is None:
        return None
    candidate = Path(path).expanduser().resolve(strict=False)
    try:
        return candidate.relative_to(root.expanduser().resolve()).as_posix()
    except ValueError:
        return None


def event_to_observed_change(root: Path, event: Any) -> feed.ObservedChange | None:
    """Map a watchdog-like event object to an observed change hint."""

    if bool(getattr(event, "is_directory", False)):
        return None
    event_type = str(getattr(event, "event_type", "") or "")
    current = _rel(root, getattr(event, "src_path", None))
    previous = None
    if event_type == "moved":
        previous = current
        current = _rel(root, getattr(event, "dest_path", None))
        kind = "moved"
    elif event_type == "created":
        kind = "created"
    elif event_type == "deleted":
        kind = "deleted"
        previous = current
        current = None
    elif event_type in {"modified", "closed", "opened"}:
        kind = "modified"
    else:
        return None
    if current is None and previous is None:
        return None
    return feed.ObservedChange(kind, current_path=current, previous_path=previous)


class BufferedNativeEventHandler:
    """Thread-safe buffer around watchdog file events."""

    def __init__(self, root: Path, base_handler: type[Any]) -> None:
        self.root = root.expanduser().resolve()
        self._events: list[feed.ObservedChange] = []
        self._lock = Lock()
        self.handler = self._build_handler(base_handler)

    def _build_handler(self, base_handler: type[Any]) -> Any:
        outer = self

        class Handler(base_handler):  # type: ignore[misc, valid-type]
            def on_any_event(self, event: Any) -> None:
                observed = event_to_observed_change(outer.root, event)
                if observed is None:
                    return
                with outer._lock:
                    outer._events.append(observed)

        return Handler()

    def drain(self) -> list[feed.ObservedChange]:
        with self._lock:
            events = list(self._events)
            self._events.clear()
        return events


def build_watchdog_observer(root: Path) -> tuple[Any, BufferedNativeEventHandler, list[Path]]:
    """Create a watchdog observer scheduled on configured source roots."""

    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError as exc:
        raise WatchdogUnavailable("install the optional watch extra: vaultwright[watch]") from exc

    roots = source_watch_roots(root)
    if not roots:
        raise NativeWatchError("no configured source roots exist to watch")
    observer = Observer()
    handler = BufferedNativeEventHandler(root, FileSystemEventHandler)
    for path in roots:
        observer.schedule(handler.handler, str(path), recursive=True)
    return observer, handler, roots
