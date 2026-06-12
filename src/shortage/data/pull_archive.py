"""Historical FDA shortage snapshots from the Internet Archive (Wayback Machine).

The live FDA database (and openFDA) is a snapshot retaining few Resolved
records. To reconstruct historical shortage spells we download archived
copies of the FDA drug-shortage CSV export (2019-2026, ~monthly) and diff
record status across snapshots.

Onsets are exact (Initial Posting Date field); resolutions are interval-
censored between consecutive snapshots — handled explicitly in the survival
models.

Output: data/raw/fda_shortages_archive/snap_<timestamp>.parquet (one per
snapshot, resumable) + _meta.json.
"""

from __future__ import annotations

import io
import json
from datetime import date

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from shortage.config import DATA_RAW

UA = {"User-Agent": "drug-shortage-research/0.1 (academic; goyal.anubhaw@gmail.com)"}
CSV_URL = "https://www.accessdata.fda.gov/scripts/drugshortages/Drugshortages.cfm?DLType=csv"
CDX = "https://web.archive.org/cdx/search/cdx"


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30))
def _get(url: str, **kw) -> requests.Response:
    r = requests.get(url, headers=UA, timeout=(10, 60), **kw)
    r.raise_for_status()
    return r


def list_snapshots() -> list[str]:
    """Monthly-collapsed Wayback timestamps for the FDA shortage CSV endpoint."""
    r = _get(
        CDX,
        params={
            "url": "accessdata.fda.gov/scripts/drugshortages/Drugshortages.cfm*",
            "output": "json",
            "from": "2018",
            "collapse": "timestamp:6",
            "filter": "statuscode:200",
        },
    )
    rows = r.json()
    return [(x[1], x[2]) for x in rows[1:]]  # (timestamp, original_url)


def pull_snapshot(ts: str, original: str, out_dir) -> str:
    """Download one archived CSV; returns status string."""
    dest = out_dir / f"snap_{ts}.parquet"
    if dest.exists():
        return "cached"
    # id_ suffix = original bytes without Wayback rewriting
    url = f"https://web.archive.org/web/{ts}id_/{original}"
    r = _get(url)
    try:
        df = pd.read_csv(io.StringIO(r.text), dtype=str, on_bad_lines="skip", engine="python")
    except Exception as e:
        return f"unparseable: {e}"
    if df.shape[1] < 5:
        return f"bad shape {df.shape}"
    df.columns = [c.strip() for c in df.columns]
    df["snapshot_ts"] = ts
    tmp = dest.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.rename(dest)
    return f"ok ({len(df):,} rows)"


def main(max_new: int | None = None) -> None:
    out = DATA_RAW / "fda_shortages_archive"
    out.mkdir(parents=True, exist_ok=True)
    stamps = list_snapshots()
    print(f"{len(stamps)} snapshots listed")
    done = 0
    for ts, original in stamps:
        status = pull_snapshot(ts, original, out)
        if status != "cached":
            print(f"  {ts}: {status}")
            done += 1
            if max_new and done >= max_new:
                print("batch limit reached")
                break
    n = len(list(out.glob("snap_*.parquet")))
    (out / "_meta.json").write_text(
        json.dumps({"pulled": date.today().isoformat(), "url": CSV_URL,
                    "snapshots_cached": n, "snapshots_listed": len(stamps)}, indent=2)
    )
    print(f"cached {n}/{len(stamps)}")


if __name__ == "__main__":
    main()
