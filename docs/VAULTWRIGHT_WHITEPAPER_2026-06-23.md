# Vaultwright Whitepaper

**Status:** strategic product revision and finite v1 execution brief
**Date:** 2026-06-23
**Repository reviewed:** `cz1993/vaultwright` at commit `2b9e79823f1ebac4b123fc434e478f82bb8d6c87`
**Audience:** maintainers, design partners, consulting operators, knowledge-management teams, and technical reviewers
**Review posture:** ambitious, practical, evidence-based, and deliberately scope-bounded

## 1. Executive Summary

Vaultwright should evolve from a business-specific document-vault template into a **profile-driven, governed knowledge workspace compiler**.

Its durable value is not the current folder taxonomy. Its durable value is the lifecycle:

1. inventory heterogeneous sources;
2. preserve originals as authoritative records;
3. generate inspectable markdown mirrors;
4. attach provenance, lifecycle state, and human review;
5. build a disposable local evidence index;
6. render domain-appropriate views for humans and agents;
7. refresh the workspace safely as sources change.

This lifecycle is useful beyond startups and consulting engagements. It can support research and learning collections, software-project documentation, reading and literature workflows, policy collections, due-diligence workspaces, and other source-backed knowledge domains.

The strategic expansion should follow one rule:

> **Generalize the engine, not the launch market.**

Vaultwright can become domain-agnostic at the product-architecture level while retaining a narrow commercial wedge. The current business-operations workflow should remain the flagship paid implementation path until other profiles show comparable evidence of value.

The four proposed ideas form a coherent stack when refined:

- **Profiles** define a workspace's domain vocabulary, folders, note types, views, workflows, and benchmark tasks.
- **Obsidian skills** provide an optional human-interface and agent-authoring adapter, not the correctness boundary.
- **A local evidence index** applies CodeGraph-like principles to documents and notes: incremental extraction, graph relationships, full-text retrieval, freshness, and bounded context assembly.
- **A visual Explorer** turns the catalog and index into a reviewable interface for navigation, provenance inspection, lifecycle health, and agent context selection.

The project must not implement these as four unrelated feature tracks. They should converge on one final v1 product:

> **Sources + profile → governed mirrors + evidence graph + human views + agent context packs.**

## 2. Decision Recommendation

Proceed with the strategic expansion, subject to five constraints.

1. Keep source preservation, provenance, review, and lifecycle semantics as the non-negotiable kernel.
2. Replace the hard-coded business taxonomy with a declarative profile contract.
3. Keep the first commercial buyer narrow even while the open-source product becomes broader.
4. Build the index before the advanced visual interface; the visual interface must be a view over shared data, not a separate source of truth.
5. Define v1 now and reject additions that do not directly complete it.

The revised product statement should be:

> **Vaultwright turns heterogeneous source collections into governed, profile-driven knowledge workspaces that humans and AI agents can inspect, navigate, cite, and refresh without replacing the original records.**

A shorter product line is:

> **Compile source collections into governed knowledge workspaces.**

## 3. Current Repository Assessment

The current repository is substantially stronger than an ordinary prototype. It now includes source and repository manifests, lifecycle contracts, audit events, conversion-review scaffolds, recovery reports, migration reports, overlap calibration, a review ledger, agent-readiness benchmark tooling, static Markdown and HTML catalogs, Microsoft 365 handoff guidance, package-template tests, release automation, safety scans, and a complete AGPL license.

The current `CATALOG.md` and `CATALOG.html` work is particularly relevant to the new direction. It already establishes a non-Obsidian, metadata-only presentation layer with lifecycle, format, domain, source, mirror, and repository summaries.

However, the repository also shows the main risk of the proposed expansion: **tool and concept proliferation**. The CLI exposes a growing collection of reports and workflows, while remaining report behavior still depends on scripts copied into each vault. The current linter also hard-codes some business-oriented content assumptions. Adding templates, indexing, skills, and visualization on top of that structure would multiply maintenance cost.

