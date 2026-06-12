# Week-8 Report — Robustness, Calibration, Decision Curves, Tariff Event Study

**Date:** 12 June 2026 · Module: `src/shortage/models/week8.py` · Results: `experiments/week8/`

## 1. Cluster-robust Diebold-Mariano (Brier, trade vs domestic)

Unit-clustered (3,938 clusters): t = −6.43, **p = 1.4e-10** — the raw-probability Brier gain survives clustering. But see §2: it does not survive recalibration.

## 2. Calibration (fit isotonic on 2021–23 folds, apply to 2024–25)

| | ECE raw | ECE isotonic | Brier raw | Brier isotonic |
|---|---|---|---|---|
| Logit +trade | 0.339 | 0.0006 | 0.209 | 9.899e-5 |
| Logit domestic | 0.336 | 0.0006 | 0.201 | 9.903e-5 |

Raw probabilities are badly mis-scaled (class-weighting artifact); isotonic recalibration fixes calibration essentially completely (ECE ≤ 0.001 — **H4's ECE ≤ 0.05 target met**). Crucially, **after recalibration the trade-vs-domestic Brier difference collapses to ~4e-9** — the §1 "gain" was probability-scale, not signal. H3 verdict is now uniform: **no discrimination gain, no recalibrated proper-score gain.**

## 3. Decision-curve analysis (RQ4, 2024–25 regime)

Net benefit of model-based alerting ≤ 0 at every threshold tested (base rate 0.0098%): in the current low-onset regime, 6-month form-level alerts are **not decision-grade** — the model beats treat-all everywhere but never beats treat-none. Honest RQ4 answer: screening value exists only in higher-event regimes (2021–23 evaluation as supplementary analysis — queued as a robustness item); the paper should frame the tool as risk-ranking for monitoring prioritization, not actionable alerts.

## 4. Tariff event study (H2 — the decisive causal margin)

Design: DiD, 2023-01–2026-06, treatment = top-tercile China import share (fixed at Jan-2025 values), post = Feb-2025 (IEEPA China tariffs); unit-clustered SEs. Figure: `reports/figures/event_study_onset.png`.

| Margin | DiD coefficient | SE | p | Base rate |
|---|---|---|---|---|
| Onset (next month, risk set) | +0.00015 | 0.00024 | **0.53** | 0.00022 |
| Resolution (next month, in-shortage) | −0.0095 | 0.0142 | **0.50** | 0.0223 |

**Both margins null at conventional levels.** The resolution point estimate is directionally consistent with the duration story (high-exposure shortages resolving ~43% slower relative to base, post-tariff) but the CI is wide — power-limited, must be reported as such. Caveat: only ~16 months post-treatment; §232 pharma tariffs took effect Jul–Sep 2026 (after our window) and generics were exempt — the treatment dose to date is modest (10–20% IEEPA).

## The paper's conclusion (as of week 8)

A careful multi-margin null with one robust exception:

1. Trade/tariff exposure does **not** improve shortage onset prediction (ΔAUC +0.001, p=0.88).
2. After recalibration it adds **no** probability-quality gain either.
3. The IEEPA tariff shock produced **no detectable** differential onset or resolution effect through Jun 2026 (power-limited; modest dose; generics exempt from §232).
4. **But:** origin-concentrated APIs persist longest in shortage (hormones HR 0.40, p=0.08; injectables p=0.046) — structural concentration, not tariff flows, is where trade risk shows up.

Framing: *"Tariffs haven't (yet) moved US drug shortages — but origin concentration predicts which shortages persist."* Policy-relevant, honest, well-powered where it can be.

## Bug fixed during analysis

Onset months are flagged in-shortage in the panel, so a same-month outcome on the not-in-shortage risk set has zero events by construction; event-study outcomes use next-month onset/resolution with shifts computed on the full panel before filtering. (The week 6–7 classification labels were unaffected — `onset_next_6m` is forward-looking by construction.)

## Remaining for weeks 9–10

k=3 sensitivity; 2021–23 DCA; SHAP/coefficient attribution figure; paper draft → arXiv.
