# SPDX-License-Identifier: AGPL-3.0-or-later
"""Package-owned Vaultwright doctor checks."""
from __future__ import annotations

import fnmatch
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

from vaultwright import recovery as recovery_module
from vaultwright import review_ledger as review_ledger_module
from vaultwright.profiles import ProfileValidationError, load_profile
from vaultwright.runtime_profile import configured_office_mirror_root
from vaultwright.views import profile_views_plan

LIFECYCLE_CONTRACT = Path("_meta/lifecycle-states.yml")
PROFILE_REL = Path("_meta/profile.yml")
LIFECYCLE_REQUIRED_FIELDS = {
    "entry_condition",
    "explanation",
    "permitted_next_actions",
    "exit_condition",
}
GITIGNORE_REQUIRED_PATTERNS = {
    "data/": "data/.vaultwright-doctor-check",
    "secrets/": "secrets/.vaultwright-doctor-check",
    "private/": "private/.vaultwright-doctor-check",
    ".env": ".env",
    "*.pem": "vaultwright-doctor-check.pem",
    ".obsidian/workspace*.json": ".obsidian/workspace.json",
}
COMMON_REQUIRED_VAULT_FILES = (
    "CLAUDE.md",
    "INDEX.md",
    LIFECYCLE_CONTRACT.as_posix(),
)
LEGACY_REQUIRED_VAULT_FILES = (
    "_meta/domain-map.yml",
    "_meta/mirror-config.yml",
)
REQUIRED_TOOL_FILES = (
    "sync_office_md.py",
    "sync_github_repos.py",
    "lint_vault.py",
    "overlap_report.py",
    "benchmark_tasks.py",
    "catalog_report.py",
    "conversion_report.py",
    "m365_report.py",
    "migration_report.py",
    "pilot_report.py",
    "recovery_report.py",
    "review_ledger.py",
    "sandbox_report.py",
)


def run_capture(cmd: list[str], cwd: Path, timeout: int = 5) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def count_manifest_states(path: Path, id_key: str) -> tuple[str, str | None]:
    if not path.exists():
        return f"{path.name}: not generated yet", None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"{path.name}: unreadable JSON", f"{path.name}: invalid JSON ({exc.__class__.__name__})"
    records = data.get("records", [])
    if not isinstance(records, list):
        return f"{path.name}: invalid records", f"{path.name}: records must be a list"
    valid = [record for record in records if isinstance(record, dict)]
    state_counts = Counter(str(record.get("lifecycle_state", "unknown")) for record in valid)
    missing_ids = sum(1 for record in valid if not str(record.get(id_key, "")).strip())
    state_summary = ", ".join(f"{state}={state_counts[state]}" for state in sorted(state_counts)) or "no states"
    message = f"{path.name}: {len(valid)} records ({state_summary})"
    warning = f"{path.name}: {missing_ids} records missing {id_key}" if missing_ids else None
    return message, warning


def git_preflight(root: Path) -> tuple[list[str], list[str]]:
    info: list[str] = []
    warnings: list[str] = []
    git = shutil.which("git")
    if not git:
        warnings.append("git not found; curated-note backup posture cannot be checked.")
        return info, warnings
    inside = run_capture([git, "rev-parse", "--is-inside-work-tree"], root)
    if not inside or inside.returncode != 0 or inside.stdout.strip() != "true":
        warnings.append("Vault root is not inside a git work tree; back up curated notes before production sync.")
        return info, warnings
    top_level = run_capture([git, "rev-parse", "--show-toplevel"], root)
    if top_level and top_level.returncode == 0:
        info.append(f"git: inside work tree ({top_level.stdout.strip()})")
    else:
        info.append("git: inside work tree")
    status = run_capture([git, "status", "--short"], root)
    if status and status.returncode == 0:
        if status.stdout.strip():
            warnings.append("git working tree has uncommitted changes; confirm backups before production sync.")
        else:
            info.append("git working tree: clean")
    return info, warnings


def active_gitignore_patterns(path: Path) -> list[str]:
    patterns: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(stripped)
    return patterns