Therefore the next step is not to add four new feature families. The next step is to create a stable kernel into which profiles, adapters, indexes, and renderers can plug.

## 4. Refined Product Scope

“Any type of knowledge base” is too broad to be useful. Vaultwright should target **source-backed knowledge workspaces** with most of these characteristics:

- authoritative source files or repositories exist outside the curated notes;
- sources change over time;
- provenance matters;
- people and agents must retrieve and reconcile information;
- stale or conflicting knowledge creates meaningful risk or wasted effort;
- a durable, inspectable workspace is preferable to a transient chat transcript.

Vaultwright should not optimize for every note-taking use case. It does not need to replace journaling apps, lightweight personal notes, creative writing tools, task managers, or generic bookmark managers.

This boundary preserves differentiation. A simple reading list with no source lifecycle may not need Vaultwright. A literature-review workspace with PDFs, citations, claims, annotations, evolving synthesis notes, and agent-assisted retrieval does.

## 5. Horizontal Core, Vertical Profiles

### 5.1 Core kernel

The core should be domain-neutral and own only universal responsibilities:

- source inventory and disposition;
- source identity and hashing;
- mirror generation;
- lifecycle state transitions;
- provenance and audit events;
- human review records;
- schema validation;
- derived indexing;
- context-pack generation;
- safe migrations;
- renderer and adapter interfaces.

The core should not contain business folder names, business statuses, or business-specific note types.

### 5.2 Profile contract

A profile should be a declarative, versioned package, not a copied folder tree. A profile should define:

```yaml
schema_version: 1
id: research-learning
name: Research and Learning
profile_version: 1.0.0

domains: {}
note_types: {}
statuses: {}
required_properties: []
optional_properties: []
folder_plan: []
templates: []
views: []
skills: []
benchmark_tasks: []
policy_defaults: {}
```

A profile may contain:

- `profile.yml` — identity, compatibility, and schema;
- `domain-map.yml` — domain and folder vocabulary;
- `note-types.yml` — allowed note types and required fields;
- `statuses.yml` — workflow states and transitions;
- `templates/` — note templates;
- `views/` — Obsidian Bases, Canvas recipes, and catalog presets;
- `skills/` — profile-specific agent procedures;
- `benchmarks/` — representative evaluation tasks;
- `example/` — a synthetic, provenance-reviewed example corpus;
- `migration/` — mappings from earlier profile versions.

Profiles should be declarative in v1. They should not execute arbitrary Python code.

### 5.3 Official v1 profiles

Ship exactly three maintained content profiles plus a minimal blank starter:

#### `business-operations`

This is the existing governance, market, customers, delivery, operations, finance, people, and sources structure. It remains the flagship consulting and implementation profile.

#### `research-learning`

This combines the proposed learning and reading-list ideas. Suggested domains include:

- inbox;
- sources and literature;
- concepts;
- questions;
- projects;
- syntheses;
- reading queue;
- archive.

Typical note types include source, literature note, concept, question, experiment, synthesis, course, and project. A standalone reading-list profile is unnecessary; it is a view and workflow within this profile.

#### `software-project`

This supports repositories and engineering documentation without attempting to replace a semantic code index. Suggested domains include:

- product and requirements;
- architecture;
- decisions and ADRs;
- APIs and interfaces;
- runbooks;
- releases;
- incidents;
- repositories and source references.

CodeGraph or another code-intelligence provider may be used as an optional adapter for symbol-level code context.

#### `blank`

A minimal profile for advanced users contains only inbox, sources, mirrors, metadata, templates, and views. It is not marketed as a complete methodology.

### 5.4 What “enterprise” means

“Enterprise” should not be an information-architecture profile. Enterprises do not share one taxonomy. Enterprise requirements concern deployment and control:

- identity and access;
- policy enforcement;
- retention;
- sensitivity labels;
- audit export;
- connector governance;
- multi-workspace administration;
- support and service levels.

