# Data Provenance

Vaultwright examples must never contain real company or personal data. Each committed source below
is synthetic/fictional, or a generated fixture based on public reference pages with licence and
attribution recorded before inclusion.

Licence checks in this file were last reviewed on 2026-06-19.

## Included Source Materials

| Path | Source | License / status | Notes |
| --- | --- | --- | --- |
| `examples/northwind-robotics-vault/` | Synthetic fictional business created for Vaultwright | Covered by this repository's license | No real company, customer, person, account, contract, or operational data. |
| `examples/northwind-robotics-vault/30_customers/acme-manufacturing/2026-01-15_acme_discovery_brief.docx` | Synthetic fictional document created for Vaultwright | Covered by this repository's license | Exercises Office-to-markdown mirroring for narrative customer docs. |
| `examples/northwind-robotics-vault/60_finance/2026-01_pipeline_snapshot.xlsx` | Synthetic fictional workbook created for Vaultwright | Covered by this repository's license | Exercises spreadsheet mirroring and table readability. |
| `examples/northwind-robotics-vault/40_delivery/2026-q1_service_readiness_review.pptx` | Synthetic fictional deck created for Vaultwright | Covered by this repository's license | Exercises slide-deck mirroring and summary readability. |
| `examples/northwind-robotics-vault/_fixtures/repos/fieldkit-control/` | Synthetic fictional code repo fixture created for Vaultwright | Covered by this repository's license | Exercises repo mirroring without live network dependency. |
| `examples/northwind-robotics-vault/tools/repos.yml` | Vaultwright example config | Covered by this repository's license | Points at the local `fieldkit-control` fixture so CI can regenerate a repo mirror. |
| `examples/government-services-vault/` | Generated public-service showcase based on Canadian business-startup government topics | Generated fixture content is synthetic/paraphrased and covered by this repository's license. Government of Canada reference pages are attributed below and treated as Open Government Licence - Canada 2.0 material. | Demonstrates familiar business registration, GST/HST, CRA account, and funding/support workflows without personal data. |
| `examples/government-services-vault/40_delivery/business-registration/2026-06_cra_business_registration_path.docx` | Generated synthetic/paraphrased fixture based on Government of Canada references: `https://www.canada.ca/en/services/taxes/business-registration.html`, `https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/business-registration/business-number-program-account/how-register/resident.html`, and `https://www.canada.ca/en/revenue-agency/news/newsroom/tax-tips/tax-tips-2025/businesses-go-online-register-business-number-cra-program-account.html` | Government of Canada references reviewed 2026-06-19; source licence: Open Government Licence - Canada 2.0, `https://open.canada.ca/en/open-government-licence-canada`. Fixture is a generated scenario, not a copied government publication. Attribution obligation: acknowledge Government of Canada source information and avoid implying endorsement. | Exercises Office mirroring for business number and CRA program-account registration guidance. |
| `examples/government-services-vault/60_finance/gst-hst/2026-06_gst_hst_registration_readiness.docx` | Generated synthetic/paraphrased fixture based on Government of Canada references: `https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/gst-hst-account/register-account.html`, `https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses.html`, and `https://www.canada.ca/en/revenue-agency/news/cra-multimedia-library/businesses-video-gallery/transcript-gst-hst-registration.html` | Government of Canada references reviewed 2026-06-19; source licence: Open Government Licence - Canada 2.0, `https://open.canada.ca/en/open-government-licence-canada`. Fixture is a generated scenario, not a copied government publication. Attribution obligation: acknowledge Government of Canada source information and avoid implying endorsement. | Exercises Office mirroring for GST/HST readiness and post-registration obligations. |
| `examples/government-services-vault/60_finance/2026-06_business_support_and_funding_tracker.xlsx` | Generated synthetic workbook based on reference topics from Business Benefits Finder (`https://innovation.ised-isde.canada.ca/s/?language=en_CA`), B.C. resources/support page (`https://www2.gov.bc.ca/gov/content/employment-business/business/small-business`), and B.C. copyright/licence guidance (`https://www2.gov.bc.ca/gov/content/home/copyright`, `https://www2.gov.bc.ca/gov/content/data/policy-standards/data-policies/open-data/open-government-licence-bc`) | Government of Canada reference reviewed 2026-06-19 under Open Government Licence - Canada 2.0. B.C. page reviewed 2026-06-19 as reference-only: no B.C. text or data is copied, and B.C. OGL applies only to records that specify it. Fixture rows are synthetic examples covered by this repository's license. | Exercises spreadsheet mirroring for funding/support discovery workflows. |
| `examples/government-services-vault/20_market/2026-06_canadian_business_startup_navigation_brief.pptx` | Generated synthetic deck using high-level themes from the Government of Canada and B.C. reference URLs listed above | Covered by this repository's license. No government text, logo, mark, or data table is copied into the committed deck. | Exercises slide-deck mirroring and a user-friendly business-startup showcase narrative. |
| `examples/government-services-vault/tools/repos.yml` | Vaultwright example config | Covered by this repository's license | Empty repo list; demonstrates clean skip behavior while Northwind covers repo mirroring. |

