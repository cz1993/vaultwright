# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_journaled_materialization_benchmark_structural_metrics() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "benchmark_journaled_materialization.py"),
            "--sources",
            "30",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["sources_total"] == 30
    assert payload["events_received"] == 12
    assert payload["events_queued_after_coalescing"] == 3
    assert payload["events_coalesced"] == 9
    assert payload["events_processed"] == 3
    assert payload["events_applied"] == 2
    assert payload["events_review_required"] == 1
    assert payload["events_failed"] == 0
    assert payload["discover_calls"] == 0
    assert payload["paths_enumerated"] == 0
    assert payload["untouched_source_bodies_read"] == 0
    assert payload["converter_invocations"] == 1
    assert all(payload["structural_pass"].values())
