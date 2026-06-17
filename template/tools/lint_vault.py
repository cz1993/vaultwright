#!/usr/bin/env python3
"""
lint_vault.py — health check for a Vaultwright knowledge base.

Reports (does not fix): notes missing required frontmatter, invalid type/status values,
unresolved wikilinks, orphan notes (no inbound links), and Office-mirror gaps.

Usage:  python3 tools/lint_vault.py
"""
from __future__ import annotations
import re, sys
from pathlib import Path
try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = ["title", "type", "status", "domain", "created", "updated"]
META = {"CLAUDE.md", "AGENTS.md", "log.md"}                 # structural, exempt from note rules
LINK_SRC_SKIP = {"CLAUDE.md", "AGENTS.md", "_meta/conventions.md"}  # docs full of illustrative links
TYPES = {"moc", "entity", "note", "guide", "policy", "record", "source-mirror", "source-ref", "repo-mirror"}
STATUSES = {"draft", "active", "in-review", "sent", "signed", "submitted", "awarded", "superseded", "archived"}
EXCLUDE_PREFIX = ("_archive", "_backup", "_deprecated")
EXCLUDE_EXACT = {"_templates", "_tmp", "tools", "node_modules"}
SOURCE_EXTS = {".docx", ".pptx", ".xlsx", ".doc"}
LINK_RE = re.compile(r"\[\[([^\]]+?)\]\]")

def excluded(rel: Path) -> bool:
    for p in rel.parts:
        if p.startswith(".") or p in EXCLUDE_EXACT or p.startswith(EXCLUDE_PREFIX):
            return True
    return False

def split_fm(text: str):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            try:
                return yaml.safe_load(text[3:end].lstrip("\n")) or {}, text[end+4:]
            except yaml.YAMLError:
                return None, text
    return {}, text

# inventory
all_files = [p for p in ROOT.rglob("*") if p.is_file() and not excluded(p.relative_to(ROOT).parent)]
md_notes = [p for p in all_files if p.suffix == ".md"]
by_stem: dict[str, list[Path]] = {}
by_name: dict[str, list[Path]] = {}
for p in all_files:
    by_name.setdefault(p.name, []).append(p)
    by_stem.setdefault(p.stem, []).append(p)

def resolve(target: str) -> bool:
    t = target.split("|")[0].split("#")[0].strip()
    if not t:
        return True
    cand = t.rsplit("/", 1)[-1]  # basename
    if cand in by_name:           # has extension, e.g. foo.pdf
        return True
    if cand in by_stem:           # note by stem
        return True
    # path-style without extension
    if (ROOT / (t + ".md")).exists() or (ROOT / t).exists():
        return True
    return False

missing_fm, bad_type, bad_status, unresolved = [], [], [], []
inbound: dict[Path, int] = {p: 0 for p in md_notes}

for p in md_notes:
    rel = p.relative_to(ROOT)
    rels = str(rel)
    is_meta = p.name in META or rels in LINK_SRC_SKIP
    fm, body = split_fm(p.read_text(encoding="utf-8", errors="ignore"))
    if not isinstance(fm, dict) or not fm:
        if not is_meta:
            missing_fm.append((rels, "no/!invalid frontmatter"))
        fm = {}
    elif not is_meta:
        miss = [k for k in REQUIRED if k not in fm or fm.get(k) in (None, "")]
        if miss:
            missing_fm.append((rels, "missing: " + ",".join(miss)))
        if fm.get("type") not in TYPES:
            bad_type.append((rels, str(fm.get("type"))))
        if fm.get("status") not in STATUSES:
            bad_status.append((rels, str(fm.get("status"))))
    if p.name in {"CLAUDE.md", "AGENTS.md"} or rels in LINK_SRC_SKIP:
        continue  # don't lint illustrative links inside the convention docs
    # collect links from body (minus inline-code examples) + frontmatter
    body_clean = re.sub(r"`+[^`]*`+", "", body)
    targets = list(LINK_RE.findall(body_clean))
    for key in ("related", "client", "program", "vendor"):
        v = fm.get(key)
        if isinstance(v, str):
            targets += LINK_RE.findall(v)
        elif isinstance(v, list):
            for it in v:
                if isinstance(it, str):
                    targets += LINK_RE.findall(it)
    targets = [t.replace("\\|", "|") for t in targets]  # Obsidian table-escaped pipes
    for t in targets:
        if not resolve(t):
            unresolved.append((str(rel), t.split("|")[0].split("#")[0].strip()))
        else:
            tt = t.split("|")[0].split("#")[0].strip().rsplit("/", 1)[-1]
            for q in by_stem.get(tt, []):
                if q.suffix == ".md" and q != p:
                    inbound[q] = inbound.get(q, 0) + 1

# mirror integrity
mirror_gap = []
for p in all_files:
    if p.suffix.lower() in SOURCE_EXTS and not excluded(p.relative_to(ROOT).parent):
        if p.suffix.lower() == ".doc":
            continue  # legacy, unsupported by converter
        if not p.with_suffix(".md").exists() and not p.with_name(p.stem + ".mirror.md").exists():
            mirror_gap.append(str(p.relative_to(ROOT)) + "  (no markdown mirror)")

orphans = sorted(str(p.relative_to(ROOT)) for p, n in inbound.items()
                 if n == 0 and p.name not in {"INDEX.md", "CLAUDE.md", "AGENTS.md", "README.md", "RETENTION.md", "log.md"})

def section(title, items, limit=40):
    print(f"\n## {title}: {len(items)}")
    for it in items[:limit]:
        print("  -", it if isinstance(it, str) else f"{it[0]}  [{it[1]}]")
    if len(items) > limit:
        print(f"  … +{len(items)-limit} more")

print(f"# lint_vault — {len(md_notes)} notes, {len(all_files)} files total")
section("Missing/invalid frontmatter", missing_fm)
section("Invalid type", bad_type)
section("Invalid status", bad_status)
section("Unresolved wikilinks", unresolved)
section("Orphan notes (no inbound links)", orphans)
section("Office files without a mirror", mirror_gap)
print("\nOK" if not (missing_fm or bad_type or bad_status or mirror_gap) else "\nISSUES FOUND (unresolved links & orphans are warnings)")
