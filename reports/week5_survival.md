# Week-5 Report — Survival Analysis of Shortage Duration (RQ2)

**Date:** 12 June 2026 · Module: `src/shortage/models/survival.py` · Results: `experiments/survival/`

## Dataset

151 ingredient-level spells with onset ≥ 2018-01 and observable panel features at onset; 116 resolution events, 35 right-censored (2026-06-12). Resolution dates use the interval midpoint; sensitivity below.

## Kaplan-Meier (figure: `reports/figures/km_injectable.png`)

| Group | Median spell duration |
|---|---|
| All spells | **28.8 months** (sensitivity: 27.8 lower-bound / 30.1 upper-bound — interval censoring barely moves it) |
| Injectable | 31.1 months |
| Non-injectable | 24.4 months |

Injectable vs non-injectable logrank **p = 0.046** — injectable shortages last significantly longer, consistent with ASPE and the sterile-injectables literature. Ingredient-level durations exceed product-level literature figures (~14 months) by construction: ingredient spells aggregate overlapping product spells.

## Cox proportional hazards (event = resolution; HR < 1 ⇒ slower resolution ⇒ longer shortage)

Concordance 0.601. **No PH violations** (all Schoenfeld p > 0.05) — proportional hazards is adequate for this specification.

Directionally (none individually significant at n=151): injectable HR 0.76, more applicants HR 0.83/log-unit (more-supplier ingredients resolve *slower* — consistent with the week-3 market-size confound), hormones (HS 2937) HR 0.40 at p = 0.083 — concentrated-origin hormone APIs (origin HHI 0.66) resolve slowest, a suggestive trade-structure link worth highlighting.

## RSF vs Cox (held-out 30% split, seed fixed)

| Model | Test concordance |
|---|---|
| Cox (penalized) | **0.595** |
| Random survival forest | 0.536 |

**Honest negative result: RSF underperforms Cox at this sample size.** With 105 training spells, flexible models overfit; the linear model wins. Integrated Brier (RSF) 0.214.

## Implications for the paper

1. Survival section stands on KM + Cox with interval-censoring sensitivity — defensible and clean. RSF stays as a reported comparison (reviewers will ask), framed as a sample-size finding.
2. The ML weight of the paper shifts to onset classification (week 6), where the panel gives 143k rows and 902 positives — there the flexible models have room to work.
3. Consider a product-level spell robustness run (larger n) if time permits.
4. The hormone/origin-concentration signal (HR 0.40, p 0.08) previews RQ3 — trade structure correlating with duration.

## Caveats

n=151 limits power; spells with onset <2018 excluded (left-truncation avoidance); trade covariates are heading-level (class mapping v1); 2024–26 onsets thin (11/3/1) pending week-5 cross-validation against FDA annual counts.