These belong in future policy and deployment packs, not in the v1 profile list.

### 5.5 Profile commands

The v1 CLI should expose a small, stable surface:

```text
vaultwright init --profile business-operations <path>
vaultwright profile list
vaultwright profile show
vaultwright profile validate
vaultwright profile diff <target-profile-version>
vaultwright profile migrate --plan
```

A public profile marketplace is explicitly out of scope for v1. Third-party profiles can be loaded from local paths after the profile contract stabilizes.

## 6. Obsidian Integration Strategy

The `kepano/obsidian-skills` project is an excellent interoperability reference. It provides Agent Skills for Obsidian-flavored Markdown, Bases, JSON Canvas, the Obsidian CLI, and web extraction. These skills teach agents how to produce valid Obsidian artifacts; they do not provide Vaultwright's provenance, lifecycle, review, or safety model.

Vaultwright should integrate at three levels.

### 6.1 Use, do not duplicate, syntax expertise

Vaultwright should declare compatibility with the Obsidian skills and provide an installer or setup report rather than copying their entire content by default.

```text
vaultwright obsidian doctor
vaultwright obsidian install-skills --agent codex
vaultwright obsidian install-skills --agent claude
```

Pin the tested skill version in a lock file and record attribution. Because the referenced project is MIT-licensed, vendoring is possible, but external installation is preferable until Vaultwright needs a controlled fork.

### 6.2 Add Vaultwright-specific governance skills

Create a small first-party skill pack that composes with the Obsidian syntax skills:

- `vaultwright-ingest`;
- `vaultwright-explore`;
- `vaultwright-review`;
- `vaultwright-consolidate`;
- `vaultwright-visualize`.

These skills should describe permissions, evidence requirements, lifecycle handling, and profile rules. They should not repeat generic Markdown, Bases, or Canvas documentation.

### 6.3 Generate profile-aware Obsidian views

Each official profile should ship:

- a home Base;
- stale/review-required views;
- source and mirror views;
- profile-specific tables or cards;
- a generated Canvas recipe for a selected topic, project, or evidence chain.

Obsidian remains an optional presentation adapter. Vaultwright correctness must remain testable without opening Obsidian.

### 6.4 Do not build an Obsidian plugin for v1

A plugin would add TypeScript, release, compatibility, permissions, and UI-support obligations before the workflow is externally validated. Use generated files and the optional Obsidian CLI first. Build a plugin only when pilots identify a task that cannot be solved well through Bases, Canvas, generated Markdown, or the Vaultwright Explorer.

## 7. Local Evidence Index

CodeGraph demonstrates several principles worth adapting:

- precompute structure instead of rediscovering it on every query;
- keep the index local;
- update incrementally;
- store relationships as a graph;
- combine graph traversal with full-text search;
- expose one high-quality exploration tool rather than many overlapping tools;
- return bounded, relevant context with freshness information.

CodeGraph itself is specialized for source code. It extracts symbols and call edges using language parsers. Vaultwright should not fork that implementation into a general-document product.

### 7.1 Evidence-index model

Vaultwright's derived index should contain nodes such as:

- source file;
- generated mirror;
- curated note;
- heading or block;
- entity;
- collection or project;
- tag;
- review decision;
- repository;
- benchmark task.

Edges should include:

- `mirrors`;
- `derived_from`;
- `cites`;
- `links_to`;
- `contains`;
- `mentions`;
- `belongs_to`;
- `supersedes`;
- `depends_on`;
- `reviewed_as`;
- `same_source_as`.

Every extracted edge needs provenance: source path, extraction method, timestamp or source hash, and confidence when heuristic.

### 7.2 Storage and authority

Use a local SQLite database with FTS5 and explicit graph tables for v1. Store it in a private derived cache outside normal vault synchronization, keyed by a stable vault ID.

The index is disposable. Markdown, manifests, profiles, and review records remain authoritative.

