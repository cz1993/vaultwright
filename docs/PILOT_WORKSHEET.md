# Pilot Worksheet

Use this worksheet for a permission-cleared design-partner pilot. Keep completed worksheets and
command transcripts outside this public repository unless every source is synthetic or public-domain
and the owner has approved publication.

## Pilot Setup

- Participant/team:
- Operator:
- Date range:
- Corpus boundary:
- Source copy location:
- Cloud AI providers used, if any:
- Data handling constraints:

## Baseline

- Current document-review workflow:
- Main pain points:
- Current tools:
- Security or client-boundary constraints:
- Baseline time to answer the fixed question set:

## Corpus Shape

Record from `python3.11 tools/vaultwright.py pilot --json` after first sync:

- content file count:
- total content bytes:
- Office/PDF source candidates:
- source manifest records:
- source formats:
- repo manifest records:
- sync audit event count:
- conversion high/medium/low counts:
- conversion-quality result records:
- conversion-quality reviewed records:
- conversion-quality missing reviews:
- conversion-quality average score:
- conversion-quality issue-code counts:
- conversion-quality correction count:
- recovery action count:
- overlap current candidate count:
- overlap near-miss count:
- overlap comparable pair count:
- overlap thresholds:
- review-ledger reviewed artifacts:
- review-ledger stale/missing or non-approved decisions:
- benchmark task count:
- benchmark result count:
- benchmark missing task/mode scores:

Do not paste source paths, document text, mirror text, secrets, personal data, or client identifiers
into this worksheet.

For a paste-ready aggregate summary, use:

```bash
python3.11 tools/vaultwright.py pilot --worksheet
```

This prints a Markdown summary with counts, review queues, and private worksheet prompts. It omits
source paths, source text, mirror text, answer text, reviewer notes, and client identifiers.

## Run Log

Record command results and elapsed time:

```bash
python3.11 tools/vaultwright.py doctor
python3.11 tools/vaultwright.py plan
python3.11 tools/vaultwright.py sync
python3.11 tools/vaultwright.py status
python3.11 tools/vaultwright.py catalog
python3.11 tools/vaultwright.py catalog --html
python3.11 tools/vaultwright.py conversion --guide
python3.11 tools/vaultwright.py conversion --init-results
python3.11 tools/vaultwright.py conversion --results _meta/conversion-quality-results.yml --require-reviewed # after filling scaffold
python3.11 tools/vaultwright.py recovery
python3.11 tools/vaultwright.py overlap
python3.11 tools/vaultwright.py overlap --worksheet
python3.11 tools/vaultwright.py m365
python3.11 tools/vaultwright.py review --json
python3.11 tools/vaultwright.py pilot --json
python3.11 tools/vaultwright.py pilot --worksheet
python3.11 tools/vaultwright.py benchmark --init-tasks
python3.11 tools/vaultwright.py benchmark --worksheet
python3.11 tools/vaultwright.py benchmark --require-generated
python3.11 tools/vaultwright.py benchmark --init-results
python3.11 tools/vaultwright.py benchmark --results _meta/agent-readiness-results.yml --require-results
python3.11 tools/vaultwright.py lint
```

## Review Results

- Unsupported/skipped files:
- Conversion high-priority items reviewed:
- Conversion medium-priority spot checks reviewed:
- Conversion guide checklist completed:
- Conversion-quality result pack completed:
- Conversion-quality average score:
- Conversion-quality correction count:
- Conversion-quality issue-code counts:
- Recovery items resolved:
- Overlap candidates reviewed:
- Overlap near misses spot-checked:
- Review ledger current approvals:
- Review ledger stale or non-approved items:
- Manual corrections made:
- Overlap threshold changes from `_meta/lint-config.yml`:
- Curated hubs/entity pages created:
- Source files verified unchanged:
- Second sync idempotency result:

## Agent-Readiness Tasks

Use `docs/AGENT_READINESS_BENCHMARK.md` for scoring. Keep prompts, scores, and citations
anonymized, and keep any private result pack outside this public repository unless it has been
reviewed for source text, personal data, client names, answer text, and reviewer notes.

| Task ID | Raw folder score | Document-chat score | Vaultwright markdown score | Notes |
| --- | ---: | ---: | ---: | --- |
| | | | | |

## Outcome

- Time to answer fixed questions before Vaultwright:
- Time to answer fixed questions after Vaultwright:
- Operator confidence score:
- Support time required:
- Participant returned after one week:
- Issues found:
- Product changes requested:
- Publishable quote, only with written permission:

## Decision

- Continue pilot:
- Stop reason, if applicable:
- Next product fix:
- Next validation corpus:
