"""Central config: paths, seeds, panel constants."""

from pathlib import Path

# Repo root = two levels up from this file (src/shortage/config.py)
ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_INTERIM = ROOT / "data" / "interim"
DATA_PROCESSED = ROOT / "data" / "processed"
EXPERIMENTS = ROOT / "experiments"
FIGURES = ROOT / "reports" / "figures"

SEED = 20260612

# Panel window
PANEL_START = "2018-01"
PANEL_END = "2026-06"

# Pharma-relevant HS chapters/headings for trade pulls
# 2936-2942: vitamins, hormones, glycosides, alkaloids, antibiotics, other organics (APIs)
# 30: pharmaceutical products (finished + bulk)
HS_CODES_API = ["2936", "2937", "2938", "2939", "2940", "2941", "2942"]
HS_CODES_FINISHED = ["30"]

# Tariff-affected origin countries of interest (H2)
TRADE_FOCUS_COUNTRIES = ["CHINA", "INDIA"]
