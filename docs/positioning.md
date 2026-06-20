# Positioning (the honest version)

Vaultwright's underlying pattern is **not novel**, and pretending otherwise would waste your time.
This page is the candid map of the landscape and where Vaultwright actually earns its place.

## The pattern is commoditized

Karpathy's "LLM wiki" gist (April 2026) crystallized "AI agent + `CLAUDE.md` schema + Obsidian +
ingest/query/lint + MOCs + anti-proliferation," and the open-source field implemented it within
weeks. Notable neighbors (stars approximate, mid-2026):

- **basic-memory** (~3k★, AGPL) — markdown + frontmatter + wikilinks + Obsidian, via an MCP server.
  Closest on *substrate*. Differs: knowledge accrues *from conversation*, schema is *inferred*, and
  it has **no binary/Office/GitHub mirror layer**.
- **claudesidian** (~2.4k★), **ballred/obsidian-claude-pkm** (~1.5k★), **AgriciDaniel/claude-obsidian**
  (~1.5k★, ships a curated-vs-auto `owner:` split), **SamurAIGPT/llm-wiki-agent** (~1.2k★, even
  markets "business/team intelligence") — personal/research "second brains" built on the same
  primitives.
- **Copilot for Obsidian** (~7k★) — the closest *product*; its v4 (summer 2026) brings Claude
  Code/Codex into the vault. A general harness, not an opinionated methodology — Vaultwright could
  run *on top of* it.
- **Khoj / AnythingLLM / NotebookLM / Onyx** — chat/RAG over your files; the artifact is a vector
  index, not a curated markdown wiki. The approach this methodology deliberately avoids.

## Where Vaultwright is differentiated

Not found in any surveyed competitor:

1. **Governed document-to-markdown lifecycle** — original files remain authoritative while
   generated mirrors, curated notes, schema, provenance, and safety checks stay inspectable.
2. **The mirror layer** — hash-refreshed markdown mirrors of **Office files *and* GitHub repos**,
   editable-original-stays-source-of-truth, with curated/auto separation under `_mirrors/`.
3. **Agent-ready substrate** — generated markdown gives coding agents plain-text, linkable,
   diffable context with manifests and sentinel boundaries instead of raw binary folders.
4. **Consulting/onboarding wedge** — the first buyer is a small consulting or advisory team
   handling document-heavy client work, not the broad personal-PKM market.
5. **Bases-driven index** — the dynamic index is generated from frontmatter, not hand-maintained.

## Interoperate, don't compete

- **Uses** markitdown (conversion) and Obsidian (UI) as dependencies, not rivals.
- **Sits alongside** basic-memory or Copilot — they can chat/recall; Vaultwright keeps the curated,
  governed, mirror-backed record.
- Works with any agent that reads a `CLAUDE.md`/`AGENTS.md` (Claude Code, Codex, …).

## Non-goals

- Not a vector-RAG chatbot over your files.
- Not a personal-PKM / Zettelkasten app (those are well served).
- Not a hosted SaaS (the enterprise/hosted offering is a *separate* commercial layer — see
  `LICENSING.md`).
- Not a fully validated product yet; lifecycle semantics and external design-partner evidence are
  release gates.

## Honest risks

- **Fast-moving field.** The pattern iterates weekly; a general harness could absorb the
  methodology as config. Defensibility rests on the **tooling + vertical**, not the schema doc.
- **Cheap to clone.** Instruction/skill files copy trivially — which is exactly why Vaultwright
  leads with the mirror system and governance.
- **Hard consumer market.** Personal-KB products have struggled (Quivr pivoted, Reor archived) —
  an argument *for* the narrower B2B-ops focus, not against the project.
