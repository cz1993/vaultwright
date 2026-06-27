# Journaled Materialization Benchmark

This benchmark records deterministic Stage 1B evidence for known-path journal replay. It uses a
temporary synthetic vault only; no private or real-world source files are read.

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 /tmp/vaultwright-codex-venv/bin/python scripts/benchmark_journaled_materialization.py --sources 1000 --json
```

Result:

| Metric | Value |
| --- | ---: |
| Synthetic source records | 1000 |
| Events received | 12 |
| Events queued after coalescing | 3 |
| Events coalesced | 9 |
| Events processed | 3 |
| Events applied | 2 |
| Events requiring review | 1 |
| Events failed | 0 |
| Whole-workspace discovery calls | 0 |
| Paths enumerated by discovery | 0 |
| Source bodies read/hashed | 3 |
| Untouched source bodies read/hashed | 0 |
| Bytes hashed | 301 |
| Converter invocations | 1 |
| Elapsed seconds | 0.220044 |
| Peak memory bytes | 7920180 |

Touched paths:

- `50_operations/source_0001.pptx` hashed twice, before and after conversion.
- `60_finance/source_0002_moved.xlsx` hashed once for safe move review.
- `50_operations/source_0001.pptx` was the only converted source.

Structural pass conditions:

- Known-path replay performed no whole-workspace discovery.
- Untouched source bodies were not read or hashed.
- The one modified source caused one converter invocation.
- Replay completed without failed events.

The moved-source event intentionally remained review-required because the previous generated
mirror still existed; that is the expected safety behavior before operator cleanup.
