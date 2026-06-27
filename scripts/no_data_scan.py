#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fail on likely secrets, credentials, PII, or unsafe data files.

The scanner is intentionally conservative and dependency-free. It is not a
replacement for human review, but it catches high-risk patterns before they
enter git history.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

MAX_FILE_BYTES = 5 * 1024 * 1024

SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}

LOCAL_DERIVED_STATE_DIRS = {".vaultwright"}

HIGH_RISK_NAME_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"(^|[._-])\.?env($|[._-])",
        r"(^|[._-])id_(rsa|dsa|ecdsa|ed25519)$",
        r"(secret|credential|password|client_secret|api[_-]?key)",
        r"\.(pem|p12|pfx|key|token)$",
    )
]

HIGH_RISK_PATH_PARTS = {
    "credentials",
    "data",
    "private",
    "secret",
    "secrets",
}

GENERATED_ARTIFACT_NAMES = {".DS_Store", "Thumbs.db", "thumbs.db"}
GENERATED_ARTIFACT_DIRS = {"build", "dist"}
GENERATED_ARTIFACT_PARTS = {"__MACOSX"}
GENERATED_ARTIFACT_SUFFIXES = {".log"}
PRIVATE_RESULT_FILENAMES = {"agent-readiness-results.yml", "agent-readiness-results.yaml"}
PRIVATE_TASK_FILENAMES = {"agent-readiness-tasks.yml", "agent-readiness-tasks.yaml"}
PRIVATE_CONVERSION_RESULT_FILENAMES = {
    "conversion-quality-results.yml",
    "conversion-quality-results.yaml",
}
PUBLIC_TASK_PACKS = {
    "examples/government-services-vault/_meta/agent-readiness-tasks.yml",
}
YAML_SUFFIXES = {".yaml", ".yml"}

DISALLOWED_DATA_EXTS = {
    ".7z",
    ".csv",
    ".db",
    ".doc",
    ".docx",
    ".gz",
    ".jsonl",
    ".parquet",
    ".pdf",
    ".ppt",
    ".pptx",
    ".sqlite",
    ".tar",
    ".tsv",
    ".xls",
    ".xlsx",
    ".zip",
}

