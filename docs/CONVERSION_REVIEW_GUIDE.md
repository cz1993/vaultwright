# Conversion Review Guide

Vaultwright mirrors make source collections easier to inspect, search, link, and hand to agents.
They do not replace the original source files. This guide defines the operator review loop for
conversion quality before mirrors are used for client-facing conclusions or durable curated notes.

Run it from a copied, permission-cleared vault:

```bash
python3.11 tools/vaultwright.py sandbox --source-root /path/to/original-documents
python3.11 tools/vaultwright.py status
python3.11 tools/vaultwright.py recovery
python3.11 tools/vaultwright.py conversion --guide
python3.11 tools/vaultwright.py conversion --init-results
python3.11 tools/vaultwright.py conversion --results _meta/conversion-quality-results.yml --require-reviewed # after filling scaffold
python3.11 tools/vaultwright.py conversion --guide --json
python3.11 tools/vaultwright.py review --artifact <generated-artifact> --status approved --reviewer <name>
```

`sandbox`, `conversion --guide`, and `conversion --results ...` are read-only. `sandbox` verifies
the copied-vault boundary, mirror isolation, manifest/recovery readiness, and basic backup posture
before review starts. `conversion --guide` prints the manifest-backed spot-check report plus an
operator checklist based on lifecycle states and source formats, including the allowed result-pack
schema. `conversion --init-results` is the only write step in this loop: it creates a private
metadata-only result scaffold under `_meta/` and prints the allowed statuses, scores, issue codes,
and forbidden free-text fields.
None of these commands may print source text, mirror text, source paths, or document bodies.

## Review Order

1. Confirm `vaultwright status` does not report unexplained stale, moved, conflicted, missing, or
   manual-modification states.
2. Resolve `vaultwright recovery` items before trusting generated mirrors.
3. Review all high-priority conversion items.
4. Spot-check all medium-priority items that will support a decision, quote, answer, or curated
   note.
5. Sample low-priority items by format for routine coverage.
6. Fill `_meta/conversion-quality-results.yml` with metadata-only statuses, 0-2 scores, correction
   counts, booleans, and controlled issue codes.
7. After the scaffold is filled, validate the result pack with
   `vaultwright conversion --results _meta/conversion-quality-results.yml --require-reviewed`.
8. Record artifact-level review decisions with `vaultwright review`, then record aggregate defects
   and manual corrections in the pilot worksheet.

## Priority Meaning

| Priority | Meaning | Minimum action |
| --- | --- | --- |
| High | lifecycle state, missing path, unsupported format, conflict, error, or manifest error makes the mirror unsafe to trust | resolve or document before use |
| Medium | source changed/stale/converter risk, high-risk format, or conversion-quality warning | spot-check source against mirror before use |
| Low | clean lifecycle and no known format-specific risk | sample by format and verify source links |

High-priority items are not an automated quality score. They are a stop sign for operator review.
The optional conversion-quality result pack stores reviewer-entered scores after source/mirror
spot checks; it is pilot evidence, not proof that future conversions will be correct.

## Format Checks

| Format | Review focus |
| --- | --- |
| `.docx` | heading hierarchy, tables, lists, links, comments/tracked changes, generated-region boundary |
| `.pdf` | scanned or image-only pages, page order, tables, footnotes, form fields, diagrams, missing pages |
| `.pptx` | slide titles, speaker notes, image-heavy slides, embedded media, tables, visual-only claims |
| `.xlsx` / `.xls` | formulas, hidden sheets, merged cells, number/date formats, workbook notes, source workbook authority |
| `.doc` | inventory-only unless manually converted to `.docx`; preserve original as source of truth |

For spreadsheets and decks, the mirror is mainly for search, triage, and citation scaffolding. Use
the original workbook or deck for calculations and layout-dependent interpretation.

## Sign-Off Criteria

A mirror can support curated notes only when:

- source path and mirror path are present and relative;
- lifecycle state is clean or intentionally reviewed;
- source and mirror still exist;
- format-specific caveats have been reviewed;
- conversion-quality results have been recorded for all relevant source manifest records when the
  pilot or engagement requires scoring;
- any high-priority recovery item is resolved or documented;
- the curated note cites source-backed paths rather than treating generated markdown as final
  authority.

## What To Record

In `_meta/conversion-quality-results.yml`, record only these metadata fields:

- `source_id`;
- optional `source_format` and priority copied from the scaffold;
- `status`: `not-reviewed`, `pass`, `needs-work`, or `blocked`;
- `score`: null for `not-reviewed`, otherwise 0, 1, or 2;
- `reviewer_corrections`: null for `not-reviewed`, otherwise a nonnegative integer;
- `checked_source`, `checked_mirror`, and `checked_links`;
- `issue_codes` from the controlled list printed by the guide, scaffold, and validator.

Do not add notes, reviewer comments, source text, mirror text, prompts, answers, excerpts, client
identifiers, secrets, or personal data. The validator rejects common free-text fields.

In `docs/PILOT_WORKSHEET.md` or a private engagement worksheet, record aggregate evidence only:

- high/medium/low conversion counts;
- conversion-quality result records, reviewed count, average score, correction count, and issue-code
  counts;
- unsupported/skipped file counts;
- conversion defects by format;
- manual corrections made;
- source files verified unchanged;
- current approval and stale-review counts from `vaultwright review --json`;
- whether the second sync remained idempotent.

Do not paste source text, mirror text, personal data, client identifiers, secrets, or private
benchmark answers into the public Vaultwright repository.