No vector embeddings are required for v1. Add semantic retrieval later only if benchmark evidence shows that full-text plus graph expansion is insufficient.

### 7.3 Incremental indexing

Index only changed files based on hashes and profile configuration. Index status should expose:

- last complete build;
- changed or deleted inputs;
- schema version;
- profile version;
- stale records;
- extraction warnings;
- source lifecycle state.

### 7.4 Exploration interface

Expose one primary command and one MCP tool:

```text
vaultwright index build
vaultwright index status
vaultwright explore "How is this decision supported?"
```

MCP:

```text
vaultwright_explore
```

The exploration result should contain:

- concise answer-oriented context;
- selected headings or file summaries;
- source and mirror paths;
- lifecycle and review state;
- graph paths explaining why items were selected;
- a token estimate;
- freshness warnings;
- prompt-safety guidance.

The tool should support a token budget and avoid silently mixing client or workspace boundaries.

### 7.5 Software-project adapter

For a software-project profile, Vaultwright may query CodeGraph through its CLI or MCP interface for symbol, dependency, and impact context. Vaultwright should preserve the higher-level evidence chain between code, documentation, ADRs, releases, and incidents while CodeGraph owns code-level semantic analysis.

## 8. Visual Explorer and Context Builder

RepoPrompt CE is now a useful open-source reference for context engineering. Its strongest transferable ideas are file-tree orientation, CodeMaps, selected context, token budgeting, multi-root workspaces, Git-diff awareness, and reviewable handoffs.

Vaultwright should not clone a code-centric native macOS application. It should build a cross-platform, read-only Explorer over its own profile and evidence models.

### 8.1 Explorer jobs

The Explorer must help a user complete concrete tasks:

1. understand what is in a workspace;
2. see which sources are current, stale, unsupported, or unreviewed;
3. follow evidence from a curated claim to its mirror and original source;
4. inspect conflicts, duplicates, and missing sources;
5. select a bounded context pack for an agent;
6. export a reviewable handoff.

A decorative force-directed graph alone does not satisfy these jobs.

### 8.2 Required v1 views

The v1 Explorer should provide four views:

- **Collection tree:** profile folders, sources, mirrors, curated notes, and repositories.
- **Evidence graph:** source–mirror–note–entity–review relationships.
- **Lifecycle dashboard:** clean, stale, missing, conflicted, unsupported, and review-required items.
- **Context builder:** selected evidence, token estimate, exclusions, source authority, and export.

### 8.3 Context packs

A context pack is a generated, reviewable handoff:

```yaml
schema_version: 1
question: "What supports the launch decision?"
profile: business-operations
selected_items: []
excluded_items: []
source_hashes: {}
lifecycle_warnings: []
review_state: {}
estimated_tokens: 0
```

Exports should be available as Markdown and JSON. Context packs are generated artifacts and must not become another authority layer.

### 8.4 Delivery sequence

Do not start with a desktop application.

1. Extend the existing catalog JSON as a stable view model.
2. Generate profile-aware Obsidian Canvas files.
3. Add a local read-only web Explorer bound to `127.0.0.1`.
4. Add context selection and export.
5. Consider a packaged desktop shell only after repeated external demand.

The existing `CATALOG.html` remains the portable snapshot for stakeholders who cannot run the Explorer.

## 9. Target Users and Go-to-Market

### 9.1 Product users

The domain-neutral product can serve:

- consulting and advisory teams;
- researchers and analysts;
- students and educators managing substantial source collections;
- software teams handling architecture, handoff, runbooks, and repository documentation;
- policy, compliance, and due-diligence teams;
- advanced individual knowledge workers with provenance-heavy collections.

### 9.2 First commercial buyer

The initial commercial buyer should remain a professional-services or implementation team with document-heavy work. This wedge has clearer willingness to pay, repeatable client corpora, and stronger demand for governance than a generic personal-knowledge market.

Broader profiles improve open-source adoption and evidence. They should not force simultaneous sales, support, and marketing motions.

