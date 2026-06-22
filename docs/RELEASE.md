# Release Checklist

Vaultwright is still a technical alpha. Releases should be conservative, source-backed, and honest
about limitations. This repository does not publish to PyPI yet.

## Release Shape

The tag workflow in `.github/workflows/release.yml` runs on `v*` tags. It:

- runs the no-data scan;
- builds source and wheel artifacts with `python -m build`;
- installs the built wheel into a fresh virtual environment;
- scaffolds a new vault from that installed wheel;
- runs smoke checks for `doctor`, `plan`, `sandbox`, `benchmark`, `catalog`, `catalog --html`,
  `conversion --guide`, `overlap`, `overlap --worksheet`, `m365`, `review`, `review --check`,
  `migration`, `migration --worksheet`, `migration --runbook`,
  `migration --normalize-frontmatter-domains --worksheet`, `pilot`, `pilot --worksheet`,
  `recovery`, and `recovery --worksheet`;
- uploads `dist/*` as workflow artifacts;
- creates or updates a draft, prerelease GitHub Release for owner review.

The build job runs with read-only repository permissions and does not persist checkout credentials.
Only the publishing job receives `contents: write`, after the artifacts have been built and smoke
tested. If a release for the tag already exists, the workflow refuses to overwrite assets unless the
existing release is still both draft and prerelease.

The release is intentionally a draft. The owner should publish it only after reviewing the generated
notes, artifact names, CI status, and release claims.

## Before Tagging

1. Confirm the worktree is clean and `main` is current with `origin/main`.
2. Confirm git identity is `cz1993 <56002317+cz1993@users.noreply.github.com>`.
3. Run:

```bash
python3.11 scripts/no_data_scan.py
PYTHONDONTWRITEBYTECODE=1 python3.11 -m pytest -q -p no:cacheprovider
python3.11 template/tools/lint_vault.py
bash -n scripts/init.sh template/tools/sync_all.sh .githooks/pre-commit
git diff --check
```

4. Confirm the latest CI run on `main` is green.
5. Review `CHANGELOG.md`, `README.md`, and `docs/VAULTWRIGHT_WHITEPAPER.md` for overclaims.
6. Confirm no real client data, personal data, private benchmark task/result packs, secrets,
   tokens, or proprietary documents are present.

## Tagging

Use a PEP 440-compatible alpha tag that matches the package version while Vaultwright is alpha:

```bash
git tag -a v0.1.0a1 -m "v0.1.0a1"
git push origin v0.1.0a1
```

Then watch the release workflow:

```bash
gh run list --repo cz1993/vaultwright --workflow Release --limit 5
gh run watch <run-id> --repo cz1993/vaultwright --exit-status
```

## Owner Review Before Publishing Draft

Before publishing the draft GitHub Release:

- verify the workflow conclusion is `success`;
- download or inspect the uploaded wheel and source distribution names;
- confirm package metadata reports `AGPL-3.0-or-later` and includes `LICENSE` plus `NOTICE`;
- confirm `vaultwright init` works from the released wheel;
- confirm any workflow rerun only updated an existing draft prerelease;
- confirm generated release notes do not imply production readiness;
- mark unresolved limitations clearly, especially conversion quality, external pilot evidence,
  lifecycle gaps, support boundaries, and licensing/commercial terms.

## Not Yet Included

These are intentionally deferred:

- PyPI publishing;
- Homebrew, Docker, or OS packages;
- signed artifacts;
- enterprise/commercial licence packaging;
- stable API guarantees.
