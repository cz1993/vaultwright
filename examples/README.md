# Examples

`government-services-vault/` is the primary public-document showcase. It uses generated Office
fixtures based on familiar Canadian business-startup government topics: CRA business registration,
GST/HST readiness, CRA account access, and funding/support discovery. It contains no real
applicant, customer, company, or personal data.

`northwind-robotics-vault/` remains a synthetic business fixture for repo-mirroring and
small-business workflow regression tests. It is fictional and contains no real company, customer,
personal, or proprietary data.

Use it to inspect:
- Dedicated Office source mirrors (`.docx`, `.xlsx`, `.pptx` -> `_mirrors/` markdown),
  regenerated during validation.
- Manifest-backed `tools/vaultwright.py plan` / `status` behavior without committing generated
  mirrors, manifests, or audit logs.
- A synthetic local repo mirror under `80_sources/repos/`, regenerated from `tools/repos.yml`.
- MOC/entity linking, frontmatter, and the Obsidian Bases index.
- The function-based file plan (`10_governance`, `30_customers`, `40_delivery`, etc.).
- Whether the resulting vault feels usable for a small-business operator, not just technically
  valid.

Every included or candidate external source is tracked in `DATA_PROVENANCE.md`.

To regenerate mirrors locally:

```bash
cd northwind-robotics-vault
python3.11 tools/vaultwright.py plan
python3.11 tools/vaultwright.py sync
python3.11 tools/vaultwright.py status
python3.11 tools/vaultwright.py lint
```

For the public-service showcase:

```bash
cd government-services-vault
python3.11 tools/vaultwright.py plan
python3.11 tools/vaultwright.py sync
python3.11 tools/vaultwright.py status
python3.11 tools/vaultwright.py lint
```
