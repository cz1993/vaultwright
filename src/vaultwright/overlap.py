#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate a metadata-only overlap calibration report for curated notes."""
from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

from vaultwright.runtime_profile import profile_domain_folders, profile_frontmatter_link_keys


DEFAULT_ROOT = Path.cwd()
LINT_CONFIG_REL = "_meta/lint-config.yml"
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
EXCLUDE_PREFIX = ("_archive", "_backup", "_deprecated")
EXCLUDE_EXACT = {"_fixtures", "_meta", "_templates", "_tmp", "tools", "node_modules"}
GENERATED_TYPES = {"source-mirror", "repo-mirror"}
ARCHIVED_STATUSES = {"archived", "superseded"}
WORD_RE = re.compile(r"[a-z0-9][a-z0-9-]{2,}")
LINK_RE = re.compile(r"\[\[([^\]]+?)\]\]")
DEFAULT_MIN_SHARED_TERMS = 18
DEFAULT_CONTENT_THRESHOLD = 0.72
DEFAULT_TITLE_THRESHOLD = 0.82
CONTENT_THRESHOLDS = (0.55, 0.65, 0.72, 0.80, 0.90)
TITLE_THRESHOLDS = (0.70, 0.82, 0.90)
MIN_SHARED_TERM_BANDS = (8, 12, 18, 24, 30)
STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "also",
    "because",
    "before",
    "being",
    "between",
    "could",
    "during",
    "each",
    "from",
    "have",
    "into",
    "more",
    "must",
    "need",
    "only",
    "other",
    "over",
    "should",
    "than",
    "that",
    "their",
    "there",
    "these",
    "this",
    "through",
    "under",
    "using",
    "where",
    "which",
    "while",
    "with",
    "within",
    "without",
    "would",
}


def excluded(rel: Path) -> bool:
    return bool(EXCLUDE_EXACT.intersection(rel.parts)) or any(part.startswith(EXCLUDE_PREFIX) for part in rel.parts)


