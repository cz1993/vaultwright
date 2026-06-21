#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate a source-path-only Vaultwright documentation catalog."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pip install pyyaml")


ROOT = Path(__file__).resolve().parent.parent
DOMAIN_MAP = Path("_meta/domain-map.yml")
SOURCE_MANIFEST = Path("_meta/source-manifest.json")
REPO_MANIFEST = Path("_meta/repo-manifest.json")
DEFAULT_OUTPUT = Path("CATALOG.md")
SOURCE_EXTS = {".docx", ".pptx", ".xlsx", ".doc", ".pdf"}
CONTENT_ROOTS = {
    "00_inbox",
    "10_governance",
    "20_market",
    "30_customers",
    "40_delivery",
    "50_operations",
    "60_finance",
    "70_people",
    "80_sources",
}
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
EXCLUDED_PARTS = RESERVED_TOP_LEVEL | {"__pycache__"}
GENERATED_CATALOGS = {"CATALOG.md"}


def relpath(path: Path, root: Path = ROOT) -> str:
    return path.relative_to(root).as_posix()


def safe_rel(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return ""
    return path.as_posix()


def md_escape(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def md_link(rel: str) -> str:
    text = md_escape(rel)
    return f"[{text}](<./{rel}>)"


def read_json_object(root: Path, rel: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    path = root / rel
    if not path.exists():
        return {}, [f"{rel.as_posix()}: missing"], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [], [f"{rel.as_posix()}: invalid JSON ({exc.__class__.__name__})"]
    if not isinstance(data, dict):
        return {}, [], [f"{rel.as_posix()}: must be a JSON object"]
    return data, [], []


def load_domains(root: Path) -> tuple[list[dict[str, str]], dict[str, str], list[str], list[str]]:
    path = root / DOMAIN_MAP
    if not path.exists():
        return [], {}, [f"{DOMAIN_MAP.as_posix()}: missing"], []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return [], {}, [], [f"{DOMAIN_MAP.as_posix()}: invalid YAML ({exc.__class__.__name__})"]
    domains = data.get("domains")
    if not isinstance(domains, dict) or not domains:
        return [], {}, [], [f"{DOMAIN_MAP.as_posix()}: missing domains map"]

    items: list[dict[str, str]] = []
    aliases: dict[str, str] = {}
    errors: list[str] = []
    for domain, info in domains.items():
        if not isinstance(info, dict) or not info.get("folder"):
            errors.append(f"{DOMAIN_MAP.as_posix()}:{domain}: missing folder")
            continue
        domain_name = str(domain)
        folder = str(info["folder"])
        purpose = str(info.get("purpose", ""))
        items.append({"domain": domain_name, "folder": folder, "purpose": purpose})
        for value in (domain_name, folder):
            aliases[value] = domain_name
        raw_aliases = info.get("aliases", [])
        if isinstance(raw_aliases, list):
            for alias in raw_aliases:
                if isinstance(alias, str) and alias.strip():
                    aliases[alias.strip()] = domain_name
    items.sort(key=lambda item: item["folder"])
    return items, aliases, [], errors


def domain_for_path(rel: str, aliases: dict[str, str]) -> str:
    path = Path(rel)
    if not path.parts:
        return "unclassified"
    return aliases.get(path.parts[0], "unclassified")


def excluded(path: Path) -> bool:
    if path.as_posix() in GENERATED_CATALOGS:
        return True
    return any(part in EXCLUDED_PARTS or part.startswith(".") for part in path.parts)


def workspace_inventory(root: Path, aliases: dict[str, str]) -> dict[str, Any]:
    extensions: Counter[str] = Counter()
    source_candidates: list[str] = []
    markdown_files: list[str] = []
    generated_mirrors = 0
    curated_markdown = 0
    top_level_counts: Counter[str] = Counter()
    legacy_folders: list[dict[str, Any]] = []
    canonical_folders = {folder for folder in CONTENT_ROOTS if (root / folder).exists()}

    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            continue
        rel = path.relative_to(root)
        if path.is_dir():
            if len(rel.parts) == 1 and rel.parts[0] not in RESERVED_TOP_LEVEL and rel.parts[0] not in CONTENT_ROOTS:
                legacy_folders.append({"folder": rel.as_posix()})
            continue
        if not path.is_file():
            continue
        suffix = path.suffix.lower() or "[no extension]"
        if suffix == ".md" and rel.parts[:1] == ("_mirrors",):
            generated_mirrors += 1
        if excluded(rel):
            continue
        extensions[suffix] += 1
        top_level_counts[rel.parts[0] if rel.parts else "."] += 1
        if suffix in SOURCE_EXTS:
            source_candidates.append(rel.as_posix())
        if suffix == ".md":
            markdown_files.append(rel.as_posix())
            curated_markdown += 1

    domain_source_counts: Counter[str] = Counter(domain_for_path(rel, aliases) for rel in source_candidates)
    domain_markdown_counts: Counter[str] = Counter(domain_for_path(rel, aliases) for rel in markdown_files)
    return {
        "extensions": dict(sorted(extensions.items())),
        "source_candidates": source_candidates,
        "markdown_files": markdown_files,
        "generated_mirrors": generated_mirrors,
        "curated_markdown": curated_markdown,
        "top_level_counts": dict(sorted(top_level_counts.items())),
        "legacy_folders": sorted(legacy_folders, key=lambda item: item["folder"]),
        "domain_source_counts": dict(sorted(domain_source_counts.items())),
        "domain_markdown_counts": dict(sorted(domain_markdown_counts.items())),
        "canonical_folders": sorted(canonical_folders),
    }


def load_manifest_records(root: Path, rel: Path, id_key: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    data, warnings, errors = read_json_object(root, rel)
    if errors or not data:
        return [], warnings, errors
    records = data.get("records", [])
    if not isinstance(records, list):
        return [], [], [f"{rel.as_posix()}: records must be a list"]
    out: list[dict[str, Any]] = []
    bad = 0
    for record in records:
        if not isinstance(record, dict):
            bad += 1
            continue
        safe = dict(record)
        safe[id_key] = str(safe.get(id_key, ""))
        out.append(safe)
    errors = [f"{rel.as_posix()}: {bad} records are not objects"] if bad else []
    return out, warnings, errors


def source_catalog_items(records: list[dict[str, Any]], aliases: dict[str, str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in records:
        source = safe_rel(record.get("current_source_path") or record.get("source_path") or record.get("source"))
        mirror = safe_rel(record.get("mirror_path"))
        fmt = str(record.get("source_format", "") or Path(source).suffix.lower().lstrip("."))
        items.append(
            {
                "source_id": str(record.get("source_id", "")),
                "source": source,
                "mirror": mirror,
                "format": fmt,
                "state": str(record.get("lifecycle_state", "unknown") or "unknown"),
                "domain": domain_for_path(source, aliases),
                "warnings": len(record.get("warnings", [])) if isinstance(record.get("warnings"), list) else 0,
                "errors": len(record.get("errors", [])) if isinstance(record.get("errors"), list) else 0,
            }
        )
    items.sort(key=lambda item: (item["domain"], item["source"], item["mirror"]))
    return items


def repo_catalog_items(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in records:
        note = safe_rel(record.get("note_path") or record.get("mirror_path"))
        items.append(
            {
                "repo_id": str(record.get("repo_id", "")),
                "repo": str(record.get("resolved_repo") or record.get("configured_repo") or record.get("repo") or ""),
                "note": note,
                "state": str(record.get("lifecycle_state", "unknown") or "unknown"),
                "warnings": len(record.get("warnings", [])) if isinstance(record.get("warnings"), list) else 0,
                "errors": len(record.get("errors", [])) if isinstance(record.get("errors"), list) else 0,
            }
        )
    items.sort(key=lambda item: (item["repo"], item["note"]))
    return items


def build_report(root: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    domains, aliases, domain_warnings, domain_errors = load_domains(root)
    inventory = workspace_inventory(root, aliases)
    source_records, source_warnings, source_errors = load_manifest_records(root, SOURCE_MANIFEST, "source_id")
    repo_records, repo_warnings, repo_errors = load_manifest_records(root, REPO_MANIFEST, "repo_id")
    source_items = source_catalog_items(source_records, aliases)
    repo_items = repo_catalog_items(repo_records)
    mirrored_sources = {item["source"] for item in source_items if item["source"]}
    unmanaged_sources = [
        rel for rel in inventory["source_candidates"]
        if rel not in mirrored_sources
    ]

    states = Counter(item["state"] for item in source_items)
    formats = Counter(item["format"] or "unknown" for item in source_items)
    domain_rows: list[dict[str, Any]] = []
    for domain in domains:
        domain_name = domain["domain"]
        domain_rows.append(
            {
                **domain,
                "source_records": sum(1 for item in source_items if item["domain"] == domain_name),
                "source_candidates": inventory["domain_source_counts"].get(domain_name, 0),
                "markdown_files": inventory["domain_markdown_counts"].get(domain_name, 0),
            }
        )
    if any(item["domain"] == "unclassified" for item in source_items) or inventory["domain_source_counts"].get("unclassified"):
        domain_rows.append(
            {
                "domain": "unclassified",
                "folder": "",
                "purpose": "Source files outside configured Vaultwright domains.",
                "source_records": sum(1 for item in source_items if item["domain"] == "unclassified"),
                "source_candidates": inventory["domain_source_counts"].get("unclassified", 0),
                "markdown_files": inventory["domain_markdown_counts"].get("unclassified", 0),
            }
        )

    report = {
        "summary": {
            "source_records": len(source_items),
            "repo_records": len(repo_items),
            "source_candidates": len(inventory["source_candidates"]),
            "unmanaged_source_candidates": len(unmanaged_sources),
            "generated_mirrors": inventory["generated_mirrors"],
            "curated_markdown": inventory["curated_markdown"],
            "legacy_top_level_folders": len(inventory["legacy_folders"]),
        },
        "states": dict(sorted(states.items())),
        "formats": dict(sorted(formats.items())),
        "domains": domain_rows,
        "source_items": source_items,
        "repo_items": repo_items,
        "unmanaged_sources": unmanaged_sources,
        "legacy_folders": inventory["legacy_folders"],
        "extensions": inventory["extensions"],
        "top_level_counts": inventory["top_level_counts"],
    }
    warnings = domain_warnings + source_warnings + repo_warnings
    errors = domain_errors + source_errors + repo_errors
    return report, warnings, errors


def table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(md_escape(value) for value in row) + " |")
    return lines


def limited(items: list[Any], max_items: int) -> tuple[list[Any], int]:
    if max_items <= 0 or len(items) <= max_items:
        return items, 0
    return items[:max_items], len(items) - max_items


def render_markdown(report: dict[str, Any], warnings: list[str], errors: list[str], max_items: int = 500) -> str:
    summary = report["summary"]
    lines = [
        "# Documentation Catalog",
        "",
        "Generated by `vaultwright catalog`. This catalog lists paths and manifest metadata only; it does not copy source document text.",
        "",
        "## Inventory Summary",
        "",
        *table(
            ["Metric", "Count"],
            [
                ["Source manifest records", summary["source_records"]],
                ["Repo manifest records", summary["repo_records"]],
                ["Source candidates in vault", summary["source_candidates"]],
                ["Unmanaged source candidates", summary["unmanaged_source_candidates"]],
                ["Generated mirrors", summary["generated_mirrors"]],
                ["Curated markdown files", summary["curated_markdown"]],
                ["Legacy top-level folders", summary["legacy_top_level_folders"]],
            ],
        ),
        "",
    ]
    if warnings or errors:
        lines.extend(["## Catalog Warnings", ""])
        for warning in warnings:
            lines.append(f"- Warning: {md_escape(warning)}")
        for error in errors:
            lines.append(f"- Error: {md_escape(error)}")
        lines.append("")

    lines.extend(["## Domains", ""])
    domain_rows = [
        [
            item["folder"] or item["domain"],
            item["domain"],
            item["source_records"],
            item["source_candidates"],
            item["markdown_files"],
            item["purpose"],
        ]
        for item in report["domains"]
    ]
    lines.extend(table(["Folder", "Domain", "Manifest Sources", "Source Candidates", "Markdown", "Purpose"], domain_rows))
    lines.append("")

    states = report["states"]
    formats = report["formats"]
    if states:
        lines.extend(["## Source Lifecycle States", ""])
        lines.extend(table(["State", "Count"], [[state, count] for state, count in states.items()]))
        lines.append("")
    if formats:
        lines.extend(["## Source Formats", ""])
        lines.extend(table(["Format", "Count"], [[fmt, count] for fmt, count in formats.items()]))
        lines.append("")

    source_items, hidden_sources = limited(report["source_items"], max_items)
    lines.extend(["## Generated Source Mirrors", ""])
    if source_items:
        for item in source_items:
            source = item["source"]
            mirror = item["mirror"]
            source_part = md_link(source) if source else "(missing source path)"
            mirror_part = md_link(mirror) if mirror else "(missing mirror path)"
            status = f"{item['format'] or 'unknown'}, {item['state']}"
            if item["warnings"] or item["errors"]:
                status += f", warnings={item['warnings']}, errors={item['errors']}"
            lines.append(f"- {source_part} -> {mirror_part} ({md_escape(status)})")
        if hidden_sources:
            lines.append(f"- {hidden_sources} additional source mirror records omitted by `--max-items`.")
    else:
        lines.append("- No source manifest records yet. Run `vaultwright sync` after reviewing `vaultwright plan`.")
    lines.append("")

    unmanaged_sources, hidden_unmanaged = limited(report["unmanaged_sources"], max_items)
    lines.extend(["## Unmanaged Source Candidates", ""])
    if unmanaged_sources:
        for source in unmanaged_sources:
            lines.append(f"- {md_link(source)}")
        if hidden_unmanaged:
            lines.append(f"- {hidden_unmanaged} additional unmanaged source candidates omitted by `--max-items`.")
    else:
        lines.append("- No unmanaged source candidates detected.")
    lines.append("")

    repo_items, hidden_repos = limited(report["repo_items"], max_items)
    lines.extend(["## Repository Mirrors", ""])
    if repo_items:
        for item in repo_items:
            note = item["note"]
            note_part = md_link(note) if note else "(missing note path)"
            status = item["state"]
            if item["warnings"] or item["errors"]:
                status += f", warnings={item['warnings']}, errors={item['errors']}"
            lines.append(f"- {md_escape(item['repo'])} -> {note_part} ({md_escape(status)})")
        if hidden_repos:
            lines.append(f"- {hidden_repos} additional repo mirror records omitted by `--max-items`.")
    else:
        lines.append("- No repository mirrors configured or generated yet.")
    lines.append("")

    lines.extend(["## Legacy Folders Needing Classification", ""])
    if report["legacy_folders"]:
        for item in report["legacy_folders"]:
            folder = item["folder"]
            lines.append(f"- {md_link(folder)}")
    else:
        lines.append("- No legacy top-level folders detected.")
    lines.append("")

    lines.extend(
        [
            "## Operator Next Steps",
            "",
            "- Run `vaultwright sandbox --source-root <original-source-root>` before using a copied pilot vault.",
            "- Run `vaultwright conversion --guide` after sync to spot-check high-risk formats.",
            "- Use `vaultwright migration` before moving legacy folders into canonical domains.",
            "- Keep this catalog regenerated after sync so reviewers and agents start from the current inventory.",
            "",
        ]
    )
    return "\n".join(lines)


def safe_output_path(root: Path, value: Path) -> Path:
    if value.is_absolute() or ".." in value.parts:
        raise ValueError("output must stay inside the vault")
    if value.suffix.lower() != ".md":
        raise ValueError("output must be a .md file")
    if any(part in {".git", ".github", ".githooks", "_meta", "_mirrors", "_tmp", "tools", "node_modules"} for part in value.parts):
        raise ValueError("output cannot live under a reserved folder")
    return root / value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a Vaultwright documentation catalog.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable catalog JSON.")
    parser.add_argument("--stdout", action="store_true", help="Print catalog Markdown instead of writing CATALOG.md.")
    parser.add_argument("--check", action="store_true", help="Fail if the output file is missing or stale.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Catalog path relative to the vault root.")
    parser.add_argument(
        "--max-items",
        type=int,
        default=500,
        help="Maximum source/repo records to list per catalog section; use 0 for no limit.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report, warnings, errors = build_report(ROOT)
    if args.json:
        print(json.dumps({"report": report, "warnings": warnings, "errors": errors}, indent=2, sort_keys=True))
        return 1 if errors else 0
    try:
        output = safe_output_path(ROOT, args.output)
    except ValueError as exc:
        print(f"catalog: {exc}", file=sys.stderr)
        return 1
    content = render_markdown(report, warnings, errors, max_items=args.max_items)
    if args.stdout:
        print(content)
        return 1 if errors else 0
    if args.check:
        if not output.exists():
            print(f"catalog: stale or missing: {args.output.as_posix()}", file=sys.stderr)
            return 1
        current = output.read_text(encoding="utf-8")
        if current != content:
            print(f"catalog: stale or missing: {args.output.as_posix()}", file=sys.stderr)
            return 1
        print(f"catalog: up to date: {args.output.as_posix()}")
        return 1 if errors else 0
    output.write_text(content, encoding="utf-8")
    print(f"catalog: wrote {args.output.as_posix()}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
