"""Week-7: form-level rebuild + formal trade ablation (H3).

Unit = (ingredient, dosage-form bucket); form falls back to the ingredient's
modal NDC form when unparseable from the shortage string.

Stages: spells | panel | run | test
"""

from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np
import pandas as pd

from shortage.config import DATA_INTERIM, DATA_PROCESSED, EXPERIMENTS, SEED
from shortage.data.resolve import map_form, norm_loose

OUT = EXPERIMENTS / "ablation"
LABEL = "onset_next_6m"
DOMESTIC = ["n_products", "n_applicants", "anda_share", "n_forms", "rx_share",
            "age_years", "log_price", "price_chg_12m", "generic_share_priced",
            "is_injectable_form", "unit_months_short_24m", "unit_ever_short",
            "f_TABLET", "f_CAPSULE", "f_LIQUID", "f_TOPICAL", "f_INHALATION"]
TRADE = ["china_share", "india_share", "origin_hhi", "imp_yoy",
         "ieepa_china_rate", "s232_anticipation", "china_tariff_exposure"]


def modal_form() -> pd.Series:
    ndc = pd.read_parquet(DATA_INTERIM / "ndc_ingredients.parquet", columns=["ing_loose", "form"])
    return ndc.groupby("ing_loose").form.agg(lambda x: x.mode().iat[0])


def stage_spells() -> None:
    mf = modal_form()
    frames = []
    for f in sorted(glob.glob(str((DATA_INTERIM.parent / "raw" / "fda_shortages_archive" / "snap_*.parquet")))):
        ts = os.path.basename(f)[5:19].rstrip(".parquet")
        df = pd.read_parquet(f)
        cols = {c.lower().strip(): c for c in df.columns}
        gn, st, ip = cols.get("generic name"), cols.get("status"), cols.get("initial posting date")
        if not (gn and st):
            continue
        frames.append(pd.DataFrame({
            "snap_date": pd.to_datetime(ts[:8], format="%Y%m%d"),
            "ing_loose": norm_loose(df[gn]), "form_raw": map_form(df[gn]),
            "status": df[st].str.strip(),
            "posting_date": pd.to_datetime(df[ip], errors="coerce") if ip else pd.NaT}))
    live = pd.read_parquet(DATA_INTERIM.parent / "raw" / "fda_shortages" / "data.parquet")
    frames.append(pd.DataFrame({
        "snap_date": pd.Timestamp("2026-06-12"),
        "ing_loose": norm_loose(live.generic_name), "form_raw": map_form(live.dosage_form),
        "status": live.status.str.strip(),
        "posting_date": pd.to_datetime(live.initial_posting_date, errors="coerce")}))
    s = pd.concat(frames, ignore_index=True)
    s = s[s.ing_loose != ""]
    fb = s.ing_loose.map(mf)
    s["form"] = np.where(s.form_raw.isin(["UNKNOWN", "OTHER"]) & fb.notna(), fb, s.form_raw)
    s["unit"] = s.ing_loose + "||" + s.form

    snap_dates = sorted(s.snap_date.unique())
    cur = (s.assign(is_cur=s.status.eq("Current"))
           .groupby(["unit", "snap_date"])
           .agg(in_short=("is_cur", "any"), pmin=("posting_date", "min")).reset_index())
    spells = []
    for unit, g in cur.groupby("unit"):
        g = g.set_index("snap_date").reindex(snap_dates)
        g["in_short"] = g["in_short"].astype(object).fillna(False).astype(bool)
        prev, sp = False, None
        for d in snap_dates:
            now = bool(g.loc[d, "in_short"])
            if now and not prev:
                sp = {"unit": unit, "first_seen": d, "onset_exact": g.loc[d, "pmin"],
                      "last_current": d, "end_lo": pd.NaT, "end_hi": pd.NaT}
            elif now:
                sp["last_current"] = d
                pm = g.loc[d, "pmin"]
                if pd.notna(pm) and (pd.isna(sp["onset_exact"]) or pm < sp["onset_exact"]):
                    sp["onset_exact"] = pm
            elif prev:
                sp.update(end_lo=sp["last_current"], end_hi=d); spells.append(sp); sp = None
            prev = now
        if sp is not None:
            spells.append(sp)
    df = pd.DataFrame(spells)
    df[["ing_loose", "form"]] = df.unit.str.split(r"\|\|", expand=True, regex=True)
    df["censored"] = df.end_hi.isna()
    df["onset"] = df.onset_exact.where(
        df.onset_exact.notna() & (df.onset_exact <= df.first_seen), df.first_seen)
    df.to_parquet(DATA_INTERIM / "shortage_spells_form.parquet", index=False)
    print(f"form spells: {len(df):,} | units {df.unit.nunique():,} | "
          f"onsets>=2018 {(df.onset >= '2018-01-01').sum():,}")


