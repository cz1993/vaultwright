# Security Model

## Scope

Vaultwright is a local/open-core document governance tool. It is not currently a hosted service and
does not provide a complete enterprise security platform. This document defines the security model
that must guide the pre-release implementation.

## Protected Assets

- Original source files.
- Generated mirrors.
- Curated notes.
- Source manifest and audit logs.
- Repository credentials and API tokens.
- Client identity, PII, financial records, legal records, and proprietary information.
- Provenance and licensing records.

## Trust Boundaries

- Local filesystem and cloud-sync folders.
- Git repository versus private working vaults.
- Source files versus generated mirrors.
- Generated content versus human-curated notes.
- AI provider boundary.
- GitHub/repository connector boundary.
- Obsidian plugins and local application state.
- Client/project boundaries.

## Model-Provider Data Flow

Vaultwright must document whether a workflow sends source or mirror content to a cloud model. The
safe default for client work is:

- do not send private source content to a model unless the operator explicitly chooses a provider
  and understands its data policy;
- prefer local summaries or manual review for sensitive files;
- log which provider/configuration was used for AI-assisted curation where practical.

## Agent Permissions

Default agent permissions:

- may read source files;
- may generate mirrors;
- may update machine-owned frontmatter;
- may propose curated-note edits;
- may add links when evidence is explicit;
- must cite source-backed notes or mirrors for durable claims.

Default prohibitions:

- no source-file modification;
- no silent deletion;
- no silent folder migration;
- no silent consolidation of human notes;
- no credential storage in the vault;
- no cross-client copying.

## Source-Document Threats

Source documents may contain:

- malicious prompt instructions;
- macros or unsafe embedded content;
- hidden OOXML metadata;
- comments, revisions, hidden sheets, or speaker notes;
- secrets or PII;
- misleading filenames or paths.

Vaultwright must treat source text as untrusted input. Future AI workflows should separate "source
content says" from "system instruction says" and should avoid executing embedded instructions.

## Plugin and Connector Policy

- Obsidian community plugins are outside Vaultwright's trust boundary.
- `vaultwright doctor` reports whether optional Obsidian config and community plugins are present,
  but operators still own plugin review and local application hardening.
- GitHub tokens must come from environment, `gh`, or OS credential storage, not files in the vault.
- Connectors should use read-only permissions where possible.
- Logs must redact tokens and avoid writing private content snippets.

## Backup and Recovery

Operators need documented recovery procedures for:

- restoring original sources;
- deleting and regenerating `_mirrors/`;
- restoring curated notes from Git or backup;
- recovering from interrupted sync;
- reverting an incorrect agent proposal.

Current recovery guidance lives in `docs/RECOVERY.md`. The copied-vault regeneration path has
regression coverage, but restore drills on pilot vaults are still required before recovery can be
treated as an operational control.

## Known Residual Risks

- Conversion may omit layout, formulas, comments, scans, or hidden content.
- Local machine compromise compromises local vaults.
- Cloud sync tools may create conflict files or expose data outside Vaultwright's control.
- AI providers may have data retention or training policies the user must evaluate.
- Public examples do not prove security for private client records.

## Near-Term Security Work

- Extend manifest and audit-log coverage through external pilots.
- Add explicit prompt-injection handling guidance.
- Expand recovery tests and run pilot restore drills.
- Run a focused security review after lifecycle semantics stabilize.
- Defer full third-party audit until CLI, manifest, and recovery design are stable.
