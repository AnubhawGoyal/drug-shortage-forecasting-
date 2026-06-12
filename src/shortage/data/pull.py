"""Week-1 data acquisition: pull core public sources and cache to parquet.

Each pull function writes to data/raw/<source>/ with a _meta.json stamp
(pull date, source URL, row count). Re-runs skip fresh caches unless forced.

Core sources (PROPOSAL.md §4):
    fda_shortages    openFDA drug shortages endpoint (outcome variable)
    ndc_directory    openFDA NDC directory bulk file (entity-resolution spine)
    drugsfda         openFDA Drugs@FDA bulk file (approval history, sponsors)
    orange_book      FDA Orange Book bulk zip (manufacturer counts, TE codes)
    nadac            Medicaid NADAC price series (data.medicaid.gov, per-year CSVs)
    trade_census     US Census intl trade API: pharma imports by HS x country x month
    ashp_shortages   ASHP current shortages list (polite scrape, cross-validation)
"""

from __future__ import annotations

import io
import json
import os
import time
import zipfile
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

from shortage.config import (
    DATA_RAW,
    HS_CODES_API,
    HS_CODES_FINISHED,
    PANEL_END,
    PANEL_START,
    ROOT,
)

load_dotenv(ROOT / ".env")

UA = {"User-Agent": "drug-shortage-research/0.1 (academic; goyal.anubhaw@gmail.com)"}
TIMEOUT = 120


# --------------------------------------------------------------------------- helpers
@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30))
def _get(url: str, timeout: int = TIMEOUT, deadline: int = 90, **kwargs) -> requests.Response:
    """GET with a hard wall-clock deadline.

    Some APIs (Census) occasionally slow-walk responses byte-by-byte, which never
    triggers requests' read timeout. Streaming with a deadline forces a retry on
    a fresh connection instead of hanging indefinitely.
    """
    t0 = time.monotonic()
    r = requests.get(url, headers=UA, timeout=(10, timeout), stream=True, **kwargs)
    r.raise_for_status()
    chunks = []
    for chunk in r.iter_content(chunk_size=1 << 16):
        if time.monotonic() - t0 > deadline:
            r.close()
            raise requests.Timeout(f"wall-clock deadline {deadline}s exceeded for {url}")
        chunks.append(chunk)
    r._content = b"".join(chunks)  # make .json()/.text/.content work as usual
    return r


def _outdir(source: str) -> Path:
    d = DATA_RAW / source
    d.mkdir(parents=True, exist_ok=True)
    return d


def _is_fresh(source: str, max_age_days: int = 7) -> bool:
    meta = DATA_RAW / source / "_meta.json"
    if not meta.exists():
        return False
    pulled = date.fromisoformat(json.loads(meta.read_text())["pulled"])
    return (date.today() - pulled).days < max_age_days


def _save(source: str, df: pd.DataFrame, url: str, name: str = "data") -> None:
    out = _outdir(source)
    df.to_parquet(out / f"{name}.parquet", index=False)
    (out / "_meta.json").write_text(
        json.dumps({"pulled": date.today().isoformat(), "url": url, "rows": len(df)}, indent=2)
    )
    print(f"  [{source}] {len(df):,} rows -> {out / f'{name}.parquet'}")


def _openfda_paged(endpoint: str, limit: int = 1000) -> pd.DataFrame:
    """Page through an openFDA endpoint using skip (max 26k records)."""
    key = os.getenv("OPENFDA_API_KEY", "")
    rows, skip = [], 0
    while True:
        params = {"limit": limit, "skip": skip}
        if key:
            params["api_key"] = key
        r = _get(f"https://api.fda.gov/{endpoint}.json", params=params)
        batch = r.json().get("results", [])
        rows.extend(batch)
        if len(batch) < limit or skip + limit >= 26000:
            break
        skip += limit
    return pd.json_normalize(rows)


