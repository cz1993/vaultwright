#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
sync_github_repos.py — keep markdown mirrors of GitHub repos in the knowledge base.

For each repo in tools/repos.yml, write a mirror note under the active profile's default repo
mirror folder (`80_sources/repos/` in the packaged business-operations profile) unless
tools/repos.yml overrides it. Each mirror captures the repo's README, docs, and metadata —
refreshed when the repo's HEAD changes. The repo on GitHub stays the source of truth; the mirror
makes its knowledge searchable, linkable, and visible in Obsidian. Idempotent: a quick
`git ls-remote` checks HEAD before cloning.

Mirrors are machine-owned. Legacy above-sentinel mirror annotations must be migrated with
`vaultwright migrate annotations --write` before sync refreshes the mirror. Only the auto region
below the sentinel is regenerated.

AUTH (read-only is enough): either
  • `gh auth login` once (git credential helper + `gh auth token`), or
  • export GH_TOKEN / GITHUB_TOKEN  (a fine-grained PAT with Contents:read + Metadata:read).
Secrets must NOT live in the vault — keep them in your keychain / environment.

Usage:
  python3.11 tools/sync_github_repos.py            # sync all repos in repos.yml via the compatibility shim
  python3.11 tools/sync_github_repos.py --plan      # report proposed repo mirror actions
  python3.11 tools/sync_github_repos.py --status    # report manifest-backed lifecycle state
  python3.11 tools/sync_github_repos.py --force     # rebuild even if HEAD is unchanged
  python3.11 tools/sync_github_repos.py --dry-run   # report only; write nothing
  python3.11 tools/sync_github_repos.py --no-log    # don't append a summary line to log.md
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, shutil, subprocess, sys, tempfile, urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent
CONFIG = Path(__file__).resolve().parent / "repos.yml"
SENTINEL = "%% AUTO-GENERATED BELOW — DO NOT EDIT %%"
REPO_MANIFEST_REL = Path("_meta/repo-manifest.json")
AUDIT_REL = Path("_meta/sync-audit.jsonl")
ANNOTATION_ROOT = Path("_meta/mirror-annotations")
PROFILE_REL = Path("_meta/profile.yml")
MANIFEST_SCHEMA_VERSION = 1
CONFIG_VERSION = "repo-mirrors:v1"
LEGACY_REPO_NOTES_DIR = "80_sources/repos"
ANNOTATION_MIGRATION_REQUIRED_WARNING = (
    "Unmigrated repo mirror annotations found above the generated sentinel; "
    "run `vaultwright migrate annotations --write` before syncing."
)
DEFAULT_ANNOTATION_FRONTMATTER_KEYS = {"title", "domain", "owner", "created", "updated"}
PROFILE_CONTEXT_KEYS = {"account", "client", "program", "vendor"}
LIFECYCLE_CONTRACT_REL = Path("_meta/lifecycle-states.yml")
MANAGED = {"type", "repo_id", "repo_manifest", "repo", "repo_url", "default_branch", "last_commit",
           "last_commit_date", "open_issues", "synced", "updated"}
KEY_ORDER = ["title", "type", "status", "domain", "owner", "created", "updated",
             "tags", "related", "account", "client", "program", "vendor",
             "repo_id", "repo_manifest", "repo", "repo_url", "default_branch", "last_commit",
             "last_commit_date", "open_issues", "synced"]
GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
CONTENT_ROOTS = {
    "00_inbox", "10_governance", "20_market", "30_customers", "40_delivery",
    "50_operations", "60_finance", "70_people", "80_sources",
}
FORBIDDEN_OUTPUT_PARTS = {
    ".git", ".githooks", ".github", ".obsidian", "_archive", "_fixtures",
    "_meta", "_templates", "_tmp", "node_modules", "tools",
}
LIFECYCLE_GUIDANCE = {
    "planned": "review the plan, then run sync to create the repo mirror.",
    "repo_changed": "run sync to refresh README/docs/metadata, then review curated notes.",
    "stale": "run sync before relying on the mirror; the repo or configuration is newer.",
    "unreachable": "check repo spelling, network access, and GitHub auth; existing mirror content is retained.",
    "repo_unconfigured": "confirm whether the repo mirror is retired, restore its repos.yml entry, or archive/remove the mirror deliberately.",
    "manual_modification": "inspect the repo mirror below the generated sentinel and preserve human edits before forcing regeneration.",
    "conflict": "resolve the target note/repo identity conflict before syncing.",
    "error": "fix the reported error, then rerun plan/status before syncing.",
}
REPO_LIFECYCLE_STATES = set(LIFECYCLE_GUIDANCE) | {"clean"}


