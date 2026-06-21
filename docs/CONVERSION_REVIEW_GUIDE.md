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
python3.11 tools/vaultwright.py conversion --guide --json
```

`sandbox` and `conversion --guide` are read-only. `sandbox` verifies the copied-vault boundary,
mirror isolation, manifest/recovery readiness, and basic backup posture before review starts.
`conversion --guide` prints the manifest-backed spot-check report plus an operator checklist based
on lifecycle states and source formats. Neither command may print source text, mirror text, source
paths, or document bodies.

## Review Order

1. Confirm `vaultwright status` does not report unexplained stale, moved, conflicted, missing, or
   manual-modification states.
2. Resolve `vaultwright recovery` items before trusting generated mirrors.
3. Review all high-priority conversion items.
4. Spot-check all medium-priority items that will support a decision, quote, answer, or curated
   note.
5. Sample low-priority items by format for routine coverage.
6. Record defects and manual corrections in the pilot worksheet.

## Priority Meaning

| Priority | Meaning | Minimum action |
| --- | --- | --- |
| High | lifecycle state, missing path, unsupported format, conflict, error, or manifest error makes the mirror unsafe to trust | resolve or document before use |
| Medium | source changed/stale/converter risk, high-risk format, or conversion-quality warning | spot-check source against mirror before use |
| Low | clean lifecycle and no known format-specific risk | sample by format and verify source links |

High-priority items are not a quality score. They are a stop sign for operator review.

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
- any high-priority recovery item is resolved or documented;
- the curated note cites source-backed paths rather than treating generated markdown as final
  authority.

## What To Record

In `docs/PILOT_WORKSHEET.md` or a private engagement worksheet, record aggregate evidence only:

- high/medium/low conversion counts;
- unsupported/skipped file counts;
- conversion defects by format;
- manual corrections made;
- source files verified unchanged;
- whether the second sync remained idempotent.

Do not paste source text, mirror text, personal data, client identifiers, secrets, or private
benchmark answers into the public Vaultwright repository.
