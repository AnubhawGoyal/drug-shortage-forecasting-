# Research Proposal — Predicting US Drug Shortages Under Trade-Policy Stress

**Author:** Anubhaw Goyal · **Date:** 12 June 2026 · **Status:** v1.0 (committed)
**Target output:** arXiv preprint (econ.GN / stat.AP) in 8–10 weeks, then journal expansion
**Repo:** `drug-shortage-forecasting/`

---

## 1. Motivation

US drug shortages remain at historically elevated levels: the ASPE data brief (published Jan 2025) documents 258 active-ingredient shortages spanning 1,961 NDCs over 2018–2023, with injectables at 50% of shortage products and generic shortage starts outnumbering brand 1,391 to 600. Since 2025, US trade policy has added a new stressor. Verified state as of June 2026: IEEPA tariffs on China (10–20% from Feb 2025, reduced to 10% in Nov 2025) apply to API/generic supply chains; Section 232 pharmaceutical tariffs (proclaimed Apr 2026, effective Jul 31 / Sep 29, 2026) impose 0–100% tiered rates on **patented** products, with generics exempt "at this time." Meanwhile 72% of API manufacturing facilities supplying the US market were overseas as of Aug 2019 (Woodcock, FDA congressional testimony).

The tariff-exposure mechanism therefore differs by segment: IEEPA country tariffs + Section 232 anticipation/uncertainty for generics (where shortages concentrate); enacted Section 232 rates for patented products. H2 and the event-study design use this segmentation.

Existing predictive work (Pall et al. 2023 on Canadian pharmacy data; the 2025 South Korean ML study in Frontiers in Pharmacology) uses domestic market-structure features only. **No published study predicts US shortages using FDA/ASHP data with survival + ML methods, and none incorporates trade-policy exposure as a predictive feature set.** That is the gap this paper fills.

## 2. Research questions and hypotheses

| | Question | Formal hypothesis |
|---|---|---|
| RQ1 | Which product- and market-structure features predict shortage onset within k months? | — |
| RQ2 | What determines shortage duration? | — |
| RQ3 | Does trade exposure (API sourcing concentration, import dependence, tariff exposure) add predictive power beyond domestic features? | **H3:** ΔAUC > 0 and ΔBrier < 0, significant at α=0.05 (DeLong; Diebold-Mariano) |
| RQ4 | Are predicted probabilities calibrated enough for decision support? | **H4:** ECE ≤ 0.05 after recalibration; positive net benefit in decision-curve analysis at top-decile alert threshold |

Supporting hypotheses: **H1** — low-manufacturer-count, low-NADAC generic injectables have the highest shortage hazard. **H2** — ingredients with API sourcing concentrated in tariff-affected countries show elevated hazard post-2025 tariff regime (event-study coefficient > 0).

RQ3 is the headline contribution; RQ1/RQ2 establish the modeling platform; RQ4 makes the paper actionable for hospital purchasing and FDA monitoring.

## 3. Unit of analysis and panel design

Active-ingredient × month panel, January 2018 – June 2026 (~102 months × ~1,500–2,500 ingredients after filtering to systemically relevant products). NDC-level data is aggregated to ingredient level (shortages propagate at the ingredient/dosage-form level, and the ASPE brief validates this aggregation). A secondary ingredient × dosage-form panel is retained for robustness.

**Outcome variables:** (a) shortage onset indicator within k ∈ {3, 6} months (classification); (b) shortage spell duration in months (survival, right-censored at June 2026).

## 4. Dataset commitments

Sixteen sources are scoped in `topic_A_drug_shortage_tariff_hybrid.md`; the following are **committed** for the core analysis (rest are enrichment):

| Tier | Source | Role |
|---|---|---|
| Core | FDA Drug Shortage Database | Outcome: onset/resolution dates, reason codes |
| Core | ASHP Drug Shortages | Outcome cross-validation, timelier listings |
| Core | FDA Orange Book | Manufacturer counts, therapeutic equivalence, approval dates |
| Core | openFDA NDC directory + Drugs@FDA | Entity resolution backbone; sponsor history |
| Core | NADAC (Medicaid) | Price level and price-trend features |
| Core | FDA Drug Establishments registration | Facility locations → foreign-sourcing proxy |
| Core | USITC DataWeb / Census USA Trade Online | Imports by HTS (HS 2936–2942, HS 30) × country × month; tariff rates |
| Enrich | DEA quotas, FDA import refusals, recalls (openFDA enforcement), CMS Part B/D, UN Comtrade | Additional hazard features and robustness |

