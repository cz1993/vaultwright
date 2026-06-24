#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Record and summarize human review decisions for generated Vaultwright artifacts.

The ledger is metadata-only: it stores artifact paths, hashes, reviewer/status fields, and short
operator notes. It does not copy artifact bodies or source document text.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from vaultwright.runtime_profile import is_office_mirror_path, is_repo_notes_path

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pip install pyyaml")


DEFAULT_ROOT = Path.cwd()
LEDGER_REL = Path("_meta/review-ledger.jsonl")
VALID_STATUSES = {"approved", "needs-work", "blocked", "deferred"}
MAX_NOTE_CHARS = 400
FRONTMATTER_METADATA_KEYS = {
    "type",
    "source_id",
    "source",
    "source_format",
    "source_sha256",
    "repo_id",
    "repo",
    "resolved_repo",
    "commit",
}
META_REVIEWABLE_NAMES = {
    "agent-readiness-results.yml",
    "agent-readiness-tasks.yml",
    "m365-handoff-report.json",
    "m365-handoff-report.txt",
    "repo-manifest.json",
    "source-manifest.json",
    "sync-audit.jsonl",
}


def now_iso() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def file_mtime_iso(path: Path) -> str:
    return dt.datetime.fromtimestamp(path.stat().st_mtime).astimezone().replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_rel(root: Path, path: Path) -> Path:
    candidate = path.expanduser() if path.is_absolute() else root / path
    if candidate.is_symlink():
        raise ValueError("artifact path must not be a symlink")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("artifact path must stay inside the vault")
    rel = resolved.relative_to(root)
    if not rel.parts or any(part.startswith(".") for part in rel.parts):
        raise ValueError("artifact path must not use hidden path components")
    if not resolved.exists() or not resolved.is_file():
        raise ValueError("artifact path must be an existing regular file")
    return rel