def stage_panel() -> None:
    sp = pd.read_parquet(DATA_INTERIM / "shortage_spells_form.parquet")
    ndc = pd.read_parquet(DATA_INTERIM / "ndc_ingredients.parquet", columns=["ing_loose", "form"])
    pairs = ndc.drop_duplicates()
    ing_feats = pd.read_parquet(DATA_PROCESSED / "panel_v2.parquet")
    keep = ["ing_loose", "month", "n_products", "n_applicants", "anda_share", "n_forms",
            "rx_share", "age_years", "log_price", "price_chg_12m", "generic_share_priced"] + TRADE
    ing_feats = ing_feats[keep]
    pairs = pairs[pairs.ing_loose.isin(set(ing_feats.ing_loose.unique()))]
    # union with observed shortage units (real products even if form bucket differs from NDC)
    sp_units = sp[["ing_loose", "form"]].drop_duplicates()
    sp_units = sp_units[sp_units.ing_loose.isin(set(ing_feats.ing_loose.unique()))]
    pairs = pd.concat([pairs, sp_units], ignore_index=True).drop_duplicates()
    pairs["unit"] = pairs.ing_loose + "||" + pairs.form

    months = pd.period_range("2018-01", "2026-06", freq="M").to_timestamp()
    grid = pairs.merge(pd.DataFrame({"month": months}), how="cross")

    sp["end_mid"] = sp.end_lo + (sp.end_hi - sp.end_lo) / 2
    sp.loc[sp.censored, "end_mid"] = pd.Timestamp("2099-01-01")
    me = grid.month + pd.offsets.MonthEnd(0)
    act = grid.merge(sp[["unit", "onset", "end_mid"]], on="unit", how="left")
    act["hit"] = (act.onset <= act.month + pd.offsets.MonthEnd(0)) & (act.end_mid >= act.month)
    in_short = act.groupby(["unit", "month"]).hit.any()
    ons = act[(act.onset.dt.year == act.month.dt.year) & (act.onset.dt.month == act.month.dt.month)]
    onset_m = ons.groupby(["unit", "month"]).size() > 0

    grid = grid.set_index(["unit", "month"])
    grid["in_shortage"] = in_short.reindex(grid.index).fillna(False)
    grid["onset_this_month"] = onset_m.reindex(grid.index).fillna(False)
    grid = grid.reset_index().sort_values(["unit", "month"])

    g = grid.groupby("unit")["onset_this_month"]
    grid[LABEL] = g.transform(lambda s: s.shift(-1).rolling(6, min_periods=1).max().fillna(0)).astype(bool)
    grid["unit_months_short_24m"] = (grid.groupby("unit")["in_shortage"]
                                     .transform(lambda s: s.rolling(24, min_periods=1).sum().shift(1)).fillna(0))
    grid["unit_ever_short"] = (grid.groupby("unit")["onset_this_month"]
                               .transform(lambda s: s.shift(1).cumsum()).fillna(0) > 0).astype(int)
    grid["is_injectable_form"] = (grid.form == "INJECTABLE").astype(int)
    for f in ["TABLET", "CAPSULE", "LIQUID", "TOPICAL", "INHALATION"]:
        grid[f"f_{f}"] = (grid.form == f).astype(int)
    grid = grid.merge(ing_feats, on=["ing_loose", "month"], how="left")
    grid.to_parquet(DATA_PROCESSED / "panel_form.parquet", index=False)
    print(f"form panel: {len(grid):,} rows | units {grid.unit.nunique():,} | "
          f"onsets {int(grid.onset_this_month.sum()):,} | pos6 {int(grid[LABEL].sum()):,}")


FOLDS = [
    ("2019-12-01", 2020, "2021-01-01", "2021-12-01"),
    ("2020-12-01", 2021, "2022-01-01", "2022-12-01"),
    ("2021-12-01", 2022, "2023-01-01", "2023-12-01"),
    ("2022-12-01", 2023, "2024-01-01", "2025-12-01"),
]


def _load_panel(features):
    pn = pd.read_parquet(DATA_PROCESSED / "panel_form.parquet")
    pn = pn[~pn.in_shortage]
    pn = pn[pn.month <= "2025-12-01"]
    for c in ["log_price", "price_chg_12m", "generic_share_priced"]:
        pn[c] = pn[c].fillna(-1)
    return pn.dropna(subset=[f for f in features if f in pn.columns])


