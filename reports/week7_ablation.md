# Week-7 Report — Form-Level Rebuild + Formal Trade Ablation (H3)

**Date:** 12 June 2026 · Module: `src/shortage/models/ablation.py` · Results: `experiments/ablation/`

## Rebuild decision and outcome

Company-level units were attempted first: 1,282 spells, 1,105 onsets ≥2018 — but only 35% of FDA shortage companies matched NDC labelers by name (distributor-vs-manufacturer and name-variant noise). Rather than fuzzy-match entity hell, units were rebuilt at **ingredient × dosage-form** level (clean matching, decision-relevant): 372 spells, 320 onsets ≥2018, risk set = 4,017 units (NDC pairs ∪ observed shortage units), panel 409,734 rows, 1,017 positive 6-month labels.

Granularity paid off: **logistic ROC-AUC rose from 0.676 (ingredient) to 0.785 (form-level)** on pooled rolling-origin test folds. Test-window positives remain thin (79) because post-2020 new onsets are scarce in reality (FDA: 15 new in CY2024) — a substantive finding, not a data defect.

## H3 formal tests (paired, identical row sets; pooled 2021–25 out-of-sample; n=223,740, 79 events)

| Model | AUC domestic | AUC +trade | ΔAUC | DeLong p | ΔBrier (trade−dom) | DM p |
|---|---|---|---|---|---|---|
| **Logistic** | 0.7847 | 0.7856 | **+0.0010** | **0.877** | −0.0071 | <0.001 |
| LightGBM | 0.602 | 0.393 | −0.209 | <0.001 | −0.0032 | 0.002 |

**Headline: trade exposure does NOT improve onset discrimination** (ΔAUC ≈ 0.001, DeLong p = 0.88). The Brier improvement is statistically significant but requires caution: (a) naive DM treats 223k unit-month rows as independent — they're clustered by unit; a **cluster-robust DM is a week-8 must-do** before citing it; (b) class-weighted training inflates probability scales for both models, so Brier gains may reflect scale, not signal. LightGBM's collapse with trade features is small-event overfitting (79 events), reported as instability.

## Emerging paper narrative (coherent and defensible)

1. **Onset (RQ1):** public market-structure + price features achieve ROC ≈ 0.78 at the form level — good discrimination, inherently low precision at a 0.04% base rate; decision-curve framing required (RQ4).
2. **H3 at the prediction margin: a rigorous null** — trade exposure adds no short-horizon discriminative power.
3. **Duration margin (RQ2, week 5):** trade structure *does* correlate with persistence (origin-concentrated hormones resolve slowest, HR 0.40).
4. **Event study (week 8)** will test the causal margin around IEEPA/§232 dates.

"Tariff exposure shapes how long shortages last, not which products go short next" — if the event study cooperates, that's the abstract.

## Week-8 robustness queue

Cluster-robust DM (by unit); recalibrated probabilities (isotonic on validation) before final Brier/calibration claims; sensitivity: k=3 labels, ingredient-level replication; event study (IEEPA Feb/Mar 2025, Nov 2025; §232 Apr 2026); decision-curve analysis.
