"""Product-level shortage spells: unit = (ingredient, company).

Same snapshot-diff logic as spells.py but at (ing_loose, company_norm)
granularity — ~10x more outcome events, matching the granularity of prior
work (Pall 2023; ASPE counts 1,991 product-level starts 2018-23).

Output: data/interim/shortage_spells_product.parquet
"""

from __future__ import annotations

import glob
import os
import re

import pandas as pd

from shortage.config import DATA_INTERIM, DATA_RAW
from shortage.data.resolve import norm_exact, norm_loose

_CO_STOP = re.compile(
    r"\b(INC|INCORPORATED|LLC|LTD|LIMITED|CORP|CORPORATION|COMPANY|CO|PHARMACEUTICALS|"
    r"PHARMACEUTICAL|PHARMA|PHARMS|USA|US|LABORATORIES|LABORATORY|LABS|LAB|HEALTHCARE|"
    r"PRODUCTS|INJECTABLES|INDUSTRIES|INTERNATIONAL|HOLDINGS|GROUP|SA|AG|GMBH|PLC|LP|"
    r"NORTH AMERICA|AMERICA|GLOBAL|THE)\b"
)
_NONWORD = re.compile(r"[^A-Z0-9 ]")
_WS = re.compile(r"\s+")


def norm_company(s: pd.Series) -> pd.Series:
    out = s.fillna("").astype(str).str.upper()
    out = out.str.replace(_NONWORD, " ", regex=True)
    out = out.str.replace(_CO_STOP, " ", regex=True)
    return out.str.replace(_WS, " ", regex=True).str.strip()


def _load_snapshots() -> pd.DataFrame:
    frames = []
    for f in sorted(glob.glob(str(DATA_RAW / "fda_shortages_archive" / "snap_*.parquet"))):
        ts = os.path.basename(f)[5:19].rstrip(".parquet")
        df = pd.read_parquet(f)
        cols = {c.lower().strip(): c for c in df.columns}
        gn, st = cols.get("generic name"), cols.get("status")
        co, ip = cols.get("company name"), cols.get("initial posting date")
        if not (gn and st and co):
            continue
        frames.append(pd.DataFrame({
            "snap_date": pd.to_datetime(ts[:8], format="%Y%m%d"),
            "generic_name": df[gn], "company": df[co],
            "status": df[st].str.strip(),
            "posting_date": pd.to_datetime(df[ip], errors="coerce") if ip else pd.NaT,
        }))
    live = pd.read_parquet(DATA_RAW / "fda_shortages" / "data.parquet")
    frames.append(pd.DataFrame({
        "snap_date": pd.Timestamp("2026-06-12"),
        "generic_name": live["generic_name"], "company": live["company_name"],
        "status": live["status"].str.strip(),
        "posting_date": pd.to_datetime(live["initial_posting_date"], errors="coerce"),
    }))
    out = pd.concat(frames, ignore_index=True)
    out["ing_loose"] = norm_loose(out["generic_name"])
    out["company_norm"] = norm_company(out["company"])
    out["unit"] = out.ing_loose + "||" + out.company_norm
    return out[(out.ing_loose != "") & (out.company_norm != "")]


def build() -> pd.DataFrame:
    snaps = _load_snapshots()
    snap_dates = sorted(snaps.snap_date.unique())
    cur = (snaps.assign(is_current=snaps.status.eq("Current"))
           .groupby(["unit", "snap_date"])
           .agg(in_short=("is_current", "any"), posting_min=("posting_date", "min"))
           .reset_index())
    spells = []
    for unit, g in cur.groupby("unit"):
        g = g.set_index("snap_date").reindex(snap_dates)
        g["in_short"] = g["in_short"].astype(object).fillna(False).astype(bool)
        prev, spell = False, None
        for d in snap_dates:
            now = bool(g.loc[d, "in_short"])
            if now and not prev:
                spell = {"unit": unit, "first_seen": d, "onset_exact": g.loc[d, "posting_min"],
                         "last_current": d, "end_lo": pd.NaT, "end_hi": pd.NaT}
            elif now:
                spell["last_current"] = d
                pm = g.loc[d, "posting_min"]
                if pd.notna(pm) and (pd.isna(spell["onset_exact"]) or pm < spell["onset_exact"]):
                    spell["onset_exact"] = pm
            elif prev:
                spell.update(end_lo=spell["last_current"], end_hi=d)
                spells.append(spell); spell = None
            prev = now
        if spell is not None:
            spells.append(spell)
    df = pd.DataFrame(spells)
    df[["ing_loose", "company_norm"]] = df.unit.str.split(r"\|\|", expand=True, regex=True)
    df["censored"] = df.end_hi.isna()
    df["onset"] = df.onset_exact.where(
        df.onset_exact.notna() & (df.onset_exact <= df.first_seen), df.first_seen)
    return df


def main() -> None:
    df = build()
    df.to_parquet(DATA_INTERIM / "shortage_spells_product.parquet", index=False)
    print(f"product spells: {len(df):,} | units: {df.unit.nunique():,} | "
          f"resolved: {(~df.censored).sum():,}")
    print(f"onsets >=2018: {(df.onset >= '2018-01-01').sum():,}")
    print(df[df.onset >= '2018-01-01'].groupby(df.onset.dt.year).size().to_string())


if __name__ == "__main__":
    main()
