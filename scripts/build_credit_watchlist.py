"""Identify top-decile S&P 600 debtors and rank by debt-stress score.

Reads data/issuer/credit_panel_annual.csv (built by build_credit_panel.py)
and produces:

  data/issuer/top_debtors_watchlist.csv  - the top 10% by latest total_debt
                                           plus 5yr trends and stress score
  data/issuer/concentration_summary.csv  - decile-level debt concentration

Stress-score components (each 0-100, higher = more stressed; mean composite):

  interest_coverage_score   100 - clamp(EBIT / interest, [0,10]) * 10
  leverage_score            clamp(net_debt/EBITDA, [0,8]) * 12.5
  fcf_score                 100 if FCF<=0 else clamp(20 - fcf_to_debt*200, [0,100])
  trend_score               clamp(interest_growth_5y / 1.5, [0,100])

Usage:
    python3.11 scripts/build_credit_watchlist.py
    python3.11 scripts/build_credit_watchlist.py --pct 5     # top 5%
    python3.11 scripts/build_credit_watchlist.py --exclude-re   # also drop REITs
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ISSUER = ROOT / "data" / "issuer"


def latest_per_ticker(df: pd.DataFrame) -> pd.DataFrame:
    """Latest fiscal year row per ticker (handles off-cycle FYs)."""
    return df.sort_values("period_end").groupby("ticker", as_index=False).tail(1)


def fy_anchor(df: pd.DataFrame, target_year: int) -> pd.DataFrame:
    """Best-match row whose fiscal_year == target_year, else closest earlier."""
    out = df.sort_values("period_end").copy()
    out = out.groupby("ticker", as_index=False).apply(
        lambda g: g[g["fiscal_year"] <= target_year].tail(1) if (g["fiscal_year"] <= target_year).any()
        else g.head(0)
    ).reset_index(drop=True)
    return out


def clamp(s: pd.Series, lo: float, hi: float) -> pd.Series:
    return s.clip(lower=lo, upper=hi)


def compute_stress(latest: pd.DataFrame, fy20: pd.DataFrame) -> pd.DataFrame:
    out = latest[["ticker", "period_end", "fiscal_year"]].copy()
    out["total_debt"] = latest["total_debt"]
    out["net_debt"] = latest["net_debt"]
    out["interest_expense"] = latest["interest_expense"]
    out["ebitda"] = latest["ebitda"]
    out["fcf"] = latest["fcf"]
    out["cash"] = latest["cash_and_equivalents"]
    out["interest_coverage_ebit"] = latest["interest_coverage_ebit"]
    out["interest_coverage_ebitda"] = latest["interest_coverage_ebitda"]
    out["net_debt_to_ebitda"] = latest["net_debt_to_ebitda"]
    out["debt_to_equity"] = latest["debt_to_equity"]
    out["fcf_to_debt"] = latest["fcf_to_debt"]
    out["implied_cost_of_debt"] = latest["implied_cost_of_debt"]

    # 5yr deltas (FY2020 anchor → latest)
    fy20_clean = fy20.sort_values("period_end").drop_duplicates("ticker", keep="last")
    fy20_anchor = fy20_clean[[
        "ticker", "total_debt", "interest_expense", "ebitda", "cash_and_equivalents"
    ]].rename(columns={
        "total_debt": "td_2020",
        "interest_expense": "ie_2020",
        "ebitda": "ebitda_2020",
        "cash_and_equivalents": "cash_2020",
    })
    out = out.merge(fy20_anchor, on="ticker", how="left")
    with np.errstate(divide="ignore", invalid="ignore"):
        out["debt_5y_pct"] = (out["total_debt"] / out["td_2020"] - 1) * 100
        out["interest_5y_pct"] = (out["interest_expense"] / out["ie_2020"] - 1) * 100
        out["ebitda_5y_pct"] = (out["ebitda"] / out["ebitda_2020"] - 1) * 100
        out["cash_5y_pct"] = (out["cash"] / out["cash_2020"] - 1) * 100
    for c in ["debt_5y_pct", "interest_5y_pct", "ebitda_5y_pct", "cash_5y_pct"]:
        out[c] = out[c].replace([np.inf, -np.inf], np.nan)
    out = out.drop(columns=["td_2020", "ie_2020", "ebitda_2020", "cash_2020"])

    # Component scores
    cov = out["interest_coverage_ebit"].fillna(0)
    out["score_coverage"] = (100 - clamp(cov, 0, 10) * 10).clip(0, 100)

    nde = out["net_debt_to_ebitda"].fillna(8)
    out["score_leverage"] = clamp(nde, 0, 8) * 12.5

    fcfd = out["fcf_to_debt"].fillna(-0.05)
    # Negative FCF = 100, FCF/Debt > 0.10 = 0
    out["score_fcf"] = (20 - fcfd * 200).clip(0, 100)

    intg = out.get("interest_5y_pct", pd.Series(0, index=out.index)).fillna(0)
    out["score_trend"] = clamp(intg / 1.5, 0, 100)

    out["stress_score"] = out[["score_coverage", "score_leverage",
                                "score_fcf", "score_trend"]].mean(axis=1).round(1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pct", type=float, default=10.0,
                    help="top percentile by total_debt (default 10)")
    ap.add_argument("--exclude-re", action="store_true",
                    help="also drop Real Estate sector")
    args = ap.parse_args()

    panel = pd.read_csv(ISSUER / "credit_panel_annual.csv")
    meta = pd.read_csv(ISSUER / "credit_meta.csv")
    panel["period_end"] = pd.to_datetime(panel["period_end"])

    if args.exclude_re:
        re_tickers = set(meta[meta["sector"] == "Real Estate"]["ticker"])
        before = panel["ticker"].nunique()
        panel = panel[~panel["ticker"].isin(re_tickers)]
        print(f"  dropped {before - panel['ticker'].nunique()} Real Estate tickers")

    latest = latest_per_ticker(panel)
    latest = latest.dropna(subset=["total_debt"])
    n = len(latest)
    top_n = max(1, int(round(n * args.pct / 100)))
    print(f"universe: {n}  top {args.pct}% = {top_n}")

    # Concentration summary
    latest_sorted = latest.sort_values("total_debt", ascending=False).reset_index(drop=True)
    total = latest_sorted["total_debt"].sum()
    deciles = []
    for p in [1, 5, 10, 25, 50, 100]:
        k = max(1, int(round(n * p / 100)))
        s = latest_sorted.head(k)["total_debt"].sum()
        deciles.append({"pct": p, "n": k, "debt_usd_b": s / 1e9,
                        "share": s / total * 100})
    conc = pd.DataFrame(deciles)
    conc.to_csv(ISSUER / "concentration_summary.csv", index=False)
    print()
    print("Debt concentration (cumulative):")
    print(conc.assign(debt_usd_b=conc["debt_usd_b"].round(0),
                       share=conc["share"].round(1)).to_string(index=False))
    print()

    # Top decile + stress score
    top = latest_sorted.head(top_n).copy()
    fy20 = panel[panel["fiscal_year"] == 2020]
    stress = compute_stress(top, fy20)
    stress = stress.merge(meta[["ticker", "name", "sector", "industry"]], on="ticker", how="left")
    stress = stress.sort_values("total_debt", ascending=False)

    # Format and save
    out_cols = [
        "ticker", "name", "sector", "industry",
        "period_end", "fiscal_year",
        "total_debt", "net_debt", "ebitda", "interest_expense", "fcf", "cash",
        "interest_coverage_ebit", "net_debt_to_ebitda",
        "debt_to_equity", "fcf_to_debt", "implied_cost_of_debt",
        "debt_5y_pct", "interest_5y_pct", "ebitda_5y_pct", "cash_5y_pct",
        "score_coverage", "score_leverage", "score_fcf", "score_trend",
        "stress_score",
    ]
    out = stress[[c for c in out_cols if c in stress.columns]]
    suffix = "_no_re" if args.exclude_re else ""
    out_path = ISSUER / f"top_debtors_watchlist{suffix}.csv"
    out.to_csv(out_path, index=False)
    print(f"watchlist -> {out_path}")
    print()
    print("Top 15 by stress score:")
    pretty = out.sort_values("stress_score", ascending=False).head(15)[
        ["ticker", "name", "sector", "total_debt", "interest_coverage_ebit",
         "net_debt_to_ebitda", "fcf_to_debt", "stress_score"]
    ].copy()
    pretty["total_debt_b"] = (pretty["total_debt"] / 1e9).round(1)
    pretty = pretty[["ticker", "name", "sector", "total_debt_b",
                     "interest_coverage_ebit", "net_debt_to_ebitda",
                     "fcf_to_debt", "stress_score"]]
    print(pretty.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