def gitignore_rule_matches(pattern: str, rel_path: str) -> bool:
    pattern = pattern.strip()
    if not pattern:
        return False
    if pattern.endswith("/"):
        prefix = pattern.lstrip("/")
        return rel_path == prefix.rstrip("/") or rel_path.startswith(prefix)
    pattern = pattern.strip("/")
    if "/" not in pattern:
        parts = rel_path.split("/")
        return any(fnmatch.fnmatch(part, pattern) for part in parts)
    return fnmatch.fnmatch(rel_path, pattern) or rel_path.startswith(pattern.rstrip("/") + "/")


def gitignore_ignores(patterns: list[str], rel_path: str) -> bool:
    ignored = False
    for pattern in patterns:
        negated = pattern.startswith("!")
        body = pattern[1:] if negated else pattern
        if gitignore_rule_matches(body, rel_path):
            ignored = not negated
    return ignored


def negates_required_pattern(pattern: str, required: str, sample: str) -> bool:
    if not pattern.startswith("!"):
        return False
    body = pattern[1:].strip("/")
    required_body = required.strip("/")
    if gitignore_rule_matches(body, sample):
        return True
    if required.endswith("/") and (body == required_body or body.startswith(required)):
        return True
    return False


def backup_preflight(root: Path) -> tuple[list[str], list[str]]:
    info: list[str] = []
    warnings: list[str] = []
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        warnings.append("backup guard: .gitignore missing; local data/secret patterns are not protected.")
    else:
        active_patterns = active_gitignore_patterns(gitignore)
        missing = [
            pattern
            for pattern, sample in GITIGNORE_REQUIRED_PATTERNS.items()
            if not gitignore_ignores(active_patterns, sample)
        ]
        reopened = [
            pattern
            for pattern, sample in GITIGNORE_REQUIRED_PATTERNS.items()
            if any(negates_required_pattern(rule, pattern, sample) for rule in active_patterns)
        ]
        if missing or reopened:
            details = []
            if missing:
                details.append("missing effective ignores: " + ", ".join(missing))
            if reopened:
                details.append("negated high-risk paths: " + ", ".join(reopened))
            warnings.append("backup guard: .gitignore unsafe; " + "; ".join(details))
        else:
            info.append("backup guard: .gitignore covers high-risk local data patterns")

    git = shutil.which("git")
    if not git:
        return info, warnings
    inside = run_capture([git, "rev-parse", "--is-inside-work-tree"], root)
    if not inside or inside.returncode != 0 or inside.stdout.strip() != "true":
        return info, warnings
    top_level = run_capture([git, "rev-parse", "--show-toplevel"], root)
    if top_level and top_level.returncode == 0:
        git_root = Path(top_level.stdout.strip()).resolve()
        if git_root == root.resolve():
            info.append("backup boundary: vault root is git root")
        else:
            warnings.append("backup boundary: vault is inside a parent git work tree; confirm workspace boundary before pilots.")
    commits = run_capture([git, "rev-list", "--count", "HEAD"], root)
    if not commits or commits.returncode != 0:
        warnings.append("backup history: no git commits found; create a backup baseline before pilot sync.")
    else:
        info.append(f"backup history: {commits.stdout.strip()} commits")
    remotes = run_capture([git, "remote"], root)
    if remotes and remotes.returncode == 0 and remotes.stdout.strip():
        info.append(f"backup remotes: {len(remotes.stdout.split())} configured")
    else:
        warnings.append("backup remotes: none configured; confirm another backup exists before pilot work.")
    return info, warnings


def profile_view_preflight(root: Path) -> tuple[list[str], list[str]]:
    info: list[str] = []
    warnings: list[str] = []
    profile_path = root / PROFILE_REL
    if not profile_path.exists():
        bases = root / "Documents.base"
        if bases.exists():
            info.append("legacy Obsidian Bases index: Documents.base present")
        else:
            warnings.append("legacy Obsidian Bases index: Documents.base missing; CLI correctness is unaffected.")
        return info, warnings

    try:
        profile = load_profile(profile_path)
    except ProfileValidationError as exc:
        warnings.append(f"profile views: unavailable until {PROFILE_REL.as_posix()} is valid ({exc})")
        return info, warnings

    plan = profile_views_plan(root, profile)
    for view in plan["views"]:
        path = str(view.get("path", ""))
        state = str(view.get("state", "unknown"))
        if state == "current":
            info.append(f"profile view: {path} current")
        elif state in {"missing", "stale"}:
            warnings.append(f"profile view: {path} {state}; run `vaultwright profile views --write`.")
        else:
            warnings.append(f"profile view: {path} {state}")
    for blocker in plan["blockers"]:
        path = str(blocker.get("path", ""))
        detail = str(blocker.get("detail", blocker.get("code", "profile view blocker")))
        warnings.append(f"profile view: {path} blocked ({detail})")
    if not plan["views"] and not plan["blockers"]:
        info.append("profile views: none declared")
    return info, warnings


