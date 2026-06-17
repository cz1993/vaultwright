#!/usr/bin/env python3
"""
sync_office_md.py — keep markdown mirrors of Office files in sync.

For every .docx/.pptx/.xlsx/.doc in the vault, write a sibling `<name>.md` "mirror":
the original stays the editable source of truth; the mirror makes its content
searchable, linkable, and visible in Obsidian — and refreshes when the original
changes (detected by content hash, so runs are idempotent and cheap).

Each mirror has two regions:
  • a human-curated region (frontmatter + a `## Notes` section) — PRESERVED across syncs
  • an auto-generated region below the sentinel line — REGENERATED from the original

Usage:
  python3 tools/sync_office_md.py                 # sync the whole vault (dir of this script's parent)
  python3 tools/sync_office_md.py --root /path    # explicit vault root
  python3 tools/sync_office_md.py --dry-run       # show what would change, write nothing
  python3 tools/sync_office_md.py --force         # rebuild mirrors even if unchanged
  python3 tools/sync_office_md.py --include-pdf   # also mirror text-based PDFs
  python3 tools/sync_office_md.py --no-log        # don't append a summary line to log.md

Requires:  pip install markitdown pyyaml
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pip install pyyaml")

try:
    from markitdown import MarkItDown
except ImportError:
    sys.exit("Missing dependency: pip install markitdown")

# --- configuration ---------------------------------------------------------

DEFAULT_EXTS = [".docx", ".pptx", ".xlsx", ".doc"]
PDF_EXTS = [".pdf"]

# Skip these directory names (and anything under them).
EXCLUDE_EXACT = {"_templates", "_tmp", "tools", "node_modules"}
EXCLUDE_PREFIX = ("_archive", "_backup", "_deprecated")

SENTINEL = "%% AUTO-GENERATED BELOW — DO NOT EDIT %%"

# Frontmatter keys the script owns and overwrites on every sync.
MANAGED_KEYS = {
    "type", "source", "source_format", "source_modified",
    "synced", "source_sha256", "updated",
}
# Canonical key order for tidy, diff-friendly frontmatter.
KEY_ORDER = [
    "title", "type", "status", "domain", "owner", "created", "updated",
    "tags", "related", "client", "program", "vendor",
    "source", "source_format", "source_modified", "synced", "source_sha256",
]

MAX_CHARS = 400_000  # safety cap on extracted text per file


# --- helpers ---------------------------------------------------------------

def now_iso() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def file_mtime_iso(p: Path) -> str:
    return dt.datetime.fromtimestamp(p.stat().st_mtime).astimezone().replace(microsecond=0).isoformat()


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_excluded(rel: Path) -> bool:
    for part in rel.parts:
        if part.startswith("."):
            return True
        if part in EXCLUDE_EXACT:
            return True
        if part.startswith(EXCLUDE_PREFIX):
            return True
    return False


def humanize(stem: str) -> str:
    return stem.replace("_", " ").replace("-", " ").strip()


def split_frontmatter(text: str):
    """Return (frontmatter_dict_or_None, body_str)."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm_raw = text[3:end].lstrip("\n")
            body = text[end + 4:]
            if body.startswith("\n"):
                body = body[1:]
            try:
                return (yaml.safe_load(fm_raw) or {}), body
            except yaml.YAMLError:
                return None, text
    return None, text


def dump_frontmatter(data: dict) -> str:
    ordered = {k: data[k] for k in KEY_ORDER if k in data}
    for k, v in data.items():
        if k not in ordered:
            ordered[k] = v
    text = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{text}---\n"


def managed_frontmatter(existing: dict | None, src: Path, root: Path, sha: str) -> dict:
    fm = dict(existing or {})
    domain = src.relative_to(root).parts[0] if len(src.relative_to(root).parts) > 1 else ""
    fm.setdefault("title", humanize(src.stem))
    fm.setdefault("status", "active")
    fm.setdefault("domain", domain)
    fm.setdefault("owner", "CZ")
    fm.setdefault("tags", [])
    fm.setdefault("related", [])
    fm.setdefault("created", dt.date.today().isoformat())
    # managed (always overwritten):
    fm["type"] = "source-mirror"
    fm["source"] = src.name
    fm["source_format"] = src.suffix.lstrip(".").lower()
    fm["source_modified"] = file_mtime_iso(src)
    fm["synced"] = now_iso()
    fm["source_sha256"] = sha
    fm["updated"] = dt.date.today().isoformat()
    return fm


def fresh_preserved_region(src: Path) -> str:
    return (
        f"> [!info] Source-mirrored document — auto-generated\n"
        f"> Original: [[{src.name}]] · edit the **original**, never this mirror.\n"
        f"> Curate notes below; everything under the line refreshes on each sync.\n\n"
        f"## Notes\n\n\n"
    )


