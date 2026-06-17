#!/usr/bin/env python3
"""
sync_github_repos.py — keep markdown mirrors of GitHub repos in the knowledge base.

For each repo in tools/repos.yml, write a mirror note under `projects/` that captures the
repo's README, docs, and metadata — refreshed when the repo's HEAD changes. The repo on
GitHub stays the source of truth; the mirror makes its knowledge searchable, linkable, and
visible in Obsidian. Idempotent: a quick `git ls-remote` checks HEAD before cloning.

Curated `## Notes` (above the sentinel) and your frontmatter (tags/related/status/…) are
preserved across syncs. Only the auto region below the sentinel is regenerated.

AUTH (read-only is enough): either
  • `gh auth login` once (git credential helper + `gh auth token`), or
  • export GH_TOKEN / GITHUB_TOKEN  (a fine-grained PAT with Contents:read + Metadata:read).
Secrets must NOT live in the vault — keep them in your keychain / environment.

Usage:
  python3 tools/sync_github_repos.py            # sync all repos in repos.yml
  python3 tools/sync_github_repos.py --force     # rebuild even if HEAD is unchanged
  python3 tools/sync_github_repos.py --dry-run   # report only; write nothing
  python3 tools/sync_github_repos.py --no-log    # don't append a summary line to log.md
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, shutil, subprocess, sys, tempfile, urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent
CONFIG = Path(__file__).resolve().parent / "repos.yml"
SENTINEL = "%% AUTO-GENERATED BELOW — DO NOT EDIT %%"
MANAGED = {"type", "repo", "repo_url", "default_branch", "last_commit",
           "last_commit_date", "open_issues", "synced", "updated"}
KEY_ORDER = ["title", "type", "status", "domain", "owner", "created", "updated",
             "tags", "related", "client", "program", "vendor",
             "repo", "repo_url", "default_branch", "last_commit", "last_commit_date",
             "open_issues", "synced"]
GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


def now_iso():
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def get_token():
    for k in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(k):
            return os.environ[k].strip()
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return None


def auth_url(slug, token):
    return f"https://x-access-token:{token}@github.com/{slug}.git" if token else f"https://github.com/{slug}.git"


def redact(text, token):
    return text.replace(token, "***") if token else text


def head_sha(slug, token):
    try:
        r = subprocess.run(["git", "ls-remote", auth_url(slug, token), "HEAD"],
                           capture_output=True, text=True, timeout=60, env=GIT_ENV)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.split()[0]
    except Exception:
        pass
    return None


def resolve_slug(entry, token):
    """Return the first of repo/aliases whose HEAD resolves, with its sha; else (None, None)."""
    for slug in [entry["repo"], *entry.get("aliases", [])]:
        sha = head_sha(slug, token)
        if sha:
            return slug, sha
    return None, None


def clone(slug, token, depth):
    tmp = tempfile.mkdtemp(prefix="ghsync_")
    try:
        r = subprocess.run(["git", "clone", "--depth", str(depth), "--no-tags", "--single-branch",
                            auth_url(slug, token), tmp],
                           capture_output=True, text=True, timeout=300, env=GIT_ENV)
        if r.returncode != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            return None, redact(r.stderr.strip()[:200], token)
        return tmp, ""
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        return None, str(e)[:200]


def is_doc(rel: str) -> bool:
    low = rel.lower()
    name = low.rsplit("/", 1)[-1]
    if "/" not in rel:
        return name.startswith("readme") or low.endswith(".md")
    if low.startswith(("docs/", "doc/", ".github/")):
        return low.endswith(".md")
    return False


def collect_docs(repodir: Path, max_file: int, max_total: int):
    docs, total = [], 0
    files = []
    for p in repodir.rglob("*"):
        if p.is_file() and ".git/" not in str(p.relative_to(repodir)):
            rel = str(p.relative_to(repodir)).replace(os.sep, "/")
            if is_doc(rel):
                files.append(rel)
    files.sort(key=lambda r: (not r.lower().rsplit("/", 1)[-1].startswith("readme"), r.lower()))
    for rel in files:
        try:
            text = (repodir / rel).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if len(text) > max_file:
            text = text[:max_file] + "\n\n> _…truncated._"
        if total + len(text) > max_total:
            docs.append((rel, "> _…omitted (per-repo size cap reached); see the repo._"))
            break
        docs.append((rel, text))
        total += len(text)
    return docs


def api_get(path, token):
    req = urllib.request.Request("https://api.github.com" + path,
                                 headers={"Accept": "application/vnd.github+json",
                                          "User-Agent": "guildbuild-kb-sync"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except Exception:
        return None


def recent_commits(repodir: Path, n: int):
    try:
        r = subprocess.run(["git", "-C", str(repodir), "log", f"-n{n}", "--format=%h%x09%cI%x09%s"],
                           capture_output=True, text=True, timeout=30)
        return [ln.split("\t", 2) for ln in r.stdout.splitlines() if ln.strip()]
    except Exception:
        return []


# --- frontmatter helpers (shared shape with sync_office_md.py) ---

def split_fm(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            try:
                fm = yaml.safe_load(text[3:end].lstrip("\n")) or {}
            except yaml.YAMLError:
                return None, text
            body = text[end + 4:]
            return fm, body[1:] if body.startswith("\n") else body
    return {}, text


def dump_fm(data):
    ordered = {k: data[k] for k in KEY_ORDER if k in data}
    for k, v in data.items():
        ordered.setdefault(k, v)
    return "---\n" + yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True, default_flow_style=False) + "---\n"


def fresh_preserved(slug, entry):
    url = f"https://github.com/{slug}"
    return (f"> [!info] GitHub repo mirror — auto-generated\n"
            f"> Source: [{slug}]({url}). Edit the repo on GitHub, never this note.\n"
            f"> Curate notes below; everything under the line refreshes on sync.\n\n"
            f"## Notes\n\n\n")


def base_fm(existing, entry, slug, domain="projects"):
    fm = dict(existing or {})
    fm.setdefault("title", entry["note"].rsplit(".", 1)[0])
    fm.setdefault("domain", domain)
    fm.setdefault("owner", "CZ")
    fm.setdefault("created", dt.date.today().isoformat())
    if not fm.get("tags"):
        fm["tags"] = entry.get("tags", ["repo"])
    if not fm.get("related"):
        fm["related"] = entry.get("related", [])
    if entry.get("client") and not fm.get("client"):
        fm["client"] = entry["client"]
    if entry.get("program") and not fm.get("program"):
        fm["program"] = entry["program"]
    fm["type"] = "repo-mirror"
    fm["repo"] = slug
    fm["repo_url"] = f"https://github.com/{slug}"
    fm["updated"] = dt.date.today().isoformat()
    return fm


def write_note(path: Path, fm, preserved_body, auto, dry):
    content = dump_fm(fm) + "\n" + preserved_body.rstrip() + "\n\n" + SENTINEL + "\n\n" + auto.rstrip() + "\n"
    if not dry:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def build_auto(slug, meta, langs, release, docs, commits):
    desc = (meta or {}).get("description") or "_(no description)_"
    topics = ", ".join((meta or {}).get("topics", [])) or "—"
    lang_str = "—"
    if langs:
        tot = sum(langs.values()) or 1
        top = sorted(langs.items(), key=lambda kv: -kv[1])[:5]
        lang_str = ", ".join(f"{k} {round(100*v/tot)}%" for k, v in top)
    rel_str = "—"
    if release:
        rel_str = f"{release.get('tag_name','')} ({(release.get('published_at') or '')[:10]})"
    lines = ["## Overview", "", desc, "",
             "| Field | Value |", "| --- | --- |",
             f"| Repo | [{slug}](https://github.com/{slug}) |",
             f"| Default branch | {(meta or {}).get('default_branch','—')} |",
             f"| Open issues + PRs | {(meta or {}).get('open_issues_count','—')} |",
             f"| Languages | {lang_str} |",
             f"| Latest release | {rel_str} |",
             f"| Topics | {topics} |",
             f"| Pushed | {((meta or {}).get('pushed_at') or '—')[:10]} |", ""]
    if docs:
        lines += ["## Docs included", ""] + [f"- `{rel}`" for rel, _ in docs] + [""]
    for rel, text in docs:
        lines += [f"## `{rel}`", "", text.strip(), ""]
    if commits:
        lines += ["## Recent commits", ""] + [f"- `{h}` {d[:10]} — {m}" for h, d, m in commits] + [""]
    return "\n".join(lines)


def pending_auto(slug, reason):
    return ("## ⏳ Not yet synced\n\n"
            f"This repo mirror is scaffolded but not yet pulled ({reason}).\n\n"
            "Configure read-only GitHub auth (`gh auth login`, or export `GH_TOKEN`) and run\n"
            "`python3 tools/sync_github_repos.py` to populate the README, docs, and metadata.\n"
            "See `tools/README.md`.\n")


def sync_one(entry, settings, token, force, dry):
    note_path = ROOT / settings.get("notes_dir", "projects") / entry["note"]
    existing_fm, existing_body = ({}, "")
    if note_path.exists():
        existing_fm, existing_body = split_fm(note_path.read_text(encoding="utf-8"))
        existing_fm = existing_fm if isinstance(existing_fm, dict) else {}
    preserved = (existing_body.split(SENTINEL, 1)[0] if SENTINEL in (existing_body or "")
                 else fresh_preserved(entry["repo"], entry))

    slug, sha = resolve_slug(entry, token)
    if not slug:
        # unreachable (private/no-auth/renamed/offline): keep real content, else scaffold a stub
        if existing_fm.get("last_commit"):
            return "skipped:unreachable"
        fm = base_fm(existing_fm, entry, entry["repo"])
        fm.setdefault("status", "draft")
        fm["synced"] = ""
        write_note(note_path, fm, preserved, pending_auto(entry["repo"], "not reachable / auth not configured"), dry)
        return "stub"

    if existing_fm.get("last_commit") == sha and not force:
        return "unchanged"

    tmp, err = clone(slug, token, max(int(settings.get("recent_commits", 10)) + 5, 15))
    if not tmp:
        if existing_fm.get("last_commit"):
            return f"error:clone ({err})"
        fm = base_fm(existing_fm, entry, slug)
        fm.setdefault("status", "draft")
        fm["synced"] = ""
        write_note(note_path, fm, preserved, pending_auto(slug, f"clone failed: {err}"), dry)
        return "stub"

    try:
        repodir = Path(tmp)
        meta = api_get(f"/repos/{slug}", token)
        langs = api_get(f"/repos/{slug}/languages", token)
        release = api_get(f"/repos/{slug}/releases/latest", token)
        docs = collect_docs(repodir, int(settings.get("max_doc_bytes", 60000)),
                            int(settings.get("max_total_bytes", 300000)))
        commits = recent_commits(repodir, int(settings.get("recent_commits", 10)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    fm = base_fm(existing_fm, entry, slug)
    # promote a never-synced/draft stub to active; otherwise respect the curated status
    fm["status"] = "active" if existing_fm.get("status") in (None, "", "draft") else existing_fm["status"]
    fm["default_branch"] = (meta or {}).get("default_branch", "")
    fm["last_commit"] = sha
    fm["last_commit_date"] = (commits[0][1] if commits else "")
    fm["open_issues"] = (meta or {}).get("open_issues_count", "")
    fm["synced"] = now_iso()
    auto = build_auto(slug, meta, langs, release, docs, commits)
    status = "updated" if note_path.exists() else "created"
    write_note(note_path, fm, preserved, auto, dry)
    return status


def main():
    ap = argparse.ArgumentParser(description="Sync markdown mirrors of GitHub repos.")
    ap.add_argument("--config", type=Path, default=CONFIG)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-log", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    settings, repos = cfg.get("settings", {}), cfg.get("repos", [])
    token = get_token()
    counts = {"created": 0, "updated": 0, "unchanged": 0, "stub": 0, "skipped": 0, "error": 0}
    changed = []
    if not args.quiet:
        print(f"github sync: {len(repos)} repos · auth={'yes' if token else 'NONE (stubs only for private repos)'}")
    for entry in repos:
        status = sync_one(entry, settings, token, args.force, args.dry_run)
        key = status.split(":")[0]
        counts[key] = counts.get(key, 0) + 1
        if not args.quiet:
            print(f"  [{status:<18}] {entry['repo']} -> projects/{entry['note']}")
        if status in ("created", "updated"):
            changed.append(entry["note"])

    summary = (f"{counts['created']} created, {counts['updated']} updated, {counts['unchanged']} unchanged, "
               f"{counts['stub']} stub, {counts['skipped']} skipped, {counts['error']} error")
    print(f"\nsync_github_repos: {summary}" + (" [dry-run]" if args.dry_run else ""))

    if (changed or counts["stub"]) and not args.dry_run and not args.no_log:
        with (ROOT / "log.md").open("a", encoding="utf-8") as f:
            f.write(f"## [{dt.date.today().isoformat()}] sync | github repos: {summary}\n")
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
