"""Trade-exposure features: ingredient -> HS-4 API heading -> origin-mix series.

Mapping strategy (v1, documented limitation):
    Each ingredient is assigned one HS-4 API heading via pharmacological class
    (openFDA pharm_class) and name heuristics:
        2936 provitamins/vitamins      2937 hormones/steroids
        2939 alkaloids (incl. opiates) 2941 antibiotics
        2942 other organic API (default)
    The ingredient inherits its heading's monthly import-origin profile from
    the cached Census trade data (value, China/India share, origin HHI, YoY).

Policy features (verified facts, see reports/verification_week2.md):
    ieepa_china_rate: 0 before Feb 2025; 10 Feb 2025; 20 Mar 2025; 10 from Nov 2025
    s232_anticipation: 1 from Apr 2025 (investigation) to Mar 2026
    s232_enacted: 1 from Apr 2026 (proclamation; patented products)
    china_tariff_exposure = ieepa_china_rate x heading China import share

Output: data/interim/trade_features.parquet (ing_loose x month)
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from shortage.config import DATA_INTERIM, DATA_RAW

HS4 = ["2936", "2937", "2939", "2941", "2942"]

_RULES = [
    # (regex on pharm_class + name, hs4)
    (r"VITAMIN|ASCORBIC|THIAMINE|RIBOFLAVIN|NIACIN|FOLIC|CYANOCOBALAMIN|CALCITRIOL|ERGOCALCIFEROL", "2936"),
    (r"CORTICOSTEROID|ESTROGEN|ANDROGEN|PROGEST|INSULIN|THYROID|GLUCOCORTICOID|"
     r"PREDNIS|CORTISONE|DEXAMETHASONE|ESTRADIOL|TESTOSTERONE|LEVOTHYROXINE|HORMONE", "2937"),
    (r"OPIOID|ALKALOID|MORPHINE|CODEINE|HYDROCODONE|OXYCODONE|HYDROMORPHONE|"
     r"ATROPINE|SCOPOLAMINE|ERGOTAMINE|QUININE|THEOPHYLLINE|CAFFEINE|COCAINE|VINCRISTINE|VINBLASTINE", "2939"),
    (r"ANTIBACTERIAL|ANTIBIOTIC|CILLIN\b|CEPHALOSPORIN|CEF[A-Z]+|MYCIN\b|CYCLINE\b|"
     r"FLOXACIN|PENEM\b|MACROLIDE|AMINOGLYCOSIDE|SULFONAMIDE ANTIBACTERIAL|VANCOMYCIN", "2941"),
]


def classify_hs4() -> pd.DataFrame:
    """ing_loose -> hs4 using NDC pharm_class + shortage-event classes + names."""
    ndc_raw = pd.read_parquet(
        DATA_RAW / "ndc_directory" / "part-0000.parquet",
        columns=["product_ndc", "pharm_class", "openfda.pharm_class_epc"],
    )
    ndc_ing = pd.read_parquet(DATA_INTERIM / "ndc_ingredients.parquet",
                              columns=["product_ndc", "ing_loose"])
    m = ndc_ing.merge(ndc_raw, on="product_ndc", how="left")

    def _txt(x):
        if isinstance(x, (list, np.ndarray)):
            return " ".join(map(str, x))
        return "" if pd.isna(x) else str(x)

    m["cls"] = (m["pharm_class"].map(_txt) + " " + m["openfda.pharm_class_epc"].map(_txt)).str.upper()
    cls = m.groupby("ing_loose")["cls"].apply(lambda s: " ".join(set(" ".join(s).split()))[:4000])
    cls = cls.reset_index()
    text = cls.ing_loose + " " + cls.cls
    cls["hs4"] = "2942"
    for pat, code in _RULES:
        hit = text.str.contains(pat, regex=True) & (cls.hs4 == "2942")
        cls.loc[hit, "hs4"] = code
    return cls[["ing_loose", "hs4"]]


def heading_series() -> pd.DataFrame:
    """Monthly origin-mix per HS-4 heading from cached Census pulls."""
    out = []
    for code in HS4:
        df = pd.read_parquet(DATA_RAW / "trade_census" / f"hs{code}.parquet")
        df["val"] = pd.to_numeric(df.GEN_VAL_MO, errors="coerce").fillna(0)
        df["month"] = pd.to_datetime(df.time, format="%Y-%m")
        df = df[df.CTY_CODE.str.fullmatch(r"[1-7][0-9]{3}")]  # true countries only (codes 1010-7990; drops TOTAL, EU/NATO/region aggregates)
        g = df.groupby("month")
        tot = g.val.sum()
        cn = df[df.CTY_NAME.str.contains("CHINA", na=False)].groupby("month").val.sum()
        ind = df[df.CTY_NAME.eq("INDIA")].groupby("month").val.sum()
        hhi = g.apply(lambda x: ((x.groupby("CTY_NAME").val.sum() / max(x.val.sum(), 1)) ** 2).sum())
        h = pd.DataFrame({
            "month": tot.index, "hs4": code,
            "imp_val": tot.values,
            "china_share": cn.reindex(tot.index).fillna(0).values / np.maximum(tot.values, 1),
            "india_share": ind.reindex(tot.index).fillna(0).values / np.maximum(tot.values, 1),
            "origin_hhi": hhi.reindex(tot.index).values,
        })
        h["imp_yoy"] = h.imp_val / h.imp_val.shift(12) - 1
        out.append(h)
    return pd.concat(out, ignore_index=True)


def policy_series(months: pd.DatetimeIndex) -> pd.DataFrame:
    df = pd.DataFrame({"month": months})
    m = df.month
    df["ieepa_china_rate"] = np.select(
        [m < "2025-02-01",
         (m >= "2025-02-01") & (m < "2025-03-01"),
         (m >= "2025-03-01") & (m < "2025-11-01"),
         m >= "2025-11-01"],
        [0.0, 10.0, 20.0, 10.0],
    )
    df["s232_anticipation"] = ((m >= "2025-04-01") & (m < "2026-04-01")).astype(int)
    df["s232_enacted"] = (m >= "2026-04-01").astype(int)
    return df


def main() -> None:
    cls = classify_hs4()
    hs = heading_series()
    months = pd.period_range("2018-01", "2026-06", freq="M").to_timestamp()
    pol = policy_series(months)

    feat = cls.merge(hs, on="hs4", how="left").merge(pol, on="month", how="left")
    feat["china_tariff_exposure"] = feat.ieepa_china_rate * feat.china_share
    feat = feat[feat.month.notna()]
    feat.to_parquet(DATA_INTERIM / "trade_features.parquet", index=False)
    print(f"trade features: {len(feat):,} rows | ingredients: {feat.ing_loose.nunique():,}")
    print("hs4 distribution:")
    print(cls.hs4.value_counts().to_string())
    chk = feat[feat.month == "2025-06-01"].groupby("hs4")[["china_share", "india_share", "origin_hhi"]].first().round(3)
    print("origin mix @2025-06:"); print(chk.to_string())


if __name__ == "__main__":
    main()