def stage_run() -> None:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
    import lightgbm as lgb

    OUT.mkdir(parents=True, exist_ok=True)
    for tag, features in [("domestic", DOMESTIC), ("trade", DOMESTIC + TRADE)]:
        pn = _load_panel(DOMESTIC + TRADE)  # same row set for both => paired tests valid
        preds = []
        for train_end, val_year, te_lo, te_hi in FOLDS:
            tr = pn[pn.month <= train_end]
            va = pn[pn.month.dt.year == val_year]
            te = pn[(pn.month >= te_lo) & (pn.month <= te_hi)]
            Xtr, ytr = tr[features].values, tr[LABEL].values
            Xte, yte = te[features].values, te[LABEL].values
            sc = StandardScaler().fit(Xtr)
            logit = LogisticRegression(max_iter=3000, class_weight="balanced", C=0.1)
            logit.fit(sc.transform(Xtr), ytr)
            p1 = logit.predict_proba(sc.transform(Xte))[:, 1]
            mdl = lgb.LGBMClassifier(n_estimators=600, learning_rate=0.03, num_leaves=31,
                                     min_child_samples=50, subsample=0.8, colsample_bytree=0.8,
                                     scale_pos_weight=(len(ytr) - ytr.sum()) / max(ytr.sum(), 1),
                                     random_state=SEED, verbose=-1)
            mdl.fit(Xtr, ytr, eval_set=[(va[features].values, va[LABEL].values)],
                    eval_metric="average_precision",
                    callbacks=[lgb.early_stopping(50, verbose=False)])
            p2 = mdl.predict_proba(Xte)[:, 1]
            f = te[["unit", "month", LABEL]].copy()
            f["p_logit"], f["p_lgbm"], f["fold"] = p1, p2, te_lo[:4]
            preds.append(f)
        allp = pd.concat(preds, ignore_index=True)
        y = allp[LABEL].values
        res = {"tag": tag, "n": len(allp), "pos": int(y.sum())}
        for mname in ["p_logit", "p_lgbm"]:
            p = allp[mname].values
            res[mname] = {"pr_auc": float(average_precision_score(y, p)),
                          "roc_auc": float(roc_auc_score(y, p)),
                          "brier": float(brier_score_loss(y, p))}
        allp.to_parquet(OUT / f"pred_form_{tag}.parquet", index=False)
        (OUT / f"metrics_form_{tag}.json").write_text(json.dumps(res, indent=2))
        print(json.dumps(res))


def _delong(y, p1, p2):
    """Paired DeLong test for difference in AUC (fast implementation)."""
    from scipy import stats

    def midrank(x):
        order = np.argsort(x); ranks = np.empty(len(x))
        i = 0
        sx = x[order]
        while i < len(x):
            j = i
            while j < len(x) - 1 and sx[j + 1] == sx[i]:
                j += 1
            ranks[order[i:j + 1]] = (i + j) / 2 + 1
            i = j + 1
        return ranks

    pos, neg = y == 1, y == 0
    m, n = pos.sum(), neg.sum()
    aucs, v01, v10 = [], [], []
    for p in (p1, p2):
        tx, ty = p[pos], p[neg]
        r_all = midrank(np.concatenate([tx, ty]))
        rx, ry = midrank(tx), midrank(ty)
        auc = (r_all[:m].sum() - m * (m + 1) / 2) / (m * n)
        aucs.append(auc)
        v01.append((r_all[:m] - rx) / n)
        v10.append(1 - (r_all[m:] - ry) / m)
    s01 = np.cov(np.vstack(v01)); s10 = np.cov(np.vstack(v10))
    var = (s01[0, 0] + s01[1, 1] - 2 * s01[0, 1]) / m + (s10[0, 0] + s10[1, 1] - 2 * s10[1, 1 - 1]) / n
    var = (s01[0, 0] + s01[1, 1] - 2 * s01[0, 1]) / m + (s10[0, 0] + s10[1, 1] - 2 * s10[0, 1]) / n
    z = (aucs[0] - aucs[1]) / np.sqrt(max(var, 1e-12))
    from scipy.stats import norm as N
    return aucs, float(z), float(2 * N.sf(abs(z)))


def stage_test() -> None:
    from scipy import stats

    d = pd.read_parquet(OUT / "pred_form_domestic.parquet")
    t = pd.read_parquet(OUT / "pred_form_trade.parquet")
    mg = d.merge(t, on=["unit", "month", LABEL], suffixes=("_dom", "_trd"))
    y = mg[LABEL].astype(int).values
    res = {"n": len(mg), "pos": int(y.sum())}
    for mname in ["p_logit", "p_lgbm"]:
        p_dom, p_trd = mg[f"{mname}_dom"].values, mg[f"{mname}_trd"].values
        aucs, z, pde = _delong(y, p_trd, p_dom)
        # Diebold-Mariano on Brier loss differential (HLN small-sample not needed, n large)
        ld = (p_trd - y) ** 2 - (p_dom - y) ** 2
        dm = ld.mean() / (ld.std(ddof=1) / np.sqrt(len(ld)))
        pdm = float(2 * stats.norm.sf(abs(dm)))
        res[mname] = {"auc_trade": aucs[0], "auc_domestic": aucs[1],
                      "delta_auc": aucs[0] - aucs[1], "delong_z": z, "delong_p": pde,
                      "brier_diff_trade_minus_dom": float(ld.mean()), "dm_stat": float(dm), "dm_p": pdm}
    (OUT / "h3_tests.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    {"spells": stage_spells, "panel": stage_panel, "run": stage_run, "test": stage_test}[sys.argv[1]]()
