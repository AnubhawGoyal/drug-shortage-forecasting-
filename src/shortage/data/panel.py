"""Build the ingredient x month analysis panel, 2018-01 .. 2026-06.

Risk set = all Orange Book ingredients marketed by month t (approval <= t,
not discontinued-only). Outcomes from reconstructed spells (spells.py).

Output: data/processed/panel.parquet
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from shortage.config import DATA_INTERIM, DATA_PROCESSED, PANEL_END, PANEL_START


def build() -> pd.DataFrame:
    ob = pd.read_parquet(DATA_INTERIM / "orange_book_ing.parquet")
    spells = pd.read_parquet(DATA_INTERIM / "shortage_spells.parquet")

    months = pd.period_range(PANEL_START, PANEL_END, freq="M").to_timestamp()

    # --- static-ish OB features per ingredient (loose key)
    feat = (
        ob.groupby("ing_loose")
        .agg(
            n_products=("ing_loose", "size"),
            n_applicants=("applicant", "nunique"),
            anda_share=("appl_type", lambda x: (x == "A").mean()),
            first_approval=("approval_date", "min"),
            injectable=("form", lambda x: (x == "INJECTABLE").any()),
            n_forms=("form", "nunique"),
            rx_share=("rx_otc_discn", lambda x: (x == "RX").mean()),
            discn_share=("rx_otc_discn", lambda x: (x == "DISCN").mean()),
        )
        .reset_index()
    )
    feat = feat[feat.discn_share < 1.0]  # drop fully-discontinued ingredients

    # --- spell lookup
    sp = spells[["ing_loose", "onset", "end_lo", "end_hi", "censored"]].copy()
    sp["end_mid"] = sp.end_lo + (sp.end_hi - sp.end_lo) / 2
    sp.loc[sp.censored, "end_mid"] = pd.Timestamp("2099-01-01")

    rows = []
    for m in months:
        m_end = m + pd.offsets.MonthEnd(0)
        df = feat.copy()
        df["month"] = m
        # marketed yet?
        df = df[(df.first_approval.isna()) | (df.first_approval <= m_end)]
        # active shortage in month m? (midpoint end convention)
        act = sp[(sp.onset <= m_end) & (sp.end_mid >= m)]
        df["in_shortage"] = df.ing_loose.isin(set(act.ing_loose))
        # onset this month?
        ons = sp[(sp.onset >= m) & (sp.onset <= m_end)]
        df["onset_this_month"] = df.ing_loose.isin(set(ons.ing_loose))
        rows.append(df)

    panel = pd.concat(rows, ignore_index=True)

    # forward-looking labels: onset within next k months (k=3, 6)
    panel = panel.sort_values(["ing_loose", "month"])
    g = panel.groupby("ing_loose")["onset_this_month"]
    for k in (3, 6):
        fwd = g.transform(
            lambda s: s.shift(-1).rolling(k, min_periods=1).max().fillna(0)
        )
        panel[f"onset_next_{k}m"] = fwd.astype(bool)

    # shortage history features (no leakage: trailing only)
    panel["months_in_shortage_24m"] = (
        panel.groupby("ing_loose")["in_shortage"]
        .transform(lambda s: s.rolling(24, min_periods=1).sum().shift(1))
        .fillna(0)
    )
    panel["ever_shortage_before"] = (
        panel.groupby("ing_loose")["onset_this_month"]
        .transform(lambda s: s.shift(1).cumsum())
        .fillna(0)
        > 0
    )
    panel["age_years"] = (panel.month - panel.first_approval).dt.days / 365.25
    return panel


def main() -> None:
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    panel = build()
    panel.to_parquet(DATA_PROCESSED / "panel.parquet", index=False)
    n_ing = panel.ing_loose.nunique()
    print(f"panel: {len(panel):,} rows | {n_ing:,} ingredients | "
          f"{panel.month.nunique()} months")
    print(f"shortage-month share: {panel.in_shortage.mean():.3%}")
    print(f"onset events: {panel.onset_this_month.sum():,}")
    print(f"onset_next_6m positive share: {panel.onset_next_6m.mean():.3%}")


if __name__ == "__main__":
    main()
