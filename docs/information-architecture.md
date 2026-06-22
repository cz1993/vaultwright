# Information Architecture

Vaultwright uses a function-based file plan, not a department chart. The top-level folders are a
starter architecture for business records; adapt the subfolders and domain map to the company.

This guidance follows three practical records/intranet architecture patterns:

- Classify records by durable business function/activity so the plan survives team and reporting
  changes.
- Keep navigation shallow and task-oriented; use metadata and links for alternate views instead of
  deep folder trees.
- Treat the file plan as a controlled vocabulary: document aliases, owner intent, and retention or
  security implications in the domain map before broad ingestion.

## Design Principles

1. **Classify by business function.** Put records where the work, accountability, and retention
   ownership live. A contract created by sales but governed by legal belongs in governance, with
   links from the customer account.
2. **Keep top-level domains stable.** Change subfolders for each industry; avoid creating a new
   top-level folder for every team, channel, initiative, or vendor.
3. **Separate source from interpretation.** Raw files stay source of truth in functional folders;
   generated mirrors live under `_mirrors/`; notes make both searchable and connected.
4. **Use metadata for cross-cutting views.** `domain`, `type`, `status`, entity links, and tags are
   how the same record appears in customer, product, finance, or compliance views.

## Starter Domains

| Folder | Domain | What Belongs Here |
| --- | --- | --- |
| `00_inbox/` | `intake` | Unprocessed files, triage notes, temporary import batches. |
| `10_governance/` | `governance` | Corporate records, ownership, policy, legal, compliance, risk, board/management evidence. |
| `20_market/` | `market` | Market research, positioning, brand, campaigns, public communications, partnerships. |
| `30_customers/` | `customers` | Accounts/clients, discovery, proposals, support records, customer decisions and relationship history. |
| `40_delivery/` | `delivery` | Products, services, projects, engagements, implementations, delivery playbooks, product/service decisions. |
| `50_operations/` | `operations` | Internal process, vendors, procurement, IT, security, facilities, systems, incidents. |
| `60_finance/` | `finance` | Accounting, statements, invoices, budgets, tax, payroll, grants, funding, banking. |
| `70_people/` | `people` | Hiring, employees, contractors, roles, onboarding, training, people policies and records. |
| `80_sources/` | `sources` | Repository mirrors, public datasets, source inventories, cross-domain raw-source indexes. |

Generated Office mirrors and optional PDF text mirrors live outside the functional source folders
at `_mirrors/<canonical-source-path>.md`. They still carry the source document's `domain` in
frontmatter, so metadata views can group them with their source function without cluttering the
raw-file folder.

The canonical machine-readable map is `template/_meta/domain-map.yml`.

`tools/lint_vault.py` enforces the map: every note must use one of these domain values, while
aliases exist only to guide filing and migration from older folder names.

## Industry Adaptation

Use subfolders and templates to adapt the starter map:

| Industry | Likely Subfolders |
| --- | --- |
| Professional services | `30_customers/<account>/`, `40_delivery/engagements/`, `10_governance/contracts/` |
| E-commerce / retail | `20_market/channels/`, `30_customers/support/`, `40_delivery/products/`, `50_operations/suppliers/` |
| Clinic / regulated services | `10_governance/compliance/`, `50_operations/systems/`, `70_people/credentials/`, customer/private areas as required |
| Contractor / trades | `30_customers/jobs/`, `40_delivery/site-work/`, `50_operations/equipment/`, `60_finance/job-costing/` |
| Software / product | `40_delivery/product/`, `80_sources/repos/`, `50_operations/security/`, `30_customers/accounts/` |

## Migration From Department Folders

Run `python3.11 tools/vaultwright.py migration` before moving folders. The report is read-only: it
uses `_meta/domain-map.yml` aliases to identify old top-level folders and prints recommended
canonical destinations, while unknown folders are flagged for human classification. Use
`python3.11 tools/vaultwright.py migration --runbook` to print the reviewed execution protocol for
legacy folder moves; it is intentionally manual and does not move files.

| Old Starter Folder | New Function Domain |
| --- | --- |
| `company/` | `10_governance/` |
| `legal/` | `10_governance/` |
| `marketing/` | `20_market/` |
| `clients/` | `30_customers/` |
| `projects/` | `40_delivery/` or `80_sources/repos/` for repo mirrors |
| `operations/` | `50_operations/` unless it is delivery work |
| `finance/` | `60_finance/` |
| `funding/` | `60_finance/` |
| `hr/` | `70_people/` |

## Reference Guidance

The starter map is intentionally conservative. It draws on records-management and intranet IA
guidance rather than a single company's department list:

- National Archives of Australia,
  ["Using Business and Records Classification"](https://www.naa.gov.au/information-management/describing-information/classifying-information/using-business-and-records-classification):
  function/activity schemes support titling conventions, metadata, security, disposal, and
  resilience through organizational change.
- Microsoft SharePoint
  [information architecture](https://learn.microsoft.com/en-us/sharepoint/information-architecture-modern-experience)
  and
  [IA principles](https://learn.microsoft.com/en-us/sharepoint/information-architecture-principles):
  effective IA starts from user tasks, labels, navigation, metadata, and search; deep folder nesting
  increases discoverability burden.
- U.S. National Archives
  [records basics](https://www.archives.gov/records-mgmt/scheduling/basics): records are kept for
  evidential or informational value, and records series can group material by subject, function,
  activity, transaction, or creation/use relationship.
- UN Archives
  [file classification guidance](https://archives.un.org/en/content/advisory-services/file-classification-schemes):
  a file plan/classification scheme is a retrieval and control tool, not just a visual folder list.