def obsidian_preflight(root: Path) -> tuple[list[str], list[str]]:
    info: list[str] = []
    warnings: list[str] = []
    view_info, view_warnings = profile_view_preflight(root)
    info.extend(view_info)
    warnings.extend(view_warnings)

    obsidian = root / ".obsidian"
    if not obsidian.exists():
        info.append("Obsidian: .obsidian not present (optional UI; CLI correctness unaffected)")
        return info, warnings
    if not obsidian.is_dir():
        warnings.append("Obsidian: .obsidian exists but is not a directory")
        return info, warnings
    info.append("Obsidian: .obsidian present")

    for filename in ("app.json", "core-plugins.json", "community-plugins.json"):
        path = obsidian / filename
        if not path.exists():
            info.append(f"Obsidian {filename}: not present")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            warnings.append(f"Obsidian {filename}: unreadable text")
            continue
        except OSError as exc:
            warnings.append(f"Obsidian {filename}: unreadable ({exc.__class__.__name__})")
            continue
        except json.JSONDecodeError as exc:
            warnings.append(f"Obsidian {filename}: invalid JSON ({exc.__class__.__name__})")
            continue
        if filename == "community-plugins.json":
            if not isinstance(data, list):
                warnings.append("Obsidian community-plugins.json: expected a list")
            elif data:
                warnings.append(
                    f"Obsidian community plugins: {len(data)} enabled; review plugin trust boundary before pilots."
                )
            else:
                info.append("Obsidian community plugins: none enabled")
        elif filename == "core-plugins.json":
            if isinstance(data, dict):
                enabled = sum(1 for value in data.values() if value)
                info.append(f"Obsidian core plugins: {enabled} enabled")
            elif isinstance(data, list):
                info.append(f"Obsidian core plugins: {len(data)} listed")
            else:
                warnings.append("Obsidian core-plugins.json: expected a list or mapping")
        else:
            info.append("Obsidian app.json: readable")

    plugins_dir = obsidian / "plugins"
    if plugins_dir.exists() and plugins_dir.is_dir():
        plugin_dirs = [path for path in plugins_dir.iterdir() if path.is_dir()]
        if plugin_dirs:
            warnings.append(
                f"Obsidian installed plugin directories: {len(plugin_dirs)} found; review local plugin code before pilots."
            )
    return info, warnings


def github_auth_preflight(root: Path) -> tuple[list[str], list[str]]:
    info: list[str] = []
    warnings: list[str] = []
    if os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
        info.append("GitHub auth: environment token detected")
        return info, warnings
    gh = shutil.which("gh")
    if not gh:
        warnings.append("GitHub auth: no GH_TOKEN/GITHUB_TOKEN or gh CLI found; private repo sync will not authenticate.")
        return info, warnings
    auth = run_capture([gh, "auth", "status", "-h", "github.com"], root)
    if auth and auth.returncode == 0:
        info.append("GitHub auth: gh is authenticated for github.com")
    else:
        warnings.append("GitHub auth: not confirmed; private repo sync needs gh auth or an env token.")
    return info, warnings


def lifecycle_contract_preflight(root: Path) -> tuple[list[str], list[str]]:
    info: list[str] = []
    warnings: list[str] = []
    path = root / LIFECYCLE_CONTRACT
    if not path.exists():
        warnings.append(f"lifecycle contract: missing {LIFECYCLE_CONTRACT.as_posix()}")
        return info, warnings
    try:
        import yaml  # type: ignore
    except ImportError:
        warnings.append("lifecycle contract: PyYAML unavailable; contract not checked")
        return info, warnings
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        warnings.append(f"lifecycle contract: unreadable ({exc.__class__.__name__})")
        return info, warnings
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        warnings.append("lifecycle contract: schema_version must be 1")
        return info, warnings

    counts: dict[str, int] = {}
    for section in ("office", "repo"):
        states = data.get(section)
        if not isinstance(states, dict) or not states:
            warnings.append(f"lifecycle contract: missing {section} states")
            continue
        counts[section] = len(states)
        for state, spec in states.items():
            label = f"lifecycle contract: {section}.{state}"
            if not isinstance(spec, dict):
                warnings.append(f"{label} must be a mapping")
                continue
            missing = sorted(field for field in LIFECYCLE_REQUIRED_FIELDS if not spec.get(field))
            if missing:
                warnings.append(f"{label} missing field(s): {', '.join(missing)}")
            actions = spec.get("permitted_next_actions")
            if (
                not isinstance(actions, list)
                or not actions
                or not all(isinstance(item, str) and item.strip() for item in actions)
            ):
                warnings.append(f"{label} permitted_next_actions must be a non-empty string list")
    if counts and not any(warning.startswith("lifecycle contract:") for warning in warnings):
        info.append(
            "lifecycle contract: "
            + ", ".join(f"{section}={counts[section]} states" for section in sorted(counts))
        )
    return info, warnings


