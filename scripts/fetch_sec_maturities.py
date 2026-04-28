"""Fetch SEC EDGAR XBRL company-facts and extract debt-maturity ladders.

Pulls structured XBRL data (NOT HTML scraping) from SEC's free Company Facts
API, which exposes every us-gaap fact a company has tagged in its filings.

The standard 10-K maturity-of-long-term-debt table is reported under:

  LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths   (year 1)
  LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo
  LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree
  LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFour
  LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFive
  LongTermDebtMaturitiesRepaymentsOfPrincipalAfterYearFive
  LongTermDebtMaturitiesRepaymentsOfPrincipalRemainderOfFiscalYear   (mid-year)

Some older filings used the deprecated `InYearOne` tag; we fall back to it.

Usage:
    # the watchlist (top 10% debtors) — fast and targeted:
    python3.11 scripts/fetch_sec_maturities.py
    # or arbitrary tickers:
    python3.11 scripts/fetch_sec_maturities.py HTZ JBLU CZR
    # full S&P 600 (slow):
    python3.11 scripts/fetch_sec_maturities.py --all-sp600

Inputs:
    data/sec/company_tickers.json     (re-downloaded if missing)
Outputs:
    data/sec/maturities/{TICKER}.json (raw companyfacts subset)
    data/sec/sec_failures.csv
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SEC = ROOT / "data" / "sec"
MAT = SEC / "maturities"
MAT.mkdir(parents=True, exist_ok=True)
ISSUER = ROOT / "data" / "issuer"

UA = "terrible-macro-hypothesis-research andreaseliades2017@gmail.com"
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# Tags we extract from each filing
MATURITY_TAGS = [
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearOne",  # deprecated alias
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFour",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFive",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalAfterYearFive",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalRemainderOfFiscalYear",
    # Sometimes total comes through:
    "LongTermDebtMaturitiesRepaymentsOfPrincipal",
]

# Context tags worth keeping for sanity-checking
CONTEXT_TAGS = [
    "LongTermDebt",
    "LongTermDebtNoncurrent",
    "LongTermDebtCurrent",
    "DebtCurrent",
    "DebtLongtermAndShorttermCombinedAmount",
]


def curl_json(url: str) -> dict | None:
    try:
        result = subprocess.run(
            ["curl", "-sSL", "--max-time", "30",
             "-H", f"User-Agent: {UA}",
             "-H", "Accept: application/json", url],
            capture_output=True, text=True, check=True, timeout=45,
        )
        if not result.stdout.strip():
            return None
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def load_ticker_map() -> dict[str, int]:
    path = SEC / "company_tickers.json"
    if not path.exists():
        print(f"downloading {TICKER_MAP_URL}...")
        d = curl_json(TICKER_MAP_URL)
        if d is None:
            raise RuntimeError("failed to fetch SEC ticker map")
        path.write_text(json.dumps(d))
    raw = json.loads(path.read_text())
    return {v["ticker"].upper(): int(v["cik_str"]) for v in raw.values()}


def extract_subset(facts: dict) -> dict:
    """Pull just the maturity + context tags from full companyfacts payload."""
    us = (facts.get("facts") or {}).get("us-gaap") or {}
    out = {
        "entityName": facts.get("entityName"),
        "cik": facts.get("cik"),
        "maturity": {},
        "context": {},
    }
    for tag in MATURITY_TAGS:
        if tag in us:
            out["maturity"][tag] = {
                "label": us[tag].get("label"),
                "units": us[tag].get("units", {}),
            }
    for tag in CONTEXT_TAGS:
        if tag in us:
            out["context"][tag] = {
                "label": us[tag].get("label"),
                "units": us[tag].get("units", {}),
            }
    return out


def fetch_one(ticker: str, cik: int, force: bool) -> tuple[bool, str]:
    out_file = MAT / f"{ticker}.json"
    if out_file.exists() and not force:
        return True, "cached"
    facts = curl_json(FACTS_URL.format(cik=cik))
    if facts is None:
        return False, "fetch-failed"
    subset = extract_subset(facts)
    if not subset["maturity"]:
        # nothing useful — still write so we don't re-hit the API
        out_file.write_text(json.dumps(subset))
        return False, "no-maturity-tags"
    out_file.write_text(json.dumps(subset))
    return True, "ok"


def resolve_targets(args, ticker_map: dict[str, int]) -> list[tuple[str, int]]:
    if args.tickers:
        wanted = [t.upper() for t in args.tickers]
    elif args.all_sp600:
        df = pd.read_csv(ROOT / "data" / "sp600" / "sp600_current.csv")
        wanted = df["ticker"].astype(str).str.upper().tolist()
    else:
        # default = the watchlist
        wp = ISSUER / "top_debtors_watchlist.csv"
        if not wp.exists():
            print(f"missing {wp}. Run build_credit_watchlist.py first.", file=sys.stderr)
            sys.exit(1)
        df = pd.read_csv(wp)
        wanted = df["ticker"].astype(str).str.upper().tolist()
    out: list[tuple[str, int]] = []
    missing: list[str] = []
    for t in wanted:
        cik = ticker_map.get(t.replace("-", "."))  # e.g. CWEN-A vs CWEN.A
        if cik is None:
            cik = ticker_map.get(t)
        if cik is None and "-" in t:
            cik = ticker_map.get(t.split("-")[0])  # CWEN-A → CWEN
        if cik is None:
            missing.append(t)
        else:
            out.append((t, cik))
    if missing:
        print(f"  no CIK match for: {', '.join(missing)}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="*",
                    help="explicit tickers (default = watchlist)")
    ap.add_argument("--all-sp600", action="store_true",
                    help="run for all current S&P 600")
    ap.add_argument("--force", action="store_true", help="re-fetch cached")
    args = ap.parse_args()

    ticker_map = load_ticker_map()
    print(f"loaded {len(ticker_map):,} ticker→CIK mappings")

    targets = resolve_targets(args, ticker_map)
    print(f"fetching {len(targets)} tickers from SEC EDGAR")
    print(f"  cache: {MAT}")
    print()

    failures: list[dict] = []
    ok = cached = no_tag = 0
    t0 = time.time()
    for i, (tk, cik) in enumerate(targets, 1):
        success, msg = fetch_one(tk, cik, args.force)
        if msg == "cached":
            cached += 1
            print(f"[{i:3d}/{len(targets)}] {tk:8s} (CIK={cik:010d}) cached")
        elif msg == "ok":
            ok += 1
            print(f"[{i:3d}/{len(targets)}] {tk:8s} (CIK={cik:010d}) ok")
        elif msg == "no-maturity-tags":
            no_tag += 1
            failures.append({"ticker": tk, "cik": cik, "reason": msg})
            print(f"[{i:3d}/{len(targets)}] {tk:8s} (CIK={cik:010d}) no maturity tags")
        else:
            failures.append({"ticker": tk, "cik": cik, "reason": msg})
            print(f"[{i:3d}/{len(targets)}] {tk:8s} (CIK={cik:010d}) FAIL: {msg}")
        if msg != "cached":
            time.sleep(0.12)  # SEC rate limit ~10 req/s; be polite

    dt = time.time() - t0
    print()
    print(f"done: ok={ok} cached={cached} no-tags={no_tag} failed={len(failures)-no_tag} in {dt:.1f}s")

    if failures:
        fp = SEC / "sec_failures.csv"
        pd.DataFrame(failures).to_csv(fp, index=False)
        print(f"  failures -> {fp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