### 9.3 Business model

The initial model remains:

- open-source core;
- official open profiles;
- paid implementation and migration;
- paid profile customization;
- paid governance and integration work;
- later commercial policy, administration, or deployment capabilities.

Do not make profile quantity the business. The valuable service is turning a real source corpus into a governed, validated workspace.

## 10. Architecture

The target architecture has six layers.

| Layer | Responsibility | Authority |
| --- | --- | --- |
| Sources | Original files, repositories, exports, and external records | Authoritative |
| Mirrors | Machine-generated Markdown and extraction metadata | Derived |
| Curated knowledge | Human-reviewed notes, syntheses, entities, and decisions | Human-governed |
| Profile | Domain vocabulary, schemas, templates, views, skills, and benchmarks | Versioned contract |
| Evidence index | Full-text and graph index for retrieval and context assembly | Disposable derived cache |
| Presentation | Obsidian, catalogs, Canvas, Explorer, MCP, and exported context packs | Derived interfaces |

### 10.1 Ownership correction

For v1, generated mirrors should become fully machine-owned. Human annotations should live in curated notes or source-ID-keyed sidecars rather than inside a file that is described as reproducible and disposable.

A migration command should preserve existing above-sentinel notes:

```text
vaultwright migrate annotations --plan
vaultwright migrate annotations --write
```

This simplifies source moves, regeneration, profile migration, indexing, and recovery.

### 10.2 Package architecture

Runtime code should live in the installed package, not in copied scripts inside every vault. A vault should contain configuration and content, not its own application fork.

Suggested package boundaries:

```text
vaultwright.core
vaultwright.profiles
vaultwright.sources
vaultwright.mirrors
vaultwright.lifecycle
vaultwright.index
vaultwright.explore
vaultwright.renderers
vaultwright.adapters.obsidian
vaultwright.adapters.codegraph
vaultwright.security
```

Existing vault-local tools may remain as compatibility shims for one migration cycle, then be removed.

## 11. Security and Governance

The expansion does not weaken current security principles.

- Source text remains untrusted evidence, not executable instruction.
- Indexes and context packs inherit the sensitivity of their sources.
- The local index must not send content to a network service by default.
- Profile packages are declarative and validated before installation.
- Third-party skills and adapters are pinned and attributed.
- Explorer binds to localhost by default and must not expose a workspace on the LAN without explicit configuration.
- One client, engagement, or protected boundary per workspace remains the conservative default.
- Derived caches are securely removable and excluded from Git.
- Context exports include source hashes and lifecycle warnings.

## 12. Validation Strategy

The existing agent-readiness benchmark should become profile-aware.

Run the same task families across profiles:

- answer;
- reconcile;
- update;
- audit;
- consolidate;
- orient;
- build a bounded context pack.

Compare:

1. raw sources;
2. raw mirrors without index;
3. Vaultwright profile plus catalog;
4. Vaultwright profile plus evidence index;
5. Vaultwright profile plus evidence index and curated knowledge.

Measure:

- answer correctness;
- citation accuracy;
- missed caveats;
- stale-source detection;
- context precision;
- reviewer correction effort;
- tool calls and elapsed time;
- context-pack token size;
- duplicate-note avoidance;
- prompt-safety violations;
- operator confidence.

The index and Explorer should be justified by measurable improvements, not by visual appeal.

## 13. Current Risks

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Generic-PKM dilution | High | Limit scope to source-backed, lifecycle-sensitive workspaces |
| Profile explosion | High | Ship three maintained profiles and no marketplace in v1 |
| Tool sprawl | High | Refactor into one package and reduce CLI surface before adding features |
| Schema fragmentation | High | Versioned profile contract with migrations and compatibility checks |
| Index becomes hidden authority | High | Keep it disposable and return provenance with every result |
| Visualization distracts from correctness | High | Build on the shared index and require task-based validation |
| Obsidian lock-in | Medium | Keep Obsidian as an adapter; retain catalogs, CLI, MCP, and web Explorer |
| CodeGraph duplication | Medium | Use an adapter for code semantics; keep Vaultwright focused on evidence lifecycle |
| Consumer support burden | Medium | Keep paid go-to-market focused on professional implementations |
| Scope never closes | Critical | Freeze a fixed v1 definition of done and reject non-gating work |

