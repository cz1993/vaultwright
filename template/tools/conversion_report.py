#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Print a read-only conversion spot-check report from the source manifest."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_MANIFEST = Path("_meta/source-manifest.json")
CLEAN_STATES = {"clean", "reviewed"}
HIGH_RISK_STATES = {"conflict", "error", "manual_modification", "source_missing", "source_moved", "unsupported"}
HIGH_RISK_FORMATS = {"pdf", "pptx", "xlsx", "xls", "doc"}
RISK_WARNING_PREFIXES = (
    "Conversion-quality risk:",
    "Large-file risk:",
    "Sensitive-name risk:",
    "Potential duplicate:",
)
FORMAT_GUIDANCE = {
    "doc": [
        "Treat legacy .doc files as inventory-only until converted manually to .docx.",
        "Check whether the retained source contains comments, tracked changes, or embedded objects.",
    ],
    "docx": [
        "Spot-check heading hierarchy, tables, lists, links, comments, and generated-region boundaries.",
        "Confirm the mirror frontmatter source path points back to the authoritative document.",
    ],
    "pdf": [
        "Check scanned or image-only pages against the original PDF; text extraction may omit them.",
        "Spot-check page order, tables, footnotes, form fields, and any diagrams used for decisions.",
    ],
    "pptx": [
        "Check slide titles, speaker notes, image-heavy slides, tables, and omitted embedded media.",
        "Use the original deck for visual layout decisions; treat the mirror as search/review text.",
    ],
    "xls": [
        "Treat legacy spreadsheets as high-risk; preserve the workbook as the source of truth.",
        "Check formulas, hidden sheets, merged cells, number/date formats, and workbook-level notes.",
    ],
    "xlsx": [
        "Check formulas, hidden sheets, merged cells, number/date formats, and workbook-level notes.",
        "Use the original workbook for calculations; use the mirror for search and citation triage.",
    ],
}


def load_source_records(root: Path) -> tuple[list[dict], list[str], list[str]]:
    path = root / SOURCE_MANIFEST
    if not path.exists():
        return [], [f"{SOURCE_MANIFEST.as_posix()}: missing; run `vaultwright sync` first."], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], [], [f"{SOURCE_MANIFEST.as_posix()}: invalid JSON ({exc.__class__.__name__})"]
    if not isinstance(data, dict):
        return [], [], [f"{SOURCE_MANIFEST.as_posix()}: must be a JSON object"]
    records = data.get("records", [])
    if not isinstance(records, list):
        return [], [], [f"{SOURCE_MANIFEST.as_posix()}: records must be a list"]
    bad = sum(1 for record in records if not isinstance(record, dict))
    errors = [f"{SOURCE_MANIFEST.as_posix()}: {bad} records are not objects"] if bad else []
    return [record for record in records if isinstance(record, dict)], [], errors


def rel_exists(root: Path, value: object) -> bool | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return None
    return (root / path).exists()