## Regenerated During CI / Local Validation

These files are generated from included sources or public mirrors. They should not be hand-edited or
treated as source material.

| Generated path | Source | License / status | Notes |
| --- | --- | --- | --- |
| `examples/northwind-robotics-vault/_mirrors/30_customers/acme-manufacturing/2026-01-15_acme_discovery_brief.md` | Synthetic `.docx` listed above | Covered by this repository's license | Generated by `sync_office_md.py`. |
| `examples/northwind-robotics-vault/_mirrors/60_finance/2026-01_pipeline_snapshot.md` | Synthetic `.xlsx` listed above | Covered by this repository's license | Generated by `sync_office_md.py`. |
| `examples/northwind-robotics-vault/_mirrors/40_delivery/2026-q1_service_readiness_review.md` | Synthetic `.pptx` listed above | Covered by this repository's license | Generated by `sync_office_md.py`. |
| `examples/northwind-robotics-vault/80_sources/repos/fieldkit-control.md` | Synthetic local code repo fixture listed above | Covered by this repository's license | Generated by `sync_github_repos.py`. |
| `examples/government-services-vault/_mirrors/40_delivery/business-registration/2026-06_cra_business_registration_path.md` | Generated `.docx` listed above | Covered by this repository's license | Generated by `sync_office_md.py`. |
| `examples/government-services-vault/_mirrors/60_finance/gst-hst/2026-06_gst_hst_registration_readiness.md` | Generated `.docx` listed above | Covered by this repository's license | Generated by `sync_office_md.py`. |
| `examples/government-services-vault/_mirrors/60_finance/2026-06_business_support_and_funding_tracker.md` | Synthetic `.xlsx` listed above | Covered by this repository's license | Generated by `sync_office_md.py`. |
| `examples/government-services-vault/_mirrors/20_market/2026-06_canadian_business_startup_navigation_brief.md` | Synthetic `.pptx` listed above | Covered by this repository's license | Generated by `sync_office_md.py`. |

## Approved External Candidates

These are approved for future collection or live mirroring only after preserving required license
notices and recording exact files/URLs.

| Candidate | Source URL | License / status | Intended use |
| --- | --- | --- | --- |
| World Bank Open Data indicator exports | `https://data.worldbank.org/` and `https://www.worldbank.org/en/about/legal/terms-of-use-for-datasets` | Generally CC BY 4.0 unless specific metadata says otherwise | Non-code public data candidate for realistic spreadsheet/report ingestion. |
| Canadian business-startup government pages | `https://open.canada.ca/en/open-government-licence-canada`, `https://www.canada.ca/en/services/taxes/business-registration.html`, `https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/business-registration/business-number-program-account/how-register/resident.html`, `https://www.canada.ca/en/revenue-agency/news/newsroom/tax-tips/tax-tips-2025/businesses-go-online-register-business-number-cra-program-account.html`, `https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/gst-hst-account/register-account.html`, `https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses.html`, `https://www.canada.ca/en/revenue-agency/news/cra-multimedia-library/businesses-video-gallery/transcript-gst-hst-registration.html`, `https://innovation.ised-isde.canada.ca/s/?language=en_CA`, `https://www2.gov.bc.ca/gov/content/employment-business/business/small-business`, `https://www2.gov.bc.ca/gov/content/home/copyright`, `https://www2.gov.bc.ca/gov/content/data/policy-standards/data-policies/open-data/open-government-licence-bc` | Government of Canada reference material is treated as reusable under Open Government Licence - Canada 2.0 for these examples. B.C. material must be checked per-page; B.C. OGL applies only to records that specify it. | Preferred source family for business-registration, tax-readiness, and funding/support showcase examples. |
| `pypa/sampleproject` | `https://github.com/pypa/sampleproject` | MIT license | Optional live public repo mirror candidate for integration testing outside required CI. |
| `microsoft/markitdown` fixtures | `https://github.com/microsoft/markitdown` | MIT license | Office/PDF conversion stress fixtures, if individual fixture provenance remains acceptable. |
| Synthetic `openpyxl`-generated workbooks | `https://openpyxl.readthedocs.io/` | Library is MIT/Expat; generated data remains synthetic | Multi-sheet workbook generation for repeatable spreadsheet mirror tests. |

## Deferred / Use With Care

| Candidate | Reason |
| --- | --- |
| Project Gutenberg texts | Useful for long-text stress tests, but redistribution/trademark terms require care. Prefer stripped public-domain text with explicit work-level review, or keep as a download-on-demand candidate rather than committed content. |