def recovery_preflight(root: Path) -> tuple[list[str], list[str]]:
    info: list[str] = []
    warnings: list[str] = []
    script = root / "tools" / "recovery_report.py"
    if not script.exists():
        return info, warnings
    try:
        items, report_warnings, report_errors = recovery_module.build_report(root)
        summary = recovery_module.summary_counts(items)
    except Exception as exc:
        detail = f"{exc.__class__.__name__}: {str(exc)[:120]}"
        warnings.append(f"recovery: unavailable ({detail})")
        return info, warnings
    warnings.extend(f"recovery: {warning}" for warning in report_warnings)
    warnings.extend(f"recovery: {error}" for error in report_errors)
    total = int(summary.get("total", 0))
    if total:
        item_word = "item" if total == 1 else "items"
        verb = "needs" if total == 1 else "need"
        warnings.append(
            "recovery: "
            f"{total} {item_word} {verb} operator action "
            f"(office={summary.get('office', 0)}, repo={summary.get('repo', 0)}, temp={summary.get('temp', 0)}); "
            "run `vaultwright recovery`."
        )
    else:
        info.append("recovery: no action items")
    return info, warnings


def review_preflight(root: Path) -> tuple[list[str], list[str]]:
    info: list[str] = []
    warnings: list[str] = []
    script = root / "tools" / "review_ledger.py"
    if not script.exists():
        return info, warnings
    try:
        report, report_warnings = review_ledger_module.build_report(root)
    except Exception as exc:
        detail = f"{exc.__class__.__name__}: {str(exc)[:120]}"
        warnings.append(f"review ledger: unavailable ({detail})")
        return info, warnings

    warnings.extend(f"review ledger: {warning}" for warning in report_warnings)
    reviewed = int(report.get("reviewed_artifacts", 0) or 0)
    if not reviewed:
        info.append("review ledger: no reviewed artifacts yet")
        return info, warnings

    statuses = report.get("statuses", {}) if isinstance(report.get("statuses"), dict) else {}
    states = report.get("current_states", {}) if isinstance(report.get("current_states"), dict) else {}
    status_summary = ", ".join(f"{key}={statuses[key]}" for key in sorted(statuses)) or "no statuses"
    state_summary = ", ".join(f"{key}={states[key]}" for key in sorted(states)) or "no states"
    info.append(f"review ledger: {reviewed} reviewed artifact(s) ({status_summary}; {state_summary})")

    stale_or_missing = sum(
        int(count)
        for state, count in states.items()
        if str(state) != "current" and isinstance(count, int)
    )
    non_approved = sum(
        int(count)
        for status, count in statuses.items()
        if str(status) != "approved" and isinstance(count, int)
    )
    if stale_or_missing:
        warnings.append(
            f"review ledger: {stale_or_missing} reviewed artifact(s) are stale, missing, or unreadable; "
            "run `vaultwright review`."
        )
    if non_approved:
        warnings.append(
            f"review ledger: {non_approved} reviewed artifact(s) are not approved; run `vaultwright review`."
        )
    return info, warnings


