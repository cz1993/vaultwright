# Contributing to Vaultwright

Thanks for your interest. Vaultwright is young; issues, discussion, and small focused PRs are all
welcome.

## Ground rules

- Keep the **mirror layer** and **governance** features (the project's differentiators) robust and
  well-tested — they are why Vaultwright exists. See `docs/positioning.md`.
- Follow the project's own philosophy: prefer **improving/consolidating** existing docs over adding
  new ones (yes, that applies to this repo too).
- Tooling is Python 3.11+ (stdlib + PyYAML + markitdown) and POSIX shell. No heavy frameworks.
- Run `python3.11 scripts/no_data_scan.py` before opening a PR. To enable the local guard, run
  `git config core.hooksPath .githooks` once in this repo.

## Developer Certificate of Origin (DCO)

Sign off every commit to certify you wrote the change and can submit it under the project license:

```
git commit -s -m "your message"     # adds: Signed-off-by: Your Name <you@example.com>
```

> **Note:** the project is offered under AGPL-3.0 **and** a separate commercial license
> (see `LICENSING.md`). To keep commercial dual-licensing possible, we may move to a **CLA**
> before accepting substantial outside contributions. Until then, by signing off you agree your
> contribution may be distributed under both the AGPL-3.0 and the project's commercial license.

## PRs

- One concern per PR; include a short rationale.
- Run `python3.11 template/tools/lint_vault.py` if you touched the schema, templates, or tools.
- If you touched example fixtures or mirror behavior, regenerate and lint temporary copies of
  `examples/northwind-robotics-vault/` and `examples/government-services-vault/` instead of
  committing generated mirrors, manifests, or audit logs.
- Run `python3.11 -m pytest` and the no-data scan before requesting review.
- Add/adjust docs in the same PR when behavior changes.