def _openfda_bulk(category: str, source: str) -> None:
    """Download openFDA bulk export partitions, one parquet per partition.

    Resumable: existing partition parquets are skipped, so interrupted pulls
    continue where they left off on the next run.
    """
    manifest = _get("https://api.fda.gov/download.json").json()
    node = manifest["results"]
    for part in category.split("/"):
        node = node[part]
    out = _outdir(source)
    parts = node["partitions"]
    for i, f in enumerate(parts):
        dest = out / f"part-{i:04d}.parquet"
        if dest.exists():
            continue
        r = _get(f["file"], deadline=240)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z, z.open(z.namelist()[0]) as fh:
            df = pd.json_normalize(json.load(fh)["results"])
        tmp = dest.with_suffix(".tmp")
        df.to_parquet(tmp, index=False)
        tmp.rename(dest)
        print(f"  [{source}] partition {i + 1}/{len(parts)}: {len(df):,} rows")
    (out / "_meta.json").write_text(
        json.dumps(
            {"pulled": date.today().isoformat(), "url": f"openFDA bulk {category}",
             "partitions": len(parts)},
            indent=2,
        )
    )


# --------------------------------------------------------------------------- sources
def pull_fda_shortages() -> None:
    """FDA drug shortages via openFDA (current + resolved, reason codes, dates)."""
    df = _openfda_paged("drug/shortages")
    _save("fda_shortages", df, "https://api.fda.gov/drug/shortages.json")


def pull_ndc_directory() -> None:
    """openFDA NDC directory bulk — the entity-resolution spine."""
    _openfda_bulk("drug/ndc", "ndc_directory")


def pull_drugsfda() -> None:
    """Drugs@FDA bulk via openFDA — approval history and sponsors."""
    _openfda_bulk("drug/drugsfda", "drugsfda")


def pull_orange_book() -> None:
    """FDA Orange Book data files (products, patents, exclusivity)."""
    url = "https://www.fda.gov/media/76860/download?attachment"
    r = _get(url)
    out = _outdir("orange_book")
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for name in z.namelist():
            if not name.lower().endswith(".txt"):
                continue
            with z.open(name) as fh:
                df = pd.read_csv(fh, sep="~", dtype=str, encoding="latin-1")
            stem = Path(name).stem.lower()
            df.to_parquet(out / f"{stem}.parquet", index=False)
            print(f"  [orange_book] {name}: {len(df):,} rows")
    (out / "_meta.json").write_text(
        json.dumps({"pulled": date.today().isoformat(), "url": url}, indent=2)
    )


def pull_nadac() -> None:
    """NADAC price series — per-year CSVs discovered via data.medicaid.gov search API.

    One dataset per calendar year; each is downloaded to its own parquet
    (resumable across runs).
    """
    search = "https://data.medicaid.gov/api/1/search"
    r = _get(search, params={"keyword": "NADAC", "page-size": 100})
    out = _outdir("nadac")
    y0, y1 = int(PANEL_START[:4]), int(PANEL_END[:4])
    year_urls: dict[int, str] = {}
    for item in r.json().get("results", {}).values():
        title = item.get("title", "")
        if not title.startswith("NADAC (National Average Drug Acquisition Cost)"):
            continue
        year_str = title.rsplit(" ", 1)[-1]
        if not (year_str.isdigit() and y0 <= int(year_str) <= y1):
            continue
        dists = item.get("distribution", [])
        if not dists:
            continue
        d0 = dists[0]
        url = d0.get("downloadURL") or d0.get("data", {}).get("downloadURL")
        if url:
            year_urls[int(year_str)] = url
    missing = [y for y in range(y0, y1 + 1) if y not in year_urls]
    if missing:
        print(f"  [nadac] WARNING: no dataset found for years {missing}")
    for year, url in sorted(year_urls.items()):
        dest = out / f"nadac_{year}.parquet"
        if dest.exists():
            continue
        df = pd.read_csv(url, dtype=str, low_memory=False)
        tmp = dest.with_suffix(".tmp")
        df.to_parquet(tmp, index=False)
        tmp.rename(dest)
        print(f"  [nadac] {year}: {len(df):,} rows")
    (out / "_meta.json").write_text(
        json.dumps(
            {"pulled": date.today().isoformat(), "url": search,
             "years": sorted(year_urls)},
            indent=2,
        )
    )


