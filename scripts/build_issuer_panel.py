"""Flatten per-ticker EODHD JSON caches into long/wide issuer panels.

Reads data/sp600/raw/{TICKER}.json (produced by fetch_eodhd_fundamentals.py)
and writes:
  data/issuer/panel_long.csv          # ticker, period_end, frequency, metric, value
  data/issuer/panel_wide_annual.csv   # one row per ticker-year
  data/issuer/panel_wide_quarterly.csv
  data/issuer/issuer_meta.csv         # ticker, name, sector, industry, ipo_date
  data/issuer/excluded_tickers.csv    # tickers filtered out + reason

Inclusion filter: ticker must have at least one Balance_Sheet.yearly entry
with period_end <= 2019-12-31 (i.e. FY2018 or FY2019 reported before/during
2019 fiscal close).

Usage:
    python3.11 scripts/build_issuer_panel.py --pilot
    python3.11 scripts/build_issuer_panel.py
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

METRICS = [
    "total_debt",
    "short_term_debt",
    "long_term_debt",
    "cash_and_equivalents",
    "net_debt",
    "interest_expense",
]

FY_CUTOFF = pd.Timestamp("2019-12-31")


def _safe_float(x) -> float | None:
    if x is None or x == "":
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v


def _pick_debt(row: dict) -> float | None:
    """Prefer totalDebt; fallback to shortLongTermDebtTotal; else ST+LT."""
    td = _safe_float(row.get("totalDebt"))
    if td is not None:
        return td
    sltt = _safe_float(row.get("shortLongTermDebtTotal"))
    if sltt is not None:
        return sltt
    st = _safe_float(row.get("shortTermDebt"))
    lt = _safe_float(row.get("longTermDebt"))
    if st is None and lt is None:
        return None
    return (st or 0.0) + (lt or 0.0)


def _pick_cash(row: dict) -> float | None:
    """Prefer cashAndShortTermInvestments; fallback to cash."""
    c = _safe_float(row.get("cashAndShortTermInvestments"))
    if c is not None:
        return c
    return _safe_float(row.get("cash"))


def _extract_period(bs_row: dict, is_row: dict | None) -> dict:
    """Combine balance-sheet + income-statement fields for one period."""
    debt = _pick_debt(bs_row)
    cash = _pick_cash(bs_row)
    st = _safe_float(bs_row.get("shortTermDebt"))
    lt = _safe_float(bs_row.get("longTermDebt"))
    net = _safe_float(bs_row.get("netDebt"))
    if net is None and debt is not None and cash is not None:
        net = debt - cash
    ie = None
    if is_row is not None:
        ie = _safe_float(is_row.get("interestExpense"))
        if ie is not None and ie < 0:
            ie = -ie  # normalize sign
    return {
        "total_debt": debt,
        "short_term_debt": st,
        "long_term_debt": lt,
        "cash_and_equivalents": cash,
        "net_debt": net,
        "interest_expense": ie,
    }


def process_ticker(tk: str, path: Path) -> tuple[dict | None, list[dict], str | None]:
    """Return (meta, rows, exclusion_reason).

    rows is list of dicts: ticker, period_end, frequency, plus metric columns.
    """
    try:
        d = json.loads(path.read_text())
    except Exception as e:
        return None, [], f"json-parse-error: {e}"

    g = d.get("General") or {}
    fin = d.get("Financials") or {}
    bs = fin.get("Balance_Sheet") or {}
    inc = fin.get("Income_Statement") or {}

    bs_y = bs.get("yearly") or {}
    bs_q = bs.get("quarterly") or {}
    is_y = inc.get("yearly") or {}
    is_q = inc.get("quarterly") or {}

    if not bs_y:
        return None, [], "no-yearly-balance-sheet"

    # Filter: any yearly period_end <= 2019-12-31
    dates = []
    for k in bs_y.keys():
        try:
            dates.append(pd.Timestamp(k))
        except Exception:
            pass
    if not dates or min(dates) > FY_CUTOFF:
        min_str = min(dates).strftime("%Y-%m-%d") if dates else "n/a"
        return None, [], f"no-fy2018-or-fy2019 (earliest={min_str})"

    meta = {
        "ticker": tk.replace(".US", ""),
        "eodhd_ticker": tk,
        "name": g.get("Name"),
        "sector": g.get("Sector"),
        "industry": g.get("Industry"),
        "ipo_date": g.get("IPODate"),
        "market_cap": _safe_float(g.get("MarketCapitalization")),
    }

    rows: list[dict] = []
    for period, row in bs_y.items():
        is_row = is_y.get(period)
        m = _extract_period(row, is_row)
        rows.append({
            "ticker": meta["ticker"],
            "period_end": period,
            "frequency": "annual",
            **m,
        })
    for period, row in bs_q.items():
        is_row = is_q.get(period)
        m = _extract_period(row, is_row)
        rows.append({
            "ticker": meta["ticker"],
            "period_end": period,
            "frequency": "quarterly",
            **m,
        })

    return meta, rows, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true",
                    help="use pilot ticker list instead of full universe")
    args = ap.parse_args()

    src = SP600 / ("pilot_tickers.csv" if args.pilot else "sp600_current.csv")
    if not src.exists():
        print(f"missing {src}", file=sys.stderr)
        return 1
    df_u = pd.read_csv(src)
    tickers = df_u["eodhd_ticker"].tolist()
    print(f"processing {len(tickers)} tickers ({'pilot' if args.pilot else 'full'})")

    all_rows: list[dict] = []
    all_meta: list[dict] = []
    excluded: list[dict] = []
    missing: list[str] = []

    for tk in tickers:
        p = RAW / f"{tk}.json"
        if not p.exists():
            missing.append(tk)
            excluded.append({"ticker": tk, "reason": "no-cache-file"})
            continue
        meta, rows, reason = process_ticker(tk, p)
        if reason is not None:
            excluded.append({"ticker": tk, "reason": reason})
            continue
        all_meta.append(meta)
        all_rows.extend(rows)

    print(f"  included={len(all_meta)}  excluded={len(excluded)}  missing-cache={len(missing)}")

    if not all_rows:
        print("no data — exiting", file=sys.stderr)
        return 1

    wide = pd.DataFrame(all_rows)
    wide["period_end"] = pd.to_datetime(wide["period_end"], errors="coerce")
    wide = wide.dropna(subset=["period_end"]).sort_values(["ticker", "frequency", "period_end"])

    # long form
    long = wide.melt(
        id_vars=["ticker", "period_end", "frequency"],
        value_vars=METRICS, var_name="metric", value_name="value",
    ).dropna(subset=["value"])

    annual = wide[wide["frequency"] == "annual"].copy()
    quarterly = wide[wide["frequency"] == "quarterly"].copy()
    annual["fiscal_year"] = annual["period_end"].dt.year

    suffix = "_pilot" if args.pilot else ""
    (ISSUER / f"panel_long{suffix}.csv").write_text(long.to_csv(index=False))
    (ISSUER / f"panel_wide_annual{suffix}.csv").write_text(annual.to_csv(index=False))
    (ISSUER / f"panel_wide_quarterly{suffix}.csv").write_text(quarterly.to_csv(index=False))
    pd.DataFrame(all_meta).to_csv(ISSUER / f"issuer_meta{suffix}.csv", index=False)
    pd.DataFrame(excluded).to_csv(ISSUER / f"excluded_tickers{suffix}.csv", index=False)

    print(f"  long rows: {len(long):,}")
    print(f"  annual ticker-periods: {len(annual):,}")
    print(f"  quarterly ticker-periods: {len(quarterly):,}")
    print(f"  -> {ISSUER}")

    # Sanity: FY coverage per ticker
    cov = annual.groupby("ticker")["fiscal_year"].agg(["min", "max", "count"])
    print()
    print("annual coverage per ticker:")
    print(cov.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
