# Vaultwright

**Turn an existing business document collection into governed, inspectable, agent-ready markdown
without modifying the original records.**

Vaultwright is a pre-release methodology + small toolkit for consultants and operators who need to
preserve source documents while making their contents usable by people and AI agents. You bring
source files, a local vault, an AI coding agent (Claude Code, OpenAI Codex, etc.), and optionally
[Obsidian](https://obsidian.md) as the reference human UI.

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
   PDF mirrors are available with `sync_office_md.py --include-pdf`. The original stays the source
   of truth; the mirror is searchable, linkable, diffable, and easier for agents to inspect than
   opaque binaries. Your hand-written notes in each mirror are preserved across syncs.
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

## How it works (four layers)

| Layer | What | Who owns it |
| --- | --- | --- |
| **Raw sources** | the real artifacts — contracts, decks, statements, repos, the original Office files | you / external; never altered |
| **Generated mirrors** | markdown mirrors under `_mirrors/` and repo mirrors under `80_sources/repos/` | the agent writes; you curate above the sentinel |
| **Wiki** | markdown notes that summarize, link, and add metadata — MOCs, entity pages, decisions, guides | the agent writes; you curate |
| **Schema** | `CLAUDE.md` — conventions + the ingest/query/lint workflows that make the agent disciplined | you + agent co-evolve |

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

## Quick start

```bash
git clone <this-repo> vaultwright && cd vaultwright
bash scripts/init.sh ~/my-business-vault     # scaffold a vault from template/
```

Then open the vault in Obsidian, point your agent at it (it reads `CLAUDE.md` first), and:

```bash
cd ~/my-business-vault
python3.11 -m pip install -r tools/requirements.txt  # markitdown + pyyaml
python3.11 tools/vaultwright.py plan                 # inspect proposed mirror actions first
python3.11 tools/vaultwright.py sync                 # mirror Office files and configured repos
python3.11 tools/vaultwright.py status               # review manifest-backed lifecycle state
python3.11 tools/vaultwright.py conversion --guide   # read-only conversion spot-check + guide
python3.11 tools/vaultwright.py migration            # dry-run report for legacy/unknown folders
python3.11 tools/vaultwright.py recovery             # read-only recovery checklist from manifests
python3.11 tools/vaultwright.py sandbox --source-root /path/to/original-documents
python3.11 tools/vaultwright.py catalog              # generate CATALOG.md inventory gateway
python3.11 tools/vaultwright.py catalog --html       # generate CATALOG.html visual inventory gateway
python3.11 tools/vaultwright.py m365                 # Microsoft 365/Copilot handoff readiness
python3.11 tools/vaultwright.py review --json        # summarize metadata-only human review decisions
python3.11 tools/vaultwright.py pilot                # aggregate pilot evidence, no source content
python3.11 tools/vaultwright.py pilot --worksheet    # redacted Markdown private-pilot summary
python3.11 tools/vaultwright.py benchmark            # validate agent-readiness task pack, if present
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
vaultwright --root ~/my-business-vault plan
```

Step-by-step: [`docs/quickstart.md`](docs/quickstart.md).

## Status

**v0 — technical alpha.** The template vault, schema, thin tool CLI, source-installable console
entry point, sync/lint tools, examples, safety guards, Office/repo manifests, and audit logs work
today. Product validation, full lifecycle semantics, and distribution-quality packaging remain open
pre-release work.

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
