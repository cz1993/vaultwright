#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Print a read-only conversion spot-check report from the source manifest."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only in stripped Python envs
    yaml = None


DEFAULT_ROOT = Path.cwd()
SOURCE_MANIFEST = Path("_meta/source-manifest.json")
QUALITY_RESULTS = Path("_meta/conversion-quality-results.yml")
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
QUALITY_STATUSES = {"not-reviewed", "pass", "needs-work", "blocked"}
QUALITY_SCORES = {0, 1, 2}
QUALITY_ISSUE_CODES = {
    "bad_source_link",
    "formatting_loss",
    "formula_or_number_loss",
    "frontmatter_error",
    "generated_region_error",
    "image_or_diagram_loss",
    "omitted_text",
    "other",
    "slide_or_layout_loss",
    "table_loss",
    "unsupported_source",
}
QUALITY_ALLOWED_TOP_FIELDS = {"schema_version", "corpus", "reviews"}
QUALITY_ALLOWED_REVIEW_FIELDS = {
    "checked_links",
    "checked_mirror",
    "checked_source",
    "issue_codes",
    "priority",
    "reviewer_corrections",
    "score",
    "source_format",
    "source_id",
    "status",
}
QUALITY_FORBIDDEN_FIELDS = {
    "answer",
    "comment",
    "content",
    "document_text",
    "mirror_excerpt",
    "mirror_text",
    "notes",
    "prompt",
    "response",
    "reviewer_notes",
    "source_excerpt",
    "source_text",
}


