# Entity-Resolution Coverage Report (Week-2 Milestone)

**Date:** 12 June 2026 · **Module:** `src/shortage/data/resolve.py` · **Outputs:** `data/interim/`

## Pipeline

FDA shortage records → normalized ingredient keys → matched against Orange Book (exploded to ingredient level, 56,213 rows) and the openFDA NDC directory (exploded to active-ingredient level, 219,622 rows).

Normalization tiers, applied in order: **exact** (uppercase, punctuation and dosage-form words stripped), **loose** (salt/hydrate suffixes also stripped), **component** (combination products split on `, ; / + AND WITH`; all components must match loose keys).

Ingredient source: 1,477 of 1,671 shortage records (88%) keyed from `openfda.substance_name`; the remaining 194 fall back to `generic_name`.

## Match rates

| Join | Tier | Ingredients | Records | Record share |
|---|---|---|---|---|
| **Orange Book** | exact | 202 | 1,388 | 83.1% |
| | loose | 10 | 169 | 10.1% |
| | component | 7 | 25 | 1.5% |
| | **matched total** | **219 / 246** | **1,582 / 1,671** | **94.7%** |
| **NDC directory** | exact | 227 | 1,624 | 97.2% |
| | loose + component | 8 | 26 | 1.6% |
| | **matched total** | **235 / 246** | **1,650 / 1,671** | **98.7%** |

217 of 246 ingredients (88%) matched in **both** sources.

## Unmatched analysis — all residuals explained

Orange Book, 27 unmatched ingredients (89 records, 5.3%):

- **13 biologics** (adalimumab + biosimilar suffixes, alteplase, peginterferon): correctly absent — biologics are licensed under BLAs and listed in the **Purple Book**, not the Orange Book. Action: flag via `is_biologic`; add Purple Book as a supplementary source if biologic shortages stay in scope.
- **Parenteral-nutrition / fluid components** (alanine, dextrose variants, sterile water, activated charcoal): listed at product granularity FDA doesn't track in OB the same way; low analytical priority but retained with `ob_match = none`.
- **Salt/ester edge cases** (pemetrexed disodium heptahydrate, esterified estrogens): resolvable by hand-mapping if needed (2–4 records each).

NDC directory, 11 unmatched (21 records, 1.3%): biosimilar suffix variants and the same nutrition components.

## Data-quality findings to carry forward

1. **Resolved-spell scarcity:** only 29 of 1,671 records have status `Resolved` in the openFDA endpoint — the API reflects a current snapshot, not full shortage history. **Survival analysis needs historical spells: bootstrap 2018–2023 outcomes from the ASPE structured set (as planned) and/or scrape the FDA resolved-shortages archive in week 3.**
2. Posting dates span 2012–2026, so onset timing is usable; `change_date`/`update_date` support spell reconstruction for current records.
3. Dosage forms mapped to 9 coarse buckets (`INJECTABLE` is the analytically critical class, consistent with ASPE).

## Verdict

Coverage exceeds the 90% working threshold on both joins. The spine (`ingredient_spine.parquet`, 246 ingredients with match flags) is ready for week-3 panel construction.