def now_iso():
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        try:
            dir_fd = os.open(str(path.parent), os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if tmp.exists():
            tmp.unlink()


def unique_list(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def load_lifecycle_contract(root: Path = ROOT) -> dict:
    path = root / LIFECYCLE_CONTRACT_REL
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def default_lifecycle_contract() -> dict:
    return load_lifecycle_contract(Path(__file__).resolve().parents[1] / "template")


def lifecycle_contract_section(contract: dict, section: str) -> dict:
    states = contract.get(section)
    return states if isinstance(states, dict) else {}


def lifecycle_state_spec(contract: dict, section: str, state: str) -> dict:
    spec = lifecycle_contract_section(contract, section).get(state)
    return spec if isinstance(spec, dict) else {}


def lifecycle_record_metadata(root: Path = ROOT) -> dict:
    contract = load_lifecycle_contract(root)
    if not contract:
        return {}
    metadata = {"lifecycle_contract": LIFECYCLE_CONTRACT_REL.as_posix()}
    schema_version = contract.get("schema_version")
    if isinstance(schema_version, int):
        metadata["lifecycle_contract_schema_version"] = schema_version
    return metadata


def lifecycle_guidance_text(state: str, contract: dict) -> str | None:
    spec = lifecycle_state_spec(contract, "repo", state)
    explanation = str(spec.get("explanation", "") or "").strip()
    actions = spec.get("permitted_next_actions")
    first_action = ""
    if isinstance(actions, list):
        for action in actions:
            first_action = str(action or "").strip()
            if first_action:
                break
    if explanation and first_action:
        return f"{explanation} Next: {first_action}"
    if explanation:
        return explanation
    if first_action:
        return first_action
    return LIFECYCLE_GUIDANCE.get(state)


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
    return f"https://github.com/{slug}.git"


def git_auth_env(token):
    if not token:
        return GIT_ENV, None
    tmp = tempfile.mkdtemp(prefix="ghsync_auth_")
    token_file = Path(tmp) / "token"
    askpass = Path(tmp) / "askpass.sh"
    token_file.write_text(token, encoding="utf-8")
    token_file.chmod(0o600)
    askpass.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in\n"
        "  *Username*) printf '%s\\n' x-access-token ;;\n"
        f"  *) cat {str(token_file)!r} ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    askpass.chmod(0o700)
    env = {**GIT_ENV, "GIT_ASKPASS": str(askpass)}
    return env, tmp


def redact(text, token):
    return text.replace(token, "***") if token else text


def head_sha(slug, token):
    env, tmp = git_auth_env(token)
    try:
        r = subprocess.run(["git", "ls-remote", auth_url(slug, token), "HEAD"],
                           capture_output=True, text=True, timeout=60, env=env)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.split()[0]
    except Exception:
        pass
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
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
    env, auth_tmp = git_auth_env(token)
    try:
        r = subprocess.run(["git", "clone", "--depth", str(depth), "--no-tags", "--single-branch",
                            auth_url(slug, token), tmp],
                           capture_output=True, text=True, timeout=300, env=env)
        if r.returncode != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            return None, redact(r.stderr.strip()[:200], token)
        return tmp, ""
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        return None, str(e)[:200]
    finally:
        if auth_tmp:
            shutil.rmtree(auth_tmp, ignore_errors=True)


def local_source_path(entry):
    local_path = entry.get("local_path")
    if not local_path:
        return None
    rel = Path(local_path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("local_path must stay inside the vault")
    resolved = (ROOT / rel).resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError("local_path must stay inside the vault")
    if resolved.is_symlink():
        raise ValueError("local_path must not be a symlink")
    return resolved


def load_profile_mapping(root: Path | None = None) -> dict:
    path = (root or ROOT) / PROFILE_REL
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def profile_domain_folders(root: Path | None = None) -> dict[str, str]:
    domains = load_profile_mapping(root).get("domains", {})
    if not isinstance(domains, dict):
        return {}
    out: dict[str, str] = {}
    for domain, definition in domains.items():
        if not isinstance(definition, dict):
            continue
        folder = definition.get("folder")
        if isinstance(folder, str) and folder.strip():
            out[str(domain)] = folder.strip()
    return out


def active_content_roots(root: Path | None = None) -> set[str]:
    folders = set(profile_domain_folders(root).values())
    return folders or set(CONTENT_ROOTS)


def default_repo_notes_dir(root: Path | None = None) -> str:
    profile = load_profile_mapping(root)
    policy_defaults = profile.get("policy_defaults", {})
    if isinstance(policy_defaults, dict):
        configured = policy_defaults.get("repo_notes_dir")
        if isinstance(configured, str) and configured.strip():
            return configured.strip()
    source_folder = profile_domain_folders(root).get("sources")
    if source_folder:
        return f"{source_folder}/repos"
    return LEGACY_REPO_NOTES_DIR


def fallback_note_output_path(note: str) -> Path:
    fallback_note = note if note.endswith(".md") else "invalid.md"
    try:
        return note_output_path(default_repo_notes_dir(), fallback_note)
    except Exception:
        return ROOT / LEGACY_REPO_NOTES_DIR / fallback_note


def safe_rel_path(value: str, label: str, *, allow_nested: bool = True) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must stay inside the vault")
    if not allow_nested and len(path.parts) != 1:
        raise ValueError(f"{label} must be a filename, not a path")
    for part in path.parts:
        if part.startswith(".") or part in FORBIDDEN_OUTPUT_PARTS:
            raise ValueError(f"{label} contains a reserved path component")
    return path


def note_output_path(notes_dir: str, note: str) -> Path:
    rel_dir = safe_rel_path(notes_dir, "notes_dir")
    rel_note = safe_rel_path(note, "note", allow_nested=False)
    if not rel_dir.parts or rel_dir.parts[0] not in active_content_roots():
        raise ValueError("notes_dir must start with a canonical content root")
    if rel_note.suffix != ".md":
        raise ValueError("note must be a .md filename")
    cursor = ROOT
    for part in rel_dir.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("notes_dir must not contain symlink components")
    output_path = ROOT / rel_dir / rel_note
    if output_path.is_symlink():
        raise ValueError("note output path must not be a symlink")
    resolved = output_path.resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError("note output path must stay inside the vault")
    resolved_rel = resolved.relative_to(ROOT)
    for part in resolved_rel.parts:
        if part.startswith(".") or part in FORBIDDEN_OUTPUT_PARTS:
            raise ValueError("note output path resolves through a reserved path component")
    return resolved


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
        if p.is_file() and not p.is_symlink() and ".git/" not in str(p.relative_to(repodir)):
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


def local_tree_sha(repodir: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(repodir.rglob("*")):
        if not p.is_file() or p.is_symlink() or ".git/" in str(p.relative_to(repodir)):
            continue
        rel = str(p.relative_to(repodir)).replace(os.sep, "/")
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return "local-" + h.hexdigest()[:40]


def api_get(path, token):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "vaultwright-sync"},
    )
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


def generated_region_hash(markdown: str) -> str | None:
    _fm, body = split_fm(markdown)
    lines = body.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.rstrip("\r\n") == SENTINEL:
            return sha256_text(line + "".join(lines[index + 1:]))
    if body.rstrip("\r\n") == SENTINEL:
        return sha256_text(SENTINEL)
    return None


def split_body_at_sentinel(body: str) -> tuple[str, bool]:
    lines = body.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.rstrip("\r\n") == SENTINEL:
            return "".join(lines[:index]), True
    if body.rstrip("\r\n") == SENTINEL:
        return "", True
    return body, False


def safe_annotation_identity(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in value.strip()).strip(".-")
    return cleaned or sha256_text(value)[:20]


def annotation_sidecar_path(kind: str, identity: str) -> Path:
    group = "source" if kind == "source-mirror" else "repo"
    return ANNOTATION_ROOT / group / f"{safe_annotation_identity(identity)}.md"


def json_safe(value):
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


def preserved_annotation_frontmatter(existing_fm: dict | None) -> dict:
    if not isinstance(existing_fm, dict):
        return {}
    return {str(key): value for key, value in existing_fm.items() if str(key) not in MANAGED}


def preserved_annotation_hash(
    *,
    kind: str,
    identity: str,
    mirror_path: str,
    existing_fm: dict | None,
    preserved_body: str,
    repo: str,
) -> str:
    payload = {
        "kind": kind,
        "identity": identity,
        "mirror_path": mirror_path,
        "frontmatter": preserved_annotation_frontmatter(existing_fm),
        "body": preserved_body.rstrip() + ("\n" if preserved_body.strip() else ""),
        "repo": repo,
    }
    encoded = json.dumps(json_safe(payload), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_text(encoded)


def split_sidecar_frontmatter(path: Path) -> dict | None:
    try:
        fm, _body = split_fm(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    return fm if isinstance(fm, dict) else None


def annotation_sidecar_matches(
    root: Path,
    *,
    repo_id: str,
    mirror_path: str,
    existing_fm: dict | None,
    preserved_body: str,
    repo: str,
) -> Path | None:
    sidecar_rel = annotation_sidecar_path("repo-mirror", repo_id)
    sidecar_fm = split_sidecar_frontmatter(root / sidecar_rel)
    if not sidecar_fm:
        return None
    expected = preserved_annotation_hash(
        kind="repo-mirror",
        identity=repo_id,
        mirror_path=mirror_path,
        existing_fm=existing_fm,
        preserved_body=preserved_body,
        repo=repo,
    )
    if str(sidecar_fm.get("preserved_sha256", "") or "") != expected:
        return None
    return sidecar_rel


def machine_owned_preserved(repo: str, url: str, sidecar_rel: Path) -> str:
    return (
        f"> [!info] GitHub repo mirror — auto-generated\n"
        f"> Source: {repo} ({url}). Edit the source repo, never this note.\n"
        f"> Human annotations were migrated to [[{sidecar_rel.as_posix()}|{sidecar_rel.name}]].\n"
        f"> This mirror is machine-owned; do not edit it directly.\n\n"
    )


def default_preserved_line(line: str) -> bool:
    stripped = line.strip()
    return (
        not stripped
        or stripped == "## Notes"
        or stripped.startswith("# ")
        or stripped == "> [!info] GitHub repo mirror — auto-generated"
        or stripped.startswith("> Source: ")
        or stripped.startswith("> Human annotations were migrated to ")
        or stripped == "> Curate notes below; everything under the line refreshes on sync."
        or stripped == "> This mirror is machine-owned; do not edit it directly."
        or stripped == "> This mirror is machine-owned; keep durable human notes in curated notes or annotation sidecars."
    )


def preserved_body_has_annotation(body: str) -> bool:
    return any(not default_preserved_line(line) for line in body.splitlines())


def repo_seed_frontmatter(entry: dict) -> dict[str, object]:
    seed: dict[str, object] = {
        "tags": entry.get("tags", ["repo"]),
        "related": entry.get("related", []),
    }
    account = entry.get("account") or entry.get("client")
    if account:
        seed["account"] = str(account)
        seed["client"] = str(account)
    for key in ("program", "vendor"):
        if entry.get(key):
            seed[key] = str(entry[key])
    return seed


def frontmatter_has_annotation(existing_fm: dict | None, entry: dict) -> bool:
    preserved = preserved_annotation_frontmatter(existing_fm)
    seed = repo_seed_frontmatter(entry)
    for key, value in preserved.items():
        if key in DEFAULT_ANNOTATION_FRONTMATTER_KEYS:
            continue
        if key == "status" and str(value or "").strip() in {"", "active", "draft"}:
            continue
        if key == "tags":
            tags = value if isinstance(value, list) else []
            clean_tags = {str(item).strip() for item in tags if str(item).strip()}
            raw_expected = seed.get("tags", ["repo"])
            expected_items = raw_expected if isinstance(raw_expected, list) else []
            expected_tags = {str(item).strip() for item in expected_items if str(item).strip()}
            if not clean_tags or clean_tags <= expected_tags:
                continue
            return True
        if key == "related":
            related = value if isinstance(value, list) else []
            clean_related = {str(item).strip() for item in related if str(item).strip()}
            raw_expected = seed.get("related", [])
            expected_items = raw_expected if isinstance(raw_expected, list) else []
            expected_related = {str(item).strip() for item in expected_items if str(item).strip()}
            if not clean_related or clean_related <= expected_related:
                continue
            return True
        if key in PROFILE_CONTEXT_KEYS and value in (None, "", []):
            continue
        if key in PROFILE_CONTEXT_KEYS and seed.get(key) == str(value or "").strip():
            continue
        if value in (None, "", []):
            continue
        return True
    return False


def annotation_migration_required(
    root: Path,
    *,
    repo_id: str,
    mirror_path: str,
    existing_fm: dict | None,
    existing_body: str,
    repo: str,
    entry: dict,
) -> bool:
    if not existing_body:
        return False
    preserved, sentinel_found = split_body_at_sentinel(existing_body)
    if not sentinel_found:
        return False
    if not (preserved_body_has_annotation(preserved) or frontmatter_has_annotation(existing_fm, entry)):
        return False
    return annotation_sidecar_matches(
        root,
        repo_id=repo_id,
        mirror_path=mirror_path,
        existing_fm=existing_fm,
        preserved_body=preserved,
        repo=repo,
    ) is None


def repo_note_conflict(existing_fm: dict, body: str, expected_repo_id: str) -> str | None:
    if not existing_fm and not body:
        return None
    if existing_fm.get("type") != "repo-mirror":
        return "Existing note is not a managed repo mirror."
    existing_repo_id = existing_fm.get("repo_id")
    if existing_repo_id and existing_repo_id != expected_repo_id:
        return "Existing repo mirror belongs to a different repo_id."
    _preserved, sentinel_found = split_body_at_sentinel(body)
    if not sentinel_found:
        return "Existing repo mirror is missing the generated sentinel."
    return None


def repo_identity_values(entry: dict, resolved_repo: str | None = None, existing_record: dict | None = None) -> set[str]:
    values = {str(entry.get("repo", "") or "").strip(), str(resolved_repo or "").strip()}
    record = existing_record or {}
    values.add(str(record.get("configured_repo", "") or "").strip())
    values.add(str(record.get("resolved_repo", "") or "").strip())
    return {value for value in values if value}


def repo_frontmatter_identity_issue(existing_fm: dict, allowed_repos: set[str]) -> str | None:
    repo_value = str(existing_fm.get("repo", "") or "").strip()
    if not existing_fm:
        return None
    if not repo_value:
        return "Repo frontmatter is missing the managed repo identity."
    if allowed_repos and repo_value not in allowed_repos:
        return "Repo frontmatter repo differs from the configured/resolved repo identity."
    return None


def review_blocks_force(record: dict) -> bool:
    if record.get("lifecycle_state") == "conflict":
        return True
    if record.get("lifecycle_state") != "manual_modification":
        return False
    warnings = record.get("warnings") or []
    force_blockers = (
        "generated sentinel",
        "no manifest-generated baseline",
        "unmigrated repo mirror annotations",
    )
    return any(any(blocker in str(warning).lower() for blocker in force_blockers) for warning in warnings)


def repo_id_for(repo: str, note: str) -> str:
    digest = hashlib.sha256(f"{repo}\0{note}".encode("utf-8")).hexdigest()[:20]
    return f"repo_{digest}"


def empty_repo_manifest() -> dict:
    return {"schema_version": MANIFEST_SCHEMA_VERSION, "updated": None, "records": []}


def repo_manifest_path(root: Path = ROOT) -> Path:
    return root / REPO_MANIFEST_REL


def load_repo_manifest(root: Path = ROOT) -> dict:
    path = repo_manifest_path(root)
    if not path.exists():
        return empty_repo_manifest()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{REPO_MANIFEST_REL.as_posix()} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{REPO_MANIFEST_REL.as_posix()} must be a JSON object")
    records = data.get("records", [])
    if not isinstance(records, list):
        raise ValueError(f"{REPO_MANIFEST_REL.as_posix()} records must be a list")
    normalized = empty_repo_manifest()
    normalized["updated"] = data.get("updated")
    normalized["records"] = [dict(r) for r in records if isinstance(r, dict)]
    return normalized


def comparable_manifest(manifest: dict) -> dict:
    records = []
    for record in manifest.get("records", []):
        clean = dict(record)
        clean["warnings"] = sorted(clean.get("warnings") or [])
        clean["errors"] = sorted(clean.get("errors") or [])
        records.append(clean)
    records.sort(key=lambda r: str(r.get("repo_id", "")))
    return {"schema_version": MANIFEST_SCHEMA_VERSION, "records": records}


def manifest_text(manifest: dict) -> str:
    records = list(manifest.get("records", []))
    records.sort(key=lambda r: str(r.get("repo_id", "")))
    return json.dumps({
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "updated": manifest.get("updated"),
        "records": records,
    }, indent=2, sort_keys=False) + "\n"


def write_repo_manifest(manifest: dict, root: Path = ROOT) -> bool:
    path = repo_manifest_path(root)
    existing = load_repo_manifest(root) if path.exists() else empty_repo_manifest()
    if comparable_manifest(existing) == comparable_manifest(manifest):
        return False
    manifest["updated"] = now_iso()
    write_text_atomic(path, manifest_text(manifest))
    return True


def upsert_repo_record(manifest: dict, record: dict) -> None:
    records = [r for r in manifest.get("records", []) if isinstance(r, dict)]
    for i, existing in enumerate(records):
        if existing.get("repo_id") == record.get("repo_id"):
            records[i] = record
            break
    else:
        records.append(record)
    records.sort(key=lambda r: str(r.get("repo_id", "")))
    manifest["records"] = records


def mark_unconfigured_repos(manifest: dict, seen_repo_ids: set[str]) -> int:
    unconfigured = 0
    for record in list(manifest.get("records", [])):
        repo_id = record.get("repo_id")
        if not isinstance(repo_id, str) or not repo_id or repo_id in seen_repo_ids:
            continue
        updated = dict(record)
        updated["lifecycle_state"] = "repo_unconfigured"
        updated.update(lifecycle_record_metadata(ROOT))
        updated["warnings"] = unique_list((updated.get("warnings") or []) + [
            "Repo config entry is missing; retained repo mirror is no longer governed by tools/repos.yml.",
        ])
        updated["errors"] = []
        upsert_repo_record(manifest, updated)
        unconfigured += 1
    return unconfigured


def repo_record_by_id(manifest: dict, repo_id: str) -> dict | None:
    for record in manifest.get("records", []):
        if isinstance(record, dict) and record.get("repo_id") == repo_id:
            return record
    return None


def append_audit(event: dict, root: Path = ROOT) -> None:
    payload = {"timestamp": now_iso(), **event}
    path = root / AUDIT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")


def sync_audit_event(plan: dict, manifest: dict, status: str, entry: dict) -> dict:
    planned_record = plan["record"]
    record = repo_record_by_id(manifest, planned_record.get("repo_id")) or planned_record
    event = {
        "tool": "sync_github_repos",
        "repo_id": planned_record.get("repo_id"),
        "repo": entry.get("repo"),
        "note_path": planned_record.get("note_path"),
        "status": status,
        "lifecycle_state": record.get("lifecycle_state"),
        "warnings": unique_list(record.get("warnings", [])),
        "errors": unique_list(record.get("errors", [])),
    }
    if record.get("lifecycle_contract"):
        event["lifecycle_contract"] = record.get("lifecycle_contract")
    if record.get("lifecycle_contract_schema_version") is not None:
        event["lifecycle_contract_schema_version"] = record.get("lifecycle_contract_schema_version")
    return event


def dump_fm(data):
    ordered = {k: data[k] for k in KEY_ORDER if k in data}
    for k, v in data.items():
        ordered.setdefault(k, v)
    return "---\n" + yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True, default_flow_style=False) + "---\n"


def fresh_preserved(slug, entry):
    url = entry.get("repo_url") or (f"local:{entry['local_path']}" if entry.get("local_path") else f"https://github.com/{slug}")
    return (f"> [!info] GitHub repo mirror — auto-generated\n"
            f"> Source: {slug} ({url}). Edit the source repo, never this note.\n"
            f"> This mirror is machine-owned; keep durable human notes in curated notes or annotation sidecars.\n\n")


def domain_from_notes_dir(notes_dir: str) -> str:
    first = Path(notes_dir).parts[0] if Path(notes_dir).parts else "sources"
    for domain, folder in profile_domain_folders().items():
        if folder == first:
            return domain
    if len(first) > 3 and first[:2].isdigit() and first[2] == "_":
        return first[3:]
    return first


def base_fm(existing, entry, slug, domain="sources"):
    fm = dict(existing or {})
    repo_id = repo_id_for(str(entry["repo"]), str(entry["note"]))
    fm.setdefault("title", entry["note"].rsplit(".", 1)[0])
    fm.setdefault("domain", domain)
    fm.setdefault("owner", "you")
    fm.setdefault("created", dt.date.today().isoformat())
    if not fm.get("tags"):
        fm["tags"] = entry.get("tags", ["repo"])
    if not fm.get("related"):
        fm["related"] = entry.get("related", [])
    if entry.get("account") and not fm.get("account"):
        fm["account"] = entry["account"]
    if entry.get("client"):
        if not fm.get("account"):
            fm["account"] = entry["client"]
    if fm.get("account"):
        fm["client"] = fm["account"]
    if entry.get("program") and not fm.get("program"):
        fm["program"] = entry["program"]
    fm["type"] = "repo-mirror"
    fm["repo_id"] = repo_id
    fm["repo_manifest"] = REPO_MANIFEST_REL.as_posix()
    fm["repo"] = slug
    fm["repo_url"] = entry.get("repo_url") or (f"local:{entry['local_path']}" if entry.get("local_path") else f"https://github.com/{slug}")
    fm["updated"] = dt.date.today().isoformat()
    return fm


def write_note(path: Path, fm, preserved_body, auto, dry):
    content = dump_fm(fm) + "\n" + preserved_body.rstrip() + "\n\n" + SENTINEL + "\n\n" + auto.rstrip() + "\n"
    if not dry:
        write_text_atomic(path, content)


def write_note_error(path: Path, fm, preserved_body, auto, dry) -> str | None:
    try:
        write_note(path, fm, preserved_body, auto, dry)
    except Exception as exc:
        name = exc.__class__.__name__
        return f"error:repo-write:{name}: {str(exc)[:120]}"
    return None


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
             f"| Repo | {repo_link(slug, meta)} |",
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


def repo_link(slug, meta):
    url = (meta or {}).get("html_url") or ""
    return f"[{slug}]({url})" if url.startswith(("http://", "https://")) else slug


def pending_auto(slug, reason):
    return ("## ⏳ Not yet synced\n\n"
            f"This repo mirror is scaffolded but not yet pulled ({reason}).\n\n"
            "Configure read-only GitHub auth (`gh auth login`, or export `GH_TOKEN`) and run\n"
            "`python3.11 tools/sync_github_repos.py` to populate the README, docs, and metadata.\n"
            "See `tools/README.md`.\n")


def validate_config(data) -> tuple[dict, list[dict], list[str]]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return {}, [], ["config must be a mapping"]
    settings = data.get("settings", {})
    repos = data.get("repos", [])
    if settings is None:
        settings = {}
    if not isinstance(settings, dict):
        errors.append("settings must be a mapping")
        settings = {}
    if repos is None:
        repos = []
    if not isinstance(repos, list):
        errors.append("repos must be a list")
        repos = []
    settings = dict(settings)
    if "notes_dir" not in settings:
        settings["notes_dir"] = default_repo_notes_dir()
    notes_dir = settings.get("notes_dir")
    seen_note_paths: dict[str, str] = {}
    valid_repos: list[dict] = []
    for i, entry in enumerate(repos):
        label = f"repos[{i}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} must be a mapping")
            continue
        repo = entry.get("repo")
        note = entry.get("note")
        if not isinstance(repo, str) or not repo.strip():
            errors.append(f"{label}.repo is required")
        if not isinstance(note, str) or not note.strip():
            errors.append(f"{label}.note is required")
        aliases = entry.get("aliases", [])
        if aliases is not None and (not isinstance(aliases, list) or any(not isinstance(a, str) for a in aliases)):
            errors.append(f"{label}.aliases must be a list of strings")
        if not any(error.startswith(label) for error in errors):
            try:
                note_path = note_output_path(str(notes_dir), str(note))
            except ValueError:
                note_path = None
            if note_path:
                note_rel = str(note_path.relative_to(ROOT))
                note_key = note_rel.casefold()
                previous = seen_note_paths.get(note_key)
                if previous:
                    errors.append(f"{label}.note duplicates output path {note_rel} from {previous}")
                    continue
                seen_note_paths[note_key] = label
            valid_repos.append(entry)
    return settings, valid_repos, errors


def plan_one(entry, settings, token, manifest):
    warnings: list[str] = []
    errors: list[str] = []
    notes_dir = settings.get("notes_dir", default_repo_notes_dir())
    repo = str(entry.get("repo", ""))
    note = str(entry.get("note", ""))
    repo_id = repo_id_for(repo, note)
    existing_record = repo_record_by_id(manifest, repo_id) or {}

    try:
        note_path = note_output_path(str(notes_dir), note)
        note_rel = str(note_path.relative_to(ROOT))
    except Exception as exc:
        note_path = fallback_note_output_path(note or "invalid.md")
        note_rel = str(note_path.relative_to(ROOT)) if note_path.is_relative_to(ROOT) else str(note_path)
        errors.append(f"Mirror path is invalid: {exc}")

    existing_fm = {}
    existing_body = ""
    existing_generated_hash = None
    if note_path.exists():
        note_text = note_path.read_text(encoding="utf-8", errors="ignore")
        fm, existing_body = split_fm(note_text)
        existing_fm = fm if isinstance(fm, dict) else {}
        existing_generated_hash = generated_region_hash(note_text)
    stored_generated_hash = existing_record.get("generated_region_sha256")
    missing_generated_baseline = bool(note_path.exists() and not stored_generated_hash)
    conflict_reason = repo_note_conflict(existing_fm, existing_body, repo_id) if note_path.exists() else None

    resolved_repo = repo
    source_type = "github"
    source_ref = entry.get("repo_url") or f"https://github.com/{repo}" if repo else ""
    last_commit = ""
    action = "unchanged"
    lifecycle_state = "clean"

    if not repo or not note:
        errors.append("repo and note are required")
    if not errors:
        try:
            local_path = local_source_path(entry)
        except ValueError as exc:
            errors.append(f"Local path is invalid: {exc}")
            local_path = None
        if local_path:
            source_type = "local"
            source_ref = str(local_path.relative_to(ROOT))
            if not local_path.exists() or not local_path.is_dir():
                errors.append(f"Local path not found: {source_ref}")
            else:
                last_commit = local_tree_sha(local_path)
        elif entry.get("local_path"):
            errors.append("Local path could not be resolved")
        else:
            resolved_repo, last_commit = resolve_slug(entry, token)
            if not resolved_repo:
                resolved_repo = repo
                warnings.append("Repository is not reachable; configure read-only GitHub auth or check network access.")

    if errors:
        action = "error"
        lifecycle_state = "error"
    elif conflict_reason:
        action = "review"
        lifecycle_state = "conflict"
        errors.append(conflict_reason)
    elif missing_generated_baseline:
        action = "review"
        lifecycle_state = "manual_modification"
        warnings.append("Existing repo mirror has no manifest-generated baseline; review before trusting it.")
    elif (
        stored_generated_hash
        and note_path.exists()
        and not existing_generated_hash
    ):
        action = "review"
        lifecycle_state = "manual_modification"
        warnings.append("Generated region sentinel is missing or altered since the last successful repo sync.")
    elif (
        stored_generated_hash
        and existing_generated_hash
        and stored_generated_hash != existing_generated_hash
    ):
        action = "review"
        lifecycle_state = "manual_modification"
        warnings.append("Generated region changed since the last successful repo sync.")
    elif annotation_migration_required(
        ROOT,
        repo_id=repo_id,
        mirror_path=note_rel,
        existing_fm=existing_fm,
        existing_body=existing_body,
        repo=str(existing_fm.get("repo") or resolved_repo or repo),
        entry=entry,
    ):
        action = "review"
        lifecycle_state = "manual_modification"
        warnings.append(ANNOTATION_MIGRATION_REQUIRED_WARNING)
    elif not last_commit:
        action = "create" if not note_path.exists() else "skip"
        lifecycle_state = "unreachable"
    elif existing_record and existing_record.get("config_version") != CONFIG_VERSION:
        action = "update"
        lifecycle_state = "stale"
        warnings.append("Repo mirror configuration version changed.")
    elif existing_record and existing_record.get("last_commit") != last_commit:
        action = "update"
        lifecycle_state = "repo_changed"
    elif identity_issue := repo_frontmatter_identity_issue(
        existing_fm,
        repo_identity_values(entry, resolved_repo, existing_record),
    ):
        action = "update"
        lifecycle_state = "stale"
        warnings.append(f"{identity_issue} Sync will rewrite managed frontmatter.")
    elif not note_path.exists():
        action = "create"
        lifecycle_state = "planned"
    elif existing_fm.get("last_commit") == last_commit:
        action = "unchanged"
        lifecycle_state = "clean"
    else:
        action = "update"
        lifecycle_state = "repo_changed"

    record = {
        "repo_id": repo_id,
        "configured_repo": repo,
        "resolved_repo": resolved_repo or repo,
        "note_path": note_rel,
        "source_type": source_type,
        "source_ref": source_ref,
        "last_commit": last_commit,
        "generated_region_sha256": stored_generated_hash or (None if missing_generated_baseline else existing_generated_hash),
        "observed_generated_region_sha256": (
            existing_generated_hash
            if existing_record.get("generated_region_sha256")
            and existing_generated_hash
            and existing_record.get("generated_region_sha256") != existing_generated_hash
            else existing_record.get("observed_generated_region_sha256")
        ),
        "config_version": CONFIG_VERSION,
        "lifecycle_state": lifecycle_state,
        **lifecycle_record_metadata(ROOT),
        "last_successful_sync": existing_record.get("last_successful_sync"),
        "warnings": unique_list(warnings),
        "errors": unique_list(errors),
    }
    return {"entry": entry, "note_path": note_path, "action": action, "record": record}


def status_for_plan(plan: dict) -> str:
    action = plan["action"]
    state = plan["record"]["lifecycle_state"]
    if action == "create":
        return f"planned:create ({state})"
    if action == "update":
        return f"planned:update ({state})"
    if action == "review":
        return f"review:{state}"
    if action == "skip":
        return f"skipped:{state}"
    if action == "error":
        return "error:plan"
    return state


def lifecycle_guidance_lines(state_counts: dict[str, int], contract: dict | None = None) -> list[str]:
    active_contract = contract if contract is not None else (
        load_lifecycle_contract(ROOT) or default_lifecycle_contract()
    )
    lines: list[str] = []
    for state in sorted(state_counts):
        count = state_counts.get(state, 0)
        if count <= 0 or state == "clean":
            continue
        guidance = lifecycle_guidance_text(state, active_contract)
        if guidance:
            lines.append(f"{state} ({count}): {guidance}")
    return lines


def print_lifecycle_guidance(state_counts: dict[str, int], contract: dict | None = None) -> None:
    lines = lifecycle_guidance_lines(state_counts, contract)
    if not lines:
        return
    print("next actions:")
    for line in lines:
        print(f"  - {line}")


def update_manifest_after_sync(manifest: dict, plan: dict, status: str) -> None:
    record = dict(plan["record"])
    note_path = plan["note_path"]
    observed_generated_hash = None
    if note_path.exists():
        text = note_path.read_text(encoding="utf-8", errors="ignore")
        fm, _body = split_fm(text)
        if isinstance(fm, dict):
            record["last_commit"] = fm.get("last_commit", record.get("last_commit", ""))
            record["last_successful_sync"] = fm.get("synced") or record.get("last_successful_sync")
        observed_generated_hash = generated_region_hash(text)
    if status.startswith(("created", "updated", "unchanged")):
        record["generated_region_sha256"] = observed_generated_hash
        record["observed_generated_region_sha256"] = None
        record["lifecycle_state"] = "clean"
        record["warnings"] = []
        record["errors"] = []
    elif status == "stub":
        record["generated_region_sha256"] = observed_generated_hash
        record["observed_generated_region_sha256"] = None
        record["lifecycle_state"] = "unreachable"
    elif status.startswith("skipped"):
        if record.get("lifecycle_state") == "manual_modification":
            record["observed_generated_region_sha256"] = observed_generated_hash
        record["lifecycle_state"] = plan["record"].get("lifecycle_state", "skipped")
    elif status.startswith("error"):
        if record.get("lifecycle_state") == "manual_modification":
            record["observed_generated_region_sha256"] = observed_generated_hash
        record["lifecycle_state"] = "error"
        record["errors"] = unique_list(record.get("errors", []) + [status])
    upsert_repo_record(manifest, record)


def print_plan_or_status(settings, repos, token, manifest, mode: str, quiet: bool) -> int:
    action_counts = {"create": 0, "update": 0, "unchanged": 0, "skip": 0, "review": 0, "error": 0}
    state_counts: dict[str, int] = {}
    seen_repo_ids: set[str] = set()
    lifecycle_contract = load_lifecycle_contract(ROOT)
    for entry in repos:
        plan = plan_one(entry, settings, token, manifest)
        action = plan["action"]
        state = plan["record"]["lifecycle_state"]
        action_counts[action] = action_counts.get(action, 0) + 1
        state_counts[state] = state_counts.get(state, 0) + 1
        seen_repo_ids.add(plan["record"]["repo_id"])
        if not quiet:
            print(f"  [{status_for_plan(plan):<28}] {entry.get('repo', '')} -> {plan['record']['note_path']}")
    unconfigured = 0
    for record in manifest.get("records", []):
        repo_id = record.get("repo_id")
        if not isinstance(repo_id, str) or not repo_id or repo_id in seen_repo_ids:
            continue
        unconfigured += 1
        state_counts["repo_unconfigured"] = state_counts.get("repo_unconfigured", 0) + 1
        action_counts["review"] = action_counts.get("review", 0) + 1
        if not quiet:
            source = record.get("configured_repo") or record.get("resolved_repo") or ""
            target = record.get("note_path") or ""
            print(f"  [{'review:repo_unconfigured':<28}] {source} -> {target}")
    summary = (
        f"{action_counts.get('create', 0)} create, {action_counts.get('update', 0)} update, "
        f"{action_counts.get('unchanged', 0)} unchanged, {action_counts.get('skip', 0)} skip, "
        f"{action_counts.get('review', 0)} review, {action_counts.get('error', 0)} error"
    )
    state_summary = ", ".join(f"{state}={count}" for state, count in sorted(state_counts.items())) or "no states"
    print(f"\nsync_github_repos {mode}: {len(repos)} configured repos, {unconfigured} unconfigured manifest repos -> {summary}")
    print(f"lifecycle: {state_summary}")
    print_lifecycle_guidance(state_counts, lifecycle_contract)
    return 1 if action_counts.get("error", 0) else 0


def sync_one(entry, settings, token, force, dry, trusted_existing_baseline=False):
    notes_dir = settings.get("notes_dir", default_repo_notes_dir())
    try:
        note_path = note_output_path(str(notes_dir), str(entry["note"]))
    except ValueError as e:
        return f"error:output-path ({e})"
    domain = domain_from_notes_dir(notes_dir)
    repo_id = repo_id_for(str(entry["repo"]), str(entry["note"]))
    existing_fm, existing_body = ({}, "")
    if note_path.exists():
        existing_fm, existing_body = split_fm(note_path.read_text(encoding="utf-8"))
        existing_fm = existing_fm if isinstance(existing_fm, dict) else {}
        conflict_reason = repo_note_conflict(
            existing_fm,
            existing_body,
            repo_id,
        )
        if conflict_reason:
            return "skipped:conflict"
        if not trusted_existing_baseline:
            return "skipped:manual_modification"
    preserved_prefix, sentinel_found = split_body_at_sentinel(existing_body or "")
    note_rel = str(note_path.relative_to(ROOT)) if note_path.is_relative_to(ROOT) else str(note_path)
    repo_for_annotation = str(existing_fm.get("repo") or entry.get("repo") or "")
    matched_annotation_sidecar = None
    if sentinel_found:
        matched_annotation_sidecar = annotation_sidecar_matches(
            ROOT,
            repo_id=repo_id,
            mirror_path=note_rel,
            existing_fm=existing_fm,
            preserved_body=preserved_prefix,
            repo=repo_for_annotation,
        )
    if matched_annotation_sidecar:
        repo_url = str(
            existing_fm.get("repo_url")
            or entry.get("repo_url")
            or (f"local:{entry['local_path']}" if entry.get("local_path") else f"https://github.com/{repo_for_annotation}")
        )
        preserved = machine_owned_preserved(repo_for_annotation, repo_url, matched_annotation_sidecar)
        frontmatter_source = {}
    else:
        preserved = fresh_preserved(entry["repo"], entry)
        frontmatter_source = existing_fm

    try:
        local_path = local_source_path(entry)
    except ValueError as e:
        return f"error:local-path ({e})"
    if local_path:
        if not local_path.exists() or not local_path.is_dir():
            return f"error:local-path ({local_path} not found)"
        slug = entry["repo"]
        sha = local_tree_sha(local_path)
        identity_issue = repo_frontmatter_identity_issue(existing_fm, repo_identity_values(entry, slug))
        if existing_fm.get("last_commit") == sha and not force and not identity_issue:
            return "unchanged"
        docs = collect_docs(local_path, int(settings.get("max_doc_bytes", 60000)),
                            int(settings.get("max_total_bytes", 300000)))
        commits = recent_commits(local_path, int(settings.get("recent_commits", 10)))
        meta = {
            "description": entry.get("description") or "Local repository fixture",
            "default_branch": entry.get("default_branch", "local"),
            "open_issues_count": "",
            "topics": entry.get("topics", []),
            "pushed_at": "",
            "html_url": entry.get("repo_url", ""),
        }
        fm = base_fm(frontmatter_source, entry, slug, domain=domain)
        fm["status"] = (
            "active"
            if frontmatter_source.get("status") in (None, "", "draft")
            else frontmatter_source["status"]
        )
        fm["default_branch"] = meta["default_branch"]
        fm["last_commit"] = sha
        fm["last_commit_date"] = (commits[0][1] if commits else "")
        fm["open_issues"] = ""
        fm["synced"] = now_iso()
        auto = build_auto(slug, meta, {}, None, docs, commits)
        status = "updated" if note_path.exists() else "created"
        error = write_note_error(note_path, fm, preserved, auto, dry)
        if error:
            return error
        return status

    slug, sha = resolve_slug(entry, token)
    if not slug:
        # unreachable (private/no-auth/renamed/offline): keep real content, else scaffold a stub
        if existing_fm.get("last_commit"):
            return "skipped:unreachable"
        fm = base_fm(frontmatter_source, entry, entry["repo"], domain=domain)
        fm.setdefault("status", "draft")
        fm["synced"] = ""
        error = write_note_error(note_path, fm, preserved, pending_auto(entry["repo"], "not reachable / auth not configured"), dry)
        if error:
            return error
        return "stub"

    identity_issue = repo_frontmatter_identity_issue(existing_fm, repo_identity_values(entry, slug))
    if existing_fm.get("last_commit") == sha and not force and not identity_issue:
        return "unchanged"

    tmp, err = clone(slug, token, max(int(settings.get("recent_commits", 10)) + 5, 15))
    if not tmp:
        if existing_fm.get("last_commit"):
            return f"error:clone ({err})"
        fm = base_fm(frontmatter_source, entry, slug, domain=domain)
        fm.setdefault("status", "draft")
        fm["synced"] = ""
        error = write_note_error(note_path, fm, preserved, pending_auto(slug, f"clone failed: {err}"), dry)
        if error:
            return error
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

    fm = base_fm(frontmatter_source, entry, slug, domain=domain)
    # promote a never-synced/draft stub to active; otherwise respect the curated status
    fm["status"] = (
        "active"
        if frontmatter_source.get("status") in (None, "", "draft")
        else frontmatter_source["status"]
    )
    fm["default_branch"] = (meta or {}).get("default_branch", "")
    fm["last_commit"] = sha
    fm["last_commit_date"] = (commits[0][1] if commits else "")
    fm["open_issues"] = (meta or {}).get("open_issues_count", "")
    fm["synced"] = now_iso()
    auto = build_auto(slug, meta, langs, release, docs, commits)
    status = "updated" if note_path.exists() else "created"
    error = write_note_error(note_path, fm, preserved, auto, dry)
    if error:
        return error
    return status


def main(argv: list[str] | None = None, default_root: Path | None = None, default_config: Path | None = None):
    global ROOT, CONFIG
    ROOT = (default_root or Path.cwd()).resolve()
    CONFIG = (default_config or ROOT / "tools" / "repos.yml").resolve()
    ap = argparse.ArgumentParser(description="Sync markdown mirrors of GitHub repos.")
    ap.add_argument("--config", type=Path, default=CONFIG)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-log", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    if args.plan and args.status:
        print("--plan and --status are mutually exclusive", file=sys.stderr)
        return 1

    if not args.config.exists():
        if args.config == CONFIG:
            print("sync_github_repos: no repos.yml found; skipped (copy tools/repos.example.yml to tools/repos.yml to enable)")
            return 0
        print(f"sync_github_repos: config not found: {args.config}", file=sys.stderr)
        return 1

    try:
        cfg = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print(f"sync_github_repos: invalid YAML in {args.config}: {exc}", file=sys.stderr)
        return 1
    settings, repos, config_errors = validate_config(cfg)
    if config_errors:
        print(f"sync_github_repos: invalid config: {args.config}", file=sys.stderr)
        for error in config_errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    token = get_token()
    try:
        manifest = load_repo_manifest(ROOT)
    except ValueError as exc:
        print(f"sync_github_repos: invalid manifest: {exc}", file=sys.stderr)
        return 1
    if args.plan:
        return print_plan_or_status(settings, repos, token, manifest, "plan", args.quiet)
    if args.status:
        return print_plan_or_status(settings, repos, token, manifest, "status", args.quiet)

    counts = {"created": 0, "updated": 0, "unchanged": 0, "stub": 0, "skipped": 0, "error": 0}
    changed = []
    seen_repo_ids: set[str] = set()
    if not args.quiet:
        print(f"github sync: {len(repos)} repos · auth={'yes' if token else 'NONE (stubs only for private repos)'}")
    for entry in repos:
        plan = plan_one(entry, settings, token, manifest)
        seen_repo_ids.add(plan["record"]["repo_id"])
        if plan["action"] == "review" and (not args.force or review_blocks_force(plan["record"])):
            status = f"skipped:{plan['record']['lifecycle_state']}"
        elif plan["action"] == "error":
            status = "error:plan"
        else:
            trusted_existing_baseline = bool(plan["record"].get("generated_region_sha256")) or not plan["note_path"].exists()
            status = sync_one(
                entry,
                settings,
                token,
                args.force,
                args.dry_run,
                trusted_existing_baseline=trusted_existing_baseline,
            )
        key = status.split(":")[0]
        counts[key] = counts.get(key, 0) + 1
        if not args.quiet:
            print(f"  [{status:<18}] {entry.get('repo', '')} -> {settings.get('notes_dir', default_repo_notes_dir())}/{entry.get('note', '')}")
        if status in ("created", "updated"):
            changed.append(entry.get("note", ""))
        if not args.dry_run:
            update_manifest_after_sync(manifest, plan, status)
            append_audit(sync_audit_event(plan, manifest, status, entry), ROOT)

    manifest_changed = False
    unconfigured = 0
    if not args.dry_run:
        unconfigured = mark_unconfigured_repos(manifest, seen_repo_ids)
        manifest_changed = write_repo_manifest(manifest, ROOT)

    summary = (f"{counts['created']} created, {counts['updated']} updated, {counts['unchanged']} unchanged, "
               f"{counts['stub']} stub, {counts['skipped']} skipped, {counts['error']} error, "
               f"{unconfigured} unconfigured")
    print(f"\nsync_github_repos: {summary}"
          + (" [dry-run]" if args.dry_run else "")
          + (" [manifest updated]" if manifest_changed else ""))

    if (changed or counts["stub"]) and not args.dry_run and not args.no_log:
        with (ROOT / "log.md").open("a", encoding="utf-8") as f:
            f.write(f"## [{dt.date.today().isoformat()}] sync | github repos: {summary}\n")
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
