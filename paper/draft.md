# Predicting US Drug Shortages Under Trade-Policy Stress: A Multi-Margin Evaluation of Tariff Exposure

**Anubhaw Goyal** (Independent Researcher) — goyal.anubhaw@gmail.com
*Draft v0.1 — June 2026 — target: arXiv stat.AP / econ.GN*

## Abstract

US drug shortages remain elevated while trade policy has placed unprecedented tariffs on pharmaceutical supply chains, prompting widespread concern that tariff exposure will worsen shortages. We assemble a reproducible public-data panel — 4,017 ingredient–dosage-form units over 102 months (2018–2026) — combining FDA shortage records (with historical spells reconstructed from 44 Internet Archive snapshots of the FDA database), Orange Book market structure, NADAC acquisition prices, and trade exposure mapped from US Census import data at HS-4 level. We evaluate tariff/trade exposure on three margins. (1) *Prediction:* gradient-boosted and logistic classifiers predict shortage onset within 6 months at ROC-AUC 0.785 under rolling-origin temporal validation, but trade features add no discriminative power (ΔAUC +0.001, DeLong p = 0.88) and, after isotonic recalibration (ECE ≤ 0.001), no proper-scoring gain. (2) *Duration:* shortage spells are long (median 28.8 months) and survival analysis shows trade *structure* matters where trade *flows* do not — origin-concentrated API classes resolve slowest (hormones HR 0.40, p = 0.08), and injectables persist significantly longer (logrank p = 0.046). (3) *Quasi-causal:* difference-in-differences around the February 2025 IEEPA China tariffs finds no detectable differential onset (p = 0.53) or resolution (p = 0.50) effect for China-exposed units through June 2026. We conclude that tariffs have not (yet) moved US drug shortages at detectable magnitudes — but origin concentration robustly predicts which shortages persist. We document power limits transparently: new shortage onsets fell to historic lows in 2024–25 (consistent with FDA/ASHP counts), the enacted tariff dose on generics was modest (10–20%), and Section 232 pharmaceutical tariffs exempt generics. All data and code are public and reproducible.

## 1. Introduction

[Shortage crisis context: ASPE (2025) documents 258 active-ingredient shortages spanning 1,961 NDCs over 2018–2023, concentrated in low-price generic sterile injectables. Policy context: IEEPA tariffs on China (Feb 2025: 10%, Mar 2025: 20%, Nov 2025: 10%) reach API/generic supply chains; Section 232 pharmaceutical tariffs (Apr 2026 proclamation; effective Jul/Sep 2026) impose 0–100% tiered rates on patented products with generics exempt "at this time". ~72% of API facilities supplying the US were overseas as of Aug 2019 (FDA testimony). The question policymakers, hospital systems, and journalists keep asking: will tariffs cause or prolong shortages?]

Contributions: (i) first US shortage-prediction study on FDA/ASHP-era data with survival + ML methods and temporal validation; (ii) a novel public reconstruction of historical shortage spells from Internet Archive snapshots, with exact onsets and interval-censored resolutions; (iii) a pre-registered-style multi-margin evaluation of trade exposure — prediction, duration, quasi-causal — that returns a careful, well-documented null on tariff flows alongside a robust positive on origin concentration; (iv) full reproducibility on public data.

## 2. Related work

Pall et al. (2023): ML on 22 Canadian pharmacies, ~69% accuracy one month ahead — richer proprietary signals, no trade features, no US scope. Frontiers in Pharmacology (2025): South Korean regulatory data, ML prediction of shortage duration/causes. ShortageSim (2025): simulation of shortage dynamics under information asymmetry. ASPE (2025): descriptive analysis 2018–2023, market-structure risk factors. Our gap: US public-data prediction with survival framing, trade-exposure evaluation, and regime-change-aware validation. [Expand with 8–10 further citations in v0.2: drug shortage economics (Conti, Berndt), tariff pass-through literature, interval-censored survival methods, forecast-evaluation under clustering.]

## 3. Data

**Outcomes.** FDA Drug Shortage Database current snapshot (1,671 records) retains only 29 resolved entries; we reconstruct history from 44 Wayback Machine snapshots of the FDA CSV export (2019–2026, ~monthly with gaps; 2022 has one snapshot). A unit is in shortage at snapshot t if any of its records is "Current"; onsets are exact (Initial Posting Date); resolutions are interval-censored between consecutive snapshots (median interval 101 days). Validation: our onset counts track FDA (15 new shortages CY2024) and ASHP (89 in 2025, 20-year low) annual figures; injectable shares match ASPE.

**Unit of analysis.** Ingredient × dosage-form bucket (4,017 marketed units; 372 spells; 320 onsets ≥2018). Company-level units were rejected: only 35% of FDA shortage companies match NDC labelers by name. Entity resolution: three-tier ingredient matching (exact / salt-stripped / component-wise), Orange Book coverage 94.7% of shortage records, NDC directory 98.7%, all residuals identified (biologics → Purple Book; parenteral nutrition components).

