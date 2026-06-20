# Vaultwright Whitepaper

**Status:** pre-release product-definition and execution brief  
**Date:** 2026-06-20  
**Audience:** consulting, advisory, implementation, operations, and diligence reviewers  
**Review posture:** professional, candid, and evidence-based

## 1. Executive Summary

Vaultwright is a small open-source toolkit and methodology for turning an existing business
document collection into a governed, inspectable markdown knowledge workspace without modifying the
original records.

The near-term workflow still helps human operators review, govern, and maintain the knowledge base.
The more important long-term opportunity is that generated markdown mirrors can become an
agent-ready knowledge substrate. Markdown is plain text, structured, diffable, linkable, and easy
for AI agents to inspect with ordinary filesystem and Git tools. That can make the generated
markdown layer more valuable to agents than a folder of opaque Office/PDF binaries, as long as
provenance and refresh safety remain strict.

The product should not be framed as another AI wiki, Obsidian template, or generic document-chat
tool. Its practical promise is narrower and more defensible:

> Preserve source records, generate auditable markdown mirrors, and create a source-linked,
> agent-readable knowledge substrate that can be refreshed safely over time.

The best first buyer is not every small business. The best first buyer is a small consulting,
advisory, compliance, implementation, or operations team that repeatedly receives messy client
document collections and must turn them into usable operating knowledge without losing provenance.

This work has made material progress:

- The folder model has moved away from a generic starter-pack structure toward durable business
  functions.
- Original Office/source files now remain in place while generated markdown mirrors live under
  dedicated `_mirrors/` storage.
- The tool now has plan/sync/status/lint/doctor commands, source manifests, repo manifests, audit
  logs, no-data safeguards, CI regeneration tests, and example vaults.
- A new public-service example vault demonstrates familiar Canadian business-startup workflows:
  business registration, CRA program accounts, GST/HST readiness, account access, and
  funding/support discovery.
- The white-paper, product contract, sync spec, security model, recovery guide, and design-partner
  protocol now describe what exists, what remains incomplete, and how to validate the product.

The honest assessment is positive but not yet production-ready. Vaultwright has a credible
technical and methodological foundation, but it still needs external design-partner validation,
larger-corpus benchmarks, stronger lifecycle handling, better conversion-quality reporting, and a
clear support/deployment model before being sold as a dependable client-facing product.

## 2. Decision Recommendation

Proceed, but keep the next phase narrow.

Recommended near-term decision:

1. Continue building Vaultwright as an open-source core plus implementation-service offering.
2. Use consulting/advisory teams as the first validation wedge.
3. Keep the government-services vault as the primary public demo because it uses familiar,
   document-heavy, low-confidentiality business guidance.
4. Do not broaden into a hosted SaaS, vector database product, or multi-industry template library
   until the mirror lifecycle is proven on real corpora.
5. Add "agent-ready markdown substrate" to the product roadmap, but do not let it weaken the
   current source-preservation, governance, and lifecycle gates.
6. Treat external pilot evidence as the next release blocker.

## 3. Target User and Commercial Wedge

Vaultwright's first buyer should be a small professional-services team that handles document-heavy
work:

- client onboarding;
- business registration and operating setup;
- funding readiness;
- compliance readiness;
- operational audits;
- finance, tax, or grant-preparation support;
- software/project handover;
- recurring client operating-system cleanup.

This buyer is attractive for four reasons:

- They already understand source preservation, audit trails, and engagement boundaries.
- They can test Vaultwright across multiple client-shaped corpora.
- They feel the cost of messy documents directly through billable review time.
- They can sell a managed process before the software is fully self-serve.

Owner-operators may benefit later, but they are not the ideal first market because they often need
more onboarding, more product polish, and more packaged guidance.

## 4. Problem Statement

Business records usually arrive as folders of contracts, decks, spreadsheets, public guidance,
emails, exports, repositories, PDFs, and working notes. The recurring failures are operational, not
theoretical:

