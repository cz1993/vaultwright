# SPDX-License-Identifier: AGPL-3.0-or-later
"""Deterministic file-stability checks for changed-source candidates."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from time import monotonic, sleep as time_sleep
from typing import Callable

from vaultwright.changes import fingerprint
from vaultwright.changes.events import JournalEventError, normalize_vault_relative_path

DEFAULT_SETTLE_SECONDS = 1.0
DEFAULT_CHECK_INTERVAL_SECONDS = 0.25
DEFAULT_TIMEOUT_SECONDS = 10.0


class StabilityError(ValueError):
    """Raised when stability settings or paths are unsafe."""


@dataclass(frozen=True)
class StabilityResult:
    path: str
    stable: bool
    timed_out: bool
    observations: int
    elapsed_seconds: float
    stable_seconds: float
    fingerprint_token: str
    exists: bool
    is_file: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


FingerprintFunc = Callable[[Path, str | Path], fingerprint.MetadataFingerprint]
ClockFunc = Callable[[], float]
SleepFunc = Callable[[float], None]


def _validate_timing(settle_seconds: float, check_interval_seconds: float, timeout_seconds: float) -> None:
    if settle_seconds < 0:
        raise StabilityError("settle_seconds must be non-negative")
    if check_interval_seconds <= 0:
        raise StabilityError("check_interval_seconds must be positive")
    if timeout_seconds < 0:
        raise StabilityError("timeout_seconds must be non-negative")


def _result(
    *,
    path: str,
    stable: bool,
    timed_out: bool,
    observations: int,
    elapsed_seconds: float,
    stable_seconds: float,
    current: fingerprint.MetadataFingerprint,
) -> StabilityResult:
    return StabilityResult(
        path=path,
        stable=stable,
        timed_out=timed_out,
        observations=observations,
        elapsed_seconds=round(max(0.0, elapsed_seconds), 6),
        stable_seconds=round(max(0.0, stable_seconds), 6),
        fingerprint_token=current.token(),
        exists=current.exists,
        is_file=current.is_file,
    )


def wait_for_file_stability(
    root: Path,
    path: str | Path,
    *,
    settle_seconds: float = DEFAULT_SETTLE_SECONDS,
    check_interval_seconds: float = DEFAULT_CHECK_INTERVAL_SECONDS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    fingerprint_func: FingerprintFunc = fingerprint.metadata_fingerprint,
    clock: ClockFunc = monotonic,
    sleeper: SleepFunc = time_sleep,
) -> StabilityResult:
    """Poll a candidate path until its cheap fingerprint is stable.

    Watcher delivery is advisory, so this helper intentionally depends on the same cheap
    metadata fingerprint used for candidate filtering. Tests can inject the fingerprint, clock,
    and sleeper so correctness does not depend on real filesystem notification timing.
    """

    _validate_timing(settle_seconds, check_interval_seconds, timeout_seconds)
    try:
        rel = normalize_vault_relative_path(path, field="path")
    except JournalEventError as exc:
        raise StabilityError(str(exc)) from exc
    assert rel is not None

    start = clock()
    deadline = start + timeout_seconds
    current = fingerprint_func(root, rel)
    observations = 1
    stable_since = start
    if settle_seconds == 0:
        return _result(
            path=rel,
            stable=True,
            timed_out=False,
            observations=observations,
            elapsed_seconds=0.0,
            stable_seconds=0.0,
            current=current,
        )

    while True:
        now = clock()
        if now >= deadline:
            return _result(
                path=rel,
                stable=False,
                timed_out=True,
                observations=observations,
                elapsed_seconds=now - start,
                stable_seconds=now - stable_since,
                current=current,
            )
        sleeper(min(check_interval_seconds, max(0.0, deadline - now)))
        now = clock()
        observed = fingerprint_func(root, rel)
        observations += 1
        if observed.token() != current.token():
            current = observed
            stable_since = now
            continue
        stable_for = now - stable_since
        if stable_for >= settle_seconds:
            return _result(
                path=rel,
                stable=True,
                timed_out=False,
                observations=observations,
                elapsed_seconds=now - start,
                stable_seconds=stable_for,
                current=current,
            )
