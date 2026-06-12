# Week-3 Report — Spell Reconstruction, Panel Build, ASPE Replication

**Date:** 12 June 2026 · Modules: `pull_archive.py`, `spells.py`, `panel.py`

## 1. Historical spell reconstruction (the snapshot problem, solved)

The live FDA database and openFDA both retain only 29 Resolved records — useless for survival analysis. Solution implemented: **Wayback Machine snapshots of the FDA shortage CSV export** (44 monthly-collapsed snapshots listed, 2019–2026; 26 cached so far — archive.org rate-limited the rest; remaining 18, mostly 2024–26, queued for next session).

Method: stack snapshots, mark an ingredient in-shortage at snapshot t if any record is `Current`, diff across snapshots. **Onsets are exact** (Initial Posting Date field). **Resolutions are interval-censored** between consecutive snapshots (median interval width: 101 days) — handled natively by interval-censored survival estimators; this is a methodological feature, not a bug.

Result: **350 ingredient-level spells** (283 interval-censored resolutions, 67 right-censored), 329 distinct ingredients, onsets 2012–2026. The archive recovered 83 shortage ingredients invisible in today's snapshot.

## 2. Panel

`data/processed/panel.parquet`: **143,242 rows = 1,556 Orange Book ingredients × 102 months** (2018-01 … 2026-06). Risk set = all OB ingredients marketed by month t (fully-discontinued excluded). Features: n_products, n_applicants, ANDA share, injectable flag, ingredient age, trailing shortage history (leak-free: shifted/trailing windows only). Labels: `onset_this_month`, `onset_next_3m` / `onset_next_6m`.

Key stats: shortage-month share 5.0%; 151 in-window onset events; `onset_next_6m` positive rate 0.63% (heavy imbalance — expected; PR-AUC and calibrated probabilities, not accuracy, are the right metrics).

## 3. ASPE replication check

| Benchmark | ASPE (2018–23) | Ours | Verdict |
|---|---|---|---|
| Ingredients in shortage | 258 (CDER Rx only) | 324 | Same order; ours +26% — we include OTC/biologic/combination keys ASPE excludes. Acceptable; will re-run on CDER-Rx filter |
| Injectable share | 50% of products | 58.3% of current-snapshot records | Directionally consistent (snapshots over-represent persistent injectable shortages) |
| Injectable risk | qualitative: highest | ever-shortage 16.9% vs 5.1% non-injectable | ✓ |

## 4. Honest findings / caveats

1. **H1 needs conditioning:** raw ever-shortage rate is *higher* for many-applicant ingredients (12.9%) than few-applicant ones (2.9%) — manufacturer count is confounded with market size/volume (big old generics have both many ANDAs and high shortage exposure). H1's "low manufacturer count → high hazard" claim must be tested *within* product class with controls (as ASPE does at product level), not raw. This goes in the modeling spec.
2. **Ingredient-level durations are long** (median 625 days for 2018+ resolved spells) vs product-level literature (~14 months): ingredient spells aggregate overlapping product spells. Correct for our unit of analysis; will report both levels.
3. **2024–26 onsets are undercounted** (4/3/1 per year) until the remaining 18 archive snapshots are cached — **blocking for tariff-era modeling; first item next session.**
4. 2022 has a single snapshot → wider resolution intervals in that year.

## 5. Next (week 4 plan)

Finish archive cache → rebuild spells/panel → ingredient→HS trade-feature mapping (Census cache + USITC tariff rates, token live) → panel v2 freeze.
