"""Build the bottom-up S&P 600 issuer-level debt dashboard.

Reads data/issuer/panel_wide_annual{_pilot}.csv and data/issuer/issuer_meta{_pilot}.csv
and produces:
  dashboard/issuer.html         (full universe run)
  dashboard/issuer_pilot.html   (--pilot run)

Clear "bottom-up lens, NOT the U.S. total" banner per research plan §5.

Charts:
  1. Aggregate sum: total debt, cash, interest expense (FY2018–latest)
  2. Median per-ticker debt / cash / interest over time
  3. Net debt distribution by fiscal year (box)
  4. Sector breakdown: total debt by GICS sector, FY2019 vs latest
  5. Implied cost of debt: interest_expense / avg(total_debt) distribution
  6. Cash-to-debt ratio: median + IQR over time

Usage:
    python3.11 scripts/build_issuer_dashboard.py --pilot
    python3.11 scripts/build_issuer_dashboard.py
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from textwrap import dedent

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent.parent
ISSUER = ROOT / "data" / "issuer"
DASH = ROOT / "dashboard"
DASH.mkdir(parents=True, exist_ok=True)

AS_OF = "2026-04-23"

COLORS = {
    "debt": "#2ca02c",
    "cash": "#1f77b4",
    "interest": "#d62728",
    "net_debt": "#8c564b",
    "ratio": "#9467bd",
}


EXCLUDED_SECTORS = {"Financial Services"}  # banks/insurance: interest expense ≠ debt interest


def load(panel: Path, meta: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(panel)
    df["period_end"] = pd.to_datetime(df["period_end"])
    df["fiscal_year"] = df["period_end"].dt.year
    m = pd.read_csv(meta)

    # Filter nonfinancials (research plan is about nonfinancial corp debt)
    m_nonfin = m[~m["sector"].isin(EXCLUDED_SECTORS)].copy()
    df = df[df["ticker"].isin(m_nonfin["ticker"])].copy()

    # Sanity clamp: an implied interest rate > 50% is almost always a scale
    # or classification error (e.g. EODHD GOLF FY2025 stores 87bn instead of 87m).
    # Null out the interest_expense in those rows so it doesn't pollute aggregates.
    mask = (
        df["interest_expense"].notna()
        & df["total_debt"].notna()
        & (df["total_debt"] > 0)
        & (df["interest_expense"] / df["total_debt"] > 0.5)
    )
    n_bad = int(mask.sum())
    if n_bad:
        print(f"  clamping {n_bad} interest-expense outliers (implied rate > 50%)")
        df.loc[mask, "interest_expense"] = pd.NA

    return df, m_nonfin, m


def chart_aggregate(df: pd.DataFrame) -> go.Figure:
    agg = df.groupby("fiscal_year")[[
        "total_debt", "cash_and_equivalents", "interest_expense"
    ]].sum(min_count=1) / 1e9  # USD billions
    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=("Total Debt (USD B)", "Cash & Equivalents (USD B)",
                        "Interest Expense (USD B)"),
    )
    fig.add_trace(go.Bar(x=agg.index, y=agg["total_debt"],
                         marker_color=COLORS["debt"], name="Debt",
                         hovertemplate="FY%{x}<br>$%{y:.1f}B<extra></extra>"),
                  row=1, col=1)
    fig.add_trace(go.Bar(x=agg.index, y=agg["cash_and_equivalents"],
                         marker_color=COLORS["cash"], name="Cash",
                         hovertemplate="FY%{x}<br>$%{y:.1f}B<extra></extra>"),
                  row=1, col=2)
    fig.add_trace(go.Bar(x=agg.index, y=agg["interest_expense"],
                         marker_color=COLORS["interest"], name="Interest",
                         hovertemplate="FY%{x}<br>$%{y:.2f}B<extra></extra>"),
                  row=1, col=3)
    fig.update_layout(
        template="plotly_white", height=380, showlegend=False,
        title=f"Aggregate across {df['ticker'].nunique()} included tickers",
        margin=dict(t=80, b=40, l=40, r=10),
    )
    return fig


def chart_median_per_ticker(df: pd.DataFrame) -> go.Figure:
    med = df.groupby("fiscal_year")[[
        "total_debt", "cash_and_equivalents", "interest_expense"
    ]].median() / 1e6
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=med.index, y=med["total_debt"], mode="lines+markers",
                             name="Debt (median)", line=dict(color=COLORS["debt"], width=3),
                             hovertemplate="FY%{x}<br>Debt $%{y:.0f}M<extra></extra>"))
    fig.add_trace(go.Scatter(x=med.index, y=med["cash_and_equivalents"], mode="lines+markers",
                             name="Cash (median)", line=dict(color=COLORS["cash"], width=3),
                             hovertemplate="FY%{x}<br>Cash $%{y:.0f}M<extra></extra>"))
    fig.add_trace(go.Scatter(x=med.index, y=med["interest_expense"], mode="lines+markers",
                             name="Interest (median)", line=dict(color=COLORS["interest"], width=3),
                             hovertemplate="FY%{x}<br>Interest $%{y:.1f}M<extra></extra>",
                             yaxis="y2"))
    fig.update_layout(
        template="plotly_white", height=420,
        title="Median per-issuer: debt, cash, interest expense",
        yaxis=dict(title="Debt / Cash (USD M)"),
        yaxis2=dict(title="Interest (USD M)", overlaying="y", side="right"),
        margin=dict(t=60, b=40, l=60, r=60),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def chart_net_debt_box(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["net_debt"]).copy()
    d["net_debt_m"] = d["net_debt"] / 1e6
    fig = go.Figure()
    for yr in sorted(d["fiscal_year"].unique()):
        sub = d[d["fiscal_year"] == yr]["net_debt_m"]
        fig.add_trace(go.Box(
            y=sub, name=f"FY{yr}", boxmean=True,
            marker_color=COLORS["net_debt"],
            hovertemplate=f"FY{yr}<br>$%{{y:.0f}}M<extra></extra>",
        ))
    fig.update_layout(
        template="plotly_white", height=400, showlegend=False,
        title="Net debt distribution across issuers, by fiscal year",
        yaxis=dict(title="Net debt (USD M)"),
        margin=dict(t=60, b=40, l=60, r=10),
    )
    return fig


def chart_sector_breakdown(df: pd.DataFrame, meta: pd.DataFrame) -> go.Figure:
    years = sorted(df["fiscal_year"].unique())
    if 2019 not in years:
        return go.Figure()
    latest = max(years)
    merged = df.merge(meta[["ticker", "sector"]], on="ticker", how="left")
    merged["sector"] = merged["sector"].fillna("Unknown")
    agg = (merged[merged["fiscal_year"].isin([2019, latest])]
           .groupby(["sector", "fiscal_year"])["total_debt"].sum(min_count=1) / 1e9
           ).unstack("fiscal_year").fillna(0)
    agg = agg.sort_values(latest, ascending=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=agg.index, x=agg[2019], orientation="h",
        name="FY2019", marker_color="#a6cee3",
        hovertemplate="%{y}<br>FY2019 $%{x:.1f}B<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=agg.index, x=agg[latest], orientation="h",
        name=f"FY{latest}", marker_color="#1f78b4",
        hovertemplate=f"%{{y}}<br>FY{latest} $%{{x:.1f}}B<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_white", height=max(320, 40 * len(agg)),
        title=f"Total debt by GICS sector: FY2019 vs FY{latest}",
        xaxis=dict(title="Total debt (USD B)"),
        barmode="group",
        margin=dict(t=60, b=40, l=180, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def chart_implied_cost(df: pd.DataFrame) -> go.Figure:
    d = df.sort_values(["ticker", "fiscal_year"]).copy()
    d["avg_debt"] = d.groupby("ticker")["total_debt"].transform(
        lambda s: (s + s.shift(1)) / 2
    )
    d["implied_rate"] = d["interest_expense"] / d["avg_debt"] * 100
    d = d.dropna(subset=["implied_rate"])
    d = d[(d["implied_rate"] >= 0) & (d["implied_rate"] <= 30)]  # drop outliers
    fig = go.Figure()
    for yr in sorted(d["fiscal_year"].unique()):
        sub = d[d["fiscal_year"] == yr]["implied_rate"]
        if len(sub) < 3:
            continue
        fig.add_trace(go.Box(
            y=sub, name=f"FY{yr}", boxmean=True,
            marker_color=COLORS["ratio"],
            hovertemplate=f"FY{yr}<br>%{{y:.1f}}%<extra></extra>",
        ))
    fig.update_layout(
        template="plotly_white", height=400, showlegend=False,
        title="Implied cost of debt: interest expense / avg(total debt)",
        yaxis=dict(title="Implied rate (%)"),
        margin=dict(t=60, b=40, l=60, r=10),
    )
    return fig


def chart_cash_to_debt(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["cash_and_equivalents", "total_debt"]).copy()
    d = d[d["total_debt"] > 0]
    d["ratio"] = d["cash_and_equivalents"] / d["total_debt"]
    stats = d.groupby("fiscal_year")["ratio"].quantile([0.25, 0.5, 0.75]).unstack()
    stats.columns = ["q25", "median", "q75"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=stats.index, y=stats["q75"], mode="lines",
        line=dict(width=0), showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=stats.index, y=stats["q25"], mode="lines",
        line=dict(width=0), fill="tonexty", fillcolor="rgba(148,103,189,0.2)",
        name="IQR (25-75%)", hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=stats.index, y=stats["median"], mode="lines+markers",
        line=dict(color=COLORS["ratio"], width=3), name="Median",
        hovertemplate="FY%{x}<br>%{y:.2f}x<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_white", height=380,
        title="Cash / total-debt ratio: median and IQR",
        yaxis=dict(title="Cash / Debt (x)"),
        margin=dict(t=60, b=40, l=60, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def build_summary(df: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    years = sorted(df["fiscal_year"].unique())
    if 2019 not in years:
        return pd.DataFrame()
    latest = max(years)
    a = df[df["fiscal_year"] == 2019]
    b = df[df["fiscal_year"] == latest]
    rows = []
    for metric, label, unit in [
        ("total_debt", "Total debt (sum)", "USD B"),
        ("cash_and_equivalents", "Cash (sum)", "USD B"),
        ("interest_expense", "Interest expense (sum)", "USD B"),
        ("net_debt", "Net debt (sum)", "USD B"),
    ]:
        va = a[metric].sum(min_count=1) / 1e9
        vb = b[metric].sum(min_count=1) / 1e9
        ch = (vb - va) / va * 100 if va else float("nan")
        rows.append({
            "metric": label, "FY2019": f"${va:,.1f}B",
            f"FY{latest}": f"${vb:,.1f}B",
            "change_pct": f"{ch:+.1f}%" if pd.notna(ch) else "n/a",
            "unit": unit,
        })
    # median debt
    va = a["total_debt"].median() / 1e6
    vb = b["total_debt"].median() / 1e6
    ch = (vb - va) / va * 100 if va else float("nan")
    rows.append({
        "metric": "Median debt per issuer", "FY2019": f"${va:,.0f}M",
        f"FY{latest}": f"${vb:,.0f}M",
        "change_pct": f"{ch:+.1f}%" if pd.notna(ch) else "n/a",
        "unit": "USD M",
    })
    return pd.DataFrame(rows)


def render(df: pd.DataFrame, meta: pd.DataFrame, out_html: Path, is_pilot: bool) -> None:
    n_tickers = df["ticker"].nunique()
    years = sorted(df["fiscal_year"].unique())
    latest = max(years)
    summary = build_summary(df, meta)

    figs = [
        ("Aggregate (sum across issuers)", chart_aggregate(df)),
        ("Median per-issuer", chart_median_per_ticker(df)),
        ("Net debt distribution", chart_net_debt_box(df)),
        ("Sector breakdown", chart_sector_breakdown(df, meta)),
        ("Implied cost of debt", chart_implied_cost(df)),
        ("Cash / debt ratio", chart_cash_to_debt(df)),
    ]

    body_parts = []
    for i, (title, fig) in enumerate(figs):
        include_plotly = (i == 0)  # CDN load only once
        html = fig.to_html(full_html=False,
                           include_plotlyjs="cdn" if include_plotly else False,
                           div_id=f"chart-{i}")
        body_parts.append(f'<section class="chart"><h2>{title}</h2>{html}</section>')

    summary_html = summary.to_html(index=False, classes="summary", border=0, escape=False) \
        if not summary.empty else ""

    mode = "PILOT (20 tickers)" if is_pilot else "FULL S&P 600 current universe"

    page = dedent(f"""\
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <title>S&amp;P 600 Issuer-Level Debt Dashboard</title>
          <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
                   margin: 0; padding: 0; background: #fafafa; color: #222; }}
            header {{ background: #1a1a2e; color: #eee; padding: 24px 40px; }}
            header h1 {{ margin: 0 0 6px 0; font-size: 24px; }}
            header .sub {{ color: #aaa; font-size: 13px; }}
            .warning {{ background: #fff3cd; border-left: 4px solid #f0ad4e;
                       padding: 14px 20px; margin: 20px 40px; font-size: 14px; color: #664d03; }}
            main {{ padding: 0 40px 40px 40px; }}
            .summary {{ width: 100%; border-collapse: collapse; margin: 16px 0 32px 0;
                        background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
            .summary th, .summary td {{ padding: 10px 14px; text-align: left;
                                         border-bottom: 1px solid #eee; font-size: 14px; }}
            .summary th {{ background: #f7f7fb; font-weight: 600; }}
            section.chart {{ background: white; margin: 16px 0;
                              box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 12px 16px; }}
            section.chart h2 {{ font-size: 16px; margin: 4px 0 8px 0; color: #444; }}
            footer {{ padding: 20px 40px 40px 40px; font-size: 12px; color: #777; }}
            footer ul {{ margin: 8px 0 0 0; padding-left: 20px; }}
            footer li {{ margin: 4px 0; }}
          </style>
        </head>
        <body>
          <header>
            <h1>S&amp;P 600 Issuer-Level Debt Dashboard</h1>
            <div class="sub">Bottom-up lens &middot; {mode} &middot; {n_tickers} tickers &middot; FY{min(years)}&ndash;FY{latest} &middot; built {AS_OF}</div>
          </header>

          <div class="warning">
            <strong>This is NOT the U.S. corporate debt total.</strong> This is a bottom-up
            aggregation of current S&amp;P 600 SmallCap constituents (with a reporting-since-2019
            filter as a proxy for historical membership, and <strong>Financial Services excluded</strong>
            because bank/insurer interest expense is dominated by deposit/policy interest, not debt interest).
            It is a thin slice of the U.S. corporate universe &mdash; see
            <code>dashboard/index.html</code> for the macro lens (FRED Z.1 / ICE BofA / Moody's).
          </div>

          <main>
            <h2 style="margin-top:16px">Summary &mdash; FY2019 vs FY{latest}</h2>
            {summary_html}

            {''.join(body_parts)}
          </main>

          <footer>
            <strong>Data source:</strong> EODHD Fundamentals API (annual &amp; quarterly,
            <code>Financials.Balance_Sheet</code> &amp; <code>Financials.Income_Statement</code>).
            Field mapping: total_debt &larr; <code>totalDebt</code> (fallback
            <code>shortLongTermDebtTotal</code> then <code>shortTermDebt + longTermDebt</code>);
            cash_and_equivalents &larr; <code>cashAndShortTermInvestments</code> (fallback
            <code>cash</code>); interest_expense normalized to positive.
            <br>
            <strong>Known limitations:</strong>
            <ul>
              <li>Current-universe proxy, NOT true historical membership &mdash; survivorship bias.</li>
              <li>Financial Services (105 tickers: mostly regional banks, insurers, asset managers) excluded.</li>
              <li>EODHD field coverage varies across issuers (capital leases, convertibles).</li>
              <li>Sanity clamp: interest_expense values with implied rate &gt; 50% nulled (data errors).</li>
              <li>Market cap is as-of today; not used for historical weighting.</li>
              <li>Interest expense sign convention flipped to positive where negative.</li>
              <li>Not comparable to FRED BCNSDODNS (nonfin corp debt aggregate).</li>
            </ul>
          </footer>
        </body>
        </html>
    """)
    out_html.write_text(page)
    print(f"  -> {out_html}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    args = ap.parse_args()

    suffix = "_pilot" if args.pilot else ""
    panel = ISSUER / f"panel_wide_annual{suffix}.csv"
    meta = ISSUER / f"issuer_meta{suffix}.csv"
    if not panel.exists() or not meta.exists():
        print(f"missing inputs: {panel}, {meta}")
        print("Run build_issuer_panel.py first.")
        return 1

    df, m_nonfin, m_all = load(panel, meta)
    out = DASH / ("issuer_pilot.html" if args.pilot else "issuer.html")
    n_fin = len(m_all) - len(m_nonfin)
    print(f"building issuer dashboard ({'pilot' if args.pilot else 'full'})")
    print(f"  total tickers in meta: {len(m_all)}  non-financial: {len(m_nonfin)}  (excluded {n_fin} financials)")
    print(f"  panel tickers: {df['ticker'].nunique()}  rows: {len(df)}")
    render(df, m_nonfin, out, is_pilot=args.pilot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
