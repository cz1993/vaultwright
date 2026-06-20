---
title: INDEX
type: moc
status: active
domain: governance
owner: you
created: 2026-01-01
updated: 2026-01-01
tags: [index, moc]
related: ["[[CLAUDE]]", "[[RETENTION]]"]
---

# Knowledge Base — Index

The map of the vault. **Start here.** Conventions live in [[CLAUDE]]; the one-screen cheat sheet is
[[_meta/conventions|conventions]].

> [!tip] Two ways to navigate
> - **This page** — the curated map of function hubs and key entities.
> - **[[Documents.base|Documents]]** — live tables generated from note frontmatter (Obsidian Bases),
>   so they never drift.

## Starter Domains

Each function gets a **hub note** (`type: moc`) as you populate it. Suggested starter file plan:

| Folder | Covers |
| --- | --- |
| `00_inbox/` | unprocessed files, imports, triage notes |
| `10_governance/` | company identity, ownership, legal, policy, compliance, risk |
| `20_market/` | market research, positioning, brand, campaigns, partnerships |
| `30_customers/` | accounts/clients, sales, discovery, proposals, support |
| `40_delivery/` | products/services, projects, implementations, delivery playbooks |
| `50_operations/` | internal process, vendors, procurement, IT, security, facilities |
| `60_finance/` | accounting, tax, payroll, budgets, funding, banking, reporting |
| `70_people/` | hiring, employees, contractors, onboarding, training |
| `80_sources/` | repo mirrors, public datasets, source inventories |

## How this knowledge base works

- **Four layers** (raw sources → generated mirrors → wiki → schema) — see [[CLAUDE]].
- **Function-based file plan** — see [[_meta/domain-map|domain map]].
- **Every note has frontmatter**; [[Documents.base|Documents]] reads it so the index maintains itself.
- **Office mirrors** and optional PDF text mirrors live under `_mirrors/`; **repo mirrors** live under `80_sources/repos/`.
  Originals stay source of truth, with lifecycle state tracked in `_meta/source-manifest.json` and
  `_meta/repo-manifest.json`, plus generated events in `_meta/sync-audit.jsonl`.
- **Agent-readiness tasks** live in `_meta/agent-readiness-tasks.yml`; use them to compare raw
  sources, document-chat transcripts, and Vaultwright markdown on the same prompts.
- **Link over filing**, and **consolidate over creating** (see [[CLAUDE]] §4–5).

## Governance

[[CLAUDE]] (schema & workflows) · [[RETENTION]] (how long things are kept) · [[_meta/conventions|conventions]] · `log.md`
