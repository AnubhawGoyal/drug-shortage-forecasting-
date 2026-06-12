"""Week-8: robustness (cluster-robust DM, calibration, DCA) + tariff event study.

Stages: dm | calib | dca | event
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
from scipy import stats

from shortage.config import DATA_PROCESSED, EXPERIMENTS, FIGURES

ABL = EXPERIMENTS / "ablation"
OUT = EXPERIMENTS / "week8"
LABEL = "onset_next_6m"


def _pred():
    d = pd.read_parquet(ABL / "pred_form_domestic.parquet")
    t = pd.read_parquet(ABL / "pred_form_trade.parquet")
    return d.merge(t, on=["unit", "month", LABEL], suffixes=("_dom", "_trd"))


def stage_dm() -> None:
    """Cluster-robust DM: Brier loss differential averaged per unit, t-test across units."""
    mg = _pred()
    y = mg[LABEL].astype(int).values
    ld = (mg.p_logit_trd.values - y) ** 2 - (mg.p_logit_dom.values - y) ** 2
    mg["ld"] = ld
    cl = mg.groupby("unit").ld.mean()
    t, p = stats.ttest_1samp(cl, 0.0)
    res = {"naive_dm_p": float(2 * stats.norm.sf(abs(ld.mean() / (ld.std(ddof=1) / np.sqrt(len(ld)))))),
           "n_clusters": int(len(cl)), "mean_loss_diff": float(ld.mean()),
           "cluster_t": float(t), "cluster_p": float(p)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dm_cluster.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


def _ece(y, p, bins=10):
    df = pd.DataFrame({"y": y, "p": p})
    df["bin"] = pd.qcut(df.p, bins, duplicates="drop")
    g = df.groupby("bin", observed=True).agg(conf=("p", "mean"), acc=("y", "mean"), n=("y", "size"))
    return float((g.n * (g.conf - g.acc).abs()).sum() / g.n.sum())


def stage_calib() -> None:
    """ECE raw vs isotonic recalibrated: fit on 2021-23 folds, apply to 2024-25 fold."""
    from sklearn.isotonic import IsotonicRegression

    mg = _pred()
    fit = mg[mg.fold_trd.astype(int) <= 2023]
    app = mg[mg.fold_trd.astype(int) == 2024]
    res = {}
    for m in ["p_logit_trd", "p_logit_dom"]:
        iso = IsotonicRegression(out_of_bounds="clip").fit(fit[m], fit[LABEL].astype(int))
        p_raw, p_cal = app[m].values, iso.predict(app[m].values)
        y = app[LABEL].astype(int).values
        res[m] = {"ece_raw": _ece(y, p_raw), "ece_iso": _ece(y, p_cal),
                  "brier_raw": float(np.mean((p_raw - y) ** 2)),
                  "brier_iso": float(np.mean((p_cal - y) ** 2)),
                  "base_rate_2024_25": float(y.mean())}
    (OUT / "calibration.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


def stage_dca() -> None:
    """Decision-curve analysis: net benefit of acting on alerts vs treat-all/none."""
    from sklearn.isotonic import IsotonicRegression

    mg = _pred()
    fit = mg[mg.fold_trd.astype(int) <= 2023]
    app = mg[mg.fold_trd.astype(int) == 2024]
    iso = IsotonicRegression(out_of_bounds="clip").fit(fit.p_logit_trd, fit[LABEL].astype(int))
    p = iso.predict(app.p_logit_trd.values)
    y = app[LABEL].astype(int).values
    rows = []
    for thr in [0.0005, 0.001, 0.002, 0.005, 0.01, 0.02]:
        act = p >= thr
        tp = float((y[act] == 1).sum()) / len(y)
        fp = float((y[act] == 0).sum()) / len(y)
        nb = tp - fp * thr / (1 - thr)
        nb_all = y.mean() - (1 - y.mean()) * thr / (1 - thr)
        rows.append({"threshold": thr, "alerts_share": float(act.mean()),
                     "net_benefit_model": nb, "net_benefit_treat_all": nb_all})
    (OUT / "dca.json").write_text(json.dumps(rows, indent=2))
    print(pd.DataFrame(rows).to_string(index=False))


def stage_event() -> None:
    """DiD/event study: onset and resolution hazards, high vs low China exposure,
    around IEEPA Feb-2025 (treatment start). Sample: 2023-01..2026-06."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import statsmodels.formula.api as smf

    pn = pd.read_parquet(DATA_PROCESSED / "panel_form.parquet",
                         columns=["unit", "month", "in_shortage", "onset_this_month",
                                  "china_share", "anda_share"])
    pn = pn[(pn.month >= "2023-01-01") & pn.china_share.notna()]
    # exposure: top tercile of china_share (fixed pre-period, Jan-2025 values)
    base = pn[pn.month == "2025-01-01"].set_index("unit").china_share
    cut = base.quantile(2 / 3)
    pn["high_exp"] = pn.unit.map(base).ge(cut).astype(int)
    pn["post"] = (pn.month >= "2025-02-01").astype(int)

    # (a) onset DiD on the not-in-shortage risk set; outcome = onset NEXT month
    # (onset months are flagged in_shortage, so same-month outcome would be filtered out)
    pn = pn.sort_values(["unit", "month"])
    pn["onset_next"] = pn.groupby("unit").onset_this_month.shift(-1)
    on = pn[~pn.in_shortage].dropna(subset=["onset_next"]).copy()
    on["y"] = on.onset_next.astype(int)
    m1 = smf.ols("y ~ high_exp * post", data=on).fit(
        cov_type="cluster", cov_kwds={"groups": on.unit})
    # (b) resolution DiD: among in-shortage rows, does the spell end next month?
    # shift on the FULL panel first (filtering first would skip non-shortage months)
    pn["next_in"] = pn.groupby("unit").in_shortage.shift(-1)
    sh = pn[pn.in_shortage].dropna(subset=["next_in"]).copy()
    sh["resolved_next"] = (~sh.next_in.astype(bool)).astype(int)
    m2 = smf.ols("resolved_next ~ high_exp * post", data=sh).fit(
        cov_type="cluster", cov_kwds={"groups": sh.unit})

    res = {"design": "DiD 2023-01..2026-06, treat=top-tercile China share (fixed Jan-2025), post=Feb-2025 (IEEPA)",
           "onset": {"coef_did": float(m1.params["high_exp:post"]),
                     "se": float(m1.bse["high_exp:post"]), "p": float(m1.pvalues["high_exp:post"]),
                     "n": int(m1.nobs), "base_rate": float(on.y.mean())},
           "resolution": {"coef_did": float(m2.params["high_exp:post"]),
                          "se": float(m2.bse["high_exp:post"]), "p": float(m2.pvalues["high_exp:post"]),
                          "n": int(m2.nobs), "base_rate": float(sh.resolved_next.mean())}}

    # event-time plot: quarterly onset rates by group
    on["q"] = on.month.dt.to_period("Q").astype(str)
    ev = on.groupby(["q", "high_exp"]).y.mean().unstack()
    fig, ax = plt.subplots(figsize=(9, 4))
    ev.plot(ax=ax, marker="o")
    ax.axvline(list(ev.index).index("2025Q1"), color="red", ls="--", label="IEEPA Feb 2025")
    ax.set_ylabel("monthly onset rate"); ax.legend(["low exposure", "high exposure", "IEEPA"])
    ax.set_title("Onset rate by China-exposure tercile")
    fig.tight_layout(); fig.savefig(FIGURES / "event_study_onset.png", dpi=150)

    (OUT / "event_study.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    {"dm": stage_dm, "calib": stage_calib, "dca": stage_dca, "event": stage_event}[sys.argv[1]]()
