# Drug Shortage Forecasting Under Trade-Policy Stress

Predicting US drug shortage onset and duration from public market-structure and trade-policy signals. See `PROPOSAL.md` for the full research plan.

## Layout

```
data/raw/        immutable cached pulls (parquet, pull-date stamped) — never edited
data/interim/    entity-resolved intermediate tables
data/processed/  frozen analysis panels (ingredient × month)
notebooks/       exploratory analysis (numbered: 01_, 02_, ...)
src/shortage/    package code (data pulls, features, models)
scripts/         entry points (pull_data.py, build_panel.py, ...)
experiments/     model runs, configs, metrics
reports/         proposal, figures, draft paper
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
pre-commit install
```

Copy `.env.example` to `.env` and add API keys (openFDA key optional but raises rate limits; USITC DataWeb token required for trade pulls).

## Week-1 data pull

```bash
python scripts/pull_data.py --all          # pull every core source
python scripts/pull_data.py --source fda_shortages nadac   # or selected sources
```

Pulls are cached to `data/raw/<source>/` as parquet with a `_meta.json` stamp; re-running skips fresh caches (override with `--force`).

## Reproducibility rules

1. `data/raw` is append-only; transformations live in code, never by hand.
2. Every model run writes config + metrics to `experiments/`.
3. Seeds fixed in `src/shortage/config.py`.
4. Temporal validation only — no random splits across time.
