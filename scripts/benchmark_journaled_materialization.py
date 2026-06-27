#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run a deterministic synthetic benchmark for journaled materialization."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import tracemalloc
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vaultwright.changes import feed, watch  # noqa: E402
from vaultwright.mirrors import office as office_sync  # noqa: E402


FOLDERS = ("40_delivery", "50_operations", "60_finance", "80_sources")
EXTENSIONS = (".docx", ".pptx", ".xlsx")
CONVERTER_NAME = "synthetic-journal-benchmark"
CONVERTER_VERSION = "1"


@dataclass
class Metrics:
    discover_calls: int = 0
    paths_enumerated: int = 0
    source_bodies_read: int = 0
    bytes_hashed: int = 0
    hashed_paths: Counter[str] = field(default_factory=Counter)
    converter_invocations: int = 0
    converted_paths: list[str] = field(default_factory=list)


class SyntheticConversion:
    def __init__(self, text: str) -> None:
        self.text_content = text


class CountingConverter:
    def __init__(self, root: Path, metrics: Metrics) -> None:
        self.root = root
        self.metrics = metrics

    def convert(self, path: str) -> SyntheticConversion:
        self.metrics.converter_invocations += 1
        source = Path(path)
        rel = source.relative_to(self.root).as_posix()
        self.metrics.converted_paths.append(rel)
        return SyntheticConversion(f"Synthetic extracted text for {rel}\n")


def source_rel(index: int) -> Path:
    folder = FOLDERS[index % len(FOLDERS)]
    ext = EXTENSIONS[index % len(EXTENSIONS)]
    return Path(folder) / f"source_{index:04d}{ext}"


def source_bytes(index: int) -> bytes:
    line = f"synthetic public benchmark source {index:04d}\n"
    return (line * (1 + index % 7)).encode("utf-8")


def write_source(root: Path, rel: Path, payload: bytes) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def seed_baseline(root: Path, count: int) -> list[str]:
    mirror_config = office_sync.load_mirror_config(root, None, None)
    routing = office_sync.load_domain_routing(root)
    manifest = office_sync.empty_manifest()
    source_paths: list[str] = []
    for index in range(count):
        rel = source_rel(index)
        write_source(root, rel, source_bytes(index))
        source = root / rel
        plan = office_sync.plan_one(
            source,
            root,
            mirror_config,
            routing,
            manifest,
            CONVERTER_NAME,
            CONVERTER_VERSION,
        )
        record = dict(plan["record"])
        extracted = f"Synthetic extracted text for {rel.as_posix()}\n"
        generated = office_sync.auto_region(extracted)
        frontmatter = office_sync.managed_frontmatter(
            None,
            source,
            root,
            record["source_sha256"],
            routing,
            record["source_id"],
            CONVERTER_NAME,
            CONVERTER_VERSION,
        )
        content = (
            office_sync.dump_frontmatter(frontmatter, root=root)
            + "\n"
            + office_sync.fresh_preserved_region(source, root)
            + generated
        )
        mirror = plan["mirror"]
        office_sync.write_text_atomic(mirror, content)
        record["normalized_content_sha256"] = office_sync.sha256_text(extracted.strip())
        record["generated_region_sha256"] = office_sync.sha256_text(generated)
        record["lifecycle_state"] = "clean"
        record["last_successful_sync"] = frontmatter["synced"]
        record["warnings"] = []
        record["errors"] = []
        office_sync.upsert_manifest_record(manifest, record)
        source_paths.append(rel.as_posix())
    office_sync.write_source_manifest(root, manifest)
    return source_paths