def pull_trade_census() -> None:
    """US imports by HS code x country x month (Census intl trade API).

    Pulls HS chapter 30 (finished pharma) at 2-digit and API headings 2936-2942
    at 4-digit, with country-of-origin detail, for the panel window.
    """
    key = os.getenv("CENSUS_API_KEY", "")
    if not key:
        raise RuntimeError(
            "CENSUS_API_KEY required — free signup at https://api.census.gov/data/key_signup.html"
        )
    base = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
    out = _outdir("trade_census")
    y0, y1 = int(PANEL_START[:4]), int(PANEL_END[:4])
    codes = HS_CODES_FINISHED + HS_CODES_API
    for code in codes:
        dest = out / f"hs{code}.parquet"
        if dest.exists():
            continue
        params = {
            "get": "CTY_CODE,CTY_NAME,GEN_VAL_MO,CON_VAL_MO",
            "I_COMMODITY": code,
            "time": f"from {y0}-01 to {y1}-{PANEL_END[5:]}",
            "COMM_LVL": f"HS{len(code)}",
            "key": key,
        }
        # Census intermittently stalls; short deadline + tenacity retry beats waiting
        r = _get(base, params=params, timeout=15, deadline=15)
        try:
            data = r.json()
        except ValueError as e:
            raise RuntimeError(f"non-JSON Census response (bad key?): {r.text[:200]}") from e
        df = pd.DataFrame(data[1:], columns=data[0])
        tmp = dest.with_suffix(".tmp")
        df.to_parquet(tmp, index=False)
        tmp.rename(dest)
        print(f"  [trade_census] HS{code}: {len(df):,} rows")
    (out / "_meta.json").write_text(
        json.dumps({"pulled": date.today().isoformat(), "url": base, "codes": codes}, indent=2)
    )


def pull_ashp_shortages() -> None:
    """ASHP current shortage list — polite single-page scrape (cross-validation).

    NOTE: respect robots.txt and rate limits; this pulls the index only.
    Detail pages are week-2 work if needed.
    """
    url = "https://www.ashp.org/drug-shortages/current-shortages/drug-shortages-list?page=CurrentShortages"
    r = _get(url)
    tables = pd.read_html(io.StringIO(r.text))
    df = max(tables, key=len) if tables else pd.DataFrame()
    _save("ashp_shortages", df, url)


SOURCES: dict[str, Callable[[], None]] = {
    "fda_shortages": pull_fda_shortages,
    "ndc_directory": pull_ndc_directory,
    "drugsfda": pull_drugsfda,
    "orange_book": pull_orange_book,
    "nadac": pull_nadac,
    "trade_census": pull_trade_census,
    "ashp_shortages": pull_ashp_shortages,
}


def pull(sources: list[str] | None = None, force: bool = False) -> dict[str, str]:
    """Pull the given sources (default: all). Returns {source: status}."""
    status: dict[str, str] = {}
    for name in sources or list(SOURCES):
        if name not in SOURCES:
            status[name] = "unknown source"
            continue
        if not force and _is_fresh(name):
            status[name] = "fresh cache, skipped"
            print(f"  [{name}] fresh cache, skipped (use --force to re-pull)")
            continue
        print(f"[pull] {name}")
        try:
            SOURCES[name]()
            status[name] = "ok"
        except Exception as e:  # keep going; report at the end
            status[name] = f"FAILED: {e}"
            print(f"  [{name}] FAILED: {e}")
    return status