- Originals remain authoritative but are hard to inspect, search, or connect.
- Summaries drift away from source files and become unofficial records.
- AI-generated notes proliferate faster than humans can verify them.
- Department-style folders such as `marketing/`, `legal/`, and `hr/` often fail for companies that
  operate across different industries, engagement types, or regulatory contexts.
- Sensitive records, provenance, retention, and licensing are handled inconsistently.
- Document-chat tools answer questions but do not leave behind a maintainable operating record.
- Consultants repeatedly re-read the same documents because prior understanding was not captured
  in a durable, source-linked structure.

The core product question is therefore:

**Can Vaultwright reduce repeated document-reading effort while preserving source authority and
making the generated knowledge base safe to refresh?**

## 5. Product Thesis

Vaultwright should be positioned as:

**A governed document-to-markdown lifecycle for organizations that must preserve original records
while making their contents usable by people and AI agents.**

The differentiators are:

- **Mirror layer:** Office and repo sources are converted into markdown mirrors that live apart from
  original files; text-based PDF mirroring is optional with explicit sync flags.
- **Governance:** no-data scanning, provenance ledgers, retention guidance, and explicit agent
  permissions are part of the product, not afterthoughts.
- **Anti-proliferation:** agents are instructed to consolidate and update before creating more
  notes; linting now reports likely duplicate/overlap candidates for human review.
- **Linking-first retrieval:** maps of content, entity pages, backlinks, and frontmatter remain the
  durable retrieval layer. Vector or semantic indexes can be optional later; they should not become
  the source of truth.
- **Agent-ready substrate:** generated markdown gives agents a transparent, file-native working
  layer with headings, frontmatter, links, diffs, and manifests instead of forcing them to reason
  directly over opaque binaries or transient chat answers.
- **Source-preserving workflow:** originals remain untouched; generated mirrors are reproducible;
  curated notes are reviewed separately.

Future direction: Vaultwright should increasingly optimize for AI-agent consumption of governed
markdown, not merely for human knowledge-base management. The product should measure whether agents
can answer, update, reconcile, and audit operational knowledge more reliably from Vaultwright's
markdown mirrors than from raw source folders or one-off document-chat transcripts. Human review
remains the governance boundary; agent-readability becomes the compounding value layer.

## 6. Government-Services Showcase Rationale

The user feedback that the example data should be closer to real government/business workflows is
correct. A fictional company such as Northwind Robotics is useful for tests, but it is not familiar
or painful enough to demonstrate why Vaultwright matters.

The stronger public example is a government-services/business-startup corpus because it has the
right characteristics:

- The content domain is familiar to many business operators.
- The documents are dense, procedural, and difficult to navigate.
- The workflow naturally spans registration, tax, account access, support, and funding.
- Public-sector guidance is easier to discuss openly than confidential client files.
- The example can demonstrate document readability, provenance, and source separation without
  committing real personal or company data.

The new `examples/government-services-vault/` is therefore the primary public showcase. It includes
generated fixture documents based on:

- Canadian business registration and business number / CRA program-account setup;
- GST/HST registration readiness and post-registration obligations;
- CRA account access and operator questions;
- business funding and support discovery;
- public-service navigation materials in `.docx`, `.xlsx`, and `.pptx` formats.

Important limitation: the committed fixtures are synthetic and paraphrased. They are not copied
government publications, do not include government logos or marks, and do not claim endorsement by
any government body. Exact source URLs, licence posture, attribution obligations, and review dates
are recorded in `examples/DATA_PROVENANCE.md`.

This showcase is still not equivalent to a real client pilot. It is a better demonstration corpus,
not a substitute for external validation.

## 7. Information Architecture Direction

Vaultwright moved from a conventional department-style starter pack toward function-based folders:

| Folder | Purpose |
| --- | --- |
| `00_inbox/` | temporary intake and triage |
| `10_governance/` | decisions, policies, risk, compliance, provenance |
| `20_market/` | market, competitors, public context, research |
| `30_customers/` | customer/account/user/entity knowledge |
| `40_delivery/` | products, services, projects, fulfillment, implementation |
| `50_operations/` | processes, vendors, tooling, support, facilities |
| `60_finance/` | accounting, tax, payroll, budgets, funding, banking |
| `70_people/` | team, roles, hiring, contractors, training |
| `80_sources/` | source references and repo mirrors |
| `_mirrors/` | generated markdown mirrors of source files |
| `_meta/` | manifests, conventions, configuration, audit state |
| `_templates/` | reusable note templates |

This is more professional than a fixed `marketing/legal/hr` structure because it can work across
industries. It also keeps the model configurable through `domain-map.yml` and `mirror-config.yml`
instead of hard-coding one organization's assumptions.

Remaining work:

- Calibrate migration guidance on real legacy folder layouts beyond the initial read-only report.
- Improve domain-specific examples without creating a rigid taxonomy library too early.
- Calibrate overlap/similarity thresholds with real pilot corpora before treating warnings as
  operational metrics.

## 8. Architecture and Invariants

Vaultwright separates four layers:

| Layer | Role | Ownership |
| --- | --- | --- |
| Raw sources | Original Office files, PDFs, repositories, exports, and public/source files | User/client; never altered by sync |
| Generated mirrors | Markdown under `_mirrors/` and repo mirrors under `80_sources/repos/` | Tool-generated; reproducible |
| Curated notes | Hubs, entity pages, decisions, guides, summaries, review notes | Human/agent co-authored; reviewed |
| Schema and controls | `CLAUDE.md`, domain map, mirror config, templates, lint rules, CI, scans | Project-owned; versioned |

Non-negotiable product invariants:

- Original source bytes are not modified by Vaultwright sync.
- Generated mirrors are distinguishable from curated notes.
- Mirror output is reproducible from a known source path and configuration.
- Provenance is preserved in frontmatter, manifests, and example ledgers.
- Unsafe paths, symlinks, secrets, and unapproved data files are rejected.
- Destructive actions are not automatic.
- Obsidian is the reference interface, not the correctness boundary.
- Real client data does not belong in this repository.

## 9. Intended Operator Workflow

The intended professional workflow is:

1. Copy or mount a permission-cleared source corpus.
2. Run a non-destructive plan command.
3. Review unsupported files, sensitive-looking paths, duplicate bytes, and format caveats.
4. Generate mirrors into `_mirrors/` without writing beside original Office files.
5. Review manifests and audit logs.
6. Create a small number of curated hubs and entity pages.
7. Answer predefined operational questions with citations back to source paths and mirrors.
8. Rerun status/sync after source changes.
9. Use lifecycle states to identify stale, missing, moved, conflicted, or manually modified mirrors.
10. Keep all client/private evidence outside the public Vaultwright codebase.

The product should optimize for this repeatable loop, not for one-time knowledge-base generation.

## 10. Mirror Lifecycle and Agent Permissions

Mirror lifecycle semantics are now a P0 product requirement.

Target lifecycle:

```text
source inventory
  -> planned
  -> mirrored clean
  -> source changed
  -> stale
  -> regenerated
  -> reviewed
```

Important states:

- `unsupported`
- `source_missing`
- `source_moved`
- `conflict`
- `manual_modification`
- `converter_changed`
- `error`

The Office mirror implementation maintains a source manifest with stable source IDs. The repo mirror
implementation maintains a repo manifest with stable repo IDs. These manifests make path-based
sync safer, but the UX remains early.

Manifest fields now include or are expected to include:

- stable source/repo ID;
- current source path or repo URL/path;
- mirror path;
- source hash or repo tree/HEAD hash;
- extracted-content hash where applicable;
- converter name/version where applicable;
- configuration version;
- last successful sync;
- lifecycle state;
- warnings, omissions, and errors.

Agent permissions should remain conservative:

- Agents may regenerate mirrors.
- Agents may propose curated-note edits.
- Agents may update machine-owned frontmatter.
- Agents may resolve links when the target is unambiguous.
- Agents may not silently overwrite human-maintained notes.
- Agents may not move, delete, or consolidate records without review.
- Agents may not make uncited factual claims in durable notes.
- Agents may not cross client boundaries.

## 11. Security and Governance Model

Current repository hygiene is stronger than typical alpha software:

- no-data scanner;
- staged pre-commit guard;
- OOXML metadata scanning;
- symlink blocking;
- path and extension checks;
- provenance allowlists for examples;
- CI regeneration tests;
- generated-output isolation under `_mirrors/`;
- explicit public-example provenance ledger.

That is not the same as full operational security readiness. A client-facing deployment still needs
to address:

- whether source data is processed locally or sent to cloud model providers;
- local-model options;
- malicious instructions embedded in source documents;
- unsafe Office files and macros;
- Obsidian community plugin risk;
- shared-folder, Git, or file-sync deployment trade-offs;
- filesystem permissions and cross-client isolation;
- backup, restoration, and secure deletion;
- agent write privileges;
- connector permissions;
- log contents;
- retention and recovery expectations.

Professional-services use should begin with a conservative operating model:

- one client or engagement per vault;
- one permission-cleared source copy per pilot;
- no secrets or client data committed to Git;
- generated mirrors reviewed before curated conclusions are written;
- cloud AI use documented explicitly in the engagement plan;
- pilot evidence anonymized before any public use.

## 12. Current Progress

| Area | Current status | Assessment |
| --- | --- | --- |
| Product positioning | Narrowed to governed document-to-markdown lifecycle with agent-ready substrate as the future direction | Stronger than generic AI wiki framing |
| Information architecture | Function-based folder structure with configurable domain map | Better cross-industry baseline |
| Mirror storage | Office mirrors and optional text-based PDF mirrors live under `_mirrors/` | Fixes messy source-folder problem |
| Office sync | Plan/sync/status, manifest, audit events, manual-edit detection, lifecycle next-action guidance | Useful alpha foundation |
| Repo sync | Plan/sync/status, repo manifest, audit events, manual-edit detection, lifecycle next-action guidance | Useful for code/source repositories |
| CLI | Vault-local wrapper and source-installable `vaultwright` entry point; CI now installs the built wheel and verifies packaged init, doctor, plan, benchmark, conversion, migration, and JSON recovery delegation; doctor reports dependency, manifest, audit, recovery-action counts, git, and GitHub-auth posture; conversion, migration, and recovery print read-only operator checklists | Better operator ergonomics; tagged release publishing still needs hardening |
| Examples | Government-services showcase plus Northwind regression fixture | Better demo plus stable tests |
| Provenance | Public fixture ledger with source URLs, licence posture, and review date | Good discipline; must be maintained |
| Safety | No-data scanner, pre-commit hook, CI checks | Strong for repository hygiene |
| Docs | Product, sync, security, recovery, protocol, and white paper | Much clearer reviewer surface |
| Tests | Unit/integration tests cover core sync, lint, examples, package CLI, and safety scans | Good engineering baseline |

## 13. Evidence and Known Gaps

Current evidence is encouraging but limited.

| Evidence | Current result | Interpretation |
| --- | --- | --- |
| Unit/integration tests | Current pytest suite passing locally and in CI on 2026-06-20 | Good engineering baseline; not product validation |
| Template lint | Clean in prior validation | Template schema is internally consistent |
| Example regeneration | Northwind and government examples regenerate in temp copies | CI can verify mirrors without committing generated residue |
| Government showcase | Canadian business registration, GST/HST, CRA account, and funding/support fixtures | Better demonstration of a consulting-relevant pain point |
| Office source manifest | Stable source IDs, hashes, mirror paths, lifecycle states, audit events, missing/manual-edit detection | Important lifecycle foundation, not finished operator UX |
| Conversion spot-check report | Read-only manifest report prioritizes high/medium/low conversion review items from states, warnings, errors, formats, and source/mirror existence | Useful pilot checklist; not a quantitative conversion-quality score |
| Repo source manifest | Stable repo IDs, local-tree/remote-HEAD hashes, audit events, manual-edit detection | Useful coverage for repo mirrors |
| Source-installable CLI | Console entry point delegates to vault-local tools and supports source-checkout `init` | Good development ergonomics |
| Private dogfood | Small copied corpus produced mirrors without source-folder clutter | Useful smoke test only |