**Features.** Domestic block: manufacturer counts, ANDA share, dosage-form, ingredient age, NADAC price level and 12-month change (11.7M weekly price rows), trailing shortage history (leak-free). Trade block: HS-4 API-heading origin mix from Census imports (China/India shares, origin HHI, import growth; aggregate-row contamination from EU/NATO rows identified and removed), plus verified policy timelines (IEEPA rates; §232 anticipation/enactment) and a China-tariff-exposure interaction.

## 4. Methods

Rolling-origin temporal validation only: four folds (test 2021 / 2022 / 2023 / 2024–25), predictions pooled (n = 223,740 unit-months; 79 events; base rate 0.04%). Paired feature-set comparison on identical rows: DeLong test on AUC; Diebold–Mariano on Brier, naive and unit-clustered. Isotonic recalibration fit on early folds, applied to the 2024–25 fold; ECE and decision-curve analysis. Survival: Kaplan–Meier with interval-censoring sensitivity (lower/mid/upper conventions), Cox PH with Schoenfeld diagnostics, random survival forest comparison. Quasi-causal: DiD with treatment = top-tercile China import share (fixed at Jan-2025), post = Feb-2025, unit-clustered SEs; outcomes = next-month onset (risk set) and next-month resolution (in-shortage set).

## 5. Results

### 5.1 Onset prediction (RQ1)

Logistic regression: pooled ROC-AUC 0.785, stable across folds; LightGBM does not beat it at 79 pooled events. Dominant predictors (standardized): injectable form (+1.42), ingredient age (+1.03), falling prices (price_chg −0.28: price *declines* predict onset, consistent with deflation-driven exit). Precision is inherently low at the base rate; k = 3 horizon yields the same picture (ROC 0.756).

### 5.2 Trade ablation (H3)

ΔAUC +0.0010 (DeLong p = 0.877). Raw Brier improves and survives unit-clustered DM (p = 1.4e-10) — but vanishes after isotonic recalibration (Δ ≈ 4e-9): the gain was probability scale, not signal. Same null at k = 3. **Caveat documented:** tariff-policy features have zero pre-2025 variation and thus cannot contribute to models trained ≤2023 — the null is fully informative only for origin-mix features; for policy features it is partially mechanical, which motivates the event study.

### 5.3 Duration (RQ2)

Median spell 28.8 months (27.8–30.1 across censoring conventions). Injectable 31.1 vs non-injectable 24.4 months (logrank p = 0.046). Cox concordance 0.601, no PH violations; hormones — the most origin-concentrated heading (HHI 0.66) — resolve slowest (HR 0.40, p = 0.08). RSF loses to Cox held-out (0.536 vs 0.595): at n = 151 spells the linear model wins, reported as a sample-size result.

### 5.4 Event study (H2)

No detectable differential effect for high-China-exposure units after IEEPA: onset DiD +0.00015 (p = 0.53); resolution DiD −0.0095 (p = 0.50; directionally consistent with slower resolution but power-limited). Window: 16 months post-treatment; dose: 10–20% IEEPA with generics exempt from §232 through the sample end.

### 5.5 Decision relevance (RQ4)

Isotonic recalibration achieves ECE ≤ 0.001 out-of-sample. Decision curves: positive net benefit over treat-all and treat-none at thresholds 0.0005–0.002 in the 2022–23 regime; no positive net benefit in the 2024–25 onset drought. The tool is a monitoring-prioritization ranker, not an alerting system, and its value is regime-dependent.

## 6. Policy discussion

Three messages. (1) Fears that 2025-vintage tariffs are already driving shortages find no support in the data through June 2026 — at the enacted dose, with generics exempt. (2) The structural risk is real but different: origin concentration (not current tariff incidence) predicts persistence; resilience policy should target single-origin API classes. (3) Monitoring systems built on public data can rank risk usefully (ROC ≈ 0.78) but cannot deliver actionable alert precision at current event rates; investment should go to data access (earlier manufacturer signals), not model complexity.

## 7. Limitations

HS-4 class-level trade mapping (establishment-registration upgrade path); value-based import shares understate China; interval-censored resolutions (~3-month precision); 2022 snapshot gap; short post-treatment window and modest tariff dose for the event study; §232 effects on patented products post-date our sample; policy features mechanically absent from pre-2025 training; ingredient-form aggregation (product-level NDC granularity blocked by company-name resolution).

## 8. Reproducibility

All data public; pipeline (pulls → entity resolution → spell reconstruction → panel → models) released at github.com/AnubhawGoyal/drug-shortage-forecasting- [make public at submission]; pinned environment; seeds fixed; temporal-validation-only rule enforced in code.

---
*[v0.2 TODO: full citations + bibliography; figures (KM curves, event-study plot, calibration plot, coefficient chart); numbers tables; LaTeX conversion; co-author methods review (cluster-robust inference, interval-censored estimators).]*