## 14. Finite v1 Execution Plan

The sequence below is intentionally gated. A later stage does not begin until the prior exit criteria are met.

### Stage 0 — Scope freeze and architecture decision

Deliverables:

- approve this product statement;
- approve the six-layer architecture;
- approve the v1 profile list;
- publish a v1 non-goals list;
- stop adding standalone report commands.

Exit criteria:

- one accepted architecture decision record;
- every open v1 issue mapped to a finish-line requirement;
- all other ideas moved to a post-v1 backlog.

### Stage 1 — Kernel and packaging convergence

Deliverables:

- move runtime logic into `src/vaultwright/`;
- replace copied runtime scripts with compatibility shims;
- define versioned core and profile schemas;
- make note types, statuses, required properties, roots, and views profile-driven;
- make mirrors machine-owned and migrate annotations;
- add workspace and profile migrations;
- preserve current lifecycle, catalog, review, recovery, safety, and benchmark behavior.

Exit criteria:

- installed wheel owns runtime behavior;
- no example or vault contains an independent application copy;
- current business vault migrates without source mutation or annotation loss;
- source integrity, idempotency, lifecycle, recovery, and security tests pass.

### Stage 2 — Official profiles

Deliverables:

- `blank` starter;
- `business-operations` profile migrated from the current template;
- `research-learning` profile with reading-list views;
- `software-project` profile with GitHub/repository documentation workflows;
- one synthetic example and benchmark task pack per maintained profile;
- profile validation and migration commands.

Exit criteria:

- all profiles initialize from the same core package;
- no profile-specific folder, type, or status is hard-coded in core code;
- profile fixtures pass identical lifecycle and safety tests.

### Stage 3 — Obsidian adapter and skills

Deliverables:

- Obsidian compatibility/doctor report;
- tested installer instructions for `kepano/obsidian-skills`;
- five Vaultwright governance skills;
- profile-specific Bases;
- generated Canvas evidence map;
- syntax and integrity tests for generated `.base` and `.canvas` files.

Exit criteria:

- each official profile opens with a usable home view in Obsidian;
- the same vault passes all core tests without Obsidian installed;
- no first-party Obsidian plugin is required.

### Stage 4 — Evidence index and exploration

Deliverables:

- local SQLite/FTS evidence index;
- incremental hash-based updates;
- documented node and edge schema;
- `index build`, `index status`, and `explore`;
- one MCP tool, `vaultwright_explore`;
- optional CodeGraph adapter for the software-project profile;
- benchmark comparison with and without the index.

Exit criteria:

- index deletion and rebuild produce equivalent query results;
- every returned item has provenance and freshness state;
- no cross-workspace retrieval is possible;
- benchmark shows a material improvement in at least context precision, citation quality, correction effort, or tool-call count.

Stage 4 is a binding product gate. If the benchmark shows a material improvement, choose the **v1 Explorer** finish line and continue to Stage 5. If it does not, choose the **v1 Core** finish line, remove the index from the release-critical path, and proceed directly to external validation with catalogs, profile views, and Obsidian integration. Do not keep iterating on the index indefinitely.

### Stage 5 — Explorer and context builder

Stage 5 runs only after the Stage 4 evidence gate selects the v1 Explorer path.

Deliverables:

- local read-only Explorer;
- collection tree;
- evidence graph;
- lifecycle dashboard;
- context basket with token estimate;
- Markdown and JSON context-pack export;
- profile-aware filters;
- retained static `CATALOG.html` export.

Exit criteria:

