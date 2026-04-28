"""Scrape S&P 600 SmallCap constituents from Wikipedia.

Writes:
  data/sp600/sp600_current.csv  - full current universe
  data/sp600/pilot_tickers.csv  - 20-ticker sector-diverse pilot subset

Same `pd.read_html` + Wikipedia pattern used in Mark Meldrum/Momentum Screen.py.
"""
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "sp600"
OUT.mkdir(parents=True, exist_ok=True)

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"


def fetch_wiki_html() -> str:
    # requests times out from python subprocess in this env — use curl via Bash
    result = subprocess.run(
        ["curl", "-sSL", "--max-time", "60", "-A",
         "Mozilla/5.0 (research-pipeline)", WIKI_URL],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def parse_constituents(html: str) -> pd.DataFrame:
    tables = pd.read_html(io.StringIO(html))
    # The first table on the page is the constituent list
    df = tables[0].copy()
    df.columns = [c.strip() for c in df.columns]
    # Normalize column names we care about
    rename = {
        "Symbol": "ticker",
        "Ticker symbol": "ticker",
        "Security": "name",
        "Company": "name",
        "GICS Sector": "gics_sector",
        "GICS Sub-Industry": "gics_sub_industry",
        "Headquarters Location": "hq",
        "Date added": "date_added",
        "Date first added": "date_added",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    keep = [c for c in ["ticker", "name", "gics_sector", "gics_sub_industry", "hq", "date_added"]
            if c in df.columns]
    df = df[keep].copy()
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    # EODHD expects suffix .US for US-listed securities
    df["eodhd_ticker"] = df["ticker"].str.replace(".", "-", regex=False) + ".US"
    return df


def make_pilot(df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    # sector-diverse sample: take up to 2 per sector until we hit n
    if "gics_sector" not in df.columns:
        return df.sample(n=min(n, len(df)), random_state=42).reset_index(drop=True)
    out: list[pd.DataFrame] = []
    rng = 42
    for sector, grp in df.groupby("gics_sector"):
        take = min(2, len(grp))
        out.append(grp.sample(n=take, random_state=rng))
        rng += 1
    pilot = pd.concat(out, ignore_index=True).sort_values("gics_sector")
    if len(pilot) > n:
        pilot = pilot.head(n)
    elif len(pilot) < n:
        # backfill from remaining
        rest = df[~df["ticker"].isin(pilot["ticker"])]
        backfill = rest.sample(n=min(n - len(pilot), len(rest)), random_state=99)
        pilot = pd.concat([pilot, backfill], ignore_index=True).sort_values("gics_sector")
    return pilot.reset_index(drop=True)


def main() -> int:
    print(f"fetching {WIKI_URL}...")
    html = fetch_wiki_html()
    df = parse_constituents(html)
    print(f"  {len(df)} constituents parsed")

    out_full = OUT / "sp600_current.csv"
    df.to_csv(out_full, index=False)
    print(f"  -> {out_full}")

    pilot = make_pilot(df, n=20)
    out_pilot = OUT / "pilot_tickers.csv"
    pilot.to_csv(out_pilot, index=False)
    print(f"  pilot ({len(pilot)}) -> {out_pilot}")
    print()
    print("pilot preview:")
    print(pilot[["ticker", "eodhd_ticker", "gics_sector"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
