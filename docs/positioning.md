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

1. **The mirror layer** — hash-refreshed markdown mirrors of **Office files *and* GitHub repos**,
   editable-original-stays-source-of-truth, with curated/auto separation. This is real tooling, not
   a copyable prompt file — the hardest part to clone and the main moat.
2. **Small-business operations as the vertical** — finance / legal / clients / HR / funding, with
   **PII isolation and a retention policy**. Every competitor is a personal/research brain.
3. **Bases-driven index** — the dynamic index is generated from frontmatter, not hand-maintained.

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

## Honest risks

- **Fast-moving field.** The pattern iterates weekly; a general harness could absorb the
  methodology as config. Defensibility rests on the **tooling + vertical**, not the schema doc.
- **Cheap to clone.** Instruction/skill files copy trivially — which is exactly why Vaultwright
  leads with the mirror system and governance.
- **Hard consumer market.** Personal-KB products have struggled (Quivr pivoted, Reor archived) —
  an argument *for* the narrower B2B-ops focus, not against the project.
