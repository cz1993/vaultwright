#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
lint_vault.py — health check for a Vaultwright knowledge base.

Reports (does not fix): notes missing required frontmatter, invalid type/status values,
unresolved wikilinks, orphan notes (no inbound links), potential note overlap, Office/repo mirror
gaps, and stale generated mirrors.

Usage:  python3.11 tools/lint_vault.py
"""
from __future__ import annotations
import datetime as dt, hashlib, itertools, json, re, sys
from pathlib import Path
try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

from vaultwright.runtime_profile import (
    profile_context_keys as runtime_profile_context_keys,
    profile_generated_mirror_statuses,
    profile_mirror_mode,
    profile_mirror_root,
)

ROOT = Path.cwd().resolve()
DEFAULT_REQUIRED = ["title", "type", "status", "domain", "created", "updated"]
META = {"CLAUDE.md", "AGENTS.md", "INDEX.md", "RETENTION.md", "CATALOG.md", "log.md"}  # structural, exempt
LINK_SRC_SKIP = {"CLAUDE.md", "AGENTS.md", "_meta/conventions.md"}  # docs full of illustrative links
DEFAULT_TYPES = {"moc", "entity", "note", "guide", "policy", "record", "source-mirror", "source-ref", "repo-mirror"}
DEFAULT_STATUSES = {"draft", "active", "in-review", "sent", "signed", "submitted", "awarded", "superseded", "archived"}
DEFAULT_INACTIVE_STATUSES = ("superseded", "archived")
EXCLUDE_PREFIX = ("_archive", "_backup", "_deprecated")
EXCLUDE_EXACT = {"_fixtures", "_meta", "_templates", "_tmp", "tools", "node_modules"}
SOURCE_EXTS = {".docx", ".pptx", ".xlsx", ".doc"}
TEMP_SOURCE_PREFIXES = ("~$",)
LINK_RE = re.compile(r"\[\[([^\]]+?)\]\]")
WORD_RE = re.compile(r"[a-z0-9][a-z0-9-]{2,}")
DEFAULT_MIRROR_MODE = "dedicated"
DEFAULT_MIRROR_ROOT = "_mirrors"
SOURCE_MANIFEST_REL = "_meta/source-manifest.json"
REPO_MANIFEST_REL = "_meta/repo-manifest.json"
PROFILE_REL = "_meta/profile.yml"
LINT_CONFIG_REL = "_meta/lint-config.yml"
REPO_CONFIG_REL = "tools/repos.yml"
DEFAULT_REPO_NOTES_DIR = "80_sources/repos"
PROFILE_POLICY_DEFAULTS: dict[str, object] = {}
PROFILE_DOMAIN_FOLDERS: dict[str, str] = {}
SENTINEL = "%% AUTO-GENERATED BELOW — DO NOT EDIT %%"
ANNOTATION_ROOT = Path("_meta/mirror-annotations")
MIRROR_MODES = {"dedicated", "sibling"}
DEFAULT_CONTENT_ROOTS = {
    "00_inbox", "10_governance", "20_market", "30_customers", "40_delivery",
    "50_operations", "60_finance", "70_people", "80_sources",
}
FORBIDDEN_OUTPUT_PARTS = {
    ".git", ".githooks", ".github", ".obsidian", "_archive", "_fixtures",
    "_meta", "_templates", "_tmp", "node_modules", "tools",
}
OVERLAP_MIN_TOKENS = 18
OVERLAP_CONTENT_THRESHOLD = 0.72
OVERLAP_TITLE_THRESHOLD = 0.82
CURRENT_SOURCE_STATES = {"clean", "reviewed", "regenerated"}
CURRENT_REPO_STATES = {"clean", "reviewed", "regenerated"}
SOURCE_MANAGED_KEYS = {
    "type", "source_id", "source", "source_manifest", "source_format", "source_modified",
    "synced", "source_sha256", "converter", "converter_version", "updated",
}
REPO_MANAGED_KEYS = {
    "type", "repo_id", "repo_manifest", "repo", "repo_url", "default_branch", "last_commit",
    "last_commit_date", "open_issues", "synced", "updated",
}
DEFAULT_ANNOTATION_FRONTMATTER_KEYS = {"title", "domain", "owner", "created", "updated"}
PROFILE_CONTEXT_KEYS = {"account", "client", "program", "vendor"}
INACTIVE_STATUSES = list(DEFAULT_INACTIVE_STATUSES)
GENERATED_MIRROR_STATUSES = {"active", "draft"}
STOPWORDS = {
    "about", "after", "again", "against", "also", "because", "before", "being", "between",
    "could", "during", "each", "from", "have", "into", "more", "must", "need", "only",
    "other", "over", "should", "than", "that", "their", "there", "these", "this", "through",
    "under", "using", "where", "which", "while", "with", "within", "without", "would",
}

def non_empty_string_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    out = [str(item).strip() for item in value if isinstance(item, str) and item.strip()]
    return out if len(out) == len(value) else None

def profile_contract() -> tuple[dict[str, object], list[tuple[str, str]]]:
    settings: dict[str, object] = {
        "required": list(DEFAULT_REQUIRED),
        "types": set(DEFAULT_TYPES),
        "statuses": set(DEFAULT_STATUSES),
        "inactive_statuses": list(DEFAULT_INACTIVE_STATUSES),
        "content_roots": set(DEFAULT_CONTENT_ROOTS),
        "domain_folders": {},
        "policy_defaults": {},
    }
    path = ROOT / PROFILE_REL
    if not path.exists():
        return settings, [(PROFILE_REL, "missing")]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return settings, [(PROFILE_REL, "invalid YAML")]
    if not isinstance(data, dict):
        return settings, [(PROFILE_REL, "must be a mapping")]

    errors: list[tuple[str, str]] = []
    required = non_empty_string_list(data.get("required_properties"))
    if required:
        settings["required"] = required
    else:
        errors.append((f"{PROFILE_REL}:required_properties", "must be a non-empty string list"))

    for field, setting in (("note_types", "types"), ("statuses", "statuses")):
        values = data.get(field)
        if isinstance(values, dict) and values:
            settings[setting] = {str(key) for key in values}
            if field == "statuses":
                saw_inactive = any(isinstance(definition, dict) and "inactive" in definition for definition in values.values())
                if saw_inactive:
                    settings["inactive_statuses"] = [
                        str(status)
                        for status, definition in values.items()
                        if isinstance(definition, dict) and definition.get("inactive") is True
                    ]
                else:
                    settings["inactive_statuses"] = [
                        status for status in DEFAULT_INACTIVE_STATUSES if status in {str(key) for key in values}
                    ]
        else:
            errors.append((f"{PROFILE_REL}:{field}", "must be a non-empty mapping"))

    domains = data.get("domains")
    domain_folders: dict[str, str] = {}
    if isinstance(domains, dict) and domains:
        for domain, definition in domains.items():
            if isinstance(definition, dict) and definition.get("folder"):
                domain_folders[str(domain)] = str(definition["folder"])
            else:
                errors.append((f"{PROFILE_REL}:domains.{domain}", "missing folder"))
    else:
        errors.append((f"{PROFILE_REL}:domains", "must be a non-empty mapping"))
    if domain_folders:
        settings["domain_folders"] = domain_folders
        settings["content_roots"] = set(domain_folders.values())
    policy_defaults = data.get("policy_defaults")
    if isinstance(policy_defaults, dict):
        settings["policy_defaults"] = dict(policy_defaults)
    else:
        errors.append((f"{PROFILE_REL}:policy_defaults", "must be a mapping"))
    return settings, errors

def domain_folders(profile_domain_folders: dict[str, str]) -> tuple[dict[str, str], dict[str, str], list[tuple[str, str]]]:
    domain_map = ROOT / "_meta" / "domain-map.yml"
    out = dict(profile_domain_folders)
    aliases: dict[str, str] = {}
    for domain_name, folder in out.items():
        aliases[folder] = folder
        aliases[domain_name] = folder
    if not domain_map.exists():
        return out, aliases, [("_meta/domain-map.yml", "missing")]
    try:
        data = yaml.safe_load(domain_map.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return out, aliases, [("_meta/domain-map.yml", "invalid YAML")]
    domains = data.get("domains", {})
    if not isinstance(domains, dict):
        return out, aliases, [("_meta/domain-map.yml", "missing domains map")]
    errors: list[tuple[str, str]] = []
    for domain, info in domains.items():
        if isinstance(info, dict) and info.get("folder"):
            folder = str(info["folder"])
            domain_name = str(domain)
            expected_folder = profile_domain_folders.get(domain_name)
            if expected_folder and expected_folder != folder:
                errors.append((f"_meta/domain-map.yml:{domain_name}", f"folder differs from {PROFILE_REL}"))
                folder = expected_folder
            elif not profile_domain_folders:
                out[domain_name] = folder
            elif domain_name not in profile_domain_folders:
                errors.append((f"_meta/domain-map.yml:{domain_name}", f"domain not declared in {PROFILE_REL}"))
                continue
            aliases[folder] = folder
            aliases[domain_name] = folder
            for alias in info.get("aliases", []) or []:
                aliases[str(alias)] = folder
        else:
            errors.append((f"_meta/domain-map.yml:{domain}", "missing folder"))
    if not out:
        errors.append(("_meta/domain-map.yml", "empty domains map"))
    return out, aliases, errors

def safe_mirror_root(value: str) -> Path:
    path = Path(str(value))
    forbidden = {".git", ".githooks", ".github", ".obsidian", "_archive", "_fixtures",
                 "_meta", "_templates", "_tmp", "node_modules", "tools"}
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("mirror root must stay inside the vault")
    for part in path.parts:
        if part.startswith(".") or part in forbidden:
            raise ValueError("mirror root contains a reserved path component")
    return path

def mirror_config() -> tuple[dict[str, Path | str], list[tuple[str, str]]]:
    cfg = ROOT / "_meta" / "mirror-config.yml"
    mode = profile_mirror_mode(ROOT)
    mirror_root = profile_mirror_root(ROOT)
    mode_label = f"{PROFILE_REL}:policy_defaults.mirror_mode"
    root_label = f"{PROFILE_REL}:policy_defaults.mirror_root"
    errors: list[tuple[str, str]] = []
    if cfg.exists():
        try:
            data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return {"mode": mode, "root": Path(mirror_root)}, [("_meta/mirror-config.yml", "invalid YAML")]
        if not isinstance(data, dict):
            return {"mode": mode, "root": Path(mirror_root)}, [("_meta/mirror-config.yml", "must be a mapping")]
        office = data.get("office_mirrors", data)
        if not isinstance(office, dict):
            return {"mode": mode, "root": Path(mirror_root)}, [("_meta/mirror-config.yml:office_mirrors", "must be a mapping")]
        mode = str(office.get("mode", mode))
        mirror_root = str(office.get("root", mirror_root))
        if "mode" in office:
            mode_label = "_meta/mirror-config.yml:office_mirrors.mode"
        if "root" in office:
            root_label = "_meta/mirror-config.yml:office_mirrors.root"
    if mode not in MIRROR_MODES:
        errors.append((mode_label, "invalid mode"))
        mode = DEFAULT_MIRROR_MODE
    try:
        root_path = safe_mirror_root(mirror_root)
    except ValueError as exc:
        errors.append((root_label, str(exc)))
        root_path = Path(DEFAULT_MIRROR_ROOT)
    return {"mode": mode, "root": root_path}, errors

def lint_config() -> tuple[dict[str, int | float], list[tuple[str, str]]]:
    config = {
        "overlap_min_tokens": OVERLAP_MIN_TOKENS,
        "overlap_content_threshold": OVERLAP_CONTENT_THRESHOLD,
        "overlap_title_threshold": OVERLAP_TITLE_THRESHOLD,
    }
    path = ROOT / LINT_CONFIG_REL
    if not path.exists():
        return config, []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return config, [(LINT_CONFIG_REL, "invalid YAML")]
    if not isinstance(data, dict):
        return config, [(LINT_CONFIG_REL, "must be a mapping")]
    overlap = data.get("overlap", {})
    if overlap is None:
        overlap = {}
    if not isinstance(overlap, dict):
        return config, [(f"{LINT_CONFIG_REL}:overlap", "must be a mapping")]
    errors: list[tuple[str, str]] = []

    min_shared_terms = overlap.get("min_shared_terms", config["overlap_min_tokens"])
    if isinstance(min_shared_terms, int) and not isinstance(min_shared_terms, bool) and min_shared_terms >= 2:
        config["overlap_min_tokens"] = min_shared_terms
    else:
        errors.append((f"{LINT_CONFIG_REL}:overlap.min_shared_terms", "must be an integer >= 2"))

    for key, config_key in (
        ("content_threshold", "overlap_content_threshold"),
        ("title_threshold", "overlap_title_threshold"),
    ):
        value = overlap.get(key, config[config_key])
        if isinstance(value, (int, float)) and not isinstance(value, bool) and 0.0 <= float(value) <= 1.0:
            config[config_key] = float(value)
        else:
            errors.append((f"{LINT_CONFIG_REL}:overlap.{key}", "must be a number between 0 and 1"))
    return config, errors

def safe_repo_rel_path(value: str, label: str, *, allow_nested: bool = True) -> Path:
    text = str(value).strip()
    path = Path(text)
    if not text or text == "." or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must stay inside the vault")
    if not allow_nested and len(path.parts) != 1:
        raise ValueError(f"{label} must be a filename, not a path")
    for part in path.parts:
        if part.startswith(".") or part in FORBIDDEN_OUTPUT_PARTS:
            raise ValueError(f"{label} contains a reserved path component")
    return path

def repo_note_path(notes_dir: str, note: str) -> Path:
    rel_dir = safe_repo_rel_path(notes_dir, "notes_dir")
    rel_note = safe_repo_rel_path(note, "note", allow_nested=False)
    if not rel_dir.parts or rel_dir.parts[0] not in CONTENT_ROOTS:
        raise ValueError("notes_dir must start with a canonical content root")
    if rel_note.suffix != ".md":
        raise ValueError("note must be a .md filename")
    cursor = ROOT
    for part in rel_dir.parts:
        cursor = cursor / part
        if cursor.exists() and cursor.is_symlink():
            raise ValueError("notes_dir must not contain symlink components")
    output_path = ROOT / rel_dir / rel_note
    if output_path.exists() and output_path.is_symlink():
        raise ValueError("note output path must not be a symlink")
    return output_path

def default_repo_notes_dir() -> str:
    configured = PROFILE_POLICY_DEFAULTS.get("repo_notes_dir")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    source_folder = PROFILE_DOMAIN_FOLDERS.get("sources")
    if source_folder:
        return f"{source_folder}/repos"
    return DEFAULT_REPO_NOTES_DIR

def repo_context_values(entry: dict[str, object], context_keys: set[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    if "account" in context_keys:
        account = entry.get("account") or entry.get("client")
        if isinstance(account, str) and account.strip():
            values["account"] = account.strip()
    if "client" in context_keys:
        client = entry.get("client") or values.get("account") or entry.get("account")
        if isinstance(client, str) and client.strip():
            values["client"] = client.strip()
    for key in sorted(context_keys - {"account", "client"}):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            values[key] = value.strip()
    return values

def repo_id_for(repo: str, note: str) -> str:
    digest = hashlib.sha256(f"{repo}\0{note}".encode("utf-8")).hexdigest()[:20]
    return f"repo_{digest}"

def repo_config() -> tuple[list[dict[str, object]], list[tuple[str, str]]]:
    path = ROOT / REPO_CONFIG_REL
    if not path.exists():
        return [], []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return [], [(REPO_CONFIG_REL, "invalid YAML")]
    if not isinstance(data, dict):
        return [], [(REPO_CONFIG_REL, "must be a mapping")]

    settings = data.get("settings", {})
    repos = data.get("repos", [])
    errors: list[tuple[str, str]] = []
    if settings is None:
        settings = {}
    if not isinstance(settings, dict):
        errors.append((f"{REPO_CONFIG_REL}:settings", "must be a mapping"))
        settings = {}
    if repos is None:
        repos = []
    if not isinstance(repos, list):
        return [], [*errors, (f"{REPO_CONFIG_REL}:repos", "must be a list")]

    notes_dir = str(settings.get("notes_dir", default_repo_notes_dir()))
    configured: list[dict[str, object]] = []
    seen_note_paths: dict[str, str] = {}
    for index, entry in enumerate(repos):
        label = f"{REPO_CONFIG_REL}:repos[{index}]"
        if not isinstance(entry, dict):
            errors.append((label, "must be a mapping"))
            continue
        repo = entry.get("repo")
        note = entry.get("note")
        if not isinstance(repo, str) or not repo.strip():
            errors.append((f"{label}.repo", "is required"))
        if not isinstance(note, str) or not note.strip():
            errors.append((f"{label}.note", "is required"))
            continue
        try:
            note_path = repo_note_path(notes_dir, note)
        except ValueError as exc:
            errors.append((f"{label}.note", str(exc)))
            continue
        note_rel = note_path.relative_to(ROOT).as_posix()
        note_key = note_rel.casefold()
        previous = seen_note_paths.get(note_key)
        if previous:
            errors.append((f"{label}.note", f"duplicates output path {note_rel} from {previous}"))
            continue
        seen_note_paths[note_key] = label
        if isinstance(repo, str) and repo.strip():
            item: dict[str, object] = {
                "repo": repo.strip(),
                "note": note.strip(),
                "repo_id": repo_id_for(repo.strip(), note.strip()),
                "path": note_path,
            }
            for key in ("tags", "related"):
                value = entry.get(key)
                if isinstance(value, list):
                    item[key] = [str(part).strip() for part in value if str(part).strip()]
            item.update(repo_context_values(entry, PROFILE_CONTEXT_KEYS))
            configured.append(item)
    return configured, errors

def load_manifest_records(rel: str, id_key: str) -> tuple[dict[str, dict], list[tuple[str, str]]]:
    path = ROOT / rel
    if not path.exists():
        return {}, []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}, [(rel, "invalid JSON")]
    if not isinstance(data, dict):
        return {}, [(rel, "must be a JSON object")]
    records = data.get("records", [])
    if not isinstance(records, list):
        return {}, [(rel, "records must be a list")]
    out: dict[str, dict] = {}
    errors: list[tuple[str, str]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append((f"{rel}:records[{index}]", "must be a mapping"))
            continue
        record_id = str(record.get(id_key, "")).strip()
        if not record_id:
            errors.append((f"{rel}:records[{index}]", f"missing {id_key}"))
            continue
        out[record_id] = record
    return out, errors

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

def normalized_words(text: str) -> set[str]:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", " ", text)
    return {word for word in WORD_RE.findall(text.lower()) if word not in STOPWORDS}

def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

def overlap_consolidation_suggestion(left: dict[str, object], right: dict[str, object]) -> str:
    left_path = str(left["path"])
    right_path = str(right["path"])
    left_type = str(left.get("type", ""))
    right_type = str(right.get("type", ""))

    left_inbound = int(left.get("inbound", 0) or 0)
    right_inbound = int(right.get("inbound", 0) or 0)
    if left_inbound != right_inbound:
        if left_inbound > right_inbound:
            keep, merge_from = left_path, right_path
            keep_inbound, merge_inbound = left_inbound, right_inbound
        else:
            keep, merge_from = right_path, left_path
            keep_inbound, merge_inbound = right_inbound, left_inbound
        return (
            f"suggestion: keep {keep} ({keep_inbound} inbound link{'s' if keep_inbound != 1 else ''} "
            f"vs {merge_inbound}); merge unique details from {merge_from}, then mark the duplicate "
            f"{inactive_status_label()} after review"
        )

    if left_type and right_type and left_type != right_type:
        return (
            f"suggestion: review boundaries ({left_type} vs {right_type}); link or consolidate "
            f"shared material before adding another note"
        )

    return (
        f"suggestion: choose one canonical note, merge unique details, then mark one note "
        f"{inactive_status_label()} after review"
    )

def inactive_status_label() -> str:
    values = [status for status in INACTIVE_STATUSES if isinstance(status, str) and status.strip()]
    return "/".join(values) if values else "with an inactive profile status"

def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def local_tree_sha(repodir: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(repodir.rglob("*")):
        if not p.is_file() or p.is_symlink() or ".git/" in str(p.relative_to(repodir)):
            continue
        rel = str(p.relative_to(repodir)).replace("\\", "/")
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return "local-" + h.hexdigest()[:40]

def main(root: Path | None = None) -> int:
    global ROOT, CONTENT_ROOTS, PROFILE_DOMAIN_FOLDERS, PROFILE_POLICY_DEFAULTS, PROFILE_CONTEXT_KEYS, INACTIVE_STATUSES, GENERATED_MIRROR_STATUSES
    ROOT = (root or Path.cwd()).resolve()
    # inventory
    all_files = sorted(
        (p for p in ROOT.rglob("*") if p.is_file() and not excluded(p.relative_to(ROOT).parent)),
        key=lambda path: path.relative_to(ROOT).as_posix(),
    )
    markdown_case = [(str(p.relative_to(ROOT)), "use lowercase .md") for p in all_files if p.suffix.lower() == ".md" and p.suffix != ".md"]
    md_notes = [p for p in all_files if p.suffix.lower() == ".md"]
    by_stem: dict[str, list[Path]] = {}
    by_name: dict[str, list[Path]] = {}
    for p in all_files:
        by_name.setdefault(p.name, []).append(p)
        by_stem.setdefault(p.stem, []).append(p)

    def target_paths(target: str) -> list[Path]:
        t = target.split("|")[0].split("#")[0].strip()
        if not t:
            return []
        path = Path(t)
        path_qualified = len(path.parts) > 1 or t.startswith("/")
        if not path.is_absolute() and ".." not in path.parts:
            direct = ROOT / path
            if direct.exists():
                return [direct]
            if not path.suffix:
                direct_md = ROOT / Path(f"{t}.md")
                if direct_md.exists():
                    return [direct_md]
                parent = ROOT / path.parent
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
        cand = t.rsplit("/", 1)[-1]  # basename
        if cand in by_name:           # has extension, e.g. foo.pdf
            return by_name[cand]
        if cand in by_stem:           # note by stem
            return by_stem[cand]
        return []

    def resolve(target: str) -> bool:
        t = target.split("|")[0].split("#")[0].strip()
        if not t:
            return True
        return bool(target_paths(target))

    PROFILE_SETTINGS, profile_errors = profile_contract()
    REQUIRED = list(PROFILE_SETTINGS["required"])
    TYPES = set(PROFILE_SETTINGS["types"])
    STATUSES = set(PROFILE_SETTINGS["statuses"])
    INACTIVE_STATUSES = list(PROFILE_SETTINGS["inactive_statuses"])
    CONTENT_ROOTS = set(PROFILE_SETTINGS["content_roots"])
    PROFILE_DOMAIN_FOLDERS = {
        str(domain): str(folder)
        for domain, folder in dict(PROFILE_SETTINGS["domain_folders"]).items()
    }
    PROFILE_POLICY_DEFAULTS = dict(PROFILE_SETTINGS["policy_defaults"])
    PROFILE_CONTEXT_KEYS = set(runtime_profile_context_keys(ROOT))
    GENERATED_MIRROR_STATUSES = profile_generated_mirror_statuses(ROOT)
    DOMAIN_FOLDERS, DOMAIN_FOLDER_ALIASES, domain_map_errors = domain_folders(PROFILE_DOMAIN_FOLDERS)
    DOMAIN_BY_FOLDER = {folder: domain for domain, folder in DOMAIN_FOLDERS.items()}
    MIRROR_CONFIG, mirror_config_errors = mirror_config()
    LINT_CONFIG, lint_config_errors = lint_config()
    CONFIGURED_REPOS, repo_config_errors = repo_config()
    CONFIGURED_REPO_NOTE_PATHS = {item["path"] for item in CONFIGURED_REPOS if isinstance(item.get("path"), Path)}
    CONFIGURED_REPOS_BY_NOTE_PATH = {
        item["path"]: item
        for item in CONFIGURED_REPOS
        if isinstance(item.get("path"), Path)
    }
    CONFIGURED_REPO_IDS = {str(item.get("repo_id")) for item in CONFIGURED_REPOS if str(item.get("repo_id", "")).strip()}
    SOURCE_MANIFEST_RECORDS, source_manifest_errors = load_manifest_records(SOURCE_MANIFEST_REL, "source_id")
    REPO_MANIFEST_RECORDS, repo_manifest_errors = load_manifest_records(REPO_MANIFEST_REL, "repo_id")
    manifest_errors = source_manifest_errors + repo_manifest_errors
    MIRROR_ROOT = MIRROR_CONFIG["root"] if isinstance(MIRROR_CONFIG["root"], Path) else Path(DEFAULT_MIRROR_ROOT)
    overlap_min_tokens = int(LINT_CONFIG["overlap_min_tokens"])
    overlap_content_threshold = float(LINT_CONFIG["overlap_content_threshold"])
    overlap_title_threshold = float(LINT_CONFIG["overlap_title_threshold"])
    DOMAINS = set(DOMAIN_FOLDERS)
    missing_fm, bad_type, bad_status, bad_domain, bad_domain_folder, bad_account_client, bad_mirror_layout, unresolved = [], [], [], [], [], [], [], []
    mirror_annotations_need_migration: list[tuple[str, str]] = []
    stale_office_mirrors: list[tuple[str, str]] = []
    stale_repo_mirrors: list[tuple[str, str]] = []
    overlap_inputs: list[dict[str, object]] = []
    note_types: dict[Path, str] = {}
    source_paths: dict[Path, str] = {}
    managed_generated_mirrors: set[Path] = set()
    repo_mirror_ids: dict[Path, str] = {}
    inbound: dict[Path, int] = {p: 0 for p in md_notes}

    def domain_lint_message(value: object) -> str:
        domain = str(value)
        canonical_folder = DOMAIN_FOLDER_ALIASES.get(domain)
        canonical_domain = DOMAIN_BY_FOLDER.get(canonical_folder or "")
        if canonical_domain and canonical_domain != domain:
            return f"{domain} -> {canonical_domain} ({canonical_folder}/)"
        return domain

    def in_mirror_root(rel: Path) -> bool:
        return bool(MIRROR_ROOT.parts) and rel.parts[:len(MIRROR_ROOT.parts)] == MIRROR_ROOT.parts

    def is_repo_mirror_path(rel: Path) -> bool:
        if (ROOT / rel) in CONFIGURED_REPO_NOTE_PATHS:
            return True
        try:
            default_root = repo_note_path(default_repo_notes_dir(), "__vaultwright_repo_probe__.md").parent
        except ValueError:
            return False
        try:
            rel_default_root = default_root.relative_to(ROOT)
        except ValueError:
            return False
        return (
            len(rel.parts) > len(rel_default_root.parts)
            and rel.parts[:len(rel_default_root.parts)] == rel_default_root.parts
        )

    def source_mirror_paths(source_rel: str) -> list[Path]:
        if not source_rel:
            return []
        source_path = Path(source_rel)
        if source_path.is_absolute() or ".." in source_path.parts:
            return []
        if MIRROR_CONFIG["mode"] == "sibling":
            preferred = source_path.with_suffix(".md")
        else:
            preferred = MIRROR_ROOT / canonical_source_rel(ROOT / source_path).with_suffix(".md")
        return [preferred, preferred.with_name(preferred.stem + ".mirror.md")]

    def has_generated_sentinel(body: str) -> bool:
        for line in body.splitlines(keepends=True):
            if line.rstrip("\r\n") == SENTINEL:
                return True
        return body.rstrip("\r\n") == SENTINEL

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
        return cleaned or hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]

    def annotation_sidecar_path(note_type: str, identity: str) -> Path:
        group = "source" if note_type == "source-mirror" else "repo"
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

    def annotation_managed_keys(note_type: str) -> set[str]:
        return SOURCE_MANAGED_KEYS if note_type == "source-mirror" else REPO_MANAGED_KEYS

    def preserved_annotation_frontmatter(fm: dict, note_type: str) -> dict:
        managed = annotation_managed_keys(note_type)
        return {str(key): value for key, value in fm.items() if str(key) not in managed}

    def configured_repo_seed(rel: Path | None) -> dict[str, object]:
        if rel is None:
            return {}
        entry = CONFIGURED_REPOS_BY_NOTE_PATH.get(ROOT / rel)
        if not entry:
            return {}
        seed: dict[str, object] = {}
        seed["tags"] = entry.get("tags", ["repo"])
        seed["related"] = entry.get("related", [])
        seed.update(repo_context_values(entry, PROFILE_CONTEXT_KEYS))
        return seed

    def annotation_frontmatter_has_content(fm: dict, note_type: str, rel: Path | None = None) -> bool:
        preserved = preserved_annotation_frontmatter(fm, note_type)
        repo_seed = configured_repo_seed(rel) if note_type == "repo-mirror" else {}
        for key, value in preserved.items():
            if key in DEFAULT_ANNOTATION_FRONTMATTER_KEYS:
                continue
            if key == "status" and str(value or "").strip() in {"", *GENERATED_MIRROR_STATUSES}:
                continue
            if key == "tags":
                tags = value if isinstance(value, list) else []
                clean_tags = {str(item).strip() for item in tags if str(item).strip()}
                expected_tags = {
                    str(item).strip()
                    for item in repo_seed.get("tags", ["repo"] if note_type == "repo-mirror" else [])
                    if str(item).strip()
                }
                if not clean_tags or (note_type == "repo-mirror" and clean_tags <= expected_tags):
                    continue
                return True
            if key == "related":
                related = value if isinstance(value, list) else []
                clean_related = {str(item).strip() for item in related if str(item).strip()}
                expected_related = {
                    str(item).strip()
                    for item in repo_seed.get("related", [])
                    if str(item).strip()
                }
                if not clean_related or (note_type == "repo-mirror" and clean_related <= expected_related):
                    continue
                return True
            if key in PROFILE_CONTEXT_KEYS and value in (None, "", []):
                continue
            if note_type == "repo-mirror" and key in PROFILE_CONTEXT_KEYS and repo_seed.get(key) == str(value or "").strip():
                continue
            return True
        return False

    def default_preserved_line(line: str) -> bool:
        stripped = line.strip()
        return (
            not stripped
            or stripped == "## Notes"
            or stripped.startswith("# ")
            or stripped == "> [!info] Source-mirrored document — auto-generated"
            or stripped == "> [!info] GitHub repo mirror — auto-generated"
            or stripped.startswith("> Original: ")
            or stripped.startswith("> Source: ")
            or stripped.startswith("> Human annotations were migrated to ")
            or stripped == "> Curate notes below; everything under the line refreshes on each sync."
            or stripped == "> Curate notes below; everything under the line refreshes on sync."
            or stripped == "> This mirror is machine-owned; do not edit it directly."
            or stripped == "> This mirror is machine-owned; keep durable human notes in curated notes or annotation sidecars."
        )

    def preserved_body_has_annotation(body: str) -> bool:
        return any(not default_preserved_line(line) for line in body.splitlines())

    def normalized_preserved_body(body: str) -> str:
        return body[1:] if body.startswith("\n") else body

    def annotation_preserved_hash(note_type: str, identity: str, rel: Path, fm: dict, preserved_body: str) -> str:
        payload = {
            "kind": note_type,
            "identity": identity,
            "mirror_path": rel.as_posix(),
            "frontmatter": preserved_annotation_frontmatter(fm, note_type),
            "body": preserved_body.rstrip() + ("\n" if preserved_body.strip() else ""),
        }
        if note_type == "source-mirror":
            payload["source"] = str(fm.get("source", "") or "")
        else:
            payload["repo"] = str(fm.get("repo", "") or "")
        encoded = json.dumps(json_safe(payload), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def matching_annotation_sidecar(rel: Path, note_type: str, fm: dict, preserved_body: str) -> bool:
        id_key = "source_id" if note_type == "source-mirror" else "repo_id"
        identity = str(fm.get(id_key, "") or "").strip()
        if not identity:
            return False
        sidecar = ROOT / annotation_sidecar_path(note_type, identity)
        if not sidecar.exists():
            return False
        sidecar_fm, _body = split_fm(sidecar.read_text(encoding="utf-8", errors="ignore"))
        if not isinstance(sidecar_fm, dict):
            return False
        expected = annotation_preserved_hash(note_type, identity, rel, fm, preserved_body)
        return str(sidecar_fm.get("preserved_sha256", "") or "") == expected

    def mirror_annotation_migration_issue(rel: Path, note_type: str, fm: dict, body: str) -> str | None:
        if note_type not in {"source-mirror", "repo-mirror"}:
            return None
        preserved, sentinel_found = split_body_at_sentinel(body)
        if not sentinel_found:
            return None
        preserved = normalized_preserved_body(preserved)
        has_annotation = preserved_body_has_annotation(preserved) or annotation_frontmatter_has_content(fm, note_type, rel)
        if not has_annotation:
            return None
        if matching_annotation_sidecar(rel, note_type, fm, preserved):
            return None
        return "above-sentinel annotations need sidecar migration; run vaultwright migrate annotations --write"

    def source_mirror_metadata_ok(rel: Path, fm: dict) -> bool:
        source = str(fm.get("source", "")).strip()
        source_id = str(fm.get("source_id", "")).strip()
        source_sha256 = str(fm.get("source_sha256", "")).strip()
        record = SOURCE_MANIFEST_RECORDS.get(source_id)
        return (
            bool(source)
            and bool(source_id)
            and str(fm.get("source_manifest", "")).strip() == SOURCE_MANIFEST_REL
            and bool(source_sha256)
            and bool(record)
            and str(record.get("current_source_path", "")).strip() == source
            and str(record.get("mirror_path", "")).strip() == rel.as_posix()
            and str(record.get("source_sha256", "")).strip() == source_sha256
        )

    def repo_mirror_metadata_ok(rel: Path, fm: dict) -> bool:
        repo_id = str(fm.get("repo_id", "")).strip()
        record = REPO_MANIFEST_RECORDS.get(repo_id)
        return (
            bool(str(fm.get("repo", "")).strip())
            and bool(repo_id)
            and str(fm.get("repo_manifest", "")).strip() == REPO_MANIFEST_REL
            and bool(record)
            and str(record.get("note_path", "")).strip() == rel.as_posix()
        )

    def source_root_matches_domain(source_rel: str, expected_folder: str | None) -> bool:
        if not source_rel or not expected_folder:
            return False
        source_path = Path(source_rel)
        if source_path.is_absolute() or ".." in source_path.parts or not source_path.parts:
            return False
        return DOMAIN_FOLDER_ALIASES.get(source_path.parts[0]) == expected_folder

    def is_managed_generated_mirror(rel: Path, note_type: str, fm: dict, has_sentinel: bool) -> bool:
        if note_type == "source-mirror":
            return (
                has_sentinel
                and source_mirror_metadata_ok(rel, fm)
                and rel in source_mirror_paths(str(fm.get("source", "")))
            )
        if note_type == "repo-mirror":
            return has_sentinel and repo_mirror_metadata_ok(rel, fm) and is_repo_mirror_path(rel)
        return False

    def source_mirror_freshness_issue(rel: Path, fm: dict) -> str | None:
        source_rel = str(fm.get("source", "")).strip()
        source_id = str(fm.get("source_id", "")).strip()
        record = SOURCE_MANIFEST_RECORDS.get(source_id, {})
        source_path = Path(source_rel)
        if not source_rel or source_path.is_absolute() or ".." in source_path.parts:
            return "source path is invalid"
        actual = ROOT / source_path
        if not actual.exists():
            return f"source missing: {source_rel}"
        if not actual.is_file():
            return f"source is not a file: {source_rel}"
        state = str(record.get("lifecycle_state", "clean") or "clean")
        if state not in CURRENT_SOURCE_STATES:
            return f"source-manifest lifecycle_state={state}; run vaultwright sync/status before relying on mirror"
        try:
            current_sha = sha256_of(actual)
        except OSError as exc:
            return f"source unreadable: {exc.__class__.__name__}"
        expected_sha = str(record.get("source_sha256") or fm.get("source_sha256") or "").strip()
        if expected_sha and current_sha != expected_sha:
            return "source hash changed; run vaultwright sync before relying on mirror"
        return None

    def repo_mirror_freshness_issue(fm: dict) -> str | None:
        repo_id = str(fm.get("repo_id", "")).strip()
        record = REPO_MANIFEST_RECORDS.get(repo_id, {})
        mirror_repo = str(fm.get("repo", "")).strip()
        manifest_repos = {
            str(record.get(key, "") or "").strip()
            for key in ("resolved_repo", "configured_repo")
            if str(record.get(key, "") or "").strip()
        }
        if manifest_repos and mirror_repo not in manifest_repos:
            return "repo frontmatter repo differs from repo manifest; run vaultwright sync before relying on mirror"
        state = str(record.get("lifecycle_state", "clean") or "clean")
        if state not in CURRENT_REPO_STATES:
            return f"repo-manifest lifecycle_state={state}; run vaultwright sync/status before relying on mirror"
        manifest_commit = str(record.get("last_commit", "") or "").strip()
        mirror_commit = str(fm.get("last_commit", "") or "").strip()
        if manifest_commit and mirror_commit and manifest_commit != mirror_commit:
            return "repo manifest last_commit differs from mirror frontmatter; run vaultwright sync before relying on mirror"
        if str(record.get("source_type", "")).strip() != "local":
            return None
        source_ref = str(record.get("source_ref", "") or "").strip()
        source_path = Path(source_ref)
        if not source_ref or source_path.is_absolute() or ".." in source_path.parts:
            return "local repo source path is invalid"
        actual = ROOT / source_path
        if not actual.exists():
            return f"local repo source missing: {source_ref}"
        if not actual.is_dir():
            return f"local repo source is not a directory: {source_ref}"
        try:
            current_commit = local_tree_sha(actual)
        except OSError as exc:
            return f"local repo source unreadable: {exc.__class__.__name__}"
        expected_commit = manifest_commit or mirror_commit
        if expected_commit and current_commit != expected_commit:
            return "local repo tree changed; run vaultwright sync before relying on mirror"
        return None

    def canonical_source_rel(src: Path) -> Path:
        rel = src.relative_to(ROOT)
        if not rel.parts:
            return rel
        canonical = DOMAIN_FOLDER_ALIASES.get(rel.parts[0])
        if not canonical:
            return rel
        return Path(canonical, *rel.parts[1:])

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
            note_type = str(fm.get("type", ""))
            source_rel = str(fm.get("source", ""))
            generated_sentinel = has_generated_sentinel(body)
            managed_generated_mirror = is_managed_generated_mirror(rel, note_type, fm, generated_sentinel)
            valid_sibling_source_mirror = (
                note_type == "source-mirror"
                and MIRROR_CONFIG["mode"] == "sibling"
                and managed_generated_mirror
                and source_root_matches_domain(source_rel, DOMAIN_FOLDERS.get(str(fm.get("domain"))))
            )
            note_types[p] = note_type
            source_paths[p] = source_rel
            if managed_generated_mirror:
                managed_generated_mirrors.add(p)
                if note_type == "source-mirror":
                    freshness_issue = source_mirror_freshness_issue(rel, fm)
                    if freshness_issue:
                        stale_office_mirrors.append((rels, freshness_issue))
                elif note_type == "repo-mirror":
                    repo_mirror_ids[p] = str(fm.get("repo_id", "")).strip()
                    freshness_issue = repo_mirror_freshness_issue(fm)
                    if freshness_issue:
                        stale_repo_mirrors.append((rels, freshness_issue))
                annotation_issue = mirror_annotation_migration_issue(rel, note_type, fm, body)
                if annotation_issue:
                    mirror_annotations_need_migration.append((rels, annotation_issue))
            miss = [k for k in REQUIRED if k not in fm or fm.get(k) in (None, "")]
            if miss:
                missing_fm.append((rels, "missing: " + ",".join(miss)))
            if fm.get("type") not in TYPES:
                bad_type.append((rels, str(fm.get("type"))))
            if fm.get("status") not in STATUSES:
                bad_status.append((rels, str(fm.get("status"))))
            if DOMAINS and fm.get("domain") not in DOMAINS:
                bad_domain.append((rels, domain_lint_message(fm.get("domain"))))
            expected_folder = DOMAIN_FOLDERS.get(str(fm.get("domain")))
            if expected_folder and rel.parts:
                if in_mirror_root(rel):
                    expected_prefix = [*MIRROR_ROOT.parts, expected_folder]
                    if fm.get("type") != "source-mirror":
                        bad_mirror_layout.append((rels, "only source-mirror notes belong under mirror root"))
                    elif list(rel.parts[:len(expected_prefix)]) != expected_prefix:
                        bad_domain_folder.append((rels, f"{fm.get('domain')} -> {Path(*expected_prefix).as_posix()}"))
                elif not valid_sibling_source_mirror and rel.parts[0] != expected_folder:
                    bad_domain_folder.append((rels, f"{fm.get('domain')} -> {expected_folder}"))
            if note_type == "source-mirror" and not managed_generated_mirror:
                if MIRROR_CONFIG["mode"] == "dedicated":
                    if in_mirror_root(rel):
                        bad_mirror_layout.append((rels, "source-mirror requires generated sentinel, manifest metadata, and source-derived path"))
                    else:
                        bad_mirror_layout.append((rels, f"source-mirror notes belong under {MIRROR_ROOT.as_posix()}"))
                else:
                    bad_mirror_layout.append((rels, "source-mirror requires generated sentinel, manifest metadata, and source-derived sibling path"))
            if note_type == "repo-mirror" and not managed_generated_mirror:
                if is_repo_mirror_path(rel):
                    bad_mirror_layout.append((rels, "repo-mirror requires generated sentinel and manifest metadata"))
                else:
                    bad_mirror_layout.append((rels, "repo-mirror notes belong under configured tools/repos.yml notes_dir or profile policy_defaults.repo_notes_dir"))
            if {"account", "client"} <= PROFILE_CONTEXT_KEYS:
                if fm.get("client") and not fm.get("account"):
                    bad_account_client.append((rels, "client requires account"))
                elif fm.get("account") and fm.get("client") and str(fm["account"]).strip() != str(fm["client"]).strip():
                    bad_account_client.append((rels, "client must match account"))
            if (
                not managed_generated_mirror
                and fm.get("status") not in set(INACTIVE_STATUSES)
            ):
                title_words = normalized_words(str(fm.get("title", "")))
                body_words = normalized_words(body)
                if title_words or len(body_words) >= overlap_min_tokens:
                    overlap_inputs.append({
                        "path": rels,
                        "title": str(fm.get("title", "")),
                        "type": note_type,
                        "title_words": title_words,
                        "body_words": body_words,
                        "domain": str(fm.get("domain", "")),
                    })
        if p.name in {"CLAUDE.md", "AGENTS.md"} or rels in LINK_SRC_SKIP:
            continue  # don't lint illustrative links inside the convention docs
        # collect links from body (minus inline-code examples) + frontmatter
        body_clean = re.sub(r"`+[^`]*`+", "", body)
        targets = list(LINK_RE.findall(body_clean))
        for key in ("related", *sorted(PROFILE_CONTEXT_KEYS)):
            v = fm.get(key)
            if isinstance(v, str):
                targets += LINK_RE.findall(v)
            elif isinstance(v, list):
                for it in v:
                    if isinstance(it, str):
                        targets += LINK_RE.findall(it)
        targets = [t.replace("\\|", "|") for t in targets]  # Obsidian table-escaped pipes
        for t in targets:
            linked_paths = target_paths(t)
            if not linked_paths:
                unresolved.append((str(rel), t.split("|")[0].split("#")[0].strip()))
            else:
                for q in linked_paths:
                    if q.suffix == ".md" and q != p:
                        inbound[q] = inbound.get(q, 0) + 1

    # mirror integrity
    mirror_gap = []
    repo_mirror_gap = []
    repo_unconfigured = []
    def expected_mirror_paths(src: Path) -> list[Path]:
        if MIRROR_CONFIG["mode"] == "sibling":
            preferred = src.with_suffix(".md")
        else:
            preferred = ROOT / MIRROR_ROOT / canonical_source_rel(src).with_suffix(".md")
        return [preferred, preferred.with_name(preferred.stem + ".mirror.md")]

    for p in all_files:
        if p.suffix.lower() in SOURCE_EXTS and not excluded(p.relative_to(ROOT).parent):
            if p.name.startswith(TEMP_SOURCE_PREFIXES):
                continue
            if p.suffix.lower() == ".doc":
                continue  # legacy, unsupported by converter
            if not any(candidate in managed_generated_mirrors for candidate in expected_mirror_paths(p)):
                mirror_gap.append(str(p.relative_to(ROOT)) + "  (no markdown mirror)")

    for expected in CONFIGURED_REPOS:
        note_path = expected["path"]
        expected_repo_id = str(expected["repo_id"])
        if not isinstance(note_path, Path):
            continue
        if note_path not in managed_generated_mirrors:
            repo_mirror_gap.append(str(note_path.relative_to(ROOT)) + "  (configured repo mirror missing or unmanaged)")
            continue
        actual_repo_id = repo_mirror_ids.get(note_path, "")
        if actual_repo_id != expected_repo_id:
            repo_mirror_gap.append(str(note_path.relative_to(ROOT)) + "  (configured repo mirror repo_id mismatch; run vaultwright sync)")

    if not repo_config_errors:
        for repo_id, record in sorted(REPO_MANIFEST_RECORDS.items()):
            if repo_id in CONFIGURED_REPO_IDS:
                continue
            note_path = str(record.get("note_path", "") or "").strip()
            label = note_path or repo_id
            repo_unconfigured.append(
                label + "  (repo manifest record not governed by tools/repos.yml; restore config or retire mirror)"
            )

    orphan_exempt_names = {"INDEX.md", "CLAUDE.md", "AGENTS.md", "README.md", "RETENTION.md", "CATALOG.md", "log.md"}
    orphans = sorted(
        str(p.relative_to(ROOT))
        for p, n in inbound.items()
        if n == 0
        and p.name not in orphan_exempt_names
        and p not in managed_generated_mirrors
    )

    overlap_candidates = []
    for left, right in itertools.combinations(overlap_inputs, 2):
        left_title = left["title_words"]
        right_title = right["title_words"]
        left_body = left["body_words"]
        right_body = right["body_words"]
        title_score = jaccard(left_title, right_title) if isinstance(left_title, set) and isinstance(right_title, set) else 0.0
        body_score = jaccard(left_body, right_body) if isinstance(left_body, set) and isinstance(right_body, set) else 0.0
        common_body = len(left_body & right_body) if isinstance(left_body, set) and isinstance(right_body, set) else 0
        reasons = []
        if len(left_title) >= 2 and len(right_title) >= 2 and title_score >= overlap_title_threshold:
            reasons.append(f"title similarity {title_score:.0%}")
        if common_body >= overlap_min_tokens and body_score >= overlap_content_threshold:
            reasons.append(f"content overlap {body_score:.0%}")
        if reasons:
            left_path = ROOT / Path(str(left["path"]))
            right_path = ROOT / Path(str(right["path"]))
            left["inbound"] = inbound.get(left_path, 0)
            right["inbound"] = inbound.get(right_path, 0)
            suggestion = overlap_consolidation_suggestion(left, right)
            overlap_candidates.append((
                f"{left['path']} <-> {right['path']}",
                "; ".join(reasons) + f" - {suggestion}",
            ))

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
    section("Invalid domain", bad_domain)
    section("Profile errors", profile_errors)
    section("Domain map errors", domain_map_errors)
    section("Mirror config errors", mirror_config_errors)
    section("Lint config errors", lint_config_errors)
    section("Repo config errors", repo_config_errors)
    section("Manifest errors", manifest_errors)
    section("Domain/folder mismatch", bad_domain_folder)
    section("Account/client mismatch", bad_account_client)
    section("Mirror layout errors", bad_mirror_layout)
    section("Mirror annotations needing migration", mirror_annotations_need_migration)
    section("Stale Office mirrors", stale_office_mirrors)
    section("Stale repo mirrors", stale_repo_mirrors)
    section("Non-lowercase markdown extension", markdown_case)
    section("Unresolved wikilinks", unresolved)
    section("Orphan notes (no inbound links)", orphans)
    section("Potential duplicate/overlap notes", overlap_candidates)
    section("Office files without a mirror", mirror_gap)
    section("Configured repos without a mirror", repo_mirror_gap)
    section("Unconfigured repo mirrors", repo_unconfigured)
    blocking = (
        missing_fm or bad_type or bad_status or bad_domain or profile_errors or domain_map_errors or mirror_config_errors
        or lint_config_errors
        or repo_config_errors or manifest_errors or bad_domain_folder or bad_account_client or bad_mirror_layout
        or mirror_annotations_need_migration or stale_office_mirrors or stale_repo_mirrors
        or markdown_case or mirror_gap or repo_mirror_gap or repo_unconfigured
    )
    print("\nOK" if not blocking else "\nISSUES FOUND (unresolved links, orphans & overlap candidates are warnings)")
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