def split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    raw = text[3:end].lstrip("\n")
    body = text[end + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        return None, text
    return data if isinstance(data, dict) else None, body


def read_artifact_frontmatter(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    fm, _body = split_frontmatter(text)
    return fm


def metadata_from_frontmatter(fm: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(fm, dict):
        return {}
    metadata: dict[str, str] = {}
    for key in sorted(FRONTMATTER_METADATA_KEYS):
        value = fm.get(key)
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            metadata[key] = str(value)
    return metadata


def classify_artifact(root: Path, rel: Path, fm: dict[str, Any] | None) -> str:
    type_value = str((fm or {}).get("type", "") or "")
    if type_value in {"source-mirror", "repo-mirror"}:
        return type_value
    if rel.as_posix() == "CATALOG.md":
        return "catalog-markdown"
    if rel.as_posix() == "CATALOG.html":
        return "catalog-html"
    if is_office_mirror_path(root, rel):
        return "generated-source-mirror"
    if is_repo_notes_path(root, rel) and rel.suffix.lower() == ".md":
        return "repo-mirror"
    if rel.parts[:1] == ("_meta",) and (rel.name in META_REVIEWABLE_NAMES or "report" in rel.name):
        return "meta-report"
    raise ValueError(
        "artifact must be a generated mirror, repo mirror, catalog, or reviewable _meta report"
    )


def clean_note(note: str) -> str:
    stripped = (note or "").strip()
    if not stripped:
        return ""
    if "\n" in stripped or "\r" in stripped:
        raise ValueError("note must be one short line; do not paste source content")
    if len(stripped) > MAX_NOTE_CHARS:
        raise ValueError(f"note must be {MAX_NOTE_CHARS} characters or fewer")
    return stripped


def load_ledger(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = root / LEDGER_REL
    if not path.exists():
        return [], []
    events: list[dict[str, Any]] = []
    warnings: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return [], [f"{LEDGER_REL.as_posix()}: unreadable text"]
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            warnings.append(f"{LEDGER_REL.as_posix()}: line {line_number} invalid JSON; skipped")
            continue
        if not isinstance(event, dict):
            warnings.append(f"{LEDGER_REL.as_posix()}: line {line_number} is not an object; skipped")
            continue
        events.append(event)
    return events, warnings


def latest_by_artifact(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for event in events:
        artifact = str(event.get("artifact_path", "") or "")
        if not artifact:
            continue
        latest[artifact] = event
    return dict(sorted(latest.items()))


def current_state(root: Path, event: dict[str, Any]) -> str:
    artifact = str(event.get("artifact_path", "") or "")
    if not artifact:
        return "invalid"
    rel = Path(artifact)
    if rel.is_absolute() or ".." in rel.parts:
        return "invalid"
    path = root / rel
    if not path.exists():
        return "missing"
    try:
        current_hash = sha256_file(path)
    except OSError:
        return "unreadable"
    if current_hash != str(event.get("artifact_sha256", "") or ""):
        return "stale"
    return "current"


def build_report(root: Path) -> tuple[dict[str, Any], list[str]]:
    events, warnings = load_ledger(root)
    latest = latest_by_artifact(events)
    statuses = Counter(str(event.get("status", "unknown") or "unknown") for event in latest.values())
    kinds = Counter(str(event.get("artifact_kind", "unknown") or "unknown") for event in latest.values())
    reviewers = Counter(str(event.get("reviewer", "unknown") or "unknown") for event in latest.values())
    current_states: dict[str, int] = Counter()
    entries: list[dict[str, Any]] = []
    for artifact, event in latest.items():
        state = current_state(root, event)
        current_states[state] += 1
        entries.append(
            {
                "artifact_path": artifact,
                "artifact_kind": event.get("artifact_kind", "unknown"),
                "status": event.get("status", "unknown"),
                "reviewer": event.get("reviewer", "unknown"),
                "timestamp": event.get("timestamp"),
                "artifact_sha256": event.get("artifact_sha256"),
                "current_state": state,
                "note": event.get("note", ""),
            }
        )
    report = {
        "ledger_path": LEDGER_REL.as_posix(),
        "events": len(events),
        "reviewed_artifacts": len(latest),
        "statuses": dict(sorted(statuses.items())),
        "artifact_kinds": dict(sorted(kinds.items())),
        "reviewers": dict(sorted(reviewers.items())),
        "current_states": dict(sorted(current_states.items())),
        "latest_reviews": entries,
    }
    return report, warnings


def record_review(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    if not args.status:
        raise ValueError("--status is required when --artifact is provided")
    if not args.reviewer or not args.reviewer.strip():
        raise ValueError("--reviewer is required when --artifact is provided")
    rel = safe_rel(root, args.artifact)
    path = root / rel
    fm = read_artifact_frontmatter(path)
    artifact_kind = args.kind or classify_artifact(root, rel, fm)
    status = str(args.status)
    if status not in VALID_STATUSES:
        raise ValueError(f"--status must be one of: {', '.join(sorted(VALID_STATUSES))}")
    event = {
        "timestamp": now_iso(),
        "artifact_path": rel.as_posix(),
        "artifact_kind": artifact_kind,
        "artifact_sha256": sha256_file(path),
        "artifact_size": path.stat().st_size,
        "artifact_modified": file_mtime_iso(path),
        "status": status,
        "reviewer": args.reviewer.strip(),
        "note": clean_note(args.note or ""),
        "metadata": metadata_from_frontmatter(fm),
    }
    ledger = root / LEDGER_REL
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")
    return event


def print_report(root: Path, report: dict[str, Any], warnings: list[str]) -> None:
    print(f"review ledger: {root}")
    print("review ledger: metadata-only review decisions; no artifact content was printed")
    print()
    print(f"ledger: {report['ledger_path']} ({report['events']} event(s))")
    print("summary:")
    print(f"  - reviewed artifacts: {report['reviewed_artifacts']}")
    for status, count in report["statuses"].items():
        print(f"  - {status}: {count}")
    for state, count in report["current_states"].items():
        print(f"  - {state} reviews: {count}")
    if warnings:
        print("warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    latest = report["latest_reviews"]
    print()
    print("latest reviews:")
    if not latest:
        print("  - none")
        return
    for entry in latest[:25]:
        digest = str(entry.get("artifact_sha256", ""))[:12]
        print(
            "  - "
            f"[{entry['status']}/{entry['current_state']}] "
            f"{entry['artifact_path']} "
            f"kind={entry['artifact_kind']} reviewer={entry['reviewer']} hash={digest}"
        )
    if len(latest) > 25:
        print(f"  - ... {len(latest) - 25} more")


def check_report(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not report["latest_reviews"]:
        failures.append("no reviewed artifacts recorded")
    for entry in report["latest_reviews"]:
        if entry.get("current_state") != "current":
            failures.append(f"{entry['artifact_path']}: review is {entry['current_state']}")
        if entry.get("status") != "approved":
            failures.append(f"{entry['artifact_path']}: latest status is {entry['status']}")
    return failures


def build_parser(default_root: Path | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record and summarize Vaultwright review ledger events.")
    parser.add_argument(
        "--root",
        type=Path,
        default=default_root or DEFAULT_ROOT,
        help="Vault root. Defaults to the current working directory.",
    )
    parser.add_argument("--artifact", type=Path, help="Generated artifact to review, relative to the vault root.")
    parser.add_argument("--status", choices=sorted(VALID_STATUSES), help="Review decision to record.")
    parser.add_argument("--reviewer", help="Reviewer name or role for a recorded decision.")
    parser.add_argument("--note", default="", help="Short metadata-only review note. Do not paste source content.")
    parser.add_argument("--kind", help="Override artifact kind after path safety checks.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output.")
    parser.add_argument("--check", action="store_true", help="Fail unless every latest review is approved and current.")
    return parser


def main(argv: list[str] | None = None, root: Path | None = None) -> int:
    parser = build_parser(root)
    args = parser.parse_args(argv)
    root = (root or args.root).expanduser().resolve()

    try:
        if args.artifact:
            event = record_review(root, args)
            if args.json:
                print(json.dumps({"recorded": event}, indent=2, sort_keys=True))
            else:
                print(
                    "review ledger: recorded "
                    f"{event['status']} for {event['artifact_path']} "
                    f"({event['artifact_kind']}, hash={event['artifact_sha256'][:12]})"
                )
            return 0

        report, warnings = build_report(root)
        if args.json:
            print(json.dumps({"report": report, "warnings": warnings}, indent=2, sort_keys=True))
        else:
            print_report(root, report, warnings)
        if args.check:
            failures = check_report(report)
            for failure in failures:
                print(f"review ledger: {failure}", file=sys.stderr)
            return 1 if failures else 0
        return 0
    except ValueError as exc:
        print(f"review ledger: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
