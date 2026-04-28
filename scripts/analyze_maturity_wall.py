"""Objective analysis of when the watchlist's debt is actually due.

Tests the hypothesis: "5 years after the Fed started hiking (2022), there should
be a refi spike around 2026/27." Evaluates against the actual FY2025-anchored
ladder, with a comparison to what the same companies' FY2019-anchored ladder
predicted for 2020-2024.

Outputs (all to data/issuer/):
  calendar_maturity_2025_anchor.csv  per-year, per-ticker $ due
  calendar_maturity_2019_anchor.csv  the historical comparison
  maturity_year_aggregate.csv        sum + count by calendar year
  maturity_extension_evidence.csv    per-ticker: did they extend or compress?
  wam_by_vintage.csv                 weighted-average maturity per anchor year

Reads cached SEC XBRL JSON in data/sec/maturities/{TICKER}.json directly so
we can pull any historical anchor — not just "latest".
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SEC_MAT = ROOT / "data" / "sec" / "maturities"
ISSUER = ROOT / "data" / "issuer"

CORE = [
    ("LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths", "y1", 1),
    ("LongTermDebtMaturitiesRepaymentsOfPrincipalInYearOne", "y1", 1),
    ("LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo", "y2", 2),
    ("LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree", "y3", 3),
    ("LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFour", "y4", 4),
    ("LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFive", "y5", 5),
    ("LongTermDebtMaturitiesRepaymentsOfPrincipalAfterYearFive", "yGT5", 6),
]
CORE_BUCKETS = ["y1", "y2", "y3", "y4", "y5", "yGT5"]


def extract_for_anchor_year(raw: dict, anchor_year: int) -> dict | None:
    """Pull the ladder for a specific fiscal-year anchor (e.g. 2019 or 2025)."""
    mat = raw.get("maturity") or {}
    if not mat:
        return None
    out = {b: None for b in CORE_BUCKETS}
    matched_end = None
    for tag, bucket, _offset in CORE:
        usd = (mat.get(tag) or {}).get("units", {}).get("USD") or []
        # Pick the 10-K FY observation for the requested fiscal year
        cands = [v for v in usd if v.get("fy") == anchor_year and v.get("fp") == "FY"
                 and v.get("form") == "10-K"]
        if not cands:
            continue
        # If the bucket already has a value (from InNextTwelveMonths vs InYearOne), keep first
        if out[bucket] is None:
            obs = sorted(cands, key=lambda v: v.get("filed") or "", reverse=True)[0]
            out[bucket] = float(obs["val"])
            matched_end = obs.get("end")
    if all(v is None for v in out.values()):
        return None
    out["anchor_end"] = matched_end
    out["anchor_year"] = anchor_year
    return out


def per_year_distribution(ladder: dict) -> dict[int, float]:
    """Map a ladder dict {y1..yGT5} to {calendar_year: amount}."""
    if ladder is None or ladder.get("anchor_end") is None:
        return {}
    anchor = pd.Timestamp(ladder["anchor_end"]).year
    out: dict[int, float] = {}
    for off, b in enumerate(["y1", "y2", "y3", "y4", "y5"], start=1):
        if ladder.get(b) is not None:
            out[anchor + off] = float(ladder[b])
    if ladder.get("yGT5") is not None:
        # bucket as anchor + 6 — represents "thereafter" pile
        out[anchor + 6] = float(ladder["yGT5"])
    return out


def weighted_avg_maturity(ladder: dict) -> float | None:
    """Approximate WAM in years; use bucket midpoints. Year-N midpoint = N - 0.5,
    yGT5 = 8.5 (rough)."""
    if ladder is None:
        return None
    weights = {"y1": 0.5, "y2": 1.5, "y3": 2.5, "y4": 3.5, "y5": 4.5, "yGT5": 8.5}
    num = den = 0.0
    for b, w in weights.items():
        v = ladder.get(b)
        if v is None or v <= 0:
            continue
        num += v * w
        den += v
    return num / den if den > 0 else None


def main() -> int:
    # Load fresh-only watchlist for context (need stress score, sector, etc.)
    fresh_summary = pd.read_csv(ISSUER / "refi_wall_summary.csv")
    fresh_summary = fresh_summary[
        (fresh_summary["total_in_table"] > 0) & (~fresh_summary["is_stale"])
    ].copy()
    fresh_tickers = set(fresh_summary["ticker"])
    print(f"working with {len(fresh_tickers)} fresh-data tickers")
    print()

    rows_2025: list[dict] = []
    rows_2019: list[dict] = []
    extensions: list[dict] = []
    wams: list[dict] = []
    matched_2019 = 0

    for tk in sorted(fresh_tickers):
        path = SEC_MAT / f"{tk}.json"
        if not path.exists():
            continue
        raw = json.loads(path.read_text())

        # FY2025 ladder (latest)
        ladder_2025 = extract_for_anchor_year(raw, 2025)
        # FY2024 fallback — some non-calendar issuers report FY24 as latest 10-K
        if ladder_2025 is None or all(ladder_2025.get(b) is None for b in CORE_BUCKETS):
            ladder_2025 = extract_for_anchor_year(raw, 2024)
        if ladder_2025 is None:
            continue

        # FY2019 ladder for the historical comparison
        ladder_2019 = extract_for_anchor_year(raw, 2019)
        if ladder_2019 is not None:
            matched_2019 += 1

        # Calendar distributions
        d_2025 = per_year_distribution(ladder_2025)
        d_2019 = per_year_distribution(ladder_2019) if ladder_2019 else {}

        for yr, amt in d_2025.items():
            rows_2025.append({"ticker": tk, "year": yr, "amount": amt,
                              "anchor_end": ladder_2025["anchor_end"]})
        for yr, amt in d_2019.items():
            rows_2019.append({"ticker": tk, "year": yr, "amount": amt,
                              "anchor_end": ladder_2019["anchor_end"]})

        # Extension test: did the company push debt out?
        # "% due within 5y" from each anchor.
        def within_5y(L):
            if L is None: return None
            vals = [L.get(b) for b in ["y1", "y2", "y3", "y4", "y5"]]
            vals = [v for v in vals if v is not None]
            tot = sum(L.get(b, 0) or 0 for b in CORE_BUCKETS)
            v5y = sum(vals)
            return v5y / tot if tot > 0 else None
        ext_2019 = within_5y(ladder_2019) if ladder_2019 else None
        ext_2025 = within_5y(ladder_2025)
        wam_2019 = weighted_avg_maturity(ladder_2019)
        wam_2025 = weighted_avg_maturity(ladder_2025)
        extensions.append({
            "ticker": tk,
            "anchor_2019": ladder_2019["anchor_end"] if ladder_2019 else None,
            "anchor_2025": ladder_2025["anchor_end"],
            "pct_within_5y_2019": ext_2019,
            "pct_within_5y_2025": ext_2025,
            "wam_2019": wam_2019,
            "wam_2025": wam_2025,
            "wam_change_yrs": (wam_2025 - wam_2019) if (wam_2025 and wam_2019) else None,
            "total_2019": sum(v for v in (ladder_2019.values() if ladder_2019 else [])
                              if isinstance(v, (int, float))),
            "total_2025": sum(v for v in ladder_2025.values()
                              if isinstance(v, (int, float))),
        })
        if wam_2019 is not None:
            wams.append({"ticker": tk, "vintage": "FY2019", "wam_yrs": wam_2019,
                          "total": extensions[-1]["total_2019"]})
        if wam_2025 is not None:
            wams.append({"ticker": tk, "vintage": "FY2025", "wam_yrs": wam_2025,
                          "total": extensions[-1]["total_2025"]})

    print(f"  FY2019 ladder available for {matched_2019} of {len(fresh_tickers)} tickers")

    df_2025 = pd.DataFrame(rows_2025)
    df_2019 = pd.DataFrame(rows_2019)
    df_ext = pd.DataFrame(extensions)
    df_wam = pd.DataFrame(wams)

    # Aggregate by calendar year
    if not df_2025.empty:
        agg_2025 = df_2025.groupby("year").agg(
            sum_b=("amount", lambda s: s.sum() / 1e9),
            n_tickers=("ticker", "nunique"),
        ).reset_index()
        agg_2025["vintage"] = "FY2025-anchor (current view)"
    else:
        agg_2025 = pd.DataFrame()

    if not df_2019.empty:
        agg_2019 = df_2019.groupby("year").agg(
            sum_b=("amount", lambda s: s.sum() / 1e9),
            n_tickers=("ticker", "nunique"),
        ).reset_index()
        agg_2019["vintage"] = "FY2019-anchor (what they expected pre-rate-hikes)"
    else:
        agg_2019 = pd.DataFrame()

    agg = pd.concat([agg_2025, agg_2019], ignore_index=True)

    # Save outputs
    df_2025.to_csv(ISSUER / "calendar_maturity_2025_anchor.csv", index=False)
    df_2019.to_csv(ISSUER / "calendar_maturity_2019_anchor.csv", index=False)
    agg.to_csv(ISSUER / "maturity_year_aggregate.csv", index=False)
    df_ext.to_csv(ISSUER / "maturity_extension_evidence.csv", index=False)
    df_wam.to_csv(ISSUER / "wam_by_vintage.csv", index=False)

    # Also build an ex-REIT calendar-year aggregate (industrial corporates only)
    meta = pd.read_csv(ISSUER / "credit_meta.csv")
    re_tickers = set(meta[meta["sector"] == "Real Estate"]["ticker"])
    if not df_2025.empty:
        df_ex = df_2025[~df_2025["ticker"].isin(re_tickers)].copy()
        agg_ex = df_ex.groupby("year").agg(
            sum_b=("amount", lambda s: s.sum() / 1e9),
            n_tickers=("ticker", "nunique"),
        ).reset_index()
        agg_ex["vintage"] = "FY2025-anchor ex-REIT (industrial corporates only)"
        agg_with_ex = pd.concat([agg, agg_ex], ignore_index=True)
        agg_with_ex.to_csv(ISSUER / "maturity_year_aggregate.csv", index=False)
        print()
        print("=" * 72)
        print("EX-REIT VIEW — industrial corporates only (mREITs distort the picture)")
        print("=" * 72)
        pretty = agg_ex.copy()
        pretty["sum_b"] = pretty["sum_b"].round(1)
        print(pretty.to_string(index=False))
        if not agg_ex.empty:
            tot = agg_ex["sum_b"].sum()
            peak = agg_ex.loc[agg_ex["sum_b"].idxmax()]
            wall = agg_ex[(agg_ex["year"] >= 2026) & (agg_ex["year"] <= 2027)]["sum_b"].sum()
            print(f"\n  total disclosed ex-RE: ${tot:.0f}B "
                  f"({df_ex['ticker'].nunique()} issuers)")
            print(f"  peak year: {int(peak['year'])} at ${peak['sum_b']:.1f}B "
                  f"({peak['sum_b']/tot*100:.1f}% of total)")
            print(f"  2026+2027 combined: ${wall:.0f}B ({wall/tot*100:.1f}% of total)")

    print()
    print("=" * 72)
    print("CALENDAR-YEAR MATURITY WALL — FY2025 anchor (what's actually due)")
    print("=" * 72)
    pretty = agg_2025.copy()
    pretty["sum_b"] = pretty["sum_b"].round(1)
    print(pretty.to_string(index=False))
    if not agg_2025.empty:
        total = agg_2025["sum_b"].sum()
        peak = agg_2025.loc[agg_2025["sum_b"].idxmax()]
        print(f"\n  total disclosed: ${total:.0f}B across {df_2025['ticker'].nunique()} fresh issuers")
        print(f"  peak year: {int(peak['year'])} at ${peak['sum_b']:.1f}B ({peak['sum_b']/total*100:.1f}% of total)")
        # 2026/27 vs rest test
        wall = agg_2025[(agg_2025["year"] >= 2026) & (agg_2025["year"] <= 2027)]["sum_b"].sum()
        if wall > 0:
            print(f"  2026+2027 combined: ${wall:.0f}B ({wall/total*100:.1f}% of total)")

    print()
    print("=" * 72)
    print("HISTORICAL COMPARISON — FY2019 anchor (what was 'due' 5y out then)")
    print("=" * 72)
    if not agg_2019.empty:
        pretty = agg_2019.copy()
        pretty["sum_b"] = pretty["sum_b"].round(1)
        print(pretty.to_string(index=False))
    else:
        print("  no FY2019 data")

    print()
    print("=" * 72)
    print("EXTENSION TEST — did companies push debt out vs FY2019?")
    print("=" * 72)
    have_both = df_ext.dropna(subset=["wam_2019", "wam_2025"])
    if not have_both.empty:
        print(f"  {len(have_both)} tickers have both FY2019 and FY2025 ladders")
        print(f"  median WAM FY2019: {have_both['wam_2019'].median():.2f} yrs")
        print(f"  median WAM FY2025: {have_both['wam_2025'].median():.2f} yrs")
        print(f"  median WAM change: {have_both['wam_change_yrs'].median():+.2f} yrs")
        print(f"  tickers extending (WAM ↑): {(have_both['wam_change_yrs'] > 0).sum()}")
        print(f"  tickers compressing (WAM ↓): {(have_both['wam_change_yrs'] < 0).sum()}")
        print()
        print("  per-ticker:")
        view = have_both[["ticker", "wam_2019", "wam_2025", "wam_change_yrs",
                           "pct_within_5y_2019", "pct_within_5y_2025"]].copy()
        view["wam_2019"] = view["wam_2019"].round(2)
        view["wam_2025"] = view["wam_2025"].round(2)
        view["wam_change_yrs"] = view["wam_change_yrs"].round(2)
        view["pct_within_5y_2019"] = (view["pct_within_5y_2019"] * 100).round(1)
        view["pct_within_5y_2025"] = (view["pct_within_5y_2025"] * 100).round(1)
        view = view.sort_values("wam_change_yrs")
        print(view.to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
