# SPDX-License-Identifier: AGPL-3.0-or-later
"""Installable Vaultwright console entry point.

The packaged command delegates operator commands to the target vault's local `tools/vaultwright.py`
wrapper. That keeps the vault tools as the source of truth while allowing a single `vaultwright`
command from editable or wheel installs.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


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


def ensure_empty_or_missing(target: Path) -> None:
    if target.exists() and any(target.iterdir()):
        raise ValueError(f"refusing: '{target}' exists and is not empty")


def run(cmd: list[str], cwd: Path) -> int:
    return subprocess.run(cmd, cwd=cwd).returncode


def vault_wrapper(root: Path) -> Path:
    wrapper = root / "tools" / "vaultwright.py"
    if not wrapper.exists():
        raise FileNotFoundError(f"{root} does not look like a Vaultwright vault: missing tools/vaultwright.py")
    return wrapper


def command_init(args: argparse.Namespace) -> int:
    template = template_source()
    if not template:
        print(
            "vaultwright init cannot find a packaged template. Reinstall Vaultwright or set "
            "VAULTWRIGHT_REPO to a source checkout.",
            file=sys.stderr,
        )
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
    print("Next: python3.11 tools/vaultwright.py doctor && python3.11 tools/vaultwright.py plan")
    return 0


def command_delegate(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    try:
        wrapper = vault_wrapper(root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return run([sys.executable, str(wrapper), args.command, *getattr(args, "delegate_args", [])], root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vaultwright command-line interface.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Vault root for plan/sync/status/lint/doctor.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Scaffold a new Vaultwright vault from the template.")
    init.add_argument("target", type=Path)
    init.set_defaults(func=command_init)
    for name, help_text in (
        ("plan", "Inventory sources and proposed mirror actions without writing."),
        ("sync", "Run Office and repo mirror syncs."),
        ("status", "Report manifest-backed lifecycle status."),
        ("lint", "Run vault health checks."),
        ("doctor", "Check required files, Python version, and dependencies."),
    ):
        sub.add_parser(name, help=help_text).set_defaults(func=command_delegate, delegate_args=[])
    overlap = sub.add_parser("overlap", help="Print a read-only overlap threshold calibration report.")
    overlap_output = overlap.add_mutually_exclusive_group()
    overlap_output.add_argument("--json", action="store_true", help="Print machine-readable overlap calibration JSON.")
    overlap_output.add_argument("--worksheet", action="store_true", help="Print a Markdown calibration worksheet.")
    overlap.add_argument("--max-pairs", type=int, default=40, help="Maximum current/near-miss pairs to print.")
    overlap.set_defaults(
        func=command_delegate,
        delegate_args=lambda args: (
            (["--json"] if args.json else [])
            + (["--worksheet"] if args.worksheet else [])
            + (["--max-pairs", str(args.max_pairs)] if args.max_pairs != 40 else [])
        ),
    )
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
    benchmark.set_defaults(
        func=command_delegate,
        delegate_args=lambda args: (
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
        ),
    )
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
    conversion.set_defaults(
        func=command_delegate,
        delegate_args=lambda args: (
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
        ),
    )
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
    migration.set_defaults(
        func=command_delegate,
        delegate_args=lambda args: (
            (["--json"] if args.json else [])
            + (["--worksheet"] if args.worksheet else [])
            + (["--runbook"] if args.runbook else [])
            + (["--normalize-frontmatter-domains"] if args.normalize_frontmatter_domains else [])
            + (["--write"] if args.write else [])
        ),
    )
    pilot = sub.add_parser("pilot", help="Print a read-only design-partner pilot evidence report.")
    pilot_output = pilot.add_mutually_exclusive_group()
    pilot_output.add_argument("--json", action="store_true", help="Print machine-readable pilot JSON.")
    pilot_output.add_argument(
        "--worksheet",
        action="store_true",
        help="Print a redacted Markdown pilot worksheet summary.",
    )
    pilot.set_defaults(
        func=command_delegate,
        delegate_args=lambda args: (
            (["--json"] if args.json else [])
            + (["--worksheet"] if args.worksheet else [])
        ),
    )
    recovery = sub.add_parser("recovery", help="Print a read-only manifest recovery checklist.")
    recovery_output = recovery.add_mutually_exclusive_group()
    recovery_output.add_argument("--json", action="store_true", help="Print machine-readable recovery JSON.")
    recovery_output.add_argument("--worksheet", action="store_true", help="Print a Markdown recovery review worksheet.")
    recovery_output.add_argument("--runbook", action="store_true", help="Print a Markdown recovery resolution runbook.")
    recovery.set_defaults(
        func=command_delegate,
        delegate_args=lambda args: (
            (["--json"] if args.json else [])
            + (["--worksheet"] if args.worksheet else [])
            + (["--runbook"] if args.runbook else [])
        ),
    )
    m365 = sub.add_parser("m365", help="Print a read-only Microsoft 365/Copilot handoff report.")
    m365.add_argument("--json", action="store_true", help="Print machine-readable handoff JSON.")
    m365.set_defaults(
        func=command_delegate,
        delegate_args=lambda args: ["--json"] if args.json else [],
    )
    review = sub.add_parser("review", help="Record or summarize metadata-only artifact review decisions.")
    review.add_argument("--artifact", type=Path, help="Generated artifact to review, relative to the vault root.")
    review.add_argument("--status", choices=["approved", "blocked", "deferred", "needs-work"], help="Review decision to record.")
    review.add_argument("--reviewer", help="Reviewer name or role for a recorded decision.")
    review.add_argument("--note", default="", help="Short metadata-only review note.")
    review.add_argument("--kind", help="Override artifact kind after path safety checks.")
    review.add_argument("--json", action="store_true", help="Print machine-readable review ledger output.")
    review.add_argument("--check", action="store_true", help="Fail unless every latest review is approved and current.")
    review.set_defaults(
        func=command_delegate,
        delegate_args=lambda args: (
            (["--artifact", str(args.artifact)] if args.artifact else [])
            + (["--status", args.status] if args.status else [])
            + (["--reviewer", args.reviewer] if args.reviewer else [])
            + (["--note", args.note] if args.note else [])
            + (["--kind", args.kind] if args.kind else [])
            + (["--json"] if args.json else [])
            + (["--check"] if args.check else [])
        ),
    )
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
    catalog.set_defaults(
        func=command_delegate,
        delegate_args=lambda args: (
            (["--json"] if args.json else [])
            + (["--html"] if args.html else [])
            + (["--stdout"] if args.stdout else [])
            + (["--check"] if args.check else [])
            + (["--output", str(args.output)] if args.output != Path("CATALOG.md") else [])
            + (["--max-items", str(args.max_items)] if args.max_items != 500 else [])
        ),
    )
    sandbox = sub.add_parser("sandbox", help="Print a read-only copied-vault sandbox readiness report.")
    sandbox.add_argument(
        "--source-root",
        type=Path,
        help="Original source collection root. Used only to verify the pilot vault is a separate copy.",
    )
    sandbox.add_argument("--json", action="store_true", help="Print machine-readable sandbox JSON.")
    sandbox.set_defaults(
        func=command_delegate,
        delegate_args=lambda args: (
            (["--source-root", str(args.source_root)] if args.source_root else [])
            + (["--json"] if args.json else [])
        ),
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if callable(getattr(args, "delegate_args", None)):
        args.delegate_args = args.delegate_args(args)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