Known gaps:

- No external design partner has completed the workflow.
- No benchmark covers hundreds or thousands of mixed client files.
- No quantitative conversion-quality score exists yet; the current conversion report is a
  conservative checklist, not automated quality measurement.
- No retrieval task measures before/after usefulness.
- No benchmark yet proves that AI agents perform better against Vaultwright-generated markdown than
  against raw source folders or ad hoc document-chat outputs; `docs/AGENT_READINESS_BENCHMARK.md`
  defines the required comparison protocol.
- No independent security review has been completed.
- No distribution-quality package release exists.
- No formal support model, pricing, or consulting statement of work exists.

## 14. Risk Register

| Risk | Severity | What could go wrong | Mitigation |
| --- | --- | --- | --- |
| Source-data leakage | High | Real client data gets committed or exposed | Keep no-data scans, hooks, CI, private pilot workspaces, and provenance rules mandatory |
| Overclaiming product readiness | High | Reviewers perceive alpha software as production-ready | Maintain explicit alpha status and release gates |
| Conversion quality gaps | High | Mirrors miss table/image/formula/comment meaning | Add conversion caveats, spot checks, quantitative scoring, and format-specific fallback paths |
| Lifecycle confusion | High | Users cannot tell whether a mirror is stale, moved, or manually changed | Continue manifest-backed lifecycle states and recovery UX |
| Tax/legal interpretation risk | High | Users mistake generated notes for official advice | Keep citations, disclaimers, review workflow, and source authority clear |
| AI note proliferation | Medium | The vault becomes another pile of generated files | Use warning-level similarity/overlap linting and stricter hub/entity workflow |
| Agent over-automation | Medium | Agents treat generated markdown as final authority and skip source/provenance review | Preserve source links, manifests, sentinel boundaries, and human review gates |
| Public-source licence drift | Medium | External source terms change or are misapplied | Keep dated provenance reviews and avoid copying protected content |
| Narrow demo domain | Medium | Government example is useful but not company-specific | Add later domain packs only after lifecycle proof |
| Packaging friction | Medium | Users struggle to install or run the CLI | Harden package release and golden-path docs |
| Obsidian dependency perception | Low/Medium | Buyers think Vaultwright requires a specific UI | Keep filesystem/schema correctness independent of Obsidian |

## 15. Release Gates

Recommended v0.1 gates:

| Gate | Required standard |
| --- | --- |
| Source integrity | Original files remain byte-for-byte unchanged |
| Idempotency | A second sync with no source changes produces no content diff |
| Lifecycle | Rename, move, delete, stale, conflict, error, and manual-modification states are tested |
| Provenance | Every mirror resolves to an identifiable source |
| Auditability | Every generated change can be explained from manifest/log evidence |
| Conversion | At least 95% of declared-supported pilot files complete without manual repair |
| Usability | A new operator completes the golden path through CLI/docs |
| Validation | At least three independent external users and multiple corpora |
| Security | Published threat model and focused code/security review |
| Recovery | Backup and restoration procedure documented and tested |
| Commercial readiness | A scoped implementation offer, support boundary, and pricing hypothesis exist |

## 16. Execution Plan

### Phase 0 - Current Batch Closure

Goal: finish the repo hardening batch without pretending external validation has happened.

Deliverables:

- government-services example aligned to business registration, GST/HST, account access, and
  funding/support;
- detailed white paper for consulting review;
- read-only manifest recovery checklist;
- local validation of tests, linting, no-data scan, and generated-output residue;
- no-context strict reviewer pass over the uncommitted worktree;
- changelog and docs aligned with actual behavior.

