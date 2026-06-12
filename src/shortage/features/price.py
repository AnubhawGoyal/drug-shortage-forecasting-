"""NADAC price features per ingredient x month (H1: low-price generics).

NDC join: NADAC 11-digit NDC -> first 9 digits (labeler5+product4) matched to
zero-padded openFDA product_ndc. Aggregation: median NADAC per unit across an
ingredient's NDCs per month; brand/generic flag from Classification for Rate
Setting. Output: data/interim/price_features.parquet (resumable per year).
"""

from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

from shortage.config import DATA_INTERIM, DATA_RAW


def ndc9_map() -> pd.DataFrame:
    ndc = pd.read_parquet(DATA_INTERIM / "ndc_ingredients.parquet",
                          columns=["product_ndc", "ing_loose"])
    parts = ndc.product_ndc.str.split("-", n=1, expand=True)
    ndc["ndc9"] = parts[0].str.zfill(5) + parts[1].str.zfill(4)
    return ndc[["ndc9", "ing_loose"]].drop_duplicates()


def year_agg(path: str, m: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df = df[["ndc", "nadac_per_unit", "effective_date", "classification_for_rate_setting"]]
    df["ndc9"] = df.ndc.astype(str).str.zfill(11).str[:9]
    df["price"] = pd.to_numeric(df.nadac_per_unit, errors="coerce")
    df["month"] = pd.to_datetime(df.effective_date, errors="coerce").values.astype("datetime64[M]")
    df = df.dropna(subset=["price", "month"]).merge(m, on="ndc9", how="inner")
    g = df.groupby(["ing_loose", "month"]).agg(
        nadac_med=("price", "median"),
        generic_share_priced=("classification_for_rate_setting", lambda x: (x == "G").mean()),
    ).reset_index()
    return g


def main() -> None:
    m = ndc9_map()
    outdir = DATA_INTERIM / "price_yearly"
    outdir.mkdir(parents=True, exist_ok=True)
    for path in sorted(glob.glob(str(DATA_RAW / "nadac" / "nadac_*.parquet"))):
        year = os.path.basename(path)[6:10]
        dest = outdir / f"agg_{year}.parquet"
        if dest.exists():
            continue
        g = year_agg(path, m)
        g.to_parquet(dest, index=False)
        print(f"{year}: {len(g):,} ing-months")

    parts = [pd.read_parquet(f) for f in sorted(glob.glob(str(outdir / "agg_*.parquet")))]
    px = (pd.concat(parts, ignore_index=True)
          .groupby(["ing_loose", "month"]).agg(nadac_med=("nadac_med", "median"),
                                               generic_share_priced=("generic_share_priced", "mean"))
          .reset_index().sort_values(["ing_loose", "month"]))
    # fill to full monthly grid per ingredient (prices persist between updates)
    full = []
    months = pd.period_range("2018-01", "2026-06", freq="M").to_timestamp()
    for ing, g in px.groupby("ing_loose"):
        s = g.set_index("month").reindex(months).ffill()
        s["ing_loose"] = ing
        full.append(s.reset_index().rename(columns={"index": "month"}))
    px = pd.concat(full, ignore_index=True).dropna(subset=["nadac_med"])
    px["log_price"] = np.log1p(px.nadac_med)
    px["price_chg_12m"] = px.groupby("ing_loose").nadac_med.pct_change(12)
    px.to_parquet(DATA_INTERIM / "price_features.parquet", index=False)
    print(f"price features: {len(px):,} rows | {px.ing_loose.nunique():,} ingredients")


if __name__ == "__main__":
    main()
