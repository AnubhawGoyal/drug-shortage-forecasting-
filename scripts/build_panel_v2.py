#!/usr/bin/env python
"""Freeze panel v2 = panel v1 + trade-exposure features."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from shortage.config import DATA_INTERIM, DATA_PROCESSED


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "panel.parquet")
    trade = pd.read_parquet(DATA_INTERIM / "trade_features.parquet")
    v2 = panel.merge(trade, on=["ing_loose", "month"], how="left")
    miss = v2.hs4.isna().mean()
    v2.to_parquet(DATA_PROCESSED / "panel_v2.parquet", index=False)
    print(f"panel_v2: {len(v2):,} rows x {v2.shape[1]} cols | trade-feature missing share: {miss:.2%}")
    print("columns:", ", ".join(v2.columns))


if __name__ == "__main__":
    main()
