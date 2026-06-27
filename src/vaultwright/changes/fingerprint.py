# SPDX-License-Identifier: AGPL-3.0-or-later
"""Cheap source metadata fingerprints for changed-file materialization."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Callable

from vaultwright.changes.events import JournalEventError, normalize_vault_relative_path


class FingerprintError(ValueError):
    """Raised when a source fingerprint cannot be represented safely."""


@dataclass(frozen=True)
class MetadataFingerprint:
    path: str
    exists: bool
    is_file: bool
    is_symlink: bool
    size: int
    mtime_ns: int
    identity_hint: str

    def token(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


def _safe_rel(value: str | Path) -> str:
    try:
        rel = normalize_vault_relative_path(value, field="path")
    except JournalEventError as exc:
        raise FingerprintError(str(exc)) from exc
    assert rel is not None
    return rel


def metadata_fingerprint(root: Path, path: str | Path) -> MetadataFingerprint:
    rel = _safe_rel(path)
    source = root.expanduser().resolve() / rel
    try:
        stat = source.lstat()
    except FileNotFoundError:
        return MetadataFingerprint(
            path=rel,
            exists=False,
            is_file=False,
            is_symlink=False,
            size=0,
            mtime_ns=0,
            identity_hint="",
        )
    except OSError as exc:
        raise FingerprintError(f"source is not readable for fingerprinting: {rel}: {exc}") from exc

    is_symlink = source.is_symlink()
    is_file = source.is_file() and not is_symlink
    identity_hint = f"{getattr(stat, 'st_dev', 0)}:{getattr(stat, 'st_ino', 0)}"
    return MetadataFingerprint(
        path=rel,
        exists=True,
        is_file=is_file,
        is_symlink=is_symlink,
        size=int(stat.st_size),
        mtime_ns=int(stat.st_mtime_ns),
        identity_hint=identity_hint,
    )


def fingerprint_token(root: Path, path: str | Path) -> str:
    return metadata_fingerprint(root, path).token()


def fingerprint_changed(previous_token: str | None, current: MetadataFingerprint) -> bool:
    return not previous_token or previous_token != current.token()


def sha256_path(root: Path, path: str | Path) -> str:
    rel = _safe_rel(path)
    source = root.expanduser().resolve() / rel
    h = hashlib.sha256()
    try:
        with source.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                h.update(chunk)
    except OSError as exc:
        raise FingerprintError(f"source is not readable for hashing: {rel}: {exc}") from exc
    return h.hexdigest()


def hash_candidate_if_fingerprint_changed(
    root: Path,
    path: str | Path,
    previous_token: str | None,
    *,
    hash_func: Callable[[Path, str | Path], str] = sha256_path,
) -> tuple[MetadataFingerprint, str | None]:
    current = metadata_fingerprint(root, path)
    if not current.exists or not current.is_file:
        return current, None
    if not fingerprint_changed(previous_token, current):
        return current, None
    return current, hash_func(root, path)
