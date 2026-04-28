"""Build a credit-focused issuer panel from cached EODHD JSONs.

Extends build_issuer_panel.py with a richer feature set tailored for
debt-sustainability analysis:

  Balance Sheet:    total_debt, st_debt, lt_debt, capital_leases, cash,
                    total_assets, total_equity, current_assets, current_liab,
                    working_capital
  Income Statement: revenue, ebit, ebitda, operating_income, interest_expense,
                    net_income, dep_amort
  Cash Flow:        cfo, capex, fcf, dividends_paid, net_borrowings,
                    stock_buybacks
  Derived:          interest_coverage_ebit, interest_coverage_ebitda,
                    net_debt_to_ebitda, debt_to_equity, debt_to_assets,
                    cash_to_st_debt, fcf_to_debt, fcf_minus_interest,
                    implied_cost_of_debt

Outputs:
  data/issuer/credit_panel_annual.csv
  data/issuer/credit_panel_quarterly.csv
  data/issuer/credit_meta.csv

Usage:
    python3.11 scripts/build_credit_panel.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SP600 = ROOT / "data" / "sp600"
RAW = SP600 / "raw"
ISSUER = ROOT / "data" / "issuer"
ISSUER.mkdir(parents=True, exist_ok=True)

EXCLUDED_SECTORS = {"Financial Services"}
FY_CUTOFF = pd.Timestamp("2019-12-31")


def f(x) -> float | None:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def pick_debt(bs: dict) -> float | None:
    """Best estimate of total debt; fallback chain."""
    return (
        f(bs.get("shortLongTermDebtTotal"))
        or ((f(bs.get("shortTermDebt")) or 0) + (f(bs.get("longTermDebt")) or 0))
        or f(bs.get("longTermDebtTotal"))
        or None
    )


def pick_cash(bs: dict) -> float | None:
    return f(bs.get("cashAndShortTermInvestments")) or f(bs.get("cash"))


def extract(period: str, bs: dict, inc: dict | None, cf: dict | None) -> dict:
    debt = pick_debt(bs)
    st = f(bs.get("shortTermDebt"))
    lt = f(bs.get("longTermDebt"))
    cap_lease = f(bs.get("capitalLeaseObligations"))
    cash = pick_cash(bs)
    nd = f(bs.get("netDebt"))
    if nd is None and debt is not None and cash is not None:
        nd = debt - cash

    inc = inc or {}
    revenue = f(inc.get("totalRevenue"))
    ebit = f(inc.get("ebit"))
    ebitda = f(inc.get("ebitda"))
    op_inc = f(inc.get("operatingIncome"))
    ni = f(inc.get("netIncome"))
    da_inc = f(inc.get("depreciationAndAmortization"))
    ie = f(inc.get("interestExpense"))
    if ie is not None and ie < 0:
        ie = -ie

    cf = cf or {}
    cfo = f(cf.get("totalCashFromOperatingActivities"))
    capex = f(cf.get("capitalExpenditures"))
    if capex is not None and capex > 0:
        capex = -capex  # normalize to negative cash outflow
    fcf = f(cf.get("freeCashFlow"))
    if fcf is None and cfo is not None and capex is not None:
        fcf = cfo + capex  # capex already negative
    div_paid = f(cf.get("dividendsPaid"))
    net_borrow = f(cf.get("netBorrowings"))
    sbs = f(cf.get("salePurchaseOfStock"))

    # Build EBITDA fallback if missing (EBIT + D&A from cash flow or inc stmt)
    if ebitda is None and ebit is not None:
        da = da_inc or f(cf.get("depreciation"))
        if da is not None:
            ebitda = ebit + da

    return {
        "period_end": period,
        "total_debt": debt,
        "short_term_debt": st,
        "long_term_debt": lt,
        "capital_lease_obligations": cap_lease,
        "cash_and_equivalents": cash,
        "net_debt": nd,
        "total_assets": f(bs.get("totalAssets")),
        "total_liab": f(bs.get("totalLiab")),
        "total_equity": f(bs.get("totalStockholderEquity")),
        "current_assets": f(bs.get("totalCurrentAssets")),
        "current_liab": f(bs.get("totalCurrentLiabilities")),
        "working_capital": f(bs.get("netWorkingCapital")),
        "revenue": revenue,
        "ebit": ebit,
        "ebitda": ebitda,
        "operating_income": op_inc,
        "net_income": ni,
        "dep_amort": da_inc,
        "interest_expense": ie,
        "cfo": cfo,
        "capex": capex,
        "fcf": fcf,
        "dividends_paid": div_paid,
        "net_borrowings": net_borrow,
        "stock_buybacks": sbs,
    }


def derive_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """Compute credit-sustainability ratios row-by-row."""
    out = df.copy()
    # Use prior-year debt average for implied rate
    out = out.sort_values(["ticker", "period_end"])
    out["avg_debt"] = out.groupby("ticker")["total_debt"].transform(
        lambda s: (s + s.shift(1)) / 2
    )

    def safe_div(a, b):
        return a / b.where(b > 0)

    out["interest_coverage_ebit"] = safe_div(out["ebit"], out["interest_expense"])
    out["interest_coverage_ebitda"] = safe_div(out["ebitda"], out["interest_expense"])
    out["net_debt_to_ebitda"] = safe_div(out["net_debt"], out["ebitda"])
    out["debt_to_equity"] = safe_div(out["total_debt"], out["total_equity"])
    out["debt_to_assets"] = safe_div(out["total_debt"], out["total_assets"])
    out["cash_to_st_debt"] = safe_div(out["cash_and_equivalents"], out["short_term_debt"])
    out["fcf_to_debt"] = safe_div(out["fcf"], out["total_debt"])
    out["fcf_minus_interest"] = out["fcf"] - out["interest_expense"]
    out["implied_cost_of_debt"] = safe_div(out["interest_expense"], out["avg_debt"])

    # Sanity: implied rate > 50% is a data error — null those interest fields
    bad = out["implied_cost_of_debt"] > 0.5
    n_bad = int(bad.sum())
    if n_bad:
        out.loc[bad, ["interest_expense", "interest_coverage_ebit",
                      "interest_coverage_ebitda", "implied_cost_of_debt",
                      "fcf_minus_interest"]] = pd.NA
    return out, n_bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-financials", action="store_true",
                    help="don't drop Financial Services sector")
    args = ap.parse_args()

    src = SP600 / "sp600_current.csv"
    universe = pd.read_csv(src)

    annual_rows: list[dict] = []
    quarter_rows: list[dict] = []
    meta_rows: list[dict] = []
    excluded: list[dict] = []

    for tk in universe["eodhd_ticker"]:
        p = RAW / f"{tk}.json"
        if not p.exists():
            excluded.append({"ticker": tk, "reason": "no-cache"})
            continue
        try:
            d = json.loads(p.read_text())
        except Exception as e:
            excluded.append({"ticker": tk, "reason": f"json-parse-error: {e}"})
            continue

        g = d.get("General") or {}
        if not args.include_financials and g.get("Sector") in EXCLUDED_SECTORS:
            excluded.append({"ticker": tk, "reason": f"sector-excluded: {g.get('Sector')}"})
            continue

        fin = d.get("Financials") or {}
        bs_y = (fin.get("Balance_Sheet") or {}).get("yearly") or {}
        bs_q = (fin.get("Balance_Sheet") or {}).get("quarterly") or {}
        is_y = (fin.get("Income_Statement") or {}).get("yearly") or {}
        is_q = (fin.get("Income_Statement") or {}).get("quarterly") or {}
        cf_y = (fin.get("Cash_Flow") or {}).get("yearly") or {}
        cf_q = (fin.get("Cash_Flow") or {}).get("quarterly") or {}

        if not bs_y:
            excluded.append({"ticker": tk, "reason": "no-yearly-bs"})
            continue

        # FY2018/2019 reporter filter
        dates = []
        for k in bs_y:
            try:
                dates.append(pd.Timestamp(k))
            except Exception:
                pass
        if not dates or min(dates) > FY_CUTOFF:
            excluded.append({"ticker": tk, "reason": f"no-fy2019 (earliest={min(dates) if dates else 'na'})"})
            continue

        ticker_short = tk.replace(".US", "")
        meta_rows.append({
            "ticker": ticker_short,
            "eodhd_ticker": tk,
            "name": g.get("Name"),
            "sector": g.get("Sector"),
            "industry": g.get("Industry"),
            "ipo_date": g.get("IPODate"),
            "market_cap": f(g.get("MarketCapitalization")),
        })

        for period, row in bs_y.items():
            r = extract(period, row, is_y.get(period), cf_y.get(period))
            r["ticker"] = ticker_short
            r["frequency"] = "annual"
            annual_rows.append(r)
        for period, row in bs_q.items():
            r = extract(period, row, is_q.get(period), cf_q.get(period))
            r["ticker"] = ticker_short
            r["frequency"] = "quarterly"
            quarter_rows.append(r)

    print(f"included: {len(meta_rows)} tickers")
    print(f"excluded: {len(excluded)}")
    print(f"  reasons: {pd.Series([e['reason'].split(':')[0] for e in excluded]).value_counts().to_dict()}")

    annual = pd.DataFrame(annual_rows)
    annual["period_end"] = pd.to_datetime(annual["period_end"], errors="coerce")
    annual = annual.dropna(subset=["period_end"]).sort_values(["ticker", "period_end"])
    annual["fiscal_year"] = annual["period_end"].dt.year

    quarterly = pd.DataFrame(quarter_rows)
    quarterly["period_end"] = pd.to_datetime(quarterly["period_end"], errors="coerce")
    quarterly = quarterly.dropna(subset=["period_end"]).sort_values(["ticker", "period_end"])

    annual, n_bad_a = derive_ratios(annual)
    quarterly, n_bad_q = derive_ratios(quarterly)
    print(f"clamped {n_bad_a} annual + {n_bad_q} quarterly outlier interest rows")

    # Reorder columns
    front = ["ticker", "period_end", "fiscal_year", "frequency"]
    annual = annual[front + [c for c in annual.columns if c not in front]]
    quarterly = quarterly[[c for c in front if c != "fiscal_year"] +
                          [c for c in quarterly.columns if c not in front]]

    annual.to_csv(ISSUER / "credit_panel_annual.csv", index=False)
    quarterly.to_csv(ISSUER / "credit_panel_quarterly.csv", index=False)
    pd.DataFrame(meta_rows).to_csv(ISSUER / "credit_meta.csv", index=False)
    pd.DataFrame(excluded).to_csv(ISSUER / "credit_excluded.csv", index=False)

    print(f"  annual rows: {len(annual):,}  cols: {len(annual.columns)}")
    print(f"  quarterly rows: {len(quarterly):,}")
    print(f"  -> {ISSUER}/credit_panel_annual.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