def auto_region(extracted: str) -> str:
    body = extracted.strip() if extracted else "_(no extractable text found in the source)_"
    if len(body) > MAX_CHARS:
        body = body[:MAX_CHARS] + "\n\n> _…truncated; see the original for full content._"
    return f"{SENTINEL}\n\n## Extracted content\n\n{body}\n"


# --- core ------------------------------------------------------------------

def mirror_path_for(src: Path) -> tuple[Path, bool]:
    """Return (mirror_path, is_collision). Prefer <stem>.md; if that exists and is NOT
    a managed mirror, fall back to <stem>.mirror.md so a hand-authored note is never clobbered."""
    sibling = src.with_suffix(".md")
    if sibling.exists():
        head = sibling.read_text(encoding="utf-8", errors="ignore")[:400]
        fm, _ = split_frontmatter(head + "\n---\n") if "---" in head else (None, "")
        is_mirror = "type: source-mirror" in head or (isinstance(fm, dict) and fm.get("type") == "source-mirror")
        if not is_mirror:
            return src.with_name(src.stem + ".mirror.md"), True
    return sibling, False


def sync_one(src: Path, root: Path, converter: MarkItDown, force: bool, dry: bool):
    """Return status string: created | updated | unchanged | skipped:<reason> | error:<msg>."""
    try:
        sha = sha256_of(src)
    except Exception as e:  # cloud-only placeholder / permission
        return f"skipped:unreadable ({e.__class__.__name__})"

    mirror, collision = mirror_path_for(src)
    existing_fm, existing_body = (None, "")
    if mirror.exists():
        existing_fm, existing_body = split_frontmatter(mirror.read_text(encoding="utf-8"))
        if not force and isinstance(existing_fm, dict) and existing_fm.get("source_sha256") == sha:
            return "unchanged"

    try:
        extracted = converter.convert(str(src)).text_content
    except Exception as e:
        name = e.__class__.__name__
        if "UnsupportedFormat" in name:
            return "skipped:unsupported-format (legacy/no converter)"
        return f"error:{name}: {str(e)[:120]}"

    # preserve the curated region (above the sentinel) if the mirror already exists
    if existing_body and SENTINEL in existing_body:
        preserved = existing_body.split(SENTINEL, 1)[0].rstrip() + "\n\n"
    elif existing_body:
        preserved = existing_body.rstrip() + "\n\n"
    else:
        preserved = fresh_preserved_region(src)

    fm = managed_frontmatter(existing_fm if isinstance(existing_fm, dict) else None, src, root, sha)
    content = dump_frontmatter(fm) + "\n" + preserved + auto_region(extracted)

    status = "updated" if mirror.exists() else "created"
    if collision and status == "created":
        status = "created(.mirror.md — sibling .md was hand-authored)"
    if not dry:
        mirror.write_text(content, encoding="utf-8")
    return status


def discover(root: Path, exts: list[str]) -> list[Path]:
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in exts:
            continue
        if is_excluded(p.relative_to(root).parent):
            continue
        out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser(description="Sync markdown mirrors of Office files.")
    ap.add_argument("--root", type=Path, default=None, help="Vault root (default: parent of this script).")
    ap.add_argument("--include-pdf", action="store_true", help="Also mirror text-based PDFs.")
    ap.add_argument("--force", action="store_true", help="Rebuild even if the source is unchanged.")
    ap.add_argument("--dry-run", action="store_true", help="Report only; write nothing.")
    ap.add_argument("--no-log", action="store_true", help="Do not append a summary line to log.md.")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    root = (args.root or Path(__file__).resolve().parent.parent).resolve()
    exts = DEFAULT_EXTS + (PDF_EXTS if args.include_pdf else [])
    converter = MarkItDown()

    files = discover(root, exts)
    counts = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0, "error": 0}
    changed = []
    for src in files:
        status = sync_one(src, root, converter, args.force, args.dry_run)
        key = status.split(":")[0].split("(")[0]
        counts[key if key in counts else "error" if key == "error" else "skipped"] = counts.get(
            key if key in counts else "skipped", 0) + 1
        if not args.quiet:
            rel = src.relative_to(root)
            print(f"  [{status:<10}] {rel}")
        if status.startswith(("created", "updated")):
            changed.append(src.relative_to(root))

    summary = (f"{counts['created']} created, {counts['updated']} updated, "
               f"{counts['unchanged']} unchanged, {counts['skipped']} skipped, {counts['error']} error")
    print(f"\nsync_office_md: {len(files)} sources → {summary}"
          + (" [dry-run]" if args.dry_run else ""))

    if changed and not args.dry_run and not args.no_log:
        log = root / "log.md"
        line = f"## [{dt.date.today().isoformat()}] sync | office mirrors: {summary}\n"
        with log.open("a", encoding="utf-8") as f:
            f.write(line)

    return 1 if counts["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
