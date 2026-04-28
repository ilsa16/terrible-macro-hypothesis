"""Fetch EODHD fundamentals for S&P 600 tickers.

Caches raw JSON per ticker to data/sp600/raw/{TICKER}.json.
Re-runs skip tickers with an existing cache unless --force is passed.

Usage:
    python3.11 scripts/fetch_eodhd_fundamentals.py --pilot   # 20-ticker pilot
    python3.11 scripts/fetch_eodhd_fundamentals.py           # full universe
    python3.11 scripts/fetch_eodhd_fundamentals.py --force   # re-download all
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SP600 = ROOT / "data" / "sp600"
RAW = SP600 / "raw"
RAW.mkdir(parents=True, exist_ok=True)
ISSUER = ROOT / "data" / "issuer"
ISSUER.mkdir(parents=True, exist_ok=True)
ENV = ROOT / ".env"


def load_api_key() -> str:
    if ENV.exists():
        for line in ENV.read_text().splitlines():
            if line.startswith("EODHD_API_KEY="):
                return line.split("=", 1)[1].strip()
    key = os.environ.get("EODHD_API_KEY")
    if not key:
        print("ERROR: EODHD_API_KEY not set in .env or env", file=sys.stderr)
        sys.exit(1)
    return key


def fetch_one(eodhd_ticker: str, key: str) -> tuple[bool, str]:
    url = (
        f"https://eodhd.com/api/fundamentals/{eodhd_ticker}"
        f"?api_token={key}&from=2018-01-01&to=2026-04-23&fmt=json"
    )
    out_file = RAW / f"{eodhd_ticker}.json"
    try:
        result = subprocess.run(
            ["curl", "-sSL", "--max-time", "60", url],
            capture_output=True, text=True, check=True,
        )
        raw = result.stdout
        # EODHD returns either a JSON object or an error text
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return False, f"non-json response: {raw[:120]}"
        if isinstance(parsed, dict) and parsed.get("error"):
            return False, f"api-error: {parsed['error']}"
        out_file.write_text(raw)
        return True, "ok"
    except subprocess.CalledProcessError as e:
        return False, f"curl-error: {e}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true", help="use 20-ticker pilot list")
    ap.add_argument("--force", action="store_true", help="re-download cached tickers")
    args = ap.parse_args()

    key = load_api_key()
    src = SP600 / ("pilot_tickers.csv" if args.pilot else "sp600_current.csv")
    if not src.exists():
        print(f"missing {src}. Run fetch_sp600_universe.py first.", file=sys.stderr)
        return 1

    df = pd.read_csv(src)
    tickers = df["eodhd_ticker"].tolist()
    print(f"fetching {len(tickers)} tickers ({'pilot' if args.pilot else 'full universe'})")
    print(f"  cache: {RAW}")
    print()

    failures: list[dict] = []
    fetched = skipped = 0
    t0 = time.time()
    for i, tk in enumerate(tickers, 1):
        cache = RAW / f"{tk}.json"
        if cache.exists() and not args.force:
            skipped += 1
            continue
        ok, msg = fetch_one(tk, key)
        if ok:
            fetched += 1
            size = cache.stat().st_size
            print(f"[{i:3d}/{len(tickers)}] {tk:12s} ok ({size/1024:.0f} KB)")
        else:
            failures.append({"ticker": tk, "reason": msg})
            print(f"[{i:3d}/{len(tickers)}] {tk:12s} FAIL: {msg}")
        time.sleep(0.15)  # polite throttle

    dt = time.time() - t0
    print()
    print(f"done: fetched={fetched} skipped={skipped} failed={len(failures)} in {dt:.1f}s")

    if failures:
        fail_file = ISSUER / "fetch_failures.csv"
        pd.DataFrame(failures).to_csv(fail_file, index=False)
        print(f"  failures -> {fail_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
