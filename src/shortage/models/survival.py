"""Week-5 survival analysis of shortage spell duration (RQ2).

Dataset: spells with onset >= 2018-01 (panel features observable at onset).
Duration: onset -> resolution midpoint (interval-censored ends; lo/hi bounds
used as sensitivity). Right-censored at 2026-06-12.

Stages (CLI): km | cox | rsf  — each writes to experiments/survival/.
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from shortage.config import DATA_INTERIM, DATA_PROCESSED, EXPERIMENTS, FIGURES, SEED

OUT = EXPERIMENTS / "survival"
CENSOR_DATE = pd.Timestamp("2026-06-12")
COVARS = ["log_applicants", "anda_share", "injectable", "log_age_years",
          "china_share", "origin_hhi", "hs_2936", "hs_2937", "hs_2939", "hs_2941"]


def build_dataset(end: str = "mid") -> pd.DataFrame:
    sp = pd.read_parquet(DATA_INTERIM / "shortage_spells.parquet")
    pn = pd.read_parquet(DATA_PROCESSED / "panel_v2.parquet")

    sp = sp[sp.onset >= "2018-01-01"].copy()
    sp["onset_month"] = sp.onset.values.astype("datetime64[M]")

    feats = pn[["ing_loose", "month", "n_applicants", "anda_share", "injectable",
                "age_years", "n_products", "hs4", "china_share", "origin_hhi"]]
    df = sp.merge(feats, left_on=["ing_loose", "onset_month"],
                  right_on=["ing_loose", "month"], how="inner")

    if end == "mid":
        endt = df.end_lo + (df.end_hi - df.end_lo) / 2
    elif end == "lo":
        endt = df.end_lo
    else:
        endt = df.end_hi
    df["event"] = ~df.censored
    df["dur_days"] = np.where(df.event, (endt - df.onset).dt.days,
                              (CENSOR_DATE - df.onset).dt.days)
    df = df[df.dur_days > 0].copy()

    df["log_applicants"] = np.log1p(df.n_applicants)
    df["log_age_years"] = np.log1p(df.age_years.clip(lower=0))
    df["injectable"] = df.injectable.astype(int)
    for c in ["2936", "2937", "2939", "2941"]:
        df[f"hs_{c}"] = (df.hs4 == c).astype(int)
    df = df.dropna(subset=COVARS + ["dur_days"])
    return df


def stage_km() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from lifelines import KaplanMeierFitter

    df = build_dataset()
    OUT.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    res = {"n_spells": len(df), "n_events": int(df.event.sum())}

    fig, ax = plt.subplots(figsize=(8, 5))
    for label, sub in [("Injectable", df[df.injectable == 1]),
                       ("Non-injectable", df[df.injectable == 0])]:
        km = KaplanMeierFitter()
        km.fit(sub.dur_days / 30.44, event_observed=sub.event, label=f"{label} (n={len(sub)})")
        km.plot_survival_function(ax=ax)
        res[f"median_months_{label.lower().replace('-','_')}"] = (
            float(km.median_survival_time_) if np.isfinite(km.median_survival_time_) else None)
    ax.set_xlabel("Months since shortage onset"); ax.set_ylabel("P(still in shortage)")
    ax.set_title("Shortage spell survival, 2018–2026 (ingredient level)")
    fig.tight_layout(); fig.savefig(FIGURES / "km_injectable.png", dpi=150)

    # logrank
    from lifelines.statistics import logrank_test
    lr = logrank_test(df[df.injectable == 1].dur_days, df[df.injectable == 0].dur_days,
                      df[df.injectable == 1].event, df[df.injectable == 0].event)
    res["logrank_injectable_p"] = float(lr.p_value)

    # sensitivity: end-date convention
    for end in ["lo", "hi"]:
        d2 = build_dataset(end)
        km = KaplanMeierFitter().fit(d2.dur_days / 30.44, d2.event)
        res[f"median_months_all_{end}"] = float(km.median_survival_time_)
    km = KaplanMeierFitter().fit(df.dur_days / 30.44, df.event)
    res["median_months_all_mid"] = float(km.median_survival_time_)

    (OUT / "km.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


def stage_cox() -> None:
    from lifelines import CoxPHFitter

    df = build_dataset()
    cph = CoxPHFitter(penalizer=0.05)
    cph.fit(df[COVARS + ["dur_days", "event"]], duration_col="dur_days", event_col="event")
    summ = cph.summary[["coef", "exp(coef)", "se(coef)", "p"]].round(4)

    # Schoenfeld / proportional-hazards check
    from lifelines.statistics import proportional_hazard_test
    ph = proportional_hazard_test(cph, df[COVARS + ["dur_days", "event"]], time_transform="rank")
    ph_p = ph.summary["p"].round(4).to_dict()

    res = {
        "n": len(df), "events": int(df.event.sum()),
        "concordance": float(cph.concordance_index_),
        "summary": summ.to_dict(orient="index"),
        "schoenfeld_p": ph_p,
    }
    (OUT / "cox.json").write_text(json.dumps(res, indent=2, default=str))
    print(f"Cox concordance: {res['concordance']:.3f}  (n={res['n']}, events={res['events']})")
    print(summ.to_string())
    print("PH-test p-values:", ph_p)


def stage_rsf() -> None:
    from sksurv.ensemble import RandomSurvivalForest
    from sksurv.metrics import concordance_index_censored, integrated_brier_score
    from sksurv.util import Surv
    from sklearn.model_selection import train_test_split

    df = build_dataset()
    X = df[COVARS].values
    y = Surv.from_arrays(df.event.values, df.dur_days.values)
    Xtr, Xte, ytr, yte, df_tr, df_te = train_test_split(
        X, y, df, test_size=0.3, random_state=SEED, stratify=df.event)

    rsf = RandomSurvivalForest(n_estimators=300, min_samples_leaf=10,
                               random_state=SEED, n_jobs=2)
    rsf.fit(Xtr, ytr)
    pred = rsf.predict(Xte)
    ci = concordance_index_censored(df_te.event.values, df_te.dur_days.values, pred)[0]

    # integrated Brier on common time grid
    times = np.percentile(df_te[df_te.event].dur_days, np.arange(10, 91, 10))
    surv_fns = rsf.predict_survival_function(Xte)
    S = np.row_stack([fn(times) for fn in surv_fns])
    ibs = integrated_brier_score(ytr, yte, S, times)

    # Cox on same split for comparison
    from lifelines import CoxPHFitter
    cph = CoxPHFitter(penalizer=0.05).fit(
        df_tr[COVARS + ["dur_days", "event"]], "dur_days", "event")
    cox_pred = cph.predict_partial_hazard(df_te[COVARS])
    cox_ci = concordance_index_censored(df_te.event.values, df_te.dur_days.values,
                                        cox_pred.values)[0]

    res = {"rsf_concordance_test": float(ci), "cox_concordance_test": float(cox_ci),
           "rsf_integrated_brier": float(ibs), "n_train": len(df_tr), "n_test": len(df_te)}
    (OUT / "rsf.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    {"km": stage_km, "cox": stage_cox, "rsf": stage_rsf}[sys.argv[1]]()
