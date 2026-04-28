"""Flatten cached SEC XBRL maturity files into a refi-wall panel.

Reads data/sec/maturities/{TICKER}.json (per-ticker XBRL subset) and emits:

  data/issuer/maturity_long.csv     ticker, fy, period_end, bucket, year, amount
  data/issuer/maturity_wide.csv     pivot: ticker × bucket
  data/issuer/refi_wall_summary.csv per-ticker totals + due-within-2y/5y

Bucket conventions:
  y1   = next 12 months from balance-sheet date  (InNextTwelveMonths or InYearOne)
  y2   = year 2  (InYearTwo)
  y3   = year 3
  y4   = year 4
  y5   = year 5
  yGT5 = beyond year 5  (AfterYearFive)
  rem  = remainder of fiscal year (mid-year filers, often 10-Q)

`year` is the calendar fiscal year the bucket falls in: e.g. y1 from a
2025-12-31 balance sheet → calendar year 2026.

Usage:
    python3.11 scripts/build_maturity_panel.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SEC = ROOT / "data" / "sec"
MAT = SEC / "maturities"
ISSUER = ROOT / "data" / "issuer"

# Map tag → (bucket, year_offset)
BUCKETS: list[tuple[str, str, int | None]] = [
    ("LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths", "y1", 1),
    ("LongTermDebtMaturitiesRepaymentsOfPrincipalInYearOne", "y1", 1),
    ("LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo", "y2", 2),
    ("LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree", "y3", 3),
    ("LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFour", "y4", 4),
    ("LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFive", "y5", 5),
    ("LongTermDebtMaturitiesRepaymentsOfPrincipalAfterYearFive", "yGT5", 6),
    ("LongTermDebtMaturitiesRepaymentsOfPrincipalRemainderOfFiscalYear", "rem", 0),
]


def latest_obs(units_usd: list[dict]) -> dict | None:
    """Pick the latest 10-K observation; fall back to latest of any form."""
    if not units_usd:
        return None
    annual = [v for v in units_usd if v.get("form") == "10-K" and v.get("fp") == "FY"]
    pool = annual or units_usd
    pool = sorted(pool, key=lambda v: (v.get("end") or "", v.get("filed") or ""),
                  reverse=True)
    return pool[0]


def process_ticker(path: Path) -> tuple[list[dict], dict]:
    raw = json.loads(path.read_text())
    rows: list[dict] = []
    summary = {
        "ticker": path.stem,
        "entity_name": raw.get("entityName"),
        "cik": raw.get("cik"),
        "period_end": None,
        "fy": None,
        "form": None,
        "filed": None,
        "y1": None, "y2": None, "y3": None, "y4": None,
        "y5": None, "yGT5": None, "rem": None,
        "total_in_table": 0.0,
        "n_buckets": 0,
    }
    mat = raw.get("maturity") or {}
    if not mat:
        return rows, summary

    # Collect the latest 10-K observation per bucket.
    # All buckets in a filing should share the same `end` date.
    chosen: dict[str, dict] = {}
    for tag, bucket, _ in BUCKETS:
        if tag not in mat:
            continue
        usd = (mat[tag].get("units") or {}).get("USD") or []
        obs = latest_obs(usd)
        if obs is None:
            continue
        # If we already have a candidate for this bucket from a more recent
        # filing, keep the newer one.
        prior = chosen.get(bucket)
        if prior is None or (obs.get("end") or "") > (prior.get("end") or ""):
            chosen[bucket] = obs

    if not chosen:
        return rows, summary

    # Anchor on the most-recent end date — only keep buckets for that filing.
    anchor_end = max(v.get("end") for v in chosen.values())
    chosen = {k: v for k, v in chosen.items() if v.get("end") == anchor_end}

    summary["period_end"] = anchor_end
    fy = next(iter(chosen.values())).get("fy")
    summary["fy"] = fy
    summary["form"] = next(iter(chosen.values())).get("form")
    summary["filed"] = next(iter(chosen.values())).get("filed")

    anchor_year = pd.Timestamp(anchor_end).year if anchor_end else None
    for tag, bucket, offset in BUCKETS:
        if bucket not in chosen:
            continue
        obs = chosen[bucket]
        val = float(obs.get("val") or 0)
        if summary[bucket] is None:
            summary[bucket] = val
            summary["n_buckets"] += 1
            summary["total_in_table"] += val
            target_year = (anchor_year + offset) if (anchor_year and offset) else None
            rows.append({
                "ticker": path.stem,
                "fy": fy,
                "period_end": anchor_end,
                "bucket": bucket,
                "year": target_year,
                "amount": val,
                "tag": tag,
                "filed": obs.get("filed"),
                "form": obs.get("form"),
            })
    return rows, summary


def main() -> int:
    files = sorted(MAT.glob("*.json"))
    print(f"processing {len(files)} cached files")

    all_rows: list[dict] = []
    summaries: list[dict] = []
    for p in files:
        rows, summary = process_ticker(p)
        all_rows.extend(rows)
        summaries.append(summary)

    long = pd.DataFrame(all_rows)
    summary_df = pd.DataFrame(summaries)

    # Derived totals
    summary_df["due_within_2y"] = (
        summary_df["y1"].fillna(0) + summary_df["y2"].fillna(0)
    )
    summary_df["due_within_5y"] = summary_df[["y1", "y2", "y3", "y4", "y5"]].fillna(0).sum(axis=1)
    summary_df["pct_due_within_2y"] = (
        summary_df["due_within_2y"] / summary_df["total_in_table"]
    ).where(summary_df["total_in_table"] > 0)
    summary_df["pct_due_within_5y"] = (
        summary_df["due_within_5y"] / summary_df["total_in_table"]
    ).where(summary_df["total_in_table"] > 0)

    long.to_csv(ISSUER / "maturity_long.csv", index=False)
    summary_df.to_csv(ISSUER / "refi_wall_summary.csv", index=False)

    # Wide pivot for convenience
    if not long.empty:
        wide = long.pivot_table(index=["ticker", "period_end"], columns="bucket",
                                values="amount", aggfunc="first").reset_index()
        wide.to_csv(ISSUER / "maturity_wide.csv", index=False)

    n_with = (summary_df["total_in_table"] > 0).sum()
    print(f"  tickers with maturity data: {n_with}/{len(summary_df)}")
    print(f"  total maturity rows: {len(long):,}")
    print(f"  -> {ISSUER}/maturity_long.csv, refi_wall_summary.csv, maturity_wide.csv")
    print()
    print("Top 15 by total in maturity table (USD M):")
    cols = ["ticker", "entity_name", "period_end", "y1", "y2", "y3", "y4", "y5",
            "yGT5", "total_in_table", "pct_due_within_2y"]
    pretty = summary_df[summary_df["total_in_table"] > 0].nlargest(15, "total_in_table")[cols].copy()
    for c in ["y1", "y2", "y3", "y4", "y5", "yGT5", "total_in_table"]:
        pretty[c] = (pretty[c].fillna(0) / 1e6).round(0).astype(int)
    pretty["pct_due_within_2y"] = (pretty["pct_due_within_2y"] * 100).round(1)
    print(pretty.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