def rel_path_problem(label: str, value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return f"{label} path missing from manifest"
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return f"{label} path is unsafe: {value}"
    return None


def warning_texts(record: dict) -> list[str]:
    warnings = record.get("warnings")
    if not isinstance(warnings, list):
        return []
    return [str(warning) for warning in warnings if str(warning).strip()]


def error_texts(record: dict) -> list[str]:
    errors = record.get("errors")
    if not isinstance(errors, list):
        return []
    return [str(error) for error in errors if str(error).strip()]


def risk_warnings(record: dict) -> list[str]:
    return [
        warning
        for warning in warning_texts(record)
        if any(warning.startswith(prefix) for prefix in RISK_WARNING_PREFIXES)
    ]


def priority_for(
    record: dict,
    source_exists: bool | None,
    mirror_exists: bool | None,
    path_problems: list[str],
) -> str:
    state = str(record.get("lifecycle_state", "unknown"))
    fmt = str(record.get("source_format", "")).lower()
    if path_problems or state in HIGH_RISK_STATES or error_texts(record) or source_exists is False or mirror_exists is False:
        return "high"
    if state not in CLEAN_STATES:
        return "medium"
    if risk_warnings(record) or fmt in HIGH_RISK_FORMATS:
        return "medium"
    return "low"


def reasons_for(
    record: dict,
    source_exists: bool | None,
    mirror_exists: bool | None,
    path_problems: list[str],
) -> list[str]:
    state = str(record.get("lifecycle_state", "unknown"))
    fmt = str(record.get("source_format", "")).lower() or "unknown"
    reasons: list[str] = []
    if state not in CLEAN_STATES:
        reasons.append(f"state={state}")
    if fmt in HIGH_RISK_FORMATS:
        reasons.append(f"format={fmt}")
    if source_exists is False:
        reasons.append("source missing")
    if mirror_exists is False:
        reasons.append("mirror missing")
    reasons.extend(path_problems)
    reasons.extend(risk_warnings(record))
    reasons.extend(error_texts(record))
    return reasons


def action_for(priority: str, record: dict) -> str:
    state = str(record.get("lifecycle_state", "unknown"))
    fmt = str(record.get("source_format", "")).lower()
    if state in {"conflict", "error", "manual_modification", "source_missing", "source_moved"}:
        return "Resolve lifecycle/recovery item before trusting the generated mirror."
    if state == "unsupported" or fmt == "doc":
        return "Keep the original as authoritative; convert manually or use a supported format."
    if state in {"converter_changed", "source_changed", "stale"}:
        return "Refresh or review the mirror before relying on generated content."
    if priority == "high":
        return "Review source, mirror, manifest warnings, and linked curated notes before use."
    if priority == "medium":
        return "Spot-check headings, tables/slides/pages, omissions, and source links before relying on the mirror."
    return "Sample as part of routine format coverage; verify source link and generated region boundary."


def build_item(root: Path, record: dict) -> dict:
    source_path = record.get("current_source_path") or record.get("source_path") or record.get("source") or ""
    mirror_path = record.get("mirror_path") or ""
    source_exists = rel_exists(root, source_path)
    mirror_exists = rel_exists(root, mirror_path)
    path_problems = [
        problem
        for problem in (
            rel_path_problem("source", source_path),
            rel_path_problem("mirror", mirror_path),
        )
        if problem
    ]
    priority = priority_for(record, source_exists, mirror_exists, path_problems)
    return {
        "priority": priority,
        "source_id": str(record.get("source_id", "")),
        "source": source_path if isinstance(source_path, str) else "",
        "mirror": mirror_path if isinstance(mirror_path, str) else "",
        "format": str(record.get("source_format", "")).lower(),
        "state": str(record.get("lifecycle_state", "unknown")),
        "source_exists": source_exists,
        "mirror_exists": mirror_exists,
        "source_size": record.get("source_size") if isinstance(record.get("source_size"), int) else None,
        "reasons": reasons_for(record, source_exists, mirror_exists, path_problems),
        "action": action_for(priority, record),
    }


def sample_low_risk(items: list[dict], per_format: int) -> list[dict]:
    selected: list[dict] = []
    by_format: dict[str, list[dict]] = {}
    for item in items:
        if item["priority"] != "low":
            continue
        by_format.setdefault(item["format"] or "unknown", []).append(item)
    for fmt in sorted(by_format):
        selected.extend(by_format[fmt][:per_format])
    return selected


def build_report(root: Path, low_risk_per_format: int = 1) -> tuple[dict, list[str], list[str]]:
    records, warnings, errors = load_source_records(root)
    if errors:
        return {"summary": summary_counts([]), "items": []}, warnings, errors
    items = [build_item(root, record) for record in records]
    review_items = [
        item
        for item in items
        if item["priority"] in {"high", "medium"}
    ] + sample_low_risk(items, low_risk_per_format)
    review_items.sort(key=lambda item: (
        {"high": 0, "medium": 1, "low": 2}.get(item["priority"], 3),
        item["format"],
        item["source"],
    ))
    return {
        "summary": summary_counts(items),
        "items": review_items,
    }, warnings, []


def build_guide(report: dict) -> dict:
    summary = report.get("summary", {})
    formats = summary.get("formats", {}) if isinstance(summary.get("formats"), dict) else {}
    high = int(summary.get("high", 0) or 0)
    medium = int(summary.get("medium", 0) or 0)
    low = int(summary.get("low", 0) or 0)
    sections = [
        {
            "title": "Preflight",
            "items": [
                "Run `vaultwright status` and `vaultwright recovery` before sign-off.",
                "Confirm source files are backed up and original source bytes remain authoritative.",
                "Do not edit generated mirror content below the sentinel; record corrections as review notes.",
            ],
        },
        {
            "title": "Priority handling",
            "items": [
                f"Resolve all high-priority items before relying on mirrors for client-facing conclusions (current high={high}).",
                f"Spot-check medium-priority items before use and record any manual corrections (current medium={medium}).",
                f"Sample low-priority records for routine coverage by format (current low={low}).",
            ],
        },
    ]
    format_items: list[str] = []
    for fmt in sorted(formats):
        guidance = FORMAT_GUIDANCE.get(fmt)
        if not guidance:
            continue
        count = formats.get(fmt, 0)
        format_items.append(f"{fmt} ({count}): " + " ".join(guidance))
    if format_items:
        sections.append({"title": "Format checks", "items": format_items})
    sections.append({
        "title": "Sign-off",
        "items": [
            "Verify each accepted mirror has a valid source path, mirror path, and lifecycle state.",
            "Record unsupported files, conversion defects, and manual corrections in the pilot worksheet.",
            "Use source-backed citations for durable curated notes; do not treat generated markdown as final authority.",
        ],
    })
    return {"sections": sections}


def summary_counts(items: list[dict]) -> dict:
    priorities = Counter(item["priority"] for item in items)
    states = Counter(item["state"] for item in items)
    formats = Counter(item["format"] or "unknown" for item in items)
    return {
        "total": len(items),
        "high": priorities.get("high", 0),
        "medium": priorities.get("medium", 0),
        "low": priorities.get("low", 0),
        "states": dict(sorted(states.items())),
        "formats": dict(sorted(formats.items())),
    }


def print_human(root: Path, report: dict, warnings: list[str], errors: list[str]) -> None:
    summary = report.get("summary", {})
    items = report.get("items", [])
    print(f"vaultwright conversion: {root}")
    print("conversion: read-only spot-check report; no files were changed")
    for warning in warnings:
        print(f"  warning: {warning}")
    for error in errors:
        print(f"  error: {error}", file=sys.stderr)
    if errors:
        return
    print(
        "conversion: "
        f"{summary.get('total', 0)} manifest records "
        f"(high={summary.get('high', 0)}, medium={summary.get('medium', 0)}, low={summary.get('low', 0)})"
    )
    if not items:
        print("conversion: no source-manifest records available for spot-checking")
        return
    print(f"conversion: {len(items)} spot-check items")
    for item in items:
        print(f"  [{item['priority']:<6}] {item['source']} -> {item['mirror']}")
        print(f"    state: {item['state']}  format: {item['format'] or 'unknown'}")
        if item["reasons"]:
            print(f"    reasons: {'; '.join(item['reasons'])}")
        print(f"    action: {item['action']}")


def print_guide(guide: dict) -> None:
    print("conversion guide: operator review checklist; no files were changed")
    for section in guide.get("sections", []):
        title = section.get("title", "Checklist")
        print(f"  {title}")
        for item in section.get("items", []):
            print(f"    - {item}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print a read-only Vaultwright conversion spot-check report.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable conversion JSON.")
    parser.add_argument("--guide", action="store_true", help="Append an operator conversion-review checklist.")
    parser.add_argument(
        "--low-risk-per-format",
        type=int,
        default=1,
        help="Include this many low-risk sample records per format in the spot-check list.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.low_risk_per_format < 0:
        print("--low-risk-per-format must be >= 0", file=sys.stderr)
        return 1
    report, warnings, errors = build_report(ROOT, low_risk_per_format=args.low_risk_per_format)
    payload = {
        "root": str(ROOT),
        "summary": report["summary"],
        "items": report["items"],
        "warnings": warnings,
        "errors": errors,
    }
    if args.guide:
        payload["guide"] = build_guide(report)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_human(ROOT, report, warnings, errors)
        if args.guide and not errors:
            print_guide(payload["guide"])
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
