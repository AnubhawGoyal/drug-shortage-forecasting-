# Week-6 Report — Onset Classification (RQ1) + Ablation Preview

**Date:** 12 June 2026 · Module: `src/shortage/models/onset.py` · Results: `experiments/onset/`

## Test-window validation (external)

Our reconstructed onset decline is real, not an artifact: FDA identified [15 new shortages in CY2024](https://www.fda.gov/media/189325/download) (peak: 251 in 2011); ASHP reported [89 new in 2025 — lowest since 2006](https://www.beckershospitalreview.com/pharmacy/new-drug-shortages-hit-20-year-low-ashp-report/). Our 8 ingredient-level 2024 onsets vs FDA's 15 product-level is consistent. Consequence: single-year 2025–26 test windows are statistically barren; evaluation uses **4-fold rolling-origin** (test years 2021 / 2022 / 2023 / 2024–25 pooled), predictions pooled across folds: 81,184 test rows, 73 positives (base rate 0.09%).

## Setup

Risk set: ingredient × month not currently in shortage. Label: onset within 6 months. Features: domestic block (market structure, history, **NADAC price block added this week** — log price, 12-month change, generic-priced share; 54% coverage, sentinel-coded) ± trade block. Logistic (balanced, L2) and LightGBM (early stopping on next-year validation).

## Pooled out-of-sample results

| Model / features | ROC-AUC | PR-AUC | Lift over base |
|---|---|---|---|
| Logistic, domestic | **0.676** | 0.00185 | ~2.0× |
| Logistic, +trade | 0.670 | 0.00170 | ~1.8× |
| LightGBM, domestic | 0.485 | 0.00110 | — (fails) |
| LightGBM, +trade | 0.642 | 0.00199 | ~2.2× |

Fold-level logistic ROC (with trade): 0.72 / 0.64 / 0.72 / 0.74 — stable ≈0.7 discrimination across regimes.

## Honest reading

1. **Moderate discrimination, low precision.** ROC ≈ 0.7 is respectable for rare-event prediction with public features, but at a 0.09% base rate the precision is too low for ingredient-level alerting at the 6-month horizon. This reframes RQ4: decision-curve analysis must show where (if anywhere) the alert use-case clears net-benefit zero.
2. **Ablation preview: no clear trade gain on AUC** (logit 0.676 → 0.670; LGBM 0.485 → 0.642 — unstable). Formal DeLong/DM tests in week 7, but H3 may resolve as a **well-powered null for onset prediction** — publishable when paired with the duration/trade-structure signal (hormones HR 0.40, p=0.08) and the event study.
3. **The power fix is product-level onsets.** ASPE counts 1,991 product-level shortage starts 2018–23 vs our 151 ingredient-level. Rebuilding labels at product (NDC) level multiplies events ~10× and directly matches Pall et al.'s granularity. **Recommended before the week-7 ablation is finalized.**
4. LightGBM's failure on domestic-only is a small-events symptom, not a bug: 131 training positives cannot support tree ensembles; with trade features (more continuous variation) it stabilizes but still doesn't beat logistic.

## Decision needed (flag for Anubhaw)

Product-level rebuild (≈1 extra session, stronger paper) vs proceed to ablation at ingredient level (faster, weaker power). Recommendation: **rebuild at product level** — it strengthens both RQ1 and the H3 test, and the spell machinery transfers unchanged.