Exit criteria:

- full validation passes locally;
- reviewer findings are resolved or documented honestly;
- final status clearly distinguishes completed engineering work from remaining validation work.

### Phase 1 - Alpha Pilot Readiness

Goal: make one trained operator able to run Vaultwright on a permission-cleared copied corpus.

Deliverables:

- tagged release publishing and published-artifact install verification;
- continued `doctor` expansion for Obsidian/plugin checks and deeper backup posture;
- deeper lifecycle recovery UX beyond current read-only recovery checklist;
- pilot-calibrated migration runbooks for legacy folder layouts;
- conversion spot-check report plus operator guide;
- pilot worksheet based on `docs/DESIGN_PARTNER_PROTOCOL.md`;
- sample statement-of-work outline for consulting delivery.

Exit criteria:

- a new operator can complete `init -> plan -> sync -> status -> lint` from docs;
- no source files are changed;
- status output explains lifecycle warning/error direction without code inspection.

### Phase 2 - Design-Partner Validation

Goal: prove usefulness on real client-shaped document collections.

Pilot requirements:

- at least three independent users or teams;
- multiple corpora across at least two business contexts;
- 50 to 2,000 source files per corpus;
- mixed Office, PDF, markdown/text, spreadsheet, deck, and optional repo sources;
- no real pilot data committed to this repository.

Metrics:

- source file count and total size;
- supported, unsupported, skipped, errored, and warning counts;
- first-sync duration;
- second-sync idempotency;
- conversion exceptions by file type;
- manual correction count and time;
- provenance spot-check pass/fail rate;
- stale or missing source detection after changes;
- time to answer fixed operational questions before/after;
- operator confidence score;
- support time required.

Exit criteria:

- pilots produce measurable time savings or quality improvement;
- recurring failure modes are understood;
- product roadmap is based on evidence rather than assumptions.

### Phase 3 - v0.1 Release

Goal: release a technically honest, scoped product.

Deliverables:

- tagged package release;
- hardened CLI docs;
- release notes with known limitations;
- security and no-data posture documented;
- recovery workflow tested;
- one or more anonymized pilot summaries;
- public demo using the government-services vault.

Exit criteria:

- release gates in Section 15 are met or explicitly deferred with rationale;
- claims in README, docs, and marketing copy match demonstrated behavior.

### Phase 4 - Commercialization

Goal: turn the validated workflow into a repeatable consulting offer.

Deliverables:

- implementation package;
- engagement checklist;
- data-handling terms;
- pricing hypothesis;
- support and maintenance boundary;
- optional private/commercial licence path;
- case-study template.

Exit criteria:

- consulting buyers can understand what is included, what is excluded, and what evidence supports
  the offer.

## 17. Consulting Offer Shape

The clearest initial business model is open source plus paid implementation services.

Potential offer:

1. Document and risk inventory.
2. Non-destructive migration plan.
3. Vaultwright setup.
4. Mirror generation and exception review.
5. First maps of content and entity pages.
6. Operator training.
7. Governance and refresh schedule.
8. Post-implementation review.

Possible deliverables:

- initialized Vaultwright vault;
- mirror manifest and audit log review;
- source inventory summary;
- exception register;
- curated starter hubs;
- operating questions answered with citations;
- refresh runbook;
- risk and retention notes;
- follow-up roadmap.

This should be sold as an implementation and governance engagement first, not as a fully automated
AI transformation promise.

## 18. Benchmark Protocol

The design-partner benchmark should compare before and after.

Baseline questions:

- How long does intake take today?
- Which document types are hardest to inspect?
- Where does provenance get lost?
- What must never leave the client environment?
- What recurring questions does the team answer from these documents?

Vaultwright tasks:

- run non-destructive plan;
- review risk warnings;
- sync mirrors;
- inspect generated mirrors;
- create or review initial hubs;
- answer fixed operational questions with citations;
- modify/move selected source files;
- rerun status/sync;
- record lifecycle results.

