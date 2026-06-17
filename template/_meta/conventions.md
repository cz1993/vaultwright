---
title: Conventions cheat sheet
type: guide
status: active
domain: company
created: 2026-01-01
updated: 2026-01-01
owner: you
tags: [meta, conventions]
related: ["[[CLAUDE]]"]
---

# Conventions cheat sheet

`CLAUDE.md` is authoritative. This is the one-screen quick reference.

## Frontmatter (every note)

- **required:** `title, type, status, domain, created, updated`
- **recommended:** `owner, tags, related`, plus entity links `client/program/vendor`

## `type`

`moc` · `entity` · `note` · `guide` · `policy` · `record` · `source-mirror` · `source-ref` · `repo-mirror`

## `status`

`draft` · `active` · `in-review` · `sent` · `signed` · `submitted` · `awarded` · `superseded` · `archived`

## `tags` — themes only, nested with `/`

e.g. `sales/proposal` · `legal/contract` · `tax/credit` · `brand` · `ops/runbook`

## Entities go in frontmatter as links, not tags

`client: "[[Acme Corp]]"` · `program: "[[Some Program]]"` · `vendor: "[[Some Vendor]]"`

## Naming

- dated/versioned: `YYYY-MM-DD_<slug>_<vN>.<ext>`
- evergreen notes: Title Case or kebab slug (reads well as a wikilink)
- UPPERCASE only: `README`, `INDEX`, `CLAUDE`, `RETENTION`

## The two disciplines

- **Link generously** — every cluster has a `[[hub]]` (moc); every recurring noun an `[[entity]]`.
- **Consolidate before creating** — extend an existing note rather than spawning a new one (§5).