def run_benchmark(source_count: int) -> dict[str, Any]:
    if source_count < 10:
        raise ValueError("source_count must be at least 10")
    with tempfile.TemporaryDirectory(prefix="vaultwright-journal-bench-") as temp:
        root = (Path(temp) / "vault").resolve()
        root.mkdir()
        sources = seed_baseline(root, source_count)
        modified_rel = sources[1]
        moved_previous = sources[2]
        deleted_rel = sources[3]
        moved_path = Path(moved_previous)
        moved_current = str(moved_path.with_name(f"{moved_path.stem}_moved{moved_path.suffix}"))

        modified = root / modified_rel
        modified.write_bytes(modified.read_bytes() + b"\nchanged once\n")
        (root / moved_previous).rename(root / moved_current)
        (root / deleted_rel).unlink()

        observed = [
            *[
                feed.ObservedChange("modified", modified_rel, observed_at=f"2099-01-01T00:00:{i:02d}Z")
                for i in range(10)
            ],
            feed.ObservedChange(
                "moved",
                current_path=moved_current,
                previous_path=moved_previous,
                observed_at="2099-01-01T00:00:10Z",
            ),
            feed.ObservedChange("deleted", previous_path=deleted_rel, observed_at="2099-01-01T00:00:11Z"),
        ]
        metrics = Metrics()
        original_sha256 = office_sync.sha256_of
        original_discover = office_sync.discover

        def counted_sha256(path: Path) -> str:
            rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
            payload = path.read_bytes()
            metrics.source_bodies_read += 1
            metrics.bytes_hashed += len(payload)
            metrics.hashed_paths[rel] += 1
            return hashlib.sha256(payload).hexdigest()

        def counted_discover(
            discover_root: Path,
            exts: list[str],
            mirror_config: dict[str, Path | str],
        ) -> list[Path]:
            metrics.discover_calls += 1
            discovered = original_discover(discover_root, exts, mirror_config)
            metrics.paths_enumerated += len(discovered)
            return discovered

        office_sync.sha256_of = counted_sha256
        office_sync.discover = counted_discover
        tracemalloc.start()
        started = time.perf_counter()
        try:
            result = watch.watch_once(
                root,
                "benchmark-worker",
                observed_feed=feed.StaticChangeFeed(observed),
                reconcile_on_start=False,
                materialize_kwargs={
                    "converter": CountingConverter(root, metrics),
                    "converter_name": CONVERTER_NAME,
                    "converter_version": CONVERTER_VERSION,
                    "append_audit": False,
                },
            )
            elapsed_seconds = time.perf_counter() - started
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
            office_sync.sha256_of = original_sha256
            office_sync.discover = original_discover

        changed_source_set = {modified_rel, moved_current}
        untouched_reads = sum(
            count for rel, count in metrics.hashed_paths.items() if rel not in changed_source_set
        )
        finish_counts = result["finish_counts"]
        return {
            "benchmark": "journaled-materialization-known-path",
            "sources_total": source_count,
            "events_received": len(observed),
            "events_queued_after_coalescing": result["feed_events_queued"],
            "events_coalesced": len(observed) - result["feed_events_queued"],
            "events_processed": result["processed"],
            "events_applied": finish_counts["applied"],
            "events_review_required": finish_counts["review-required"],
            "events_failed": finish_counts["failed"],
            "paths_enumerated": metrics.paths_enumerated,
            "discover_calls": metrics.discover_calls,
            "source_bodies_read": metrics.source_bodies_read,
            "untouched_source_bodies_read": untouched_reads,
            "bytes_hashed": metrics.bytes_hashed,
            "hashed_paths": dict(sorted(metrics.hashed_paths.items())),
            "converter_invocations": metrics.converter_invocations,
            "converted_paths": metrics.converted_paths,
            "elapsed_seconds": round(elapsed_seconds, 6),
            "peak_memory_bytes": peak,
            "structural_pass": {
                "known_path_processing_no_discovery": metrics.discover_calls == 0,
                "untouched_sources_not_hashed": untouched_reads == 0,
                "one_changed_source_at_most_one_conversion": metrics.converter_invocations <= 1,
                "clean_replay_no_failures": finish_counts["failed"] == 0,
            },
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=int, default=1000, help="Number of synthetic sources.")
    parser.add_argument("--json", action="store_true", help="Print indented JSON.")
    args = parser.parse_args(argv)
    result = run_benchmark(args.sources)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True))
    failed = [key for key, passed in result["structural_pass"].items() if not passed]
    if failed:
        print("benchmark structural checks failed: " + ", ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