def markdown_files(root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in root.rglob("*.md")
            if path.is_file()
            and not excluded(path.relative_to(root).parent)
            and path.relative_to(root).parts
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def active_content_roots(root: Path) -> set[str]:
    folders = set(profile_domain_folders(root).values())
    return folders or set(CONTENT_ROOTS)


def split_fm(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        data = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}, parts[2]
    return data if isinstance(data, dict) else {}, parts[2]


def normalized_words(text: str) -> set[str]:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", " ", text)
    return {word for word in WORD_RE.findall(text.lower()) if word not in STOPWORDS}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def lint_config(root: Path) -> tuple[dict[str, int | float], list[str]]:
    config: dict[str, int | float] = {
        "min_shared_terms": DEFAULT_MIN_SHARED_TERMS,
        "content_threshold": DEFAULT_CONTENT_THRESHOLD,
        "title_threshold": DEFAULT_TITLE_THRESHOLD,
    }
    path = root / LINT_CONFIG_REL
    if not path.exists():
        return config, []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return config, [f"{LINT_CONFIG_REL}: invalid YAML"]
    if not isinstance(data, dict):
        return config, [f"{LINT_CONFIG_REL}: must be a mapping"]
    overlap = data.get("overlap", {})
    if overlap is None:
        overlap = {}
    if not isinstance(overlap, dict):
        return config, [f"{LINT_CONFIG_REL}:overlap must be a mapping"]

    errors: list[str] = []
    min_shared_terms = overlap.get("min_shared_terms", config["min_shared_terms"])
    if isinstance(min_shared_terms, int) and not isinstance(min_shared_terms, bool) and min_shared_terms >= 2:
        config["min_shared_terms"] = min_shared_terms
    else:
        errors.append(f"{LINT_CONFIG_REL}:overlap.min_shared_terms must be an integer >= 2")
    for key in ("content_threshold", "title_threshold"):
        value = overlap.get(key, config[key])
        if isinstance(value, (int, float)) and not isinstance(value, bool) and 0.0 <= float(value) <= 1.0:
            config[key] = float(value)
        else:
            errors.append(f"{LINT_CONFIG_REL}:overlap.{key} must be a number between 0 and 1")
    return config, errors


def target_paths(root: Path, target: str, by_name: dict[str, list[Path]], by_stem: dict[str, list[Path]]) -> list[Path]:
    text = target.split("|")[0].split("#")[0].strip()
    if not text:
        return []
    path = Path(text)
    path_qualified = len(path.parts) > 1 or text.startswith("/")
    if not path.is_absolute() and ".." not in path.parts:
        direct = root / path
        if direct.exists():
            return [direct]
        if not path.suffix:
            direct_md = root / Path(f"{text}.md")
            if direct_md.exists():
                return [direct_md]
            parent = root / path.parent
            if parent.exists():
                same_path_stem = sorted(
                    candidate
                    for candidate in parent.glob(f"{path.name}.*")
                    if candidate.is_file() and candidate.stem == path.name
                )
                if same_path_stem:
                    return same_path_stem
    if path_qualified:
        return []
    candidate = text.rsplit("/", 1)[-1]
    if candidate in by_name:
        return by_name[candidate]
    if candidate in by_stem:
        return by_stem[candidate]
    return []


def collect_notes(root: Path) -> tuple[list[dict[str, Any]], dict[Path, int]]:
    files = markdown_files(root)
    content_roots = active_content_roots(root)
    frontmatter_link_keys = profile_frontmatter_link_keys(root)
    by_name: dict[str, list[Path]] = {}
    by_stem: dict[str, list[Path]] = {}
    for path in files:
        by_name.setdefault(path.name, []).append(path)
        by_stem.setdefault(path.stem, []).append(path)

    inbound: dict[Path, int] = {path: 0 for path in files}
    parsed: list[tuple[Path, Path, dict[str, Any], str]] = []
    for path in files:
        rel = path.relative_to(root)
        text = path.read_text(encoding="utf-8", errors="ignore")
        fm, body = split_fm(text)
        parsed.append((path, rel, fm, body))
        body_clean = re.sub(r"`+[^`]*`+", "", body)
        targets = list(LINK_RE.findall(body_clean))
        for key in sorted(frontmatter_link_keys):
            value = fm.get(key)
            if isinstance(value, str):
                targets.extend(LINK_RE.findall(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        targets.extend(LINK_RE.findall(item))
        for target in targets:
            for linked in target_paths(root, target.replace("\\|", "|"), by_name, by_stem):
                if linked.suffix == ".md" and linked != path:
                    inbound[linked] = inbound.get(linked, 0) + 1

    notes: list[dict[str, Any]] = []
    for path, rel, fm, body in parsed:
        if not rel.parts or rel.parts[0] not in content_roots:
            continue
        note_type = str(fm.get("type", "") or "")
        status = str(fm.get("status", "") or "")
        if note_type in GENERATED_TYPES or status in ARCHIVED_STATUSES:
            continue
        title_words = normalized_words(str(fm.get("title", "") or ""))
        body_words = normalized_words(body)
        if not title_words and not body_words:
            continue
        notes.append(
            {
                "path": rel.as_posix(),
                "type": note_type or "unknown",
                "domain": str(fm.get("domain", "") or "unknown"),
                "title_words": title_words,
                "body_words": body_words,
                "title_token_count": len(title_words),
                "body_token_count": len(body_words),
                "inbound_links": inbound.get(path, 0),
            }
        )
    return notes, inbound


def pair_record(left: dict[str, Any], right: dict[str, Any], config: dict[str, int | float]) -> dict[str, Any]:
    left_title = left["title_words"]
    right_title = right["title_words"]
    left_body = left["body_words"]
    right_body = right["body_words"]
    title_score = jaccard(left_title, right_title)
    content_score = jaccard(left_body, right_body)
    shared_terms = len(left_body & right_body)
    title_hit = (
        len(left_title) >= 2
        and len(right_title) >= 2
        and title_score >= float(config["title_threshold"])
    )
    content_hit = (
        shared_terms >= int(config["min_shared_terms"])
        and content_score >= float(config["content_threshold"])
    )
    current = title_hit or content_hit
    near_miss = (
        not current
        and (
            (
                shared_terms >= max(2, int(config["min_shared_terms"]) - 5)
                and content_score >= max(0.0, float(config["content_threshold"]) - 0.10)
            )
            or title_score >= max(0.0, float(config["title_threshold"]) - 0.10)
        )
    )
    return {
        "left_path": left["path"],
        "right_path": right["path"],
        "left_type": left["type"],
        "right_type": right["type"],
        "left_domain": left["domain"],
        "right_domain": right["domain"],
        "same_domain": left["domain"] == right["domain"],
        "left_inbound_links": left["inbound_links"],
        "right_inbound_links": right["inbound_links"],
        "title_score": round(title_score, 4),
        "content_score": round(content_score, 4),
        "shared_terms": shared_terms,
        "current_candidate": current,
        "near_miss": near_miss,
        "reasons": [
            reason
            for reason, hit in (
                ("title", title_hit),
                ("content", content_hit),
            )
            if hit
        ],
    }


def rank_pair(pair: dict[str, Any]) -> tuple[float, float, int, int]:
    return (
        max(float(pair["title_score"]), float(pair["content_score"])),
        float(pair["content_score"]),
        int(pair["shared_terms"]),
        int(pair["left_inbound_links"]) + int(pair["right_inbound_links"]),
    )


def matrix_counts(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    content = []
    for min_terms in MIN_SHARED_TERM_BANDS:
        counts = {
            f"{threshold:.2f}": sum(
                1
                for pair in pairs
                if int(pair["shared_terms"]) >= min_terms and float(pair["content_score"]) >= threshold
            )
            for threshold in CONTENT_THRESHOLDS
        }
        content.append({"min_shared_terms": min_terms, "counts": counts})
    title = {
        f"{threshold:.2f}": sum(1 for pair in pairs if float(pair["title_score"]) >= threshold)
        for threshold in TITLE_THRESHOLDS
    }
    return {"content": content, "title": title}


def build_report(root: Path, max_pairs: int) -> tuple[dict[str, Any], list[str]]:
    config, errors = lint_config(root)
    notes, _inbound = collect_notes(root)
    pairs = [pair_record(left, right, config) for left, right in itertools.combinations(notes, 2)]
    pairs.sort(key=rank_pair, reverse=True)
    current = [pair for pair in pairs if pair["current_candidate"]]
    near_misses = [pair for pair in pairs if pair["near_miss"]]
    report = {
        "schema_version": 1,
        "config": config,
        "summary": {
            "curated_notes": len(notes),
            "comparable_pairs": len(pairs),
            "current_candidates": len(current),
            "near_misses": len(near_misses),
        },
        "threshold_matrix": matrix_counts(pairs),
        "current_candidates": current[:max_pairs],
        "near_misses": near_misses[:max_pairs],
    }
    return report, errors


def percent(value: float) -> str:
    return f"{value:.0%}"


def format_pair(pair: dict[str, Any]) -> str:
    reasons = ",".join(pair["reasons"]) or "near-miss"
    return (
        f"{pair['left_path']} <-> {pair['right_path']} "
        f"[reasons={reasons}; title={percent(float(pair['title_score']))}; "
        f"content={percent(float(pair['content_score']))}; shared_terms={pair['shared_terms']}; "
        f"same_domain={pair['same_domain']}; types={pair['left_type']}/{pair['right_type']}; "
        f"inbound={pair['left_inbound_links']}/{pair['right_inbound_links']}]"
    )


def print_text(report: dict[str, Any], errors: list[str]) -> None:
    summary = report["summary"]
    config = report["config"]
    print("overlap: read-only calibration report; no note bodies, shared terms, source text, or reviewer notes were printed")
    for error in errors:
        print(f"warning: {error}")
    print(
        "overlap: "
        f"curated_notes={summary['curated_notes']} comparable_pairs={summary['comparable_pairs']} "
        f"current_candidates={summary['current_candidates']} near_misses={summary['near_misses']}"
    )
    print(
        "overlap: current config "
        f"min_shared_terms={config['min_shared_terms']} "
        f"content_threshold={config['content_threshold']:.2f} "
        f"title_threshold={config['title_threshold']:.2f}"
    )
    print("\n## Content threshold matrix")
    for row in report["threshold_matrix"]["content"]:
        counts = " ".join(f">={threshold}:{count}" for threshold, count in row["counts"].items())
        print(f"  - min_shared_terms={row['min_shared_terms']}: {counts}")
    print("\n## Title threshold matrix")
    print("  - " + " ".join(f">={threshold}:{count}" for threshold, count in report["threshold_matrix"]["title"].items()))
    print(f"\n## Current candidate pairs: {summary['current_candidates']}")
    for pair in report["current_candidates"]:
        print("  - " + format_pair(pair))
    if not report["current_candidates"]:
        print("  - None at the current threshold.")
    print(f"\n## Near misses: {summary['near_misses']}")
    for pair in report["near_misses"]:
        print("  - " + format_pair(pair))
    if not report["near_misses"]:
        print("  - None near the current threshold.")
    print("\n## Operator next steps")
    print("  - Review candidate pairs before changing `_meta/lint-config.yml`; warnings remain human-gated.")
    print("  - If most candidates are false positives, raise thresholds or min_shared_terms in the copied pilot vault.")
    print("  - If real duplicates are missing, lower thresholds in the copied pilot vault and rerun `vaultwright overlap`.")


def print_worksheet(report: dict[str, Any], errors: list[str]) -> None:
    summary = report["summary"]
    config = report["config"]
    print("# Vaultwright Overlap Calibration Worksheet")
    print("")
    print("Generated by `vaultwright overlap --worksheet`. Read-only; no files were changed.")
    print("No note bodies, shared terms, source text, or reviewer notes are included.")
    print("")
    print("## Current Settings")
    print("")
    print(f"- Curated notes reviewed: {summary['curated_notes']}")
    print(f"- Comparable note pairs: {summary['comparable_pairs']}")
    print(f"- Current candidate pairs: {summary['current_candidates']}")
    print(f"- Near misses: {summary['near_misses']}")
    print(f"- `min_shared_terms`: {config['min_shared_terms']}")
    print(f"- `content_threshold`: {config['content_threshold']:.2f}")
    print(f"- `title_threshold`: {config['title_threshold']:.2f}")
    if errors:
        print("")
        print("## Configuration Warnings")
        print("")
        for error in errors:
            print(f"- {error}")
    print("")
    print("## Candidate Review")
    print("")
    if report["current_candidates"]:
        for index, pair in enumerate(report["current_candidates"], start=1):
            print(f"- [ ] Pair {index}: `{pair['left_path']}` <-> `{pair['right_path']}`")
            print(
                f"  - Scores: title={percent(float(pair['title_score']))}, "
                f"content={percent(float(pair['content_score']))}, shared_terms={pair['shared_terms']}"
            )
            print(f"  - Context: same_domain={pair['same_domain']}, types={pair['left_type']}/{pair['right_type']}")
            print("  - Reviewer decision: duplicate / related-but-distinct / false-positive")
    else:
        print("- [ ] No current candidates. Spot-check near misses if reviewers still see duplicate notes.")
    print("")
    print("## Threshold Decision")
    print("")
    print("- [ ] Keep defaults.")
    print("- [ ] Increase thresholds because candidates are mostly false positives.")
    print("- [ ] Decrease thresholds because reviewers found missed duplicates.")
    print("- [ ] Record the reason for any `_meta/lint-config.yml` change in the private pilot notes.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a Vaultwright overlap calibration report.")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Print machine-readable overlap calibration JSON.")
    output.add_argument("--worksheet", action="store_true", help="Print a Markdown calibration worksheet.")
    parser.add_argument("--max-pairs", type=int, default=40, help="Maximum current/near-miss pairs to print.")
    return parser


def main(argv: list[str] | None = None, root: Path | None = None) -> int:
    args = build_parser().parse_args(argv)
    active_root = (root or DEFAULT_ROOT).expanduser().resolve()
    if args.max_pairs < 0:
        print("overlap: --max-pairs must be >= 0", file=sys.stderr)
        return 2
    report, errors = build_report(active_root, args.max_pairs)
    if args.json:
        payload = {"report": report, "warnings": errors}
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.worksheet:
        print_worksheet(report, errors)
    else:
        print_text(report, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
