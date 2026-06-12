"""Reconstruct ingredient-level shortage spells from archived FDA snapshots.

A spell = a maximal period during which an ingredient has >=1 record with
status 'Current' in the FDA shortage database.

Dating rules:
    onset    exact, from min Initial Posting Date of the spell's records
    end      interval-censored: (last snapshot seen Current, first snapshot
             seen not-Current]; right-censored (NaT) if still Current in the
             latest snapshot (incl. the live June-2026 pull)

Output: data/interim/shortage_spells.parquet
"""

from __future__ import annotations

import glob
import os
import re

import pandas as pd

from shortage.config import DATA_INTERIM, DATA_RAW

# Reuse normalization from resolve.py (single source of truth)
from shortage.data.resolve import norm_exact, norm_loose  # noqa: E402


def _load_snapshots() -> pd.DataFrame:
    """Stack archived snapshots + the live pull into (snap_date, ingredient, status)."""
    frames = []
    for f in sorted(glob.glob(str(DATA_RAW / "fda_shortages_archive" / "snap_*.parquet"))):
        ts = os.path.basename(f)[5:19].rstrip(".parquet")
        df = pd.read_parquet(f)
        cols = {c.lower().strip(): c for c in df.columns}
        gn = cols.get("generic name")
        st = cols.get("status")
        ip = cols.get("initial posting date")
        if not (gn and st):
            continue
        frames.append(
            pd.DataFrame(
                {
                    "snap_date": pd.to_datetime(ts[:8], format="%Y%m%d"),
                    "generic_name": df[gn],
                    "status": df[st].str.strip(),
                    "posting_date": pd.to_datetime(df[ip], errors="coerce") if ip else pd.NaT,
                }
            )
        )
    # live pull = latest snapshot
    live = pd.read_parquet(DATA_RAW / "fda_shortages" / "data.parquet")
    frames.append(
        pd.DataFrame(
            {
                "snap_date": pd.Timestamp("2026-06-12"),
                "generic_name": live["generic_name"],
                "status": live["status"].str.strip(),
                "posting_date": pd.to_datetime(live["initial_posting_date"], errors="coerce"),
            }
        )
    )
    out = pd.concat(frames, ignore_index=True)
    out["ing_exact"] = norm_exact(out["generic_name"])
    out["ing_loose"] = norm_loose(out["generic_name"])
    return out[out.ing_exact != ""]


def build_spells() -> pd.DataFrame:
    snaps = _load_snapshots()
    snap_dates = sorted(snaps.snap_date.unique())

    # ingredient x snapshot: in shortage if any record Current
    cur = (
        snaps.assign(is_current=snaps.status.eq("Current"))
        .groupby(["ing_loose", "snap_date"])
        .agg(in_short=("is_current", "any"), posting_min=("posting_date", "min"))
        .reset_index()
    )

    spells = []
    for ing, g in cur.groupby("ing_loose"):
        g = g.set_index("snap_date").reindex(snap_dates)
        g["in_short"] = g["in_short"].fillna(False)  # absent from snapshot = not listed
        prev = False
        spell = None
        for d in snap_dates:
            now = bool(g.loc[d, "in_short"])
            if now and not prev:
                spell = {
                    "ing_loose": ing,
                    "first_seen": d,
                    "onset_exact": g.loc[d, "posting_min"],
                    "last_current": d,
                    "end_lo": pd.NaT,
                    "end_hi": pd.NaT,
                }
            elif now:
                spell["last_current"] = d
                pm = g.loc[d, "posting_min"]
                if pd.notna(pm) and (pd.isna(spell["onset_exact"]) or pm < spell["onset_exact"]):
                    spell["onset_exact"] = pm
            elif prev:
                spell["end_lo"] = spell["last_current"]
                spell["end_hi"] = d
                spells.append(spell)
                spell = None
            prev = now
        if spell is not None:
            spells.append(spell)  # right-censored

    df = pd.DataFrame(spells)
    df["censored"] = df.end_hi.isna()
    # onset: prefer exact posting date when it's plausibly within/<= first_seen
    df["onset"] = df.onset_exact.where(
        df.onset_exact.notna() & (df.onset_exact <= df.first_seen), df.first_seen
    )
    # duration bounds in days
    mid = df.end_lo + (df.end_hi - df.end_lo) / 2
    df["dur_mid_days"] = (mid - df.onset).dt.days
    df["dur_lo_days"] = (df.end_lo - df.onset).dt.days
    df["dur_hi_days"] = (df.end_hi - df.onset).dt.days
    return df


def main() -> None:
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    df = build_spells()
    df.to_parquet(DATA_INTERIM / "shortage_spells.parquet", index=False)
    n_res = (~df.censored).sum()
    print(f"spells: {len(df):,} | resolved (interval-censored end): {n_res:,} | "
          f"right-censored: {df.censored.sum():,}")
    print(f"ingredients with >=1 spell: {df.ing_loose.nunique():,}")
    print(f"onset range: {df.onset.min().date()} -> {df.onset.max().date()}")
    d = df.loc[~df.censored, "dur_mid_days"]
    print(f"resolved spell duration (midpoint): median {d.median():.0f}d, mean {d.mean():.0f}d")


if __name__ == "__main__":
    main()