- Explorer reads the same index and profile contracts as CLI/MCP;
- no separate business logic exists in the UI;
- a user can orient, trace evidence, identify review items, and export a bounded context pack;
- accessibility and basic cross-platform browser testing pass.

### Stage 6 — External validation and v1 release

Run exactly three structured external pilots:

1. one business-operations corpus;
2. one research-learning corpus;
3. one software-project corpus.

Each pilot must complete initialization, inventory, sync, review, profile-aware navigation, change refresh, a recovery drill, and a reviewable handoff. On the v1 Explorer path, pilots must additionally complete index build, exploration, and context-pack export.

Release gates:

- original sources remain byte-for-byte unchanged;
- repeat sync is idempotent;
- profile migrations preserve curated knowledge;
- lifecycle states and recovery actions are understandable without code inspection;
- every generated answer, handoff, or context result is source-backed;
- no serious security finding remains unresolved;
- each pilot reports a measurable improvement in at least one target task;
- installation and upgrade work from a built release artifact;
- known limitations and support boundaries are published.

## 15. v1 Definition of Done

Stage 4 selects one of two terminal release definitions. Both are valid finished products; the project must not remain indefinitely between them.

### Mandatory v1 Core finish line

Vaultwright v1 Core is finished when all of the following exist and pass their gates:

1. one installable cross-platform core package;
2. one versioned profile contract;
3. three official content profiles plus a blank starter;
4. one safe migration path from the current business template;
5. machine-owned mirrors and preserved human annotations;
6. one Obsidian adapter and first-party governance skill pack;
7. profile-aware catalogs, Bases, and Canvas outputs;
8. three external profile pilots;
9. one tagged v1 release with upgrade, recovery, security, and support documentation.

### Conditional v1 Explorer finish line

When the Stage 4 benchmark gate passes, v1 additionally requires:

10. one disposable local evidence index;
11. one exploration CLI/MCP interface;
12. one read-only visual Explorer with context export.

When the Stage 4 benchmark gate fails, these three items move to the post-v1 research backlog and v1 Core closes without them.

After the selected finish line is met, the maintainer stops feature work, resolves release defects, publishes, and gathers usage evidence.

## 16. Explicit Post-v1 Backlog

The following are not v1 requirements:

- hosted SaaS;
- multi-user real-time collaboration;
- enterprise administration console;
- Obsidian plugin;
- public profile marketplace;
- mobile application;
- automatic OCR and high-fidelity layout extraction for every format;
- vector embeddings by default;
- autonomous note deletion or consolidation;
- email and mailbox ingestion;
- broad connector catalog;
- desktop application shell;
- automatic enterprise permission or retention enforcement.

New proposals enter this backlog unless they replace, rather than add to, a v1 requirement.

## 17. Bottom Line

The proposed direction is strategically sound when reframed as a coherent product architecture.

Vaultwright should not remain permanently tied to finance, HR, legal, and startup operations. Those concepts belong in one profile. The core opportunity is a governed compiler for source-backed knowledge workspaces.

The expansion succeeds only if it preserves the project's discipline:

- original records remain authoritative;
- generated layers remain inspectable and disposable;
- profiles are contracts, not forks;
- indexes accelerate retrieval but never become authority;
- views share one model;
- agent context is bounded and reviewable;
- every stage has an exit gate;
- v1 has a fixed finish line.

That product is broader than the current business template, but still specific enough to be defensible and finishable.

## References Reviewed

- Vaultwright repository: https://github.com/cz1993/vaultwright
- Vaultwright current whitepaper: https://github.com/cz1993/vaultwright/blob/main/docs/VAULTWRIGHT_WHITEPAPER.md
- Obsidian Agent Skills: https://github.com/kepano/obsidian-skills
- CodeGraph: https://github.com/colbymchenry/codegraph
- RepoPrompt documentation: https://repoprompt.com/docs
- RepoPrompt Community Edition: https://github.com/repoprompt/repoprompt-ce
