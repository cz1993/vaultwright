# Vaultwright

**Turn your AI coding agent into the maintainer of a connected markdown knowledge base for
running your business.**

Vaultwright is a methodology + a small toolkit. You bring an AI coding agent (Claude Code,
OpenAI Codex, etc.), [Obsidian](https://obsidian.md), and your real business files. Vaultwright
gives the agent a disciplined operating manual so it behaves like a **wiki maintainer**, not a
chatbot — filing, linking, summarizing, and keeping everything current in plain markdown you own.

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
   idempotent). The original stays the source of truth; the mirror is searchable, linkable, and
   visible in your graph. Your hand-written notes in each mirror are preserved across syncs.
2. **Linking-first retrieval.** Maps of Content, entity pages, backlinks, and a frontmatter-driven
   index (Obsidian **Bases**) *are* the retrieval engine — no vector database needed at
   small-business scale. Connections defeat the silos and build the index for free.
3. **Anti-proliferation discipline.** The agent is told to **consolidate and update before
   creating**, and a linter flags near-duplicate and stale notes. Restraint is a feature.
4. **Governance for real business records.** PII isolation, a retention policy, and
   secrets-stay-out-of-the-vault — because this holds finance, legal, and client data, not just
   personal notes.

## Who it's for

Technical founders and small-business owners who already know git and can run a project, and who
want their docs and projects organized and *kept* organized by an AI agent — without handing their
data to a SaaS black box.

## How it works (three layers)

| Layer | What | Who owns it |
| --- | --- | --- |
| **Raw sources** | the real artifacts — contracts, decks, statements, repos, the original Office files | you / external; never altered |
| **Wiki** | markdown notes that summarize, link, and add metadata — MOCs, entity pages, and the auto-generated mirrors | the agent writes; you curate |
| **Schema** | `CLAUDE.md` — conventions + the ingest/query/lint workflows that make the agent disciplined | you + agent co-evolve |

Full write-up: [`docs/methodology.md`](docs/methodology.md).

## Quick start

```bash
git clone <this-repo> vaultwright && cd vaultwright
bash scripts/init.sh ~/my-business-vault     # scaffold a vault from template/
```

Then open the vault in Obsidian, point your agent at it (it reads `CLAUDE.md` first), and:

```bash
cd ~/my-business-vault
pip install -r tools/requirements.txt        # markitdown + pyyaml
python3 tools/sync_office_md.py              # mirror your Office files
# edit tools/repos.yml, then:
python3 tools/sync_github_repos.py           # mirror your GitHub repos
python3 tools/lint_vault.py                  # health check
```

Step-by-step: [`docs/quickstart.md`](docs/quickstart.md).

## Status

**v0 — early.** The template vault, the schema, and the three tools work today. A CLI
(`vaultwright init/sync/lint/doctor`) is on the roadmap ([`cli/README.md`](cli/README.md)).

## License

AGPL-3.0 for the open core, with a separate **commercial license** for enterprise/closed use, and
consulting available. See [`LICENSE`](LICENSE) and [`LICENSING.md`](LICENSING.md). "Vaultwright" is
a trademark — see [`TRADEMARK.md`](TRADEMARK.md).

## Credits

The "LLM wiki" pattern (Andrej Karpathy), [markitdown](https://github.com/microsoft/markitdown)
(Microsoft), and [Obsidian](https://obsidian.md). Interoperates with — rather than competes with —
tools like [basic-memory](https://github.com/basicmachines-co/basic-memory) and Copilot for
Obsidian.