def profile_contract_preflight(root: Path) -> tuple[list[str], list[str], list[str]]:
    info: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    profile_path = root / PROFILE_REL
    if not profile_path.exists():
        warnings.append(
            f"profile contract: {PROFILE_REL.as_posix()} missing; using legacy domain-map/mirror-config checks."
        )
        for rel in LEGACY_REQUIRED_VAULT_FILES:
            if not (root / rel).exists():
                errors.append(f"Missing required vault file: {rel}")
        return info, warnings, errors

    try:
        profile = load_profile(profile_path)
    except ProfileValidationError as exc:
        errors.append(f"profile contract: invalid {PROFILE_REL.as_posix()} ({exc})")
        return info, warnings, errors

    info.append(f"profile contract: {profile.id} {profile.profile_version}")
    domain_map = root / "_meta" / "domain-map.yml"
    if domain_map.exists():
        info.append("legacy domain map: present")
    else:
        warnings.append("legacy domain map: missing; legacy aliases unavailable.")
    mirror_config = root / "_meta" / "mirror-config.yml"
    if mirror_config.exists():
        info.append("Office mirror config: present")
    else:
        info.append("Office mirror config: absent; using profile policy defaults")
    return info, warnings, errors


def main(root: Path | None = None) -> int:
    root = (root or Path.cwd()).expanduser().resolve()
    info: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []

    print(f"vaultwright doctor: {root}")
    if sys.version_info < (3, 11):
        errors.append("Python 3.11+ is required.")
    else:
        info.append(f"Python: {sys.version.split()[0]}")
    for rel in COMMON_REQUIRED_VAULT_FILES:
        if not (root / rel).exists():
            errors.append(f"Missing required vault file: {rel}")
    profile_info, profile_warnings, profile_errors = profile_contract_preflight(root)
    info.extend(profile_info)
    warnings.extend(profile_warnings)
    errors.extend(profile_errors)
    mirror_root = configured_office_mirror_root(root)
    mirror_root_text = mirror_root.as_posix()
    if (root / mirror_root).exists():
        info.append(f"Office mirror root: {mirror_root_text}")
    else:
        info.append(f"Office mirror root: {mirror_root_text} (will be created on first sync)")
    for script in REQUIRED_TOOL_FILES:
        if not (root / "tools" / script).exists():
            errors.append(f"Missing tool: tools/{script}")
    for module in ("yaml", "markitdown"):
        if importlib.util.find_spec(module) is None:
            errors.append(f"Missing Python dependency: {module}")
        else:
            info.append(f"Python dependency: {module}")
    source_summary, source_warning = count_manifest_states(root / "_meta" / "source-manifest.json", "source_id")
    repo_summary, repo_warning = count_manifest_states(root / "_meta" / "repo-manifest.json", "repo_id")
    info.extend([source_summary, repo_summary])
    if source_warning:
        warnings.append(source_warning)
    if repo_warning:
        warnings.append(repo_warning)
    audit = root / "_meta" / "sync-audit.jsonl"
    if audit.exists():
        try:
            events = sum(1 for line in audit.read_text(encoding="utf-8").splitlines() if line.strip())
            info.append(f"sync-audit.jsonl: {events} events")
        except UnicodeDecodeError:
            warnings.append("sync-audit.jsonl: unreadable text")
    else:
        info.append("sync-audit.jsonl: not generated yet")
    if not (root / "tools" / "repos.yml").exists():
        warnings.append("No tools/repos.yml found; repo sync will skip until configured.")
    recovery_info, recovery_warnings = recovery_preflight(root)
    review_info, review_warnings = review_preflight(root)
    obsidian_info, obsidian_warnings = obsidian_preflight(root)
    backup_info, backup_warnings = backup_preflight(root)
    git_info, git_warnings = git_preflight(root)
    gh_info, gh_warnings = github_auth_preflight(root)
    lifecycle_info, lifecycle_warnings = lifecycle_contract_preflight(root)
    info.extend(lifecycle_info)
    warnings.extend(lifecycle_warnings)
    info.extend(recovery_info)
    warnings.extend(recovery_warnings)
    info.extend(review_info)
    warnings.extend(review_warnings)
    info.extend(obsidian_info)
    warnings.extend(obsidian_warnings)
    info.extend(backup_info)
    warnings.extend(backup_warnings)
    info.extend(git_info)
    warnings.extend(git_warnings)
    info.extend(gh_info)
    warnings.extend(gh_warnings)

    for item in info:
        print(f"  info: {item}")
    for warning in warnings:
        print(f"  warning: {warning}")
    for error in errors:
        print(f"  error: {error}", file=sys.stderr)
    if errors:
        return 1
    print("vaultwright doctor: OK")
    return 0
