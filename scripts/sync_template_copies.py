#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Check or refresh repository copies derived from the canonical template.

The root `template/` directory is the source of truth. The packaged template under
`src/vaultwright/template/` must match it exactly, while example vaults keep their local
`tools/repos.yml` but otherwise inherit every file from `template/tools/`.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


IGNORED_PARTS = {"__pycache__"}
IGNORED_SUFFIXES = {".pyc"}
EXAMPLE_ALLOWED_EXTRA_TOOL_FILES = {"repos.yml"}


@dataclass(frozen=True)
class Drift:
    scope: str
    kind: str
    rel: str

    def line(self) -> str:
        return f"{self.scope}: {self.kind}: {self.rel}"


def ignored(rel: Path) -> bool:
    return bool(IGNORED_PARTS.intersection(rel.parts)) or rel.suffix in IGNORED_SUFFIXES


def files_under(root: Path) -> dict[str, Path]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*"))
        if path.is_file() and not ignored(path.relative_to(root))
    }


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def executable_bits(path: Path) -> int:
    return path.stat().st_mode & 0o111


def file_drift_kind(source: Path, target: Path) -> str | None:
    if source.read_bytes() != target.read_bytes():
        return "differs"
    if executable_bits(source) != executable_bits(target):
        return "mode differs"
    return None


def prune_empty_dirs(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass


def sync_exact_tree(source: Path, target: Path, scope: str, write: bool) -> list[Drift]:
    drifts: list[Drift] = []
    source_files = files_under(source)
    target_files = files_under(target)

    for rel, source_path in source_files.items():
        target_path = target / rel
        if rel not in target_files:
            drifts.append(Drift(scope, "missing", rel))
            if write:
                copy_file(source_path, target_path)
        else:
            kind = file_drift_kind(source_path, target_path)
            if not kind:
                continue
            drifts.append(Drift(scope, kind, rel))
            if write:
                copy_file(source_path, target_path)

    for rel, target_path in target_files.items():
        if rel not in source_files:
            drifts.append(Drift(scope, "extra", rel))
            if write:
                target_path.unlink()

    if write:
        prune_empty_dirs(target)
    return drifts


def sync_example_tools(root: Path, write: bool) -> list[Drift]:
    template_tools = root / "template" / "tools"
    source_files = files_under(template_tools)
    drifts: list[Drift] = []

    for example in sorted((root / "examples").glob("*-vault")):
        tools_dir = example / "tools"
        scope = f"examples/{example.name}/tools"
        target_files = files_under(tools_dir)

        for rel, source_path in source_files.items():
            target_path = tools_dir / rel
            if rel not in target_files:
                drifts.append(Drift(scope, "missing", rel))
                if write:
                    copy_file(source_path, target_path)
            else:
                kind = file_drift_kind(source_path, target_path)
                if not kind:
                    continue
                drifts.append(Drift(scope, kind, rel))
                if write:
                    copy_file(source_path, target_path)

        for rel, target_path in target_files.items():
            if rel in source_files or rel in EXAMPLE_ALLOWED_EXTRA_TOOL_FILES:
                continue
            drifts.append(Drift(scope, "extra", rel))
            if write:
                target_path.unlink()

        if write:
            prune_empty_dirs(tools_dir)

    return drifts


def sync_template_copies(root: Path, write: bool) -> list[Drift]:
    drifts = sync_exact_tree(
        root / "template",
        root / "src" / "vaultwright" / "template",
        "src/vaultwright/template",
        write,
    )
    drifts.extend(sync_example_tools(root, write))
    return drifts


def validate_root(root: Path) -> None:
    if not (root / "template" / "CLAUDE.md").is_file():
        raise ValueError(f"{root} does not look like the Vaultwright repository: missing template/CLAUDE.md")
    if not (root / "template" / "tools").is_dir():
        raise ValueError(f"{root} does not look like the Vaultwright repository: missing template/tools/")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check or refresh Vaultwright template-derived copies.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root. Defaults to cwd.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Fail if copied template files drift. Default.")
    mode.add_argument("--write", action="store_true", help="Refresh copied template files in place.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = args.root.expanduser().resolve()
    write = bool(args.write)
    try:
        validate_root(root)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    drifts = sync_template_copies(root, write)

    if drifts:
        verb = "updated" if write else "drift"
        print(f"template copies: {verb} ({len(drifts)} file issue(s))")
        for drift in drifts:
            print(f"  {drift.line()}")
        if not write:
            print("Run: python3.11 scripts/sync_template_copies.py --write")
            return 1
        return 0

    print("template copies: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
