#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Print a read-only migration report for legacy top-level folders."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pip install pyyaml")


ROOT = Path(__file__).resolve().parent.parent
DOMAIN_MAP_REL = Path("_meta/domain-map.yml")
SOURCE_EXTS = {".docx", ".pptx", ".xlsx", ".doc", ".pdf"}
RESERVED_TOP_LEVEL = {
    ".git",
    ".githooks",
    ".github",
    ".obsidian",
    "_archive",
    "_fixtures",
    "_meta",
    "_mirrors",
    "_templates",
    "_tmp",
    "node_modules",
    "tools",
}


def load_domain_routing(root: Path) -> tuple[dict[str, str], dict[str, dict[str, str]], list[str]]:
    path = root / DOMAIN_MAP_REL
    if not path.exists():
        return {}, {}, [f"{DOMAIN_MAP_REL.as_posix()}: missing"]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return {}, {}, [f"{DOMAIN_MAP_REL.as_posix()}: invalid YAML ({exc.__class__.__name__})"]
    domains = data.get("domains")
    if not isinstance(domains, dict) or not domains:
        return {}, {}, [f"{DOMAIN_MAP_REL.as_posix()}: missing domains map"]

    canonical: dict[str, str] = {}
    aliases: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    for domain, info in domains.items():
        if not isinstance(info, dict) or not info.get("folder"):
            errors.append(f"{DOMAIN_MAP_REL.as_posix()}:{domain}: missing folder")
            continue
        domain_name = str(domain)
        folder = str(info["folder"])
        canonical[folder] = domain_name
        for key in (domain_name, folder):
            aliases[key] = {"domain": domain_name, "folder": folder}
        raw_aliases = info.get("aliases", [])
        if isinstance(raw_aliases, list):
            for alias in raw_aliases:
                if isinstance(alias, str) and alias.strip():
                    aliases[alias.strip()] = {"domain": domain_name, "folder": folder}
    return canonical, aliases, errors


def folder_counts(path: Path) -> dict[str, int]:
    counts = {"files": 0, "dirs": 0, "markdown": 0, "office": 0}
    for child in path.rglob("*"):
        if child.is_symlink():
            continue
        if child.is_dir():
            counts["dirs"] += 1
            continue
        if not child.is_file():
            continue
        counts["files"] += 1
        suffix = child.suffix.lower()
        if suffix == ".md":
            counts["markdown"] += 1
        if suffix in SOURCE_EXTS:
            counts["office"] += 1
    return counts


def should_ignore_top_level(path: Path, canonical_folders: set[str]) -> bool:
    name = path.name
    return name in RESERVED_TOP_LEVEL or name in canonical_folders


def build_report(root: Path) -> tuple[list[dict], list[str], list[str]]:
    canonical, aliases, errors = load_domain_routing(root)
    if errors:
        return [], [], errors

    items: list[dict] = []
    warnings: list[str] = []
    canonical_folders = set(canonical)
    for path in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_dir() or path.is_symlink():
            continue
        if should_ignore_top_level(path, canonical_folders):
            continue
        alias = aliases.get(path.name)
        counts = folder_counts(path)
        if path.name.startswith((".", "_")):
            warnings.append(f"{path.name}: non-reserved hidden/underscore folder reported for review")
        if alias and alias["folder"] != path.name:
            items.append({
                "kind": "alias_folder",
                "folder": path.name,
                "domain": alias["domain"],
                "recommended_folder": alias["folder"],
                "counts": counts,
                "action": (
                    f"Review, then move contents into {alias['folder']}/; update links/frontmatter; "
                    "remove the old folder only after backup review."
                ),
            })
        else:
            items.append({
                "kind": "unknown_folder",
                "folder": path.name,
                "domain": "",
                "recommended_folder": "",
                "counts": counts,
                "action": (
                    "Review whether this belongs under an existing canonical folder or should be "
                    "documented in _meta/domain-map.yml before ingestion."
                ),
            })
    return items, warnings, []


def summary_counts(items: list[dict]) -> dict[str, int]:
    return {
        "total": len(items),
        "alias": sum(1 for item in items if item["kind"] == "alias_folder"),
        "unknown": sum(1 for item in items if item["kind"] == "unknown_folder"),
    }


def print_human(root: Path, items: list[dict], warnings: list[str], errors: list[str]) -> None:
    print(f"vaultwright migration: {root}")
    print("migration: dry-run only; no files were moved")
    for warning in warnings:
        print(f"  warning: {warning}")
    for error in errors:
        print(f"  error: {error}", file=sys.stderr)
    if errors:
        return
    summary = summary_counts(items)
    if not items:
        print("migration: no legacy or unknown top-level folders found")
        return
    print(
        "migration: "
        f"{summary['total']} top-level folders need review "
        f"(alias={summary['alias']}, unknown={summary['unknown']})"
    )
    for item in items:
        target = item["recommended_folder"] or "manual classification"
        print(f"  [{item['kind']:<14}] {item['folder']} -> {target}")
        if item["domain"]:
            print(f"    domain: {item['domain']}")
        counts = item["counts"]
        print(
            "    contents: "
            f"files={counts['files']}, dirs={counts['dirs']}, "
            f"markdown={counts['markdown']}, office={counts['office']}"
        )
        print(f"    action: {item['action']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print a read-only Vaultwright folder migration report.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable migration JSON.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    items, warnings, errors = build_report(ROOT)
    if args.json:
        print(json.dumps({
            "root": str(ROOT),
            "summary": summary_counts(items),
            "items": items,
            "warnings": warnings,
            "errors": errors,
        }, indent=2, sort_keys=True))
    else:
        print_human(ROOT, items, warnings, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
