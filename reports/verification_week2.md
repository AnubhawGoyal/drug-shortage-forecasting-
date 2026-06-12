# Verification Memo — Week 1–2 Claims Audit

**Date:** 12 June 2026 · Every load-bearing claim checked against a primary or authoritative source.

## Confirmed ✓

| Claim | Verified fact | Source |
|---|---|---|
| ASPE shortage counts | 258 unique active ingredients, 1,961 NDCs in shortage 2018–2023; injectables 50% (n=1,018); generic starts 1,391 vs brand 600. Published Jan 8, 2025 | [ASPE, Analysis of Drug Shortages 2018–2023](https://aspe.hhs.gov/reports/drug-shortages-2018-2023) |
| 72% API facilities overseas | As of Aug 2019, 28% of API facilities supplying the US were domestic, 72% overseas (13% of overseas in China) — Woodcock testimony, Oct 30, 2019. **Vintage: 2019 — date it when citing** | [FDA congressional testimony](https://www.fda.gov/news-events/congressional-testimony/safeguarding-pharmaceutical-supply-chains-global-economy-10302019) |
| Pall et al. 2023 exists | ML on 22 Canadian pharmacies' sales data; ~69% accuracy 1 month ahead | [PMC10009839](https://pmc.ncbi.nlm.nih.gov/articles/PMC10009839/) |
| "Foresight Learning" scoop (Topic C) | Real: "Forecasting Supply Chain Disruptions with Foresight Learning," arXiv 2604.01298 (Apr 2026) — confirms Topic C scoop risk, validates Topic A choice | [arXiv 2604.01298](https://arxiv.org/html/2604.01298) |
| Our pull completeness | openFDA shortages API total = **1,671** = our cached row count exactly; status counts match (1,146 Current / 496 To Be Discontinued / 29 Resolved) | api.fda.gov live query, 12 Jun 2026 |
| Snapshot finding | openFDA endpoint covers "2012 to present" but retains only 29 Resolved records → historical spell reconstruction from ASPE + FDA archive is required (week-3 plan unchanged) | [openFDA drug shortages overview](https://open.fda.gov/apis/drug/drugshortages/) |
| Internal consistency | Injectables = 58.3% of our (current-snapshot) shortage records vs ASPE's 50% for 2018–23 — directionally consistent; current snapshots over-represent persistent injectable shortages. OB generic (ANDA) share 75.3%, plausible | local data |
| Novelty of Topic A | No US FDA/ASHP-based survival+ML shortage-prediction study found; closest works: Canada 2023, South Korea 2025, ShortageSim simulation (arXiv 2509.01813, cite as related work) | searches 12 Jun 2026 |

## Corrected ✗→✓

1. **"Pharma tariffs heading toward 200% in 2026"** (topic memo) — outdated. The 200% figure was a 2025 threat, not enacted. Verified June 2026 state: **Section 232 tariffs proclaimed Apr 2026: 0–100% tiered, patented products only, generics exempt "at this time"** (effective Jul 31 / Sep 29, 2026; onshoring deals → 20% or 0%; EU/JP/KR/CH 15%). Sources: [White House proclamation](https://www.whitehouse.gov/presidential-actions/2026/04/adjusting-imports-of-pharmaceuticals-and-pharmaceutical-ingredients-into-the-united-states/), [Crowell](https://www.crowell.com/en/insights/client-alerts/trump-administration-imposes-section-232-tariffs-on-patented-pharmaceutical-imports-tiered-rate-structure-takes-effect-beginning-july-31-2026), [Skadden](https://www.skadden.com/insights/publications/2026/06/deadline-approaching-for-companies-seeking-onshoring-deals).
2. **H2 mechanism refined.** Shortages concentrate in generics, but generics are exempt from Section 232. The tariff channel for generics is the **IEEPA China tariffs (10% Feb 2025 → 20% Mar 2025 → 10% Nov 2025)**, which do hit API/generic supply chains ([CBP CSMS](https://content.govdelivery.com/accounts/USDHSCBP/bulletins/3fa83c4), [Thompson Coburn](https://www.thompsoncoburn.com/insights/58-november-4-2025-reducing-the-20-ieepa-fentanyl-tariffs-on-china-to-10-reciprocal-tariffs-on-china-remain-at-10-until-november-2026/), [BioPharma Dive](https://www.biopharmadive.com/news/tariffs-china-trump-generic-drugs-pharma/739645/)) — plus Section 232 anticipation effects. PROPOSAL.md §1 updated; event-study dates must use the IEEPA timeline (Feb/Mar 2025, Nov 2025) for generics, Apr 2026 proclamation for patented.
3. **South Korea study is 2025, not 2026** — Frontiers in Pharmacology, [10.3389/fphar.2025.1608843](https://www.frontiersin.org/journals/pharmacology/articles/10.3389/fphar.2025.1608843/full). Fixed in PROPOSAL.md.

## Net effect on the project

Design intact; novelty intact; data pipeline verified complete. The only substantive change is sharper H2/event-study specification (tariff segmentation by generic vs patented), which strengthens the paper.