Outcome measures:

- time saved;
- confidence in answers;
- number of unsupported files;
- number of conversion defects;
- number of manual corrections;
- quality of citations;
- ease of repeat sync;
- willingness to use the workspace again one week later.

## 19. Open Questions

Important unresolved questions:

- What conversion-quality threshold is acceptable for consulting delivery?
- Which source formats create the most support burden?
- Should PDF extraction have tiers such as text-only, OCR, and table-aware modes?
- How much domain-specific taxonomy is useful before it becomes rigid?
- What should the first commercial support boundary include?
- Which AI providers or local models are acceptable for early pilots?
- How should source permissions and client data boundaries be represented in the vault?
- What is the minimum useful UI beyond CLI and Obsidian?
- What evidence will convince professional consulting reviewers that the workflow is repeatable?

## 20. Technical Implementation Appendix

Available today:

- Template vault with function-based folders and Obsidian-compatible schema.
- Dedicated `_mirrors/` storage for Office mirrors and optional text-based PDF mirrors.
- Office source manifest at `_meta/source-manifest.json`, plus non-mutating `--plan` and
  manifest-backed `--status`.
- Repo mirrors under `80_sources/repos/`.
- Repo source manifest at `_meta/repo-manifest.json`, plus repo `--plan` and `--status`.
- Machine-readable sync audit events in `_meta/sync-audit.jsonl`.
- Thin `tools/vaultwright.py` wrapper for `plan`, `sync`, `status`, `lint`, and `doctor`.
- Source-installable `vaultwright` console entry point via `pyproject.toml`.
- Warning-level plan risk reporting for sensitive-looking paths, duplicate bytes, and
  format-specific conversion caveats.
- Recovery guide and design-partner validation protocol.
- Domain map and mirror config.
- Linter for frontmatter, domain/folder placement, mirror presence, mirror layout, and metadata
  consistency.
- No-data scanner with staged and default modes, provenance allowlists, OOXML scanning, path checks,
  and symlink blocking.
- CI that compiles tools, runs tests, scans data, and regenerates example mirrors in temp copies.
- Public examples and provenance ledger.

Experimental or partially defined:

- Combined mirror files with curated notes above a sentinel.
- Agent-maintained curated-note workflows.
- Private dogfood on an existing corpus copy.
- Government-services showcase as a public demo of advisory workflows.
- Pilot-calibrated migration guidance for legacy folder/domain structures.
- Quantitative conversion-quality scoring beyond the current read-only spot-check report.

Roadmap:

- Full lifecycle transitions for rename, move, stale, conflict, converter change, and recovery.
- Distribution-quality `vaultwright` packaging.
- Richer quantitative conversion-quality scoring beyond checklist-based spot checks.
- Recovery tests and external design-partner execution.
- Higher-fidelity PDF/spreadsheet extraction tiers.
- Better similarity/overlap scoring calibrated by design-partner corpora.
- Typed links and richer evidence relationships.
- Agent-readiness benchmarks comparing raw source folders, document-chat transcripts, and
  Vaultwright-generated markdown for question answering, reconciliation, update, and audit tasks,
  using `docs/AGENT_READINESS_BENCHMARK.md`.
- External design-partner evidence.

## 21. Bottom Line

Vaultwright should continue, but it should stay narrow. The architecture is credible because raw
sources stay intact, generated mirrors are isolated, provenance is visible, and governance is built
into the workflow. The government-services example is a stronger public demo because it shows a
realistic business pain point without exposing confidential records.

The next milestone is not more polish. The next milestone is proof: repeated synchronization of
real, permission-cleared client-shaped document collections must create a trustworthy,
maintainable evidence workspace that operators and AI agents can actually use.

If that proof emerges, Vaultwright can become both a credible consulting offer and a viable
software product. If it does not, additional AI features, templates, dashboards, or agent wrappers
will not compensate.
