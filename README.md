# Vaultwright

**Compile source collections into governed, profile-driven knowledge workspaces without modifying
the original records.**

Vaultwright is a pre-release methodology + small toolkit for source-backed knowledge workspaces.
The first commercial wedge remains consulting and implementation teams with document-heavy client
work, but the core is now converging toward profile-driven workspaces for business operations,
research/learning, software-project documentation, and minimal blank starts. You bring source files,
a local vault, an AI coding agent (Claude Code, OpenAI Codex, etc.), and optionally
[Obsidian](https://obsidian.md) as a reference human UI.

> Inspired by Andrej Karpathy's ["LLM wiki" pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).
> Honest about the landscape — see [`docs/positioning.md`](docs/positioning.md).

## The problem

- **Silos.** Your contracts, decks, spreadsheets, repos, and notes don't know about each other.
- **"When everything is documented, nothing is."** Naive AI doc-generation *spawns* files until
  the pile is unusable.
- **RAG re-derives every time.** Chat-over-your-files tools answer from a vector index and forget;
  nothing is *built up*.

## What makes Vaultwright different

Most "AI second brain in Obsidian" projects stop at the wiki pattern. Vaultwright leads with the
parts nobody else ships:

1. **The mirror layer.** Your Office files (`.docx/.pptx/.xlsx`, via Microsoft
   [markitdown](https://github.com/microsoft/markitdown)) and your **GitHub repos** get
   auto-generated markdown **mirrors** that refresh when the original changes (content-hashed,
   idempotent). Office mirrors live under `_mirrors/` so raw source folders stay clean; text-based
   PDF mirrors are available with `sync_office_md.py --include-pdf` or by setting
   `office_mirrors.include_pdf: true` in `_meta/mirror-config.yml` for unattended syncs. The
   original stays the source of truth; the mirror is searchable, linkable, diffable, and easier for
   agents to inspect than opaque binaries. Generated mirrors are machine-owned; durable human notes
   belong in curated notes or migrated `_meta/mirror-annotations/` sidecars.
2. **Linking-first retrieval.** Maps of Content, entity pages, backlinks, and a frontmatter-driven
   index (Obsidian **Bases**) are the initial retrieval engine. `vaultwright catalog` also
   generates a path-and-metadata-only `CATALOG.md` gateway for reviewers and agents that do not use
   Obsidian. Vector or semantic indexes may help later, but they are not the source of truth.
3. **Anti-proliferation discipline.** The agent is told to **consolidate and update before
   creating**, and the linter flags structural drift plus likely note overlap with review-only
   consolidation suggestions. Restraint is a feature.
4. **Governance for real business records.** PII isolation, a retention policy, and
   secrets-stay-out-of-the-vault — because this holds finance, governance, customer, people, and
   operational records, not just personal notes.

## Who it's for

Small consulting, advisory, implementation, and operations teams that receive messy client or
engagement document collections and need to turn them into governed, source-linked operating
knowledge. Owner-operators may benefit later, but the first release is scoped around teams that
already understand provenance, engagement boundaries, and source preservation.

## How it works (six layers)

| Layer | What | Who owns it |
| --- | --- | --- |
| **Sources** | original files, repositories, exports, and external records | authoritative; never altered by Vaultwright |
| **Mirrors** | machine-generated Markdown and extraction metadata | derived, reproducible artifacts |
| **Curated knowledge** | human-reviewed notes, syntheses, entities, and decisions | human-governed |
| **Profile** | domain vocabulary, schemas, templates, views, skills, and benchmarks | versioned contract |
| **Evidence index** | future full-text/graph cache for retrieval and context assembly | disposable derived cache |
| **Presentation** | Obsidian, catalogs, Canvas, Explorer, MCP, and context packs | derived interfaces |

Product contract: [`docs/PRODUCT.md`](docs/PRODUCT.md). Sync contract:
[`docs/SYNC_SPEC.md`](docs/SYNC_SPEC.md). Security model:
[`docs/SECURITY_MODEL.md`](docs/SECURITY_MODEL.md). Recovery guide:
[`docs/RECOVERY.md`](docs/RECOVERY.md). Design-partner protocol:
[`docs/DESIGN_PARTNER_PROTOCOL.md`](docs/DESIGN_PARTNER_PROTOCOL.md).
Conversion review guide:
[`docs/CONVERSION_REVIEW_GUIDE.md`](docs/CONVERSION_REVIEW_GUIDE.md).
Release checklist:
[`docs/RELEASE.md`](docs/RELEASE.md).
Agent-readiness benchmark:
[`docs/AGENT_READINESS_BENCHMARK.md`](docs/AGENT_READINESS_BENCHMARK.md).
Full write-up: [`docs/methodology.md`](docs/methodology.md).
Professional review brief: [`docs/VAULTWRIGHT_WHITEPAPER.md`](docs/VAULTWRIGHT_WHITEPAPER.md).
Current v1 architecture decision:
[`docs/adr/0001-profile-driven-v1-architecture.md`](docs/adr/0001-profile-driven-v1-architecture.md).
Finish-line matrix: [`docs/V1_FINISH_LINE.md`](docs/V1_FINISH_LINE.md).

## Quick start

```bash
git clone <this-repo> vaultwright && cd vaultwright
bash scripts/init.sh ~/my-business-vault     # scaffold the business-operations template
```

Then open the vault in Obsidian, point your agent at it (it reads `CLAUDE.md` first), and:

```bash
cd ~/my-business-vault
python3.11 -m pip install -r tools/requirements.txt  # markitdown + pyyaml
python3.11 tools/vaultwright.py plan                 # inspect proposed mirror actions first
python3.11 tools/vaultwright.py sync                 # mirror Office files and configured repos
python3.11 tools/vaultwright.py status               # review manifest-backed lifecycle state
python3.11 tools/vaultwright.py conversion --guide   # read-only conversion spot-check + guide
python3.11 tools/vaultwright.py conversion --init-results # private quality review scaffold
python3.11 tools/vaultwright.py conversion --results _meta/conversion-quality-results.yml --require-reviewed # after filling scaffold
python3.11 tools/vaultwright.py migration            # dry-run report for legacy/unknown folders
python3.11 tools/vaultwright.py migration --runbook  # legacy folder move protocol
python3.11 tools/vaultwright.py migration --normalize-frontmatter-domains --worksheet # review domain alias cleanup
python3.11 tools/vaultwright.py recovery --worksheet # review manifest recovery actions
python3.11 tools/vaultwright.py sandbox --source-root /path/to/original-documents
python3.11 tools/vaultwright.py catalog              # generate CATALOG.md inventory gateway
python3.11 tools/vaultwright.py catalog --html       # generate CATALOG.html visual inventory gateway
python3.11 tools/vaultwright.py m365                 # Microsoft 365/Copilot handoff readiness
python3.11 tools/vaultwright.py review --json        # summarize metadata-only human review decisions
python3.11 tools/vaultwright.py overlap              # calibrate overlap thresholds without note bodies
python3.11 tools/vaultwright.py pilot                # aggregate pilot evidence, no source content
python3.11 tools/vaultwright.py pilot --worksheet    # redacted Markdown private-pilot summary
python3.11 tools/vaultwright.py benchmark            # validate agent-readiness task pack, if present
python3.11 tools/vaultwright.py benchmark --init-tasks    # create private task scaffold
python3.11 tools/vaultwright.py benchmark --worksheet     # print private benchmark run sheet
python3.11 tools/vaultwright.py benchmark --init-results  # create private result scaffold
python3.11 tools/vaultwright.py benchmark --results _meta/agent-readiness-results.yml --require-prompt-safety # after scoring
# edit tools/repos.yml, then:
python3.11 tools/sync_github_repos.py                # mirror your GitHub repos
python3.11 tools/vaultwright.py lint                 # health check
```

Run `sandbox` from a duplicated pilot vault, not the original document folder. It is read-only and
checks copy-boundary, mirror isolation, manifest/recovery readiness, and basic backup posture
without printing source paths or document text.

Use `review` after spot-checking mirrors, catalogs, or handoff reports. It appends metadata-only
decisions to `_meta/review-ledger.jsonl` with artifact hashes, so later changes are reported as
stale reviews instead of silently preserving old approvals.

From a source checkout, the pre-release console entry point is also available:

```bash
python3.11 -m pip install -e .
vaultwright profile list
vaultwright init --profile business-operations ~/my-business-vault
vaultwright --root ~/my-business-vault profile validate
vaultwright --root ~/my-business-vault profile diff 0.1.0
vaultwright --root ~/my-business-vault profile migrate --plan
vaultwright --root ~/my-business-vault migrate annotations --plan
vaultwright --root ~/my-business-vault plan
```

`business-operations` is the only packaged profile today. Research/learning, software-project, and
blank profiles are v1 finish-line work, so the CLI rejects them until their contracts and fixtures
exist.

Step-by-step: [`docs/quickstart.md`](docs/quickstart.md).

## Status

**v0 - technical alpha.** The template vault, schema, thin tool CLI, source-installable console
entry point, sync/lint tools, examples, safety guards, Office/repo manifests, and audit logs work
today. The v1 finish line is now fixed around package-owned runtime behavior, versioned profiles,
profile-aware views, and external validation before optional Explorer work becomes release-critical.

## License

Vaultwright is licensed under the GNU Affero General Public License v3.0 or later for the open
core, with a separate **commercial license** planned for enterprise/closed use and consulting.
`LICENSE` contains the full AGPL-3.0 text; commercial terms and contribution policy still require
owner/counsel finalization before accepting outside contributions. See [`LICENSING.md`](LICENSING.md).
"Vaultwright" is a trademark — see [`TRADEMARK.md`](TRADEMARK.md).

## Credits

The "LLM wiki" pattern (Andrej Karpathy), [markitdown](https://github.com/microsoft/markitdown)
(Microsoft), and [Obsidian](https://obsidian.md). Interoperates with — rather than competes with —
tools like [basic-memory](https://github.com/basicmachines-co/basic-memory) and Copilot for
Obsidian.
