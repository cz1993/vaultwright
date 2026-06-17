# Licensing & commercial model

> **Not legal advice.** This documents the *intended* model so you can brief an IP lawyer and
> finalize it before any public release. The author is not a lawyer.

## Goals (from the project owner)

1. Be genuinely open source.
2. Build on permissive open-source dependencies (markitdown, PyYAML, etc.) without friction.
3. Ensure people who reuse Vaultwright **respect the project's IP** (attribution; can't quietly
   close-source improvements; can't pass a fork off as official "Vaultwright").
4. Be able to **charge enterprises** that use it at scale, and offer **consulting / implementation**.

## The model: AGPL-3.0 open core + commercial dual-license + trademark

**Code license — AGPL-3.0.** The whole project is offered under the GNU Affero GPL v3.

- *Why it fits the goals:* AGPL is OSI-approved open source (goal 1). It is compatible with our
  permissive MIT dependencies — permissive deps impose no obligations on us (goal 2). Its
  copyleft + the network clause (§13) mean anyone who modifies Vaultwright — **including running
  a modified version as a hosted service** — must release their source under AGPL too (goal 3).
- *Why it enables revenue (goal 4):* precisely because many companies' policies forbid AGPL in
  their stack or won't open-source their changes, they will prefer to **buy a commercial
  license** instead. That is the dual-licensing lever (below). This is the same model used by
  basic-memory, Khoj, and historically MongoDB/MySQL.

**Commercial dual-license.** Because the project's copyright is consolidated (see *Contributions*
below), the owner can additionally sell the *same code* under a private commercial license that
waives the AGPL obligations — for enterprises that want closed/hosted use at scale. Pricing,
support SLAs, and indemnity live in that agreement, not here. See `docs/positioning.md` for who
this buyer is.

**Open core (optional, later).** Keep the core AGPL and free; develop premium/enterprise modules
(e.g. SSO, multi-vault governance dashboards, hosted sync) in a **separate** repository under a
commercial license. Don't retro-close anything already shipped as AGPL.

**Trademark.** The *name* "Vaultwright" and any logo are protected separately from the code — see
`TRADEMARK.md`. AGPL lets anyone fork the code; trademark stops them from calling their fork
"Vaultwright." This is the cleanest mechanism for goal 3 ("respect our IP / no impersonation").

**Services.** Consulting, personalization, and implementation are sold independently of the
license and are compatible with all of the above.

## Contributions (required for dual-licensing to work)

To be able to offer a commercial license, the owner must hold sufficient rights to all the code.
Two options — pick one with your lawyer:

- **CLA (recommended for dual-licensing):** contributors sign a Contributor License Agreement
  granting Ci Zhu (cz1993) the right to relicense their contributions (e.g. via CLA Assistant).
- **DCO (lighter, weaker):** contributors add `Signed-off-by:` (Developer Certificate of Origin).
  Simpler, but does **not** by itself grant relicensing rights, which complicates dual-licensing.

`CONTRIBUTING.md` currently sets up DCO; switch to a CLA before accepting outside contributions if
you want to keep commercial dual-licensing clean. Consider assigning copyright to a single entity
(Ci Zhu (cz1993)).

## Alternatives considered (and why not, for now)

- **MIT / Apache-2.0** — maximum adoption and the friendliest for dependencies, but **permissive
  licenses cannot compel an enterprise to pay**; anyone may use it at any scale, closed, for free.
  Good if adoption matters more than direct license revenue. (Apache adds an explicit patent grant
  and trademark reservation, which is nice.)
- **BSL 1.1 / "source-available"** — lets you **restrict production/competing use and charge now**,
  converting to an open license after a change date (3-4 yrs). Directly serves goal 4, **but it is
  not OSI "open source"** (conflicts with goal 1) and draws community friction (cf. HashiCorp,
  Sentry). Choose this only if charging-for-production matters more than the open-source label.

## TODO before launch

- [ ] Vendor the full AGPL-3.0 text into `LICENSE` (see the banner in that file).
- [ ] Decide CLA vs DCO with counsel; wire up CLA Assistant if CLA.
- [ ] Register/secure the "Vaultwright" mark; confirm name availability.
- [ ] Draft the commercial license agreement + pricing tiers (what counts as "at scale").
- [ ] Add SPDX headers (`SPDX-License-Identifier: AGPL-3.0-or-later`) to source files.
