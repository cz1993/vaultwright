# SPDX-License-Identifier: AGPL-3.0-or-later
"""Installable Vaultwright console entry point.

The packaged command owns profile commands and migrated runtime behavior directly. Vault-local
operator scripts remain compatibility shims for users who run commands from inside a copied vault.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from vaultwright import benchmark as benchmark_module
from vaultwright import catalog as catalog_module
from vaultwright import conversion as conversion_module
from vaultwright import doctor as doctor_module
from vaultwright import lint as lint_module
from vaultwright import m365 as m365_module
from vaultwright import migration as migration_module
from vaultwright import overlap as overlap_module
from vaultwright import pilot as pilot_module
from vaultwright import recovery as recovery_module
from vaultwright import review_ledger as review_ledger_module
from vaultwright import sandbox as sandbox_module
from vaultwright.annotation_migration import (
    annotation_migration_plan,
    public_plan,
    write_annotation_sidecars,
)
from vaultwright.changes import journal as journal_module
from vaultwright.changes import reconcile as reconcile_module
from vaultwright.changes import replay as replay_module
from vaultwright.mirrors import github_repos as repo_sync_module
from vaultwright.mirrors import office as office_sync_module
from vaultwright.profile_migration import profile_migration_plan, write_profile_migration
from vaultwright.profiles import ProfileContract, ProfileValidationError, load_profile
from vaultwright.views import profile_views_plan, write_profile_views

BUILTIN_PROFILE_DIR = Path(__file__).resolve().parent / "builtin_profiles"
SCAFFOLDED_PROFILE_IDS = {"business-operations"}


def template_source() -> Path | None:
    env_root = os.environ.get("VAULTWRIGHT_REPO")
    candidates = []
    if env_root:
        candidates.append(Path(env_root))
    here = Path(__file__).resolve()
    candidates.extend(here.parents)
    for candidate in candidates:
        template = candidate / "template"
        if (template / "CLAUDE.md").exists():
            return template
    return None


def built_in_profile_paths() -> list[Path]:
    paths: list[Path] = []
    template = template_source()
    if template:
        paths.append(template / "_meta" / "profile.yml")
    if BUILTIN_PROFILE_DIR.exists():
        paths.extend(sorted(BUILTIN_PROFILE_DIR.glob("*.yml")))
    return paths


def built_in_profiles() -> dict[str, tuple[ProfileContract, Path]]:
    profiles: dict[str, tuple[ProfileContract, Path]] = {}
    for path in built_in_profile_paths():
        if not path.exists():
            continue
        profile = load_profile(path)
        if profile.id in profiles:
            previous_path = profiles[profile.id][1]
            raise ProfileValidationError(
                f"duplicate built-in profile id {profile.id}: {previous_path} and {path}"
            )
        profiles[profile.id] = (profile, path)
    return dict(sorted(profiles.items()))


def ensure_empty_or_missing(target: Path) -> None:
    if target.exists() and any(target.iterdir()):
        raise ValueError(f"refusing: '{target}' exists and is not empty")


def built_in_profile() -> tuple[ProfileContract, Path] | None:
    profiles = built_in_profiles()
    return profiles.get("business-operations")


def print_profile_summary(profile: ProfileContract) -> None:
    summary = profile.summary()
    print(f"id: {summary['id']}")
    print(f"name: {summary['name']}")
    print(f"profile_version: {summary['profile_version']}")
    print(f"schema_version: {summary['schema_version']}")
    print(f"domains: {summary['domains']}")
    print(f"note_types: {summary['note_types']}")
    print(f"statuses: {summary['statuses']}")
    print(f"templates: {summary['templates']}")
    print(f"views: {summary['views']}")


def command_profile_list(args: argparse.Namespace) -> int:
    try:
        profiles = built_in_profiles()
    except ProfileValidationError as exc:
        print(f"profile list: invalid built-in profile: {exc}", file=sys.stderr)
        return 1
    if not profiles:
        print("profile list: no built-in profiles found", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps([profile.summary() for profile, _path in profiles.values()], indent=2, sort_keys=True))
    else:
        print("id\tversion\tname")
        for profile, _path in profiles.values():
            print(f"{profile.id}\t{profile.profile_version}\t{profile.name}")
    return 0


def load_current_profile(root: Path) -> tuple[ProfileContract, Path]:
    path = root / "_meta" / "profile.yml"
    if not path.exists():
        raise ProfileValidationError(f"missing profile: {path}")
    return load_profile(path), path


def load_optional_current_profile(root: Path) -> tuple[ProfileContract | None, Path]:
    path = root / "_meta" / "profile.yml"
    if not path.exists():
        return None, path
    return load_profile(path), path


def command_profile_show(args: argparse.Namespace) -> int:
    try:
        if args.profile_id:
            profiles = built_in_profiles()
            if not profiles:
                print("profile show: no built-in profiles found", file=sys.stderr)
                return 1
            loaded = profiles.get(args.profile_id)
            if not loaded:
                print(f"profile show: unknown built-in profile: {args.profile_id}", file=sys.stderr)
                return 1
            profile, path = loaded
        else:
            profile, path = load_current_profile(args.root.expanduser().resolve())
    except ProfileValidationError as exc:
        print(f"profile show: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(profile.as_dict(), indent=2, sort_keys=True))
    else:
        print_profile_summary(profile)
        print(f"path: {path}")
    return 0


def command_profile_validate(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    path = args.path.expanduser().resolve() if args.path else root / "_meta" / "profile.yml"
    try:
        profile = load_profile(path)
    except ProfileValidationError as exc:
        print(f"profile validate: {exc}", file=sys.stderr)
        return 1
    if args.json:
        payload = {"ok": True, "path": str(path), "profile": profile.summary()}
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"profile validate: OK {profile.id} {profile.profile_version} (schema {profile.schema_version})")
    return 0


def command_profile_views(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    try:
        profile, _path = load_current_profile(root)
    except ProfileValidationError as exc:
        print(f"profile views: {exc}", file=sys.stderr)
        return 1
    plan = profile_views_plan(root, profile)
    write_result = None
    if args.write:
        write_result = write_profile_views(root, profile)
        plan = profile_views_plan(root, profile)
    if args.json:
        payload = {"plan": plan, "write": write_result} if write_result is not None else plan
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        mode = "--write" if args.write else "--check"
        print(f"profile views {mode}: {profile.id} {profile.profile_version}")
        print(
            "Summary: "
            f"{plan['summary']['views']} view(s), "
            f"{plan['summary']['actions']} action(s), "
            f"{plan['summary']['blockers']} blocker(s)"
        )
        if plan["blockers"]:
            print("Blockers:")
            for blocker in plan["blockers"]:
                print(f"- {blocker['code']}: {blocker['path']}: {blocker['detail']}")
        elif args.write and write_result is not None:
            print(
                "Write summary: "
                f"{write_result['summary']['written']} written, "
                f"{write_result['summary']['skipped']} skipped, "
                f"{write_result['summary']['errors']} error(s)"
            )
            for item in write_result["written"]:
                print(f"- wrote {item['path']}: {item['detail']}")
            for item in write_result["skipped"]:
                print(f"- skipped {item['path']}: {item['detail']}")
            for item in write_result["errors"]:
                print(f"- error {item['path']}: {item['detail']}")
        elif not plan["actions"]:
            print("Profile-generated views are current.")
        else:
            print("Required view updates:")
            for action in plan["actions"]:
                print(f"- {action['action']}: {action['path']} ({action['reason']})")
    if plan["blockers"]:
        return 1
    if write_result and write_result["errors"]:
        return 1
    if args.check and plan["actions"]:
        return 1
    return 0


def load_target_profile(profile_id: str | None = None) -> tuple[ProfileContract, Path, Path]:
    template = template_source()
    if not template:
        raise ProfileValidationError("no built-in profiles found")
    profiles = built_in_profiles()
    if not profiles:
        raise ProfileValidationError("no built-in profiles found")
    target_id = profile_id or "business-operations"
    loaded = profiles.get(target_id)
    if not loaded:
        raise ProfileValidationError(f"unknown built-in profile: {target_id}")
    profile, path = loaded
    if profile.id not in SCAFFOLDED_PROFILE_IDS:
        available = ", ".join(sorted(SCAFFOLDED_PROFILE_IDS))
        raise ProfileValidationError(
            f"profile '{profile.id}' has a packaged contract but no scaffold template yet; "
            f"scaffolded profiles: {available}"
        )
    return profile, path, template


def command_profile_diff(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    try:
        current, _current_path = load_current_profile(root)
        target, target_path, template = load_target_profile(current.id)
    except ProfileValidationError as exc:
        print(f"profile diff: {exc}", file=sys.stderr)
        return 1
    if args.target_profile_version != target.profile_version:
        print(
            f"profile diff: target profile version '{args.target_profile_version}' is not available; "
            f"available: {target.profile_version}",
            file=sys.stderr,
        )
        return 1
    plan = profile_migration_plan(root, template, current, target, target_path)
    if args.json:
        print(json.dumps(plan, indent=2, sort_keys=True))
    else:
        print(f"profile diff: {current.id} {current.profile_version} -> {target.profile_version}")
        if not plan["differences"]:
            print("No profile contract differences detected.")
        else:
            for difference in plan["differences"]:
                print(f"- {difference['field']}: {difference['kind']}")
    return 1 if plan["blockers"] else 0


def command_profile_migrate(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    try:
        current, _current_path = load_optional_current_profile(root)
        target_profile_id = args.profile or (current.id if current else None)
        target, target_path, template = load_target_profile(target_profile_id)
    except ProfileValidationError as exc:
        print(f"profile migrate: {exc}", file=sys.stderr)
        return 1
    plan = profile_migration_plan(root, template, current, target, target_path)
    write_result = None
    if args.write:
        write_result = write_profile_migration(root, template, plan)
    if args.json:
        payload = {"plan": plan, "write": write_result} if write_result is not None else plan
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        current_version = current.profile_version if current else "none"
        mode = "--write" if args.write else "--plan"
        print(f"profile migrate {mode}: {target.id} {current_version} -> {target.profile_version}")
        print(f"Summary: {plan['summary']['actions']} action(s), {plan['summary']['blockers']} blocker(s)")
        if plan["blockers"]:
            print("Blockers:")
            for blocker in plan["blockers"]:
                print(f"- {blocker['code']}: {blocker['detail']}")
        elif args.write and write_result is not None:
            print(
                "Write summary: "
                f"{write_result['summary']['written']} written, "
                f"{write_result['summary']['skipped']} skipped, "
                f"{write_result['summary']['errors']} error(s)"
            )
            for item in write_result["written"]:
                print(f"- wrote {item['path']}: {item['detail']}")
            for item in write_result["skipped"]:
                print(f"- skipped {item['path']}: {item['detail']}")
            for item in write_result["errors"]:
                print(f"- error {item['path']}: {item['detail']}")
        elif not plan["actions"]:
            print("No profile migration actions needed.")
        else:
            print("Planned actions:")
            for action in plan["actions"]:
                print(f"- {action['action']}: {action['path']}")
    if plan["blockers"]:
        return 1
    if write_result and write_result["errors"]:
        return 1
    return 0


def command_init(args: argparse.Namespace) -> int:
    try:
        profile, _profile_path, template = load_target_profile(args.profile)
    except ProfileValidationError as exc:
        print(f"vaultwright init: {exc}", file=sys.stderr)
        return 1
    target = args.target.expanduser().resolve()
    try:
        ensure_empty_or_missing(target)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template, target, dirs_exist_ok=True)
    print(f"Vaultwright vault created at: {target}")
    print(f"Profile: {profile.id} {profile.profile_version}")
    print("Next: python3.11 tools/vaultwright.py doctor && python3.11 tools/vaultwright.py plan")
    return 0


def catalog_args(args: argparse.Namespace) -> list[str]:
    return (
        (["--json"] if args.json else [])
        + (["--html"] if args.html else [])
        + (["--stdout"] if args.stdout else [])
        + (["--check"] if args.check else [])
        + (["--output", str(args.output)] if args.output != Path("CATALOG.md") else [])
        + (["--max-items", str(args.max_items)] if args.max_items != 500 else [])
    )


def command_catalog(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    return catalog_module.main(catalog_args(args), root=root)


def conversion_args(args: argparse.Namespace) -> list[str]:
    return (
        (["--results", str(args.results)] if args.results else [])
        + (["--init-results"] if args.init_results else [])
        + (["--force"] if args.force else [])
        + (["--require-reviewed"] if args.require_reviewed else [])
        + (["--json"] if args.json else [])
        + (["--guide"] if args.guide else [])
        + (
            ["--low-risk-per-format", str(args.low_risk_per_format)]
            if args.low_risk_per_format != 1
            else []
        )
    )


def command_conversion(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    return conversion_module.main(conversion_args(args), root=root)


def command_lint(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    return lint_module.main(root=root)


def review_args(args: argparse.Namespace) -> list[str]:
    return (
        (["--artifact", str(args.artifact)] if args.artifact else [])
        + (["--status", args.status] if args.status else [])
        + (["--reviewer", args.reviewer] if args.reviewer else [])
        + (["--note", args.note] if args.note else [])
        + (["--kind", args.kind] if args.kind else [])
        + (["--json"] if args.json else [])
        + (["--check"] if args.check else [])
    )


def command_review(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    return review_ledger_module.main(review_args(args), root=root)


def recovery_args(args: argparse.Namespace) -> list[str]:
    return (
        (["--json"] if args.json else [])
        + (["--worksheet"] if args.worksheet else [])
        + (["--runbook"] if args.runbook else [])
    )


def command_recovery(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    return recovery_module.main(recovery_args(args), root=root)


def command_m365(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    return m365_module.main(["--json"] if args.json else [], root=root)


def migration_args(args: argparse.Namespace) -> list[str]:
    return (
        (["--json"] if args.json else [])
        + (["--worksheet"] if args.worksheet else [])
        + (["--runbook"] if args.runbook else [])
        + (["--normalize-frontmatter-domains"] if args.normalize_frontmatter_domains else [])
        + (["--write"] if args.write else [])
    )


def command_migration(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    return migration_module.main(migration_args(args), root=root)


def overlap_args(args: argparse.Namespace) -> list[str]:
    return (
        (["--json"] if args.json else [])
        + (["--worksheet"] if args.worksheet else [])
        + (["--max-pairs", str(args.max_pairs)] if args.max_pairs != 40 else [])
    )


def command_overlap(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    return overlap_module.main(overlap_args(args), root=root)


def benchmark_args(args: argparse.Namespace) -> list[str]:
    return (
        (["--tasks", str(args.tasks)] if args.tasks else [])
        + (["--results", str(args.results)] if args.results else [])
        + (["--init-tasks"] if args.init_tasks else [])
        + (["--init-results"] if args.init_results else [])
        + (["--force"] if args.force else [])
        + (["--scaffold-sources", str(args.scaffold_sources)] if args.scaffold_sources != 5 else [])
        + (["--scaffold-curated", str(args.scaffold_curated)] if args.scaffold_curated != 5 else [])
        + (["--worksheet"] if args.worksheet else [])
        + (["--require-generated"] if args.require_generated else [])
        + (["--require-results"] if args.require_results else [])
        + (["--require-citations"] if args.require_citations else [])
        + (["--require-prompt-safety"] if args.require_prompt_safety else [])
        + (["--json"] if args.json else [])
    )


def command_benchmark(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    return benchmark_module.main(benchmark_args(args), root=root)


def pilot_args(args: argparse.Namespace) -> list[str]:
    return (
        (["--json"] if args.json else [])
        + (["--worksheet"] if args.worksheet else [])
    )


def command_pilot(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    return pilot_module.main(pilot_args(args), root=root)


def sandbox_args(args: argparse.Namespace) -> list[str]:
    return (
        (["--source-root", str(args.source_root)] if args.source_root else [])
        + (["--json"] if args.json else [])
    )


def command_sandbox(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    return sandbox_module.main(sandbox_args(args), root=root)


def command_doctor(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    return doctor_module.main(root=root)


def repo_config(root: Path) -> Path:
    return root / "tools" / "repos.yml"


def command_plan(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    status = office_sync_module.main(["--plan"], default_root=root)
    config = repo_config(root)
    if config.exists():
        status = max(status, repo_sync_module.main(["--plan"], default_root=root, default_config=config))
    else:
        print("vaultwright plan: no tools/repos.yml found; repo plan skipped")
    return status


def command_sync(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    office = office_sync_module.main([], default_root=root)
    repos = repo_sync_module.main([], default_root=root, default_config=repo_config(root))
    return office or repos


def command_status(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    status = office_sync_module.main(["--status"], default_root=root)
    config = repo_config(root)
    if config.exists():
        status = max(status, repo_sync_module.main(["--status"], default_root=root, default_config=config))
    else:
        print("vaultwright status: no tools/repos.yml found; repo status skipped")
    return status


def command_journal_status(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    try:
        payload = journal_module.journal_status(root, initialize_state=args.init)
    except journal_module.JournalError as exc:
        print(f"journal status: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(f"vaultwright journal status: {payload['state_path']}")
    print(f"state: {'initialized' if payload['initialized'] else 'not initialized'}")
    print(f"last event sequence: {payload['last_event_sequence']}")
    print(f"last observed sequence: {payload['last_observed_sequence']}")
    print(f"last applied sequence: {payload['last_applied_sequence']}")
    print(
        "counts: "
        f"queued={payload['queued_count']} "
        f"processing={payload['processing_count']} "
        f"failed={payload['failed_count']} "
        f"review-required={payload['review_required_count']}"
    )
    print(f"last reconciliation: {payload['last_reconciliation'] or 'never'}")
    worker = payload["worker"]
    if worker["locked"]:
        print(f"worker: locked by {worker['holder']} until {worker['expires_at']}")
    elif worker.get("stale"):
        print(f"worker: stale lease from {worker['holder']} expired at {worker['expires_at']}")
    else:
        print("worker: unlocked")
    return 0


def command_journal_replay(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    holder = args.holder or f"cli-{os.getpid()}"
    try:
        payload = replay_module.replay_journal(
            root,
            holder,
            retry_failed=args.retry_failed,
            max_events=args.max_events,
            lease_ttl_seconds=args.lease_ttl_seconds,
        )
    except (journal_module.JournalError, replay_module.ReplayError) as exc:
        print(f"journal replay: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"vaultwright journal replay: processed {payload['processed']} event(s)")
        print(f"recovered processing: {len(payload['recovered_processing'])}")
        print(f"retried failed: {len(payload['retried_failed'])}")
        counts = payload["finish_counts"]
        print(
            "finish counts: "
            f"applied={counts['applied']} "
            f"review-required={counts['review-required']} "
            f"failed={counts['failed']}"
        )
        lease = payload["lease"]
        if payload["acquired"]:
            print(f"worker: acquired by {holder} until {lease['expires_at']}")
        else:
            print(f"worker: locked by {lease['holder']} until {lease['expires_at']}")
    if not payload["acquired"]:
        return 1
    return 1 if payload["finish_counts"]["failed"] else 0


def command_reconcile(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    try:
        payload = reconcile_module.reconcile_workspace(root)
    except (journal_module.JournalError, reconcile_module.ReconciliationError) as exc:
        print(f"reconcile: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(f"vaultwright reconcile: queued {payload['events_queued']} event(s)")
    print(f"scanned sources: {payload['scanned_sources']}")
    print(f"manifest records: {payload['manifest_records']}")
    print(
        "event counts: "
        f"created={payload['event_counts']['created']} "
        f"modified={payload['event_counts']['modified']} "
        f"moved={payload['event_counts']['moved']} "
        f"deleted={payload['event_counts']['deleted']} "
        f"reconcile-required={payload['event_counts']['reconcile-required']}"
    )
    print(f"existing unresolved events skipped: {payload['events_skipped']}")
    print(f"candidate full hashes: {payload['full_hashes']} ({payload['bytes_hashed']} bytes)")
    print(f"last reconciliation: {payload['reconciled_at']}")
    return 0


def command_migrate_annotations(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    plan = annotation_migration_plan(root)
    if args.write:
        result = write_annotation_sidecars(root, plan)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            summary = result["summary"]
            print(
                "migrate annotations --write: "
                f"{summary['written']} written, {summary['blockers']} blocker(s)"
            )
            if result["blockers"]:
                print("Blockers:")
                for blocker in result["blockers"]:
                    print(f"- {blocker['code']}: {blocker['detail']}")
            elif not result["written"]:
                print("No mirror annotations need migration.")
            else:
                for item in result["written"]:
                    print(f"- {item['mirror_path']} -> {item['sidecar_path']}")
        return 1 if result["blockers"] else 0

    payload = public_plan(plan)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        summary = payload["summary"]
        print(
            "migrate annotations --plan: "
            f"{summary['actions']} action(s), {summary['blockers']} blocker(s), "
            f"{summary['already_migrated']} already migrated"
        )
        if payload["blockers"]:
            print("Blockers:")
            for blocker in payload["blockers"]:
                print(f"- {blocker['code']}: {blocker['detail']}")
        elif not payload["actions"]:
            print("No mirror annotations need migration.")
        else:
            print("Planned actions:")
            for action in payload["actions"]:
                print(f"- {action['mirror_path']} -> {action['sidecar_path']}")
    return 1 if payload["blockers"] else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vaultwright command-line interface.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Vault root for plan/sync/status/lint/doctor.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Scaffold a new Vaultwright vault from the template.")
    init.add_argument(
        "--profile",
        default="business-operations",
        help="Profile to initialize. Currently scaffolded: business-operations.",
    )
    init.add_argument("target", type=Path)
    init.set_defaults(func=command_init)
    profile = sub.add_parser("profile", help="Inspect and validate Vaultwright profile contracts.")
    profile_sub = profile.add_subparsers(dest="profile_command", required=True)
    profile_list = profile_sub.add_parser("list", help="List built-in profiles.")
    profile_list.add_argument("--json", action="store_true", help="Print machine-readable profile summaries.")
    profile_list.set_defaults(func=command_profile_list)
    profile_show = profile_sub.add_parser("show", help="Show a built-in or current-vault profile.")
    profile_show.add_argument(
        "profile_id",
        nargs="?",
        help="Built-in profile ID. Omit to show --root/_meta/profile.yml.",
    )
    profile_show.add_argument("--json", action="store_true", help="Print machine-readable profile details.")
    profile_show.set_defaults(func=command_profile_show)
    profile_validate = profile_sub.add_parser("validate", help="Validate a profile contract.")
    profile_validate.add_argument("--path", type=Path, help="Profile YAML path. Defaults to --root/_meta/profile.yml.")
    profile_validate.add_argument("--json", action="store_true", help="Print machine-readable validation result.")
    profile_validate.set_defaults(func=command_profile_validate)
    profile_views = profile_sub.add_parser("views", help="Check or regenerate profile-owned view files.")
    profile_views_mode = profile_views.add_mutually_exclusive_group(required=True)
    profile_views_mode.add_argument("--check", action="store_true", help="Fail if generated profile views are stale.")
    profile_views_mode.add_argument("--write", action="store_true", help="Regenerate profile-owned view files.")
    profile_views.add_argument("--json", action="store_true", help="Print machine-readable view generation output.")
    profile_views.set_defaults(func=command_profile_views)
    profile_diff = profile_sub.add_parser("diff", help="Compare current vault profile with a built-in target version.")
    profile_diff.add_argument("target_profile_version", help="Target built-in profile version, for example 0.1.0.")
    profile_diff.add_argument("--json", action="store_true", help="Print machine-readable diff and migration plan.")
    profile_diff.set_defaults(func=command_profile_diff)
    profile_migrate = profile_sub.add_parser("migrate", help="Plan or apply safe profile migration work.")
    profile_migrate_mode = profile_migrate.add_mutually_exclusive_group(required=True)
    profile_migrate_mode.add_argument("--plan", action="store_true", help="Print a read-only migration plan.")
    profile_migrate_mode.add_argument(
        "--write",
        action="store_true",
        help="Create missing shared/folder-plan directories and copy missing packaged profile files without overwriting.",
    )
    profile_migrate.add_argument(
        "--profile",
        help="Built-in target profile ID. Defaults to the current vault profile or the packaged default.",
    )
    profile_migrate.add_argument("--json", action="store_true", help="Print machine-readable migration plan.")
    profile_migrate.set_defaults(func=command_profile_migrate)
    migrate = sub.add_parser("migrate", help="Run package-owned Vaultwright migrations.")
    migrate_sub = migrate.add_subparsers(dest="migrate_command", required=True)
    annotations = migrate_sub.add_parser(
        "annotations",
        help="Move human mirror annotations into source-ID-keyed sidecars.",
    )
    annotations_mode = annotations.add_mutually_exclusive_group(required=True)
    annotations_mode.add_argument("--plan", action="store_true", help="Print a read-only annotation migration plan.")
    annotations_mode.add_argument("--write", action="store_true", help="Write annotation sidecars without editing mirrors.")
    annotations.add_argument("--json", action="store_true", help="Print machine-readable migration output.")
    annotations.set_defaults(func=command_migrate_annotations)
    sub.add_parser("plan", help="Inventory sources and proposed mirror actions without writing.").set_defaults(func=command_plan)
    sub.add_parser("sync", help="Run Office and repo mirror syncs.").set_defaults(func=command_sync)
    sub.add_parser("status", help="Report manifest-backed lifecycle status.").set_defaults(func=command_status)
    journal = sub.add_parser("journal", help="Inspect local journaled materialization state.")
    journal_sub = journal.add_subparsers(dest="journal_command", required=True)
    journal_status = journal_sub.add_parser("status", help="Report local journal queue and worker state.")
    journal_status.add_argument("--init", action="store_true", help="Initialize local journal state if missing.")
    journal_status.add_argument("--json", action="store_true", help="Print machine-readable journal status.")
    journal_status.set_defaults(func=command_journal_status)
    journal_replay = journal_sub.add_parser("replay", help="Replay recoverable local journal work.")
    journal_replay.add_argument(
        "--holder",
        help="Worker lease holder ID. Defaults to a process-scoped CLI holder.",
    )
    journal_replay.add_argument(
        "--retry-failed",
        action="store_true",
        help="Requeue failed events before replaying. Interrupted processing events are always recovered.",
    )
    journal_replay.add_argument("--max-events", type=int, help="Maximum number of events to process.")
    journal_replay.add_argument(
        "--lease-ttl-seconds",
        type=int,
        default=300,
        help="Worker lease time-to-live in seconds.",
    )
    journal_replay.add_argument("--json", action="store_true", help="Print machine-readable replay results.")
    journal_replay.set_defaults(func=command_journal_replay)
    reconcile = sub.add_parser("reconcile", help="Queue missed journal events from source/manifest state.")
    reconcile.add_argument("--json", action="store_true", help="Print machine-readable reconciliation results.")
    reconcile.set_defaults(func=command_reconcile)
    sub.add_parser("doctor", help="Check required files, Python version, and dependencies.").set_defaults(func=command_doctor)
    sub.add_parser("lint", help="Run vault health checks.").set_defaults(func=command_lint)
    overlap = sub.add_parser("overlap", help="Print a read-only overlap threshold calibration report.")
    overlap_output = overlap.add_mutually_exclusive_group()
    overlap_output.add_argument("--json", action="store_true", help="Print machine-readable overlap calibration JSON.")
    overlap_output.add_argument("--worksheet", action="store_true", help="Print a Markdown calibration worksheet.")
    overlap.add_argument("--max-pairs", type=int, default=40, help="Maximum current/near-miss pairs to print.")
    overlap.set_defaults(func=command_overlap)
    benchmark = sub.add_parser("benchmark", help="Validate the agent-readiness benchmark task pack and optional result pack.")
    benchmark.add_argument("--tasks", type=Path, help="Task pack path relative to the vault root.")
    benchmark.add_argument("--results", type=Path, help="Optional benchmark results path relative to the vault root.")
    benchmark.add_argument("--init-tasks", action="store_true", help="Create a private benchmark task scaffold.")
    benchmark.add_argument("--init-results", action="store_true", help="Create a private benchmark result scaffold.")
    benchmark.add_argument("--force", action="store_true", help="Overwrite an existing task or result scaffold.")
    benchmark.add_argument("--scaffold-sources", type=int, default=5, help="Maximum source/mirror pairs for --init-tasks.")
    benchmark.add_argument("--scaffold-curated", type=int, default=5, help="Maximum curated markdown notes for --init-tasks.")
    benchmark.add_argument("--worksheet", action="store_true", help="Print a private benchmark run worksheet.")
    benchmark.add_argument("--require-generated", action="store_true", help="Require generated mirror paths to exist.")
    benchmark.add_argument("--require-results", action="store_true", help="Require benchmark results for every task/mode pair.")
    benchmark.add_argument(
        "--require-citations",
        action="store_true",
        help="Fail scored benchmark results that do not cite a declared source or generated mirror path.",
    )
    benchmark.add_argument(
        "--require-prompt-safety",
        action="store_true",
        help="Fail benchmark results with missing prompt-safety review or recorded prompt-safety violations.",
    )
    benchmark.add_argument("--json", action="store_true", help="Print machine-readable benchmark JSON.")
    benchmark.set_defaults(func=command_benchmark)
    conversion = sub.add_parser("conversion", help="Print a read-only conversion spot-check report.")
    conversion.add_argument("--json", action="store_true", help="Print machine-readable conversion JSON.")
    conversion.add_argument("--guide", action="store_true", help="Append an operator conversion-review checklist.")
    conversion.add_argument("--results", type=Path, help="Validate a metadata-only conversion quality result pack.")
    conversion.add_argument("--init-results", action="store_true", help="Create a metadata-only quality result scaffold.")
    conversion.add_argument("--force", action="store_true", help="Overwrite an existing quality result scaffold.")
    conversion.add_argument(
        "--require-reviewed",
        action="store_true",
        help="Fail unless every source manifest record has a reviewed quality result.",
    )
    conversion.add_argument(
        "--low-risk-per-format",
        type=int,
        default=1,
        help="Include this many low-risk sample records per format in the spot-check list.",
    )
    conversion.set_defaults(func=command_conversion)
    migration = sub.add_parser("migration", help="Report legacy folder/frontmatter migration work.")
    migration_output = migration.add_mutually_exclusive_group()
    migration_output.add_argument("--json", action="store_true", help="Print machine-readable migration JSON.")
    migration_output.add_argument("--worksheet", action="store_true", help="Print a Markdown migration review worksheet.")
    migration_output.add_argument("--runbook", action="store_true", help="Print a Markdown legacy-folder migration runbook.")
    migration.add_argument(
        "--normalize-frontmatter-domains",
        action="store_true",
        help="Preview known legacy frontmatter domain aliases that can be rewritten to canonical domains.",
    )
    migration.add_argument(
        "--write",
        action="store_true",
        help="With --normalize-frontmatter-domains, rewrite known frontmatter domain aliases. Does not move files.",
    )
    migration.set_defaults(func=command_migration)
    pilot = sub.add_parser("pilot", help="Print a read-only design-partner pilot evidence report.")
    pilot_output = pilot.add_mutually_exclusive_group()
    pilot_output.add_argument("--json", action="store_true", help="Print machine-readable pilot JSON.")
    pilot_output.add_argument(
        "--worksheet",
        action="store_true",
        help="Print a redacted Markdown pilot worksheet summary.",
    )
    pilot.set_defaults(func=command_pilot)
    recovery = sub.add_parser("recovery", help="Print a read-only manifest recovery checklist.")
    recovery_output = recovery.add_mutually_exclusive_group()
    recovery_output.add_argument("--json", action="store_true", help="Print machine-readable recovery JSON.")
    recovery_output.add_argument("--worksheet", action="store_true", help="Print a Markdown recovery review worksheet.")
    recovery_output.add_argument("--runbook", action="store_true", help="Print a Markdown recovery resolution runbook.")
    recovery.set_defaults(func=command_recovery)
    m365 = sub.add_parser("m365", help="Print a read-only Microsoft 365/Copilot handoff report.")
    m365.add_argument("--json", action="store_true", help="Print machine-readable handoff JSON.")
    m365.set_defaults(func=command_m365)
    review = sub.add_parser("review", help="Record or summarize metadata-only artifact review decisions.")
    review.add_argument("--artifact", type=Path, help="Generated artifact to review, relative to the vault root.")
    review.add_argument("--status", choices=["approved", "blocked", "deferred", "needs-work"], help="Review decision to record.")
    review.add_argument("--reviewer", help="Reviewer name or role for a recorded decision.")
    review.add_argument("--note", default="", help="Short metadata-only review note.")
    review.add_argument("--kind", help="Override artifact kind after path safety checks.")
    review.add_argument("--json", action="store_true", help="Print machine-readable review ledger output.")
    review.add_argument("--check", action="store_true", help="Fail unless every latest review is approved and current.")
    review.set_defaults(func=command_review)
    catalog = sub.add_parser("catalog", help="Generate a source-path-only documentation catalog.")
    catalog.add_argument("--json", action="store_true", help="Print machine-readable catalog JSON.")
    catalog.add_argument("--html", action="store_true", help="Write or print an HTML catalog instead of Markdown.")
    catalog.add_argument("--stdout", action="store_true", help="Print catalog output instead of writing a file.")
    catalog.add_argument("--check", action="store_true", help="Fail if the catalog output is missing or stale.")
    catalog.add_argument(
        "--output",
        type=Path,
        default=Path("CATALOG.md"),
        help="Catalog path relative to the vault root. Defaults to CATALOG.html when --html is used.",
    )
    catalog.add_argument(
        "--max-items",
        type=int,
        default=500,
        help="Maximum source/repo records to list per catalog section; use 0 for no limit.",
    )
    catalog.set_defaults(func=command_catalog)
    sandbox = sub.add_parser("sandbox", help="Print a read-only copied-vault sandbox readiness report.")
    sandbox.add_argument(
        "--source-root",
        type=Path,
        help="Original source collection root. Used only to verify the pilot vault is a separate copy.",
    )
    sandbox.add_argument("--json", action="store_true", help="Print machine-readable sandbox JSON.")
    sandbox.set_defaults(func=command_sandbox)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