**Entity resolution is the hidden critical path**: FDA shortage ↔ Orange Book joins via active ingredient + dosage form; NDC normalization via openFDA; ingredient → HS-code mapping for trade exposure. Mitigation: bootstrap from ASPE's pre-structured 2018–2023 ingredient list, extend forward to 2026.

## 5. Feature architecture

**Domestic block (baseline model):** manufacturer count and HHI per ingredient; generic share; dosage form (injectable flag); NADAC price level, 12-month price change; time since first approval; prior shortage history; recall events trailing 12 months; DEA quota flag.

**Trade block (ablation set):** import-country concentration (HHI of import value by origin, at mapped HS codes); China+India import share; tariff-rate exposure (statutory + announced rates weighted by origin mix); import-volume year-over-year change; import-refusal events; foreign-establishment share for the ingredient's registered facilities.

## 6. Models and evaluation protocol

1. **Onset classification:** logistic regression baseline → XGBoost/LightGBM. **Temporal validation only:** rolling-origin, train ≤ Dec 2023, validate 2024, test Jan 2025 – Jun 2026 (the tariff era is the test window — deliberate, since RQ3 is about the new regime; pre-period test windows reported for robustness). Metrics: AUC, PR-AUC, Brier.
2. **Trade-exposure ablation (headline):** identical pipelines with/without trade block. DeLong test on AUC; Diebold-Mariano on Brier series; SHAP attribution.
3. **Survival (duration):** Kaplan-Meier by class/form; Cox PH with Schoenfeld diagnostics; random survival forest for non-linearities; concordance index, integrated Brier.
4. **Calibration:** reliability diagrams, ECE; isotonic/Platt recalibration on validation fold; decision-curve analysis for the "act on top-10% alerts" hospital-purchasing use case.
5. **Quasi-causal check:** event-study / DiD on shortage hazard, high vs low import-exposure ingredients, around 2025 tariff announcement dates. This is supporting evidence, not a causal-identification paper.

**Reproducibility:** pinned environment (`pyproject.toml` + lock), seeds fixed, all raw pulls cached to parquet with pull-date stamps, one-command pipeline (`make all` equivalent via `invoke`/`snakemake`-lite scripts), data/code released with the preprint (raw redistribution per source licenses; otherwise pull scripts).

## 7. Timeline (aggressive — assumes ~25–30 hrs/week, no major data surprises)

| Week (w/c) | Milestone |
|---|---|
| 1 (Jun 15) | Lit review notes finalized; all core-source pull scripts running; raw cache complete |
| 2 (Jun 22) | Entity resolution v1: shortage ↔ Orange Book ↔ NDC spine; coverage report |
| 3 (Jun 29) | Panel v1 (ingredient × month); descriptives notebook; ASPE replication check |
| 4 (Jul 6) | Ingredient → HS mapping; trade features built; panel v2 frozen |
| 5 (Jul 13) | Survival analysis complete (KM, Cox, RSF) |
| 6 (Jul 20) | Onset classification + rolling-origin validation complete |
| 7 (Jul 27) | **Ablation result locked** (DeLong/DM tests); SHAP; calibration + decision curves |
| 8 (Aug 3) | Event-study robustness; sensitivity runs (k=3 vs 6, NDC-level panel) |
| 9 (Aug 10) | Full draft: intro/related work/data/methods/results |
| 10 (Aug 17) | Polish, figures, internal red-team pass → **arXiv submission ~Aug 21** |

Stated assumptions: USITC/Census account approval is immediate; ASHP scraping is feasible at small scale; entity resolution doesn't exceed 2 weeks (fallback: restrict to ASPE's 258-ingredient set, still publishable). Slip risk concentrated in weeks 2–4; weeks 5–8 are compute-light (laptop-scale).

## 8. Venues

arXiv first (econ.GN or stat.AP). Journal expansion targets: *Health Care Management Science*, *International Journal of Production Economics*, *Production and Operations Management*, *AJHP* (pharmacist-facing decision-support angle).

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Entity resolution blows the budget | Start from ASPE 2018–2023 structured set; cap at 2 weeks; degrade to ingredient-only joins |
| API-sourcing data imperfect | Triangulate: establishment registrations + import flows + import refusals; report as proxy with sensitivity analysis |
| Tariff-era test window too short | Report k=3 onset (more events); pre-period test windows as robustness |
| Scooped on trade-exposure angle | Weekly arXiv alert (`drug shortage` + `tariff` + `forecast`); preprint-first strategy minimizes exposure |
| Medical venues expect clinical framing | Decision-curve analysis + pharmacist decision-support section |

## 10. Deliverables

1. arXiv preprint (~Aug 21, 2026)
2. Public GitHub repo: pull scripts, pipeline, frozen panel schema
3. Reusable ingredient-level shortage panel 2018–2026 (a dataset contribution in its own right)
