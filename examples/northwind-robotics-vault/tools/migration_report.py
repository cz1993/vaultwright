#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Print a read-only migration report for legacy folders and frontmatter domains."""
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
STRUCTURAL_MD = {"AGENTS.md", "CLAUDE.md", "INDEX.md", "RETENTION.md", "CATALOG.md", "log.md"}
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


def load_domain_routing(root: Path) -> tuple[dict[str, str], dict[str, dict[str, str]], set[str], list[str]]:
    path = root / DOMAIN_MAP_REL
    if not path.exists():
        return {}, {}, set(), [f"{DOMAIN_MAP_REL.as_posix()}: missing"]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return {}, {}, set(), [f"{DOMAIN_MAP_REL.as_posix()}: invalid YAML ({exc.__class__.__name__})"]
    domains = data.get("domains")
    if not isinstance(domains, dict) or not domains:
        return {}, {}, set(), [f"{DOMAIN_MAP_REL.as_posix()}: missing domains map"]

    canonical: dict[str, str] = {}
    aliases: dict[str, dict[str, str]] = {}
    canonical_domains: set[str] = set()
    errors: list[str] = []
    for domain, info in domains.items():
        if not isinstance(info, dict) or not info.get("folder"):
            errors.append(f"{DOMAIN_MAP_REL.as_posix()}:{domain}: missing folder")
            continue
        domain_name = str(domain)
        folder = str(info["folder"])
        canonical_domains.add(domain_name)
        canonical[folder] = domain_name
        for key in (domain_name, folder):
            aliases[key] = {"domain": domain_name, "folder": folder}
        raw_aliases = info.get("aliases", [])
        if isinstance(raw_aliases, list):
            for alias in raw_aliases:
                if isinstance(alias, str) and alias.strip():
                    aliases[alias.strip()] = {"domain": domain_name, "folder": folder}
    return canonical, aliases, canonical_domains, errors


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


def excluded_rel(rel: Path) -> bool:
    return any(part in RESERVED_TOP_LEVEL or part.startswith(".") for part in rel.parts)


def split_frontmatter(text: str) -> tuple[dict | None, str]:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            try:
                data = yaml.safe_load(text[3:end].lstrip("\n")) or {}
            except yaml.YAMLError:
                return None, text
            return data if isinstance(data, dict) else None, text[end + 4:]
    return {}, text


def frontmatter_domain_items(root: Path, aliases: dict[str, dict[str, str]], canonical_domains: set[str]) -> list[dict]:
    items: list[dict] = []
    for path in sorted(root.rglob("*.md"), key=lambda p: p.relative_to(root).as_posix()):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root)
        if excluded_rel(rel) or path.name in STRUCTURAL_MD:
            continue
        fm, _body = split_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
        if not isinstance(fm, dict):
            continue
        raw_domain = fm.get("domain")
        if raw_domain in (None, ""):
            continue
        current_domain = str(raw_domain)
        if current_domain in canonical_domains:
            continue
        alias = aliases.get(current_domain)
        if alias:
            kind = "frontmatter_domain_alias"
            recommended_domain = alias["domain"]
            recommended_folder = alias["folder"]
            action = (
                f"Review, then update frontmatter `domain: {recommended_domain}` and move the note "
                f"under {recommended_folder}/ if ownership belongs there."
            )
        else:
            kind = "frontmatter_domain_unknown"
            recommended_domain = ""
            recommended_folder = ""
            action = (
                "Review whether the domain should map to an existing canonical domain or be added to "
                "_meta/domain-map.yml before moving the note."
            )
        items.append({
            "kind": kind,
            "path": rel.as_posix(),
            "current_domain": current_domain,
            "recommended_domain": recommended_domain,
            "recommended_folder": recommended_folder,
            "current_folder": rel.parts[0] if rel.parts else "",
            "action": action,
        })
    return items


def build_report(root: Path) -> tuple[list[dict], list[dict], list[str], list[str]]:
    canonical, aliases, canonical_domains, errors = load_domain_routing(root)
    if errors:
        return [], [], [], errors

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
    return items, frontmatter_domain_items(root, aliases, canonical_domains), warnings, []


def summary_counts(items: list[dict]) -> dict[str, int]:
    return {
        "total": len(items),
        "alias": sum(1 for item in items if item["kind"] == "alias_folder"),
        "unknown": sum(1 for item in items if item["kind"] == "unknown_folder"),
    }


def frontmatter_summary_counts(items: list[dict]) -> dict[str, int]:
    return {
        "total": len(items),
        "alias": sum(1 for item in items if item["kind"] == "frontmatter_domain_alias"),
        "unknown": sum(1 for item in items if item["kind"] == "frontmatter_domain_unknown"),
    }


def print_human(root: Path, items: list[dict], frontmatter_items: list[dict], warnings: list[str], errors: list[str]) -> None:
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
    else:
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

    frontmatter_summary = frontmatter_summary_counts(frontmatter_items)
    if not frontmatter_items:
        print("migration: no legacy frontmatter domains found")
        return
    print(
        "migration: "
        f"{frontmatter_summary['total']} note frontmatter domains need review "
        f"(alias={frontmatter_summary['alias']}, unknown={frontmatter_summary['unknown']})"
    )
    for item in frontmatter_items:
        target = item["recommended_domain"] or "manual classification"
        print(f"  [{item['kind']}] {item['path']}: {item['current_domain']} -> {target}")
        if item["recommended_folder"]:
            print(f"    folder: {item['recommended_folder']}")
        print(f"    action: {item['action']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print a read-only Vaultwright folder migration report.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable migration JSON.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    items, frontmatter_items, warnings, errors = build_report(ROOT)
    if args.json:
        print(json.dumps({
            "root": str(ROOT),
            "summary": summary_counts(items),
            "frontmatter_summary": frontmatter_summary_counts(frontmatter_items),
            "items": items,
            "frontmatter_items": frontmatter_items,
            "warnings": warnings,
            "errors": errors,
        }, indent=2, sort_keys=True))
    else:
        print_human(ROOT, items, frontmatter_items, warnings, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