SECRET_PATTERNS = [
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("github token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b")),
    ("github fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("openai api key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("aws access key", re.compile(r"\b(A3T[A-Z0-9]|AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
]

OOXML_EXTS = {".docx", ".pptx", ".xlsx"}
OOXML_TEXT_PART_SUFFIXES = (".xml", ".rels", ".txt", ".csv")
OOXML_CONTENT_PART_PREFIXES = (
    "customxml/",
    "word/document.xml",
    "word/header",
    "word/footer",
    "word/comments",
    "word/footnotes",
    "word/endnotes",
    "ppt/slides/",
    "ppt/notesSlides/",
    "xl/sharedStrings.xml",
    "xl/worksheets/",
    "xl/comments",
)
PROVENANCE_FILES = (
    "examples/DATA_PROVENANCE.md",
    "tests/fixtures/DATA_PROVENANCE.md",
)
ALLOWED_OFFICE_METADATA = {
    "",
    "Vaultwright",
    "Vaultwright Example",
    "Northwind Robotics",
}
IDENTITY_METADATA_FIELDS = {
    "category",
    "company",
    "contentstatus",
    "creator",
    "description",
    "hyperlinkbase",
    "identifier",
    "keywords",
    "lastmodifiedby",
    "manager",
    "subject",
    "title",
}


def run_git(args: list[str], root: Path, *, text: bool = False) -> list[str] | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=text,
    )
    if not text:
        return result.stdout
    return result.stdout.splitlines()


def git_paths(args: list[str], root: Path) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [p for p in result.stdout.decode().split("\0") if p]


def repo_root() -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(result.stdout.strip()).resolve()
    except Exception:
        return Path.cwd().resolve()


def path_is_skipped(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def local_derived_state_part(rel: str) -> str:
    for part in Path(rel).parts:
        if part in LOCAL_DERIVED_STATE_DIRS:
            return part
    return ""


def path_is_tracked(root: Path, rel: str) -> bool:
    try:
        lines = run_git(["ls-files", "--error-unmatch", "--", rel], root, text=True)
    except subprocess.CalledProcessError:
        return False
    assert isinstance(lines, list)
    return bool(lines)


def provenance_texts(root: Path, staged: bool) -> list[str]:
    texts: list[str] = []
    for rel in PROVENANCE_FILES:
        if staged:
            try:
                raw = run_git(["show", f":{rel}"], root)
            except subprocess.CalledProcessError:
                continue
            assert isinstance(raw, bytes)
            texts.append(raw.decode("utf-8", errors="ignore"))
            continue
        path = root / rel
        if path.exists():
            texts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return texts


def provenance_allowlist(root: Path, *, staged: bool = False) -> set[str]:
    allowed: set[str] = set()
    path_re = re.compile(r"`([^`]+\.(?:7z|csv|db|doc|docx|gz|jsonl|parquet|pdf|ppt|pptx|sqlite|tar|tsv|xls|xlsx|zip))`")
    for text in provenance_texts(root, staged):
        for match in path_re.findall(text):
            allowed.add(match.replace(os.sep, "/"))
    return allowed


def staged_mode(root: Path, rel: str) -> str:
    try:
        lines = run_git(["ls-files", "-s", "--", rel], root, text=True)
    except subprocess.CalledProcessError:
        return ""
    assert isinstance(lines, list)
    return lines[0].split()[0] if lines else ""


def collect_paths(root: Path, args: argparse.Namespace) -> list[tuple[str, Path | None, bytes | None, str]]:
    if args.paths:
        out = []
        for p in args.paths:
            path = Path(p)
            abs_path = path if path.is_absolute() else Path.cwd() / path
            try:
                rel = str(abs_path.absolute().relative_to(root)).replace(os.sep, "/")
            except ValueError:
                rel = str(abs_path.absolute())
            mode = "120000" if abs_path.is_symlink() else ""
            out.append((rel, abs_path, None, mode))
        return out
    if args.staged:
        rels = git_paths(["diff", "--cached", "--name-only", "-z", "--diff-filter=ACMRT"], root)
        out = []
        for rel in rels:
            try:
                raw = run_git(["show", f":{rel}"], root)
            except subprocess.CalledProcessError:
                continue
            assert isinstance(raw, bytes)
            out.append((rel.replace(os.sep, "/"), None, raw, staged_mode(root, rel)))
        return out
    rels = git_paths(["ls-files", "-z", "--cached", "--others", "--exclude-standard"], root)
    ignored = git_paths(["ls-files", "-z", "--others", "--ignored", "--exclude-standard"], root)
    rels = sorted(set(rels + ignored))
    return [(rel.replace(os.sep, "/"), root / rel, None, "") for rel in rels]


def luhn_ok(number: str) -> bool:
    digits = [int(ch) for ch in number if ch.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    parity = len(digits) % 2
    for idx, digit in enumerate(digits):
        if idx % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def scan_text_patterns(rel: str, text: str, *, include_payment_card: bool = True) -> list[str]:
    findings: list[str] = []
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(f"{rel}: possible {label}")

    if not include_payment_card:
        return findings

    for match in re.finditer(r"\b(?:\d[ -]*?){13,19}\b", text):
        candidate = match.group(0)
        digits = re.sub(r"\D", "", candidate)
        if luhn_ok(digits):
            findings.append(f"{rel}: possible payment card number")
            break
    return findings


def looks_like_agent_readiness_results(rel_path: Path, text: str) -> bool:
    if rel_path.suffix.lower() not in YAML_SUFFIXES or "_meta" not in rel_path.parts:
        return False
    required_patterns = (
        r"(?m)^\s*schema_version\s*:\s*1\s*$",
        r"(?m)^\s*results\s*:\s*$",
        r"(?m)^\s*-\s*task_id\s*:",
        r"(?m)^\s*mode\s*:",
        r"(?m)^\s*score\s*:",
    )
    return all(re.search(pattern, text) for pattern in required_patterns)


def looks_like_agent_readiness_tasks(rel_path: Path, text: str) -> bool:
    if rel_path.suffix.lower() not in YAML_SUFFIXES or "_meta" not in rel_path.parts:
        return False
    required_patterns = (
        r"(?m)^\s*schema_version\s*:\s*1\s*$",
        r"(?m)^\s*tasks\s*:\s*$",
        r"(?m)^\s*-\s*id\s*:",
        r"(?m)^\s*family\s*:",
        r"(?m)^\s*prompt\s*:",
        r"(?m)^\s*success_criteria\s*:",
    )
    return all(re.search(pattern, text) for pattern in required_patterns)


def looks_like_conversion_quality_results(rel_path: Path, text: str) -> bool:
    if rel_path.suffix.lower() not in YAML_SUFFIXES or "_meta" not in rel_path.parts:
        return False
    required_patterns = (
        r"(?m)^\s*schema_version\s*:\s*1\s*$",
        r"(?m)^\s*reviews\s*:\s*$",
        r"(?m)^\s*-\s*source_id\s*:",
        r"(?m)^\s*status\s*:",
        r"(?m)^\s*score\s*:",
    )
    return all(re.search(pattern, text) for pattern in required_patterns)


def public_task_pack_allowed(rel: str) -> bool:
    return rel.replace(os.sep, "/") in PUBLIC_TASK_PACKS


def is_ooxml_content_part(name: str) -> bool:
    low = name.lower()
    return any(low == prefix.lower() or low.startswith(prefix.lower()) for prefix in OOXML_CONTENT_PART_PREFIXES)


def xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def node_text(node: ET.Element) -> str:
    return " ".join(part.strip() for part in node.itertext() if part.strip()).strip()


def scan_docprops_metadata(rel: str, part_name: str, xml: bytes) -> list[str]:
    findings: list[str] = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        findings.append(f"{rel}: invalid OOXML metadata")
        return findings

    part_rel = f"{rel}:{part_name}"
    if part_name.lower() == "docprops/custom.xml":
        for prop in root.iter():
            if xml_local_name(prop.tag) != "property":
                continue
            prop_name = (prop.attrib.get("name") or "").strip()
            prop_value = node_text(prop)
            if prop_name and prop_name not in ALLOWED_OFFICE_METADATA:
                findings.append(f"{part_rel}: unexpected OOXML custom metadata name")
            if prop_value and prop_value not in ALLOWED_OFFICE_METADATA:
                findings.append(f"{part_rel}: unexpected OOXML custom metadata value")
        return findings

    for node in root.iter():
        label = xml_local_name(node.tag).lower()
        if label not in IDENTITY_METADATA_FIELDS:
            continue
        value = node_text(node)
        if value and value not in ALLOWED_OFFICE_METADATA:
            findings.append(f"{part_rel}: unexpected OOXML {label} metadata")
    return findings


def scan_ooxml(rel: str, raw: bytes) -> list[str]:
    findings: list[str] = []
    text_parts: list[tuple[str, bytes]] = []
    try:
        with ZipFile(io.BytesIO(raw)) as zf:
            for name in zf.namelist():
                if name.lower().endswith(OOXML_TEXT_PART_SUFFIXES):
                    text_parts.append((name, zf.read(name)))
    except (BadZipFile, OSError):
        return findings

    for part_name, xml in text_parts:
        part_rel = f"{rel}:{part_name}"
        raw_text = xml.decode("utf-8", errors="ignore")
        content_part = is_ooxml_content_part(part_name) or part_name.lower().endswith(".rels")
        findings.extend(scan_text_patterns(part_rel, raw_text, include_payment_card=content_part))
        if part_name.lower().startswith("docprops/"):
            findings.extend(scan_docprops_metadata(rel, part_name, xml))
        try:
            part_root = ET.fromstring(xml)
            attr_text = " ".join(
                str(value)
                for node in part_root.iter()
                for value in node.attrib.values()
            )
            text = " ".join([*part_root.itertext(), attr_text])
        except ET.ParseError:
            text = raw_text
        for finding in scan_text_patterns(part_rel, text, include_payment_card=content_part):
            findings.append(finding)
    return findings


def scan_bytes(
    root: Path,
    rel: str,
    raw: bytes,
    size: int,
    allowed_data: set[str],
    *,
    allow_generated_sync_audit: bool = False,
) -> list[str]:
    findings: list[str] = []
    rel_path = Path(rel)
    skipped_parts = [part for part in rel_path.parts if part in SKIP_DIRS]
    if skipped_parts:
        findings.append(f"{rel}: generated/vendor directory must not be committed ({skipped_parts[0]})")
    generated_parts = [
        part
        for part in rel_path.parts[:-1]
        if part in GENERATED_ARTIFACT_DIRS or part.endswith(".egg-info")
    ]
    if generated_parts:
        findings.append(f"{rel}: generated/vendor directory must not be committed ({generated_parts[0]})")

    name = rel_path.name
    if name in PRIVATE_RESULT_FILENAMES and "_meta" in rel_path.parts:
        findings.append(f"{rel}: benchmark result packs must stay out of the public repo")
    if name in PRIVATE_CONVERSION_RESULT_FILENAMES and "_meta" in rel_path.parts:
        findings.append(f"{rel}: conversion quality result packs must stay out of the public repo")
    private_task_pack_name = (
        name in PRIVATE_TASK_FILENAMES
        and "_meta" in rel_path.parts
        and not public_task_pack_allowed(rel)
    )
    if private_task_pack_name:
        findings.append(f"{rel}: private benchmark task packs must stay out of the public repo")

    if (
        name in GENERATED_ARTIFACT_NAMES
        or rel_path.suffix.lower() in GENERATED_ARTIFACT_SUFFIXES
        or any(part in GENERATED_ARTIFACT_PARTS for part in rel_path.parts)
    ):
        findings.append(f"{rel}: generated/OS artifact must not be committed")

    for pattern in HIGH_RISK_NAME_PATTERNS:
        if pattern.search(name):
            findings.append(f"{rel}: high-risk filename")
            break

    # Repo paths are relative. Explicit external paths may be absolute; do not let
    # macOS system prefixes such as /private/var/... produce false positives.
    if not rel_path.is_absolute():
        high_risk_parts = HIGH_RISK_PATH_PARTS.intersection(part.lower() for part in rel_path.parts[:-1])
        if high_risk_parts:
            findings.append(f"{rel}: high-risk path component ({sorted(high_risk_parts)[0]})")

    suffix = rel_path.suffix.lower()
    generated_sync_audit = (
        allow_generated_sync_audit
        and rel_path.name == "sync-audit.jsonl"
        and rel_path.parent.name == "_meta"
    )
    if suffix in DISALLOWED_DATA_EXTS and rel not in allowed_data and not generated_sync_audit:
        findings.append(f"{rel}: data/binary file must be listed in DATA_PROVENANCE.md")

    if size > MAX_FILE_BYTES and rel not in allowed_data:
        findings.append(f"{rel}: file is larger than {MAX_FILE_BYTES} bytes")
        return findings

    if suffix in OOXML_EXTS:
        findings.extend(scan_ooxml(rel, raw))

    if b"\0" in raw[:4096]:
        return findings

    text = raw.decode("utf-8", errors="ignore")
    if looks_like_agent_readiness_results(rel_path, text):
        findings.append(f"{rel}: benchmark result packs must stay out of the public repo")
    if looks_like_conversion_quality_results(rel_path, text):
        findings.append(f"{rel}: conversion quality result packs must stay out of the public repo")
    if (
        looks_like_agent_readiness_tasks(rel_path, text)
        and not public_task_pack_allowed(rel)
        and not private_task_pack_name
    ):
        findings.append(f"{rel}: private benchmark task packs must stay out of the public repo")
    findings.extend(scan_text_patterns(rel, text))
    return findings


def scan_file(
    root: Path,
    rel: str,
    path: Path | None,
    raw: bytes | None,
    mode: str,
    allowed_data: set[str],
    *,
    allow_generated_sync_audit: bool = False,
) -> list[str]:
    symlink_findings = [f"{rel}: symlink must not be committed"] if mode == "120000" else []
    if raw is None:
        if path is None:
            return symlink_findings
        if path.is_symlink():
            if not symlink_findings:
                symlink_findings.append(f"{rel}: symlink must not be committed")
            try:
                raw = os.readlink(path).encode("utf-8", errors="ignore")
            except OSError:
                raw = b""
            size = len(raw)
            return symlink_findings + scan_bytes(
                root,
                rel,
                raw,
                size,
                allowed_data,
                allow_generated_sync_audit=allow_generated_sync_audit,
            )
        if not path.exists():
            return symlink_findings
        if not path.is_file():
            return symlink_findings
        try:
            raw = path.read_bytes()
        except OSError as exc:
            return symlink_findings + [f"{rel}: unreadable ({exc.__class__.__name__})"]
        size = path.stat().st_size
    else:
        size = len(raw)
    return symlink_findings + scan_bytes(
        root,
        rel,
        raw,
        size,
        allowed_data,
        allow_generated_sync_audit=allow_generated_sync_audit,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan the repo for likely data or secrets.")
    parser.add_argument("--staged", action="store_true", help="scan staged files only")
    parser.add_argument("--paths", nargs="*", help="explicit paths to scan")
    args = parser.parse_args()

    root = repo_root()
    allowed_data = provenance_allowlist(root, staged=args.staged)
    allow_generated_sync_audit = bool(args.paths and not args.staged)
    findings: list[str] = []
    for rel, path, raw, mode in collect_paths(root, args):
        local_state = local_derived_state_part(rel)
        if local_state and (args.staged or (not args.paths and path_is_tracked(root, rel))):
            findings.append(f"{rel}: local derived state must not be committed ({local_state})")
            continue
        if local_state and not args.paths:
            continue
        findings.extend(
            scan_file(
                root,
                rel,
                path,
                raw,
                mode,
                allowed_data,
                allow_generated_sync_audit=allow_generated_sync_audit,
            )
        )

    if findings:
        print("no_data_scan: issues found", file=sys.stderr)
        for finding in findings:
            print(f"  - {finding}", file=sys.stderr)
        return 1
    print("no_data_scan: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
