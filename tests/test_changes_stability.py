# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

import pytest

from vaultwright.changes.fingerprint import MetadataFingerprint
from vaultwright.changes.stability import StabilityError, wait_for_file_stability


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def fp(path: str, *, size: int, mtime_ns: int) -> MetadataFingerprint:
    return MetadataFingerprint(
        path=path,
        exists=True,
        is_file=True,
        is_symlink=False,
        size=size,
        mtime_ns=mtime_ns,
        identity_hint="1:1",
    )


def sequenced_fingerprints(items: list[MetadataFingerprint]):
    calls: list[str] = []

    def fingerprint_func(_root: Path, path: str | Path) -> MetadataFingerprint:
        calls.append(str(path))
        index = min(len(calls) - 1, len(items) - 1)
        return items[index]

    return fingerprint_func, calls


def test_wait_for_file_stability_requires_repeated_stable_observations(tmp_path: Path) -> None:
    clock = FakeClock()
    stable = fp("10_sources/brief.docx", size=12, mtime_ns=100)
    fingerprint_func, calls = sequenced_fingerprints([stable, stable, stable])

    result = wait_for_file_stability(
        tmp_path,
        "10_sources/brief.docx",
        settle_seconds=1.0,
        check_interval_seconds=0.5,
        timeout_seconds=3.0,
        fingerprint_func=fingerprint_func,
        clock=clock,
        sleeper=clock.sleep,
    )

    assert result.stable is True
    assert result.timed_out is False
    assert result.observations == 3
    assert result.elapsed_seconds == 1.0
    assert result.stable_seconds == 1.0
    assert calls == ["10_sources/brief.docx"] * 3


def test_wait_for_file_stability_resets_after_metadata_change(tmp_path: Path) -> None:
    clock = FakeClock()
    first = fp("10_sources/brief.docx", size=12, mtime_ns=100)
    changed = fp("10_sources/brief.docx", size=18, mtime_ns=200)
    fingerprint_func, _calls = sequenced_fingerprints([first, changed, changed, changed])

    result = wait_for_file_stability(
        tmp_path,
        "10_sources/brief.docx",
        settle_seconds=1.0,
        check_interval_seconds=0.5,
        timeout_seconds=3.0,
        fingerprint_func=fingerprint_func,
        clock=clock,
        sleeper=clock.sleep,
    )

    assert result.stable is True
    assert result.observations == 4
    assert result.elapsed_seconds == 1.5
    assert result.stable_seconds == 1.0
    assert result.fingerprint_token == changed.token()


def test_wait_for_file_stability_times_out_when_metadata_keeps_changing(tmp_path: Path) -> None:
    clock = FakeClock()
    first = fp("10_sources/brief.docx", size=12, mtime_ns=100)
    second = fp("10_sources/brief.docx", size=18, mtime_ns=200)
    calls: list[str] = []

    def alternating_fingerprint(_root: Path, path: str | Path) -> MetadataFingerprint:
        calls.append(str(path))
        return first if len(calls) % 2 else second

    result = wait_for_file_stability(
        tmp_path,
        "10_sources/brief.docx",
        settle_seconds=0.75,
        check_interval_seconds=0.5,
        timeout_seconds=1.0,
        fingerprint_func=alternating_fingerprint,
        clock=clock,
        sleeper=clock.sleep,
    )

    assert result.stable is False
    assert result.timed_out is True
    assert result.observations == 3
    assert result.elapsed_seconds == 1.0
    assert calls == ["10_sources/brief.docx"] * 3


def test_wait_for_file_stability_rejects_unsafe_paths(tmp_path: Path) -> None:
    with pytest.raises(StabilityError, match="parent-directory"):
        wait_for_file_stability(tmp_path, "../outside.docx")
