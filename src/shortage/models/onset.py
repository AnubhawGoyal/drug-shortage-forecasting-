"""Week-6 onset classification (RQ1): predict shortage onset within 6 months.

Risk set: ingredient x month rows NOT currently in shortage.
Temporal splits (validated against FDA/ASHP annual counts, see week6 report):
    train <= 2022-12 | val 2023 | test 2024-01 .. 2026-06
Models: logistic baseline, LightGBM. Metrics: PR-AUC, ROC-AUC, Brier.

Feature sets (week-7 ablation reuses this module):
    DOMESTIC: market structure + history
    TRADE:    DOMESTIC + trade-exposure block
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from shortage.config import DATA_PROCESSED, EXPERIMENTS, SEED

OUT = EXPERIMENTS / "onset"
LABEL = "onset_next_6m"

DOMESTIC = ["n_products", "n_applicants", "anda_share", "injectable", "n_forms",
            "rx_share", "age_years", "months_in_shortage_24m", "ever_shortage_before",
            "log_price", "price_chg_12m", "generic_share_priced"]
TRADE = ["china_share", "india_share", "origin_hhi", "imp_yoy",
         "ieepa_china_rate", "s232_anticipation", "china_tariff_exposure"]


FOLDS = [  # (train_end, val_year, test_lo, test_hi) — rolling origin
    ("2019-12-01", 2020, "2021-01-01", "2021-12-01"),
    ("2020-12-01", 2021, "2022-01-01", "2022-12-01"),
    ("2021-12-01", 2022, "2023-01-01", "2023-12-01"),
    ("2022-12-01", 2023, "2024-01-01", "2025-12-01"),  # 2024+ pooled (event-scarce)
]


def load(features: list[str]) -> pd.DataFrame:
    pn = pd.read_parquet(DATA_PROCESSED / "panel_v2.parquet")
    pn = pn[~pn.in_shortage].copy()          # risk set
    pn = pn[pn.month <= "2025-12-01"]        # full 6m label lookahead
    pn["ever_shortage_before"] = pn.ever_shortage_before.astype(int)
    pn["injectable"] = pn.injectable.astype(int)
    for c in ["log_price", "price_chg_12m", "generic_share_priced"]:
        if c in features:
            pn[c] = pn[c].fillna(-1)  # sentinel: no NADAC coverage (documented)
    return pn.dropna(subset=[f for f in features if f in pn.columns])


def run(features: list[str], tag: str) -> dict:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
    import lightgbm as lgb

    pn = load(features)
    preds, fold_stats = [], []
    for train_end, val_year, te_lo, te_hi in FOLDS:
        tr = pn[pn.month <= train_end]
        va = pn[pn.month.dt.year == val_year]
        te = pn[(pn.month >= te_lo) & (pn.month <= te_hi)]
        Xtr, ytr = tr[features].values, tr[LABEL].values
        Xva, yva = va[features].values, va[LABEL].values
        Xte, yte = te[features].values, te[LABEL].values

        sc = StandardScaler().fit(Xtr)
        logit = LogisticRegression(max_iter=2000, class_weight="balanced", C=0.1)
        logit.fit(sc.transform(Xtr), ytr)
        p1 = logit.predict_proba(sc.transform(Xte))[:, 1]

        m = lgb.LGBMClassifier(
            n_estimators=600, learning_rate=0.03, num_leaves=15, min_child_samples=50,
            subsample=0.8, colsample_bytree=0.8,
            scale_pos_weight=(len(ytr) - ytr.sum()) / max(ytr.sum(), 1),
            random_state=SEED, verbose=-1)
        m.fit(Xtr, ytr, eval_set=[(Xva, yva)], eval_metric="average_precision",
              callbacks=[lgb.early_stopping(50, verbose=False)])
        p2 = m.predict_proba(Xte)[:, 1]

        f = te[["ing_loose", "month", LABEL]].copy()
        f["p_logit"], f["p_lgbm"], f["fold"] = p1, p2, te_lo[:4]
        preds.append(f)
        fold_stats.append({"fold": te_lo[:4], "n_test": len(te), "pos_test": int(yte.sum()),
                           "logit_roc": float(roc_auc_score(yte, p1)) if yte.sum() else None,
                           "lgbm_roc": float(roc_auc_score(yte, p2)) if yte.sum() else None})

    allp = pd.concat(preds, ignore_index=True)
    y, P1, P2 = allp[LABEL].values, allp.p_logit.values, allp.p_lgbm.values
    res = {"tag": tag, "n_test_pooled": len(allp), "pos_test_pooled": int(y.sum()),
           "base_rate": float(y.mean()), "folds": fold_stats,
           "logit": {"pr_auc": float(average_precision_score(y, P1)),
                     "roc_auc": float(roc_auc_score(y, P1)),
                     "brier": float(brier_score_loss(y, P1))},
           "lgbm": {"pr_auc": float(average_precision_score(y, P2)),
                    "roc_auc": float(roc_auc_score(y, P2)),
                    "brier": float(brier_score_loss(y, P2))}}
    OUT.mkdir(parents=True, exist_ok=True)
    allp.to_parquet(OUT / f"pred_{tag}.parquet", index=False)
    (OUT / f"metrics_{tag}.json").write_text(json.dumps(res, indent=2))
    return res


def main(which: str) -> None:
    if which in ("domestic", "both"):
        r = run(DOMESTIC, "domestic")
        print(json.dumps(r, indent=2))
    if which in ("trade", "both"):
        r = run(DOMESTIC + TRADE, "trade")
        print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "both")