def quality_schema() -> dict:
    return {
        "statuses": sorted(QUALITY_STATUSES),
        "scores": sorted(QUALITY_SCORES),
        "issue_codes": sorted(QUALITY_ISSUE_CODES),
        "forbidden_fields": sorted(QUALITY_FORBIDDEN_FIELDS),
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
                f"Resolve all high-priority items before relying on mirrors for source-backed conclusions (current high={high}).",
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
    schema = quality_schema()
    sections.append({
        "title": "Quality result pack",
        "items": [
            "Fill the private result scaffold after source/mirror review, then run "
            "`vaultwright conversion --results _meta/conversion-quality-results.yml --require-reviewed`.",
            "Allowed statuses: " + ", ".join(schema["statuses"]) + ".",
            "Scores are 0, 1, or 2 for reviewed records; leave score null only when status is not-reviewed.",
            "Allowed issue codes: " + ", ".join(schema["issue_codes"]) + ".",
            "Do not add free-text fields such as: " + ", ".join(schema["forbidden_fields"]) + ".",
        ],
    })
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


def safe_rel_path(value: Path | str | None, default: Path) -> tuple[Path, str | None]:
    rel = default if value is None else Path(value)
    if rel.is_absolute() or ".." in rel.parts:
        return rel, f"results path is unsafe: {rel}"
    return rel, None


def empty_quality_summary(rel: Path, available: bool = False) -> dict:
    return {
        "available": available,
        "path": rel.as_posix(),
        "records": 0,
        "reviewed": 0,
        "missing_reviews": 0,
        "statuses": {},
        "scores": {},
        "average_score": None,
        "reviewer_corrections": 0,
        "issue_codes": {},
    }


def load_yaml_mapping(path: Path, rel: Path) -> tuple[dict | None, list[str]]:
    if yaml is None:
        return None, ["PyYAML is required to read conversion quality results"]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return None, [f"{rel.as_posix()}: unreadable text"]
    except Exception as exc:
        return None, [f"{rel.as_posix()}: invalid YAML ({exc.__class__.__name__})"]
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return None, [f"{rel.as_posix()}: must be a YAML mapping"]
    return data, []


def quality_source_index(records: list[dict]) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for record in records:
        source_id = str(record.get("source_id", "") or "").strip()
        if source_id:
            indexed[source_id] = record
    return indexed


def validate_quality_record(
    record: object,
    index: int,
    source_records: dict[str, dict],
    seen_source_ids: set[str],
    summary: dict,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    label = f"reviews[{index}]"
    if not isinstance(record, dict):
        return [], [f"{label}: must be a mapping"]

    fields = set(str(key) for key in record)
    forbidden = sorted(fields.intersection(QUALITY_FORBIDDEN_FIELDS))
    if forbidden:
        errors.append(f"{label}: text/note fields are not allowed ({', '.join(forbidden)})")
    unsupported = sorted(fields.difference(QUALITY_ALLOWED_REVIEW_FIELDS))
    if unsupported:
        errors.append(f"{label}: unsupported field(s): {', '.join(unsupported)}")

    source_id = str(record.get("source_id", "") or "").strip()
    if not source_id:
        errors.append(f"{label}: source_id is required")
    elif source_id in seen_source_ids:
        errors.append(f"{label}: duplicate source_id {source_id}")
    elif source_id not in source_records:
        errors.append(f"{label}: source_id not found in source manifest: {source_id}")
    seen_source_ids.add(source_id)

    status = str(record.get("status", "") or "").strip()
    if status not in QUALITY_STATUSES:
        errors.append(f"{label}: status must be one of {', '.join(sorted(QUALITY_STATUSES))}")
    summary["statuses"][status or "missing"] += 1

    score = record.get("score")
    if status == "not-reviewed":
        if score is not None:
            errors.append(f"{label}: score must be null when status=not-reviewed")
    elif isinstance(score, bool) or not isinstance(score, int) or score not in QUALITY_SCORES:
        errors.append(f"{label}: score must be 0, 1, or 2 for reviewed records")
    else:
        summary["scores"][str(score)] += 1
        summary["_score_total"] += score
        summary["_score_count"] += 1

    corrections = record.get("reviewer_corrections")
    if status == "not-reviewed":
        if corrections is not None:
            errors.append(f"{label}: reviewer_corrections must be null when status=not-reviewed")
    elif isinstance(corrections, bool) or not isinstance(corrections, int) or corrections < 0:
        errors.append(f"{label}: reviewer_corrections must be a nonnegative integer for reviewed records")
    else:
        summary["reviewer_corrections"] += corrections

    for field in ("checked_source", "checked_mirror", "checked_links"):
        if not isinstance(record.get(field), bool):
            errors.append(f"{label}: {field} must be true or false")

    issue_codes = record.get("issue_codes")
    if not isinstance(issue_codes, list):
        errors.append(f"{label}: issue_codes must be a list")
    else:
        allowed_codes = ", ".join(sorted(QUALITY_ISSUE_CODES))
        for code_index, code in enumerate(issue_codes):
            if not isinstance(code, str) or code not in QUALITY_ISSUE_CODES:
                errors.append(
                    f"{label}: unsupported issue code at issue_codes[{code_index}]; allowed: {allowed_codes}"
                )
            else:
                summary["issue_codes"][code] += 1

    if status and status != "not-reviewed":
        summary["reviewed"] += 1
    return warnings, errors


def validate_quality_results(
    root: Path,
    result_path: Path | str | None = None,
    *,
    require_reviewed: bool = False,
    missing_ok: bool = False,
) -> tuple[dict, list[str], list[str]]:
    rel, path_error = safe_rel_path(result_path, QUALITY_RESULTS)
    summary = empty_quality_summary(rel)
    if path_error:
        return summary, [], [path_error]

    if not (root / SOURCE_MANIFEST).exists():
        return summary, [], [f"{SOURCE_MANIFEST.as_posix()}: missing; run `vaultwright sync` first."]
    records, manifest_warnings, manifest_errors = load_source_records(root)
    if manifest_errors:
        return summary, manifest_warnings, manifest_errors
    source_records = quality_source_index(records)
    summary["missing_reviews"] = len(source_records)

    path = root / rel
    if not path.exists():
        if missing_ok:
            return summary, manifest_warnings, []
        return summary, manifest_warnings, [f"{rel.as_posix()}: missing"]

    data, yaml_errors = load_yaml_mapping(path, rel)
    if yaml_errors:
        return summary, manifest_warnings, yaml_errors

    assert data is not None
    summary["available"] = True
    warnings = list(manifest_warnings)
    errors: list[str] = []
    top_fields = set(str(key) for key in data)
    unsupported_top = sorted(top_fields.difference(QUALITY_ALLOWED_TOP_FIELDS))
    if unsupported_top:
        errors.append(f"{rel.as_posix()}: unsupported top-level field(s): {', '.join(unsupported_top)}")
    if data.get("schema_version") != 1:
        errors.append(f"{rel.as_posix()}: schema_version must be 1")
    if not isinstance(data.get("corpus"), str) or not data.get("corpus", "").strip():
        errors.append(f"{rel.as_posix()}: corpus is required")
    reviews = data.get("reviews")
    if not isinstance(reviews, list):
        errors.append(f"{rel.as_posix()}: reviews must be a list")
        return summary, warnings, errors

    working_summary = {
        "statuses": Counter(),
        "scores": Counter(),
        "issue_codes": Counter(),
        "reviewed": 0,
        "reviewer_corrections": 0,
        "_score_total": 0,
        "_score_count": 0,
    }
    seen_source_ids: set[str] = set()
    for index, record in enumerate(reviews):
        item_warnings, item_errors = validate_quality_record(
            record,
            index,
            source_records,
            seen_source_ids,
            working_summary,
        )
        warnings.extend(item_warnings)
        errors.extend(item_errors)

    expected_source_ids = set(source_records)
    reviewed_or_present = seen_source_ids.intersection(expected_source_ids)
    missing_source_ids = expected_source_ids.difference(reviewed_or_present)
    summary.update(
        {
            "records": len(reviews),
            "reviewed": working_summary["reviewed"],
            "missing_reviews": len(missing_source_ids),
            "statuses": dict(sorted(working_summary["statuses"].items())),
            "scores": dict(sorted(working_summary["scores"].items())),
            "average_score": (
                round(working_summary["_score_total"] / working_summary["_score_count"], 2)
                if working_summary["_score_count"]
                else None
            ),
            "reviewer_corrections": working_summary["reviewer_corrections"],
            "issue_codes": dict(sorted(working_summary["issue_codes"].items())),
        }
    )
    if missing_source_ids:
        warnings.append(f"{rel.as_posix()}: {len(missing_source_ids)} source manifest record(s) have no quality review")
    if require_reviewed and (missing_source_ids or summary["statuses"].get("not-reviewed", 0)):
        errors.append(f"{rel.as_posix()}: every source manifest record must have a reviewed quality result")
    return summary, warnings, errors


def write_quality_results_scaffold(
    root: Path,
    result_path: Path | str | None = None,
    *,
    force: bool = False,
) -> tuple[dict, list[str], list[str]]:
    rel, path_error = safe_rel_path(result_path, QUALITY_RESULTS)
    summary = empty_quality_summary(rel, available=True)
    if path_error:
        return summary, [], [path_error]
    if yaml is None:
        return summary, [], ["PyYAML is required to write conversion quality results"]

    if not (root / SOURCE_MANIFEST).exists():
        return summary, [], [f"{SOURCE_MANIFEST.as_posix()}: missing; run `vaultwright sync` first."]
    records, warnings, errors = load_source_records(root)
    if errors:
        return summary, warnings, errors
    path = root / rel
    if path.exists() and not force:
        return summary, warnings, [f"{rel.as_posix()}: already exists; pass --force to overwrite"]
    path.parent.mkdir(parents=True, exist_ok=True)
    scaffold_records = []
    for record in records:
        source_id = str(record.get("source_id", "") or "").strip()
        if not source_id:
            continue
        item = build_item(root, record)
        scaffold_records.append(
            {
                "source_id": source_id,
                "source_format": str(record.get("source_format", "") or "").lower(),
                "priority": item["priority"],
                "status": "not-reviewed",
                "score": None,
                "reviewer_corrections": None,
                "checked_source": False,
                "checked_mirror": False,
                "checked_links": False,
                "issue_codes": [],
            }
        )
    payload = {
        "schema_version": 1,
        "corpus": root.name,
        "reviews": scaffold_records,
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
    summary.update(
        {
            "records": len(scaffold_records),
            "missing_reviews": len(scaffold_records),
            "statuses": {"not-reviewed": len(scaffold_records)} if scaffold_records else {},
        }
    )
    return summary, warnings, []


def print_counts(label: str, counts: dict[str, int]) -> None:
    rendered = ", ".join(f"{key}={counts[key]}" for key in sorted(counts)) or "none"
    print(f"  {label}: {rendered}")


def print_quality_summary(summary: dict) -> None:
    average = summary.get("average_score")
    average_text = "n/a" if average is None else str(average)
    print(
        "conversion results: "
        f"available={summary.get('available', False)} "
        f"records={summary.get('records', 0)} "
        f"reviewed={summary.get('reviewed', 0)} "
        f"missing={summary.get('missing_reviews', 0)} "
        f"average_score={average_text} "
        f"corrections={summary.get('reviewer_corrections', 0)}"
    )
    print_counts("result statuses", summary.get("statuses", {}))
    print_counts("result scores", summary.get("scores", {}))
    print_counts("result issues", summary.get("issue_codes", {}))


def print_quality_schema(schema: dict) -> None:
    print(
        "conversion results schema: "
        f"statuses={', '.join(schema['statuses'])}; "
        f"scores={', '.join(str(score) for score in schema['scores'])}"
    )
    print(f"  issue codes: {', '.join(schema['issue_codes'])}")
    print(f"  forbidden fields: {', '.join(schema['forbidden_fields'])}")


def print_human(
    root: Path,
    report: dict,
    warnings: list[str],
    errors: list[str],
    quality_summary: dict | None = None,
) -> None:
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
    if quality_summary is not None:
        print_quality_summary(quality_summary)
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
    parser.add_argument("--results", type=Path, help="Validate a metadata-only conversion quality result pack.")
    parser.add_argument("--init-results", action="store_true", help="Create a metadata-only quality result scaffold.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing quality result scaffold.")
    parser.add_argument(
        "--require-reviewed",
        action="store_true",
        help="Fail unless every source manifest record has a reviewed quality result.",
    )
    parser.add_argument(
        "--low-risk-per-format",
        type=int,
        default=1,
        help="Include this many low-risk sample records per format in the spot-check list.",
    )
    return parser


def main(argv: list[str] | None = None, root: Path | None = None) -> int:
    args = build_parser().parse_args(argv)
    active_root = (root or DEFAULT_ROOT).expanduser().resolve()
    if args.low_risk_per_format < 0:
        print("--low-risk-per-format must be >= 0", file=sys.stderr)
        return 1
    quality_rel = args.results or QUALITY_RESULTS
    if args.init_results:
        schema = quality_schema()
        quality_summary, warnings, errors = write_quality_results_scaffold(active_root, quality_rel, force=args.force)
        payload = {
            "root": str(active_root),
            "quality_results": quality_summary,
            "quality_schema": schema,
            "warnings": warnings,
            "errors": errors,
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            for warning in warnings:
                print(f"  warning: {warning}")
            for error in errors:
                print(f"  error: {error}", file=sys.stderr)
            if not errors:
                print(f"conversion results scaffold: wrote {quality_summary['path']}")
                print_quality_summary(quality_summary)
                print_quality_schema(schema)
        return 1 if errors else 0

    report, warnings, errors = build_report(active_root, low_risk_per_format=args.low_risk_per_format)
    include_quality = bool(args.results or args.require_reviewed or (active_root / QUALITY_RESULTS).exists())
    quality_summary = None
    if include_quality:
        quality_summary, result_warnings, result_errors = validate_quality_results(
            active_root,
            quality_rel,
            require_reviewed=args.require_reviewed,
        )
        warnings.extend(result_warnings)
        errors.extend(result_errors)
    payload = {
        "root": str(active_root),
        "summary": report["summary"],
        "items": report["items"],
        "warnings": warnings,
        "errors": errors,
    }
    if quality_summary is not None:
        payload["quality_results"] = quality_summary
    if args.guide:
        payload["guide"] = build_guide(report)
        payload["quality_schema"] = quality_schema()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_human(active_root, report, warnings, errors, quality_summary)
        if args.guide and not errors:
            print_guide(payload["guide"])
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
