"""Refi-wall dashboard: when is the watchlist's debt due?

Combines:
  data/issuer/refi_wall_summary.csv   (per-ticker maturity ladder)
  data/issuer/top_debtors_watchlist_no_re.csv  (stress score + ratios)
  data/issuer/credit_meta.csv          (sector / industry)

Charts:
  1. Aggregate refi wall — sum of y1/y2/y3/y4/y5/yGT5 across watchlist
  2. % due within 2 years — per ticker, sorted by exposure
  3. Refi wall vs FCF — bubble chart: y1+y2 maturities vs latest FCF
  4. Per-company stacked bars — every covered ticker's full ladder
  5. Most-stressed names — refi schedule for the 12 highest stress scores
     that have maturity data

Output: dashboard/refi_wall.html
"""
from __future__ import annotations

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

BUCKETS = ["y1", "y2", "y3", "y4", "y5", "yGT5"]
BUCKET_LABELS = {
    "y1": "Year 1", "y2": "Year 2", "y3": "Year 3",
    "y4": "Year 4", "y5": "Year 5", "yGT5": "After year 5",
}
BUCKET_COLORS = {
    "y1": "#b30000", "y2": "#e34a33", "y3": "#fc8d59",
    "y4": "#fdbb84", "y5": "#fdd49e", "yGT5": "#bdbdbd",
}


def load() -> dict:
    summary = pd.read_csv(ISSUER / "refi_wall_summary.csv")
    summary = summary[summary["total_in_table"] > 0].copy()
    watch = pd.read_csv(ISSUER / "top_debtors_watchlist.csv")
    watch_nore = pd.read_csv(ISSUER / "top_debtors_watchlist_no_re.csv")
    meta = pd.read_csv(ISSUER / "credit_meta.csv")
    panel = pd.read_csv(ISSUER / "credit_panel_annual.csv")
    panel["period_end"] = pd.to_datetime(panel["period_end"])
    summary = summary.merge(meta[["ticker", "sector", "industry"]],
                             on="ticker", how="left")
    summary = summary.merge(
        watch[["ticker", "stress_score", "interest_5y_pct",
                "fcf_to_debt", "interest_coverage_ebit", "fcf",
                "ebitda", "interest_expense", "total_debt"]],
        on="ticker", how="left",
    )
    return {"summary": summary, "watch": watch, "watch_nore": watch_nore,
             "meta": meta, "panel": panel}


def chart_aggregate_wall(summary: pd.DataFrame) -> go.Figure:
    agg = summary[BUCKETS].sum(axis=0) / 1e9
    total = agg.sum()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[BUCKET_LABELS[b] for b in BUCKETS], y=agg.values,
        marker_color=[BUCKET_COLORS[b] for b in BUCKETS],
        text=[f"${v:.1f}B<br>{v/total*100:.1f}%" for v in agg.values],
        textposition="outside",
        hovertemplate="%{x}<br>$%{y:.1f}B<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_white", height=380, showlegend=False,
        title=f"Aggregate refi wall across {len(summary)} top-decile issuers — total ${total:.0f}B",
        yaxis=dict(title="USD billions"),
        margin=dict(t=60, b=40, l=60, r=20),
    )
    return fig


def chart_pct_within_2y(summary: pd.DataFrame) -> go.Figure:
    d = summary.dropna(subset=["pct_due_within_2y"]).copy()
    d["pct_2y"] = d["pct_due_within_2y"] * 100
    d = d.sort_values("pct_2y")
    colors = ["#d62728" if x > 50 else "#fc8d59" if x > 25 else "#1a9850"
               for x in d["pct_2y"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=d["ticker"], x=d["pct_2y"], orientation="h",
        marker_color=colors,
        text=[f"{v:.0f}% (${tt/1e6:,.0f}M total)"
              for v, tt in zip(d["pct_2y"], d["total_in_table"])],
        textposition="outside",
        customdata=d[["entity_name", "y1", "y2", "total_in_table"]].values,
        hovertemplate=("<b>%{y}</b> — %{customdata[0]}<br>"
                       "Year 1: $%{customdata[1]:,.0f}M<br>"
                       "Year 2: $%{customdata[2]:,.0f}M<br>"
                       "Total in maturity table: $%{customdata[3]:,.0f}M<br>"
                       "Due within 2y: %{x:.1f}%<extra></extra>"),
    ))
    fig.add_vline(x=25, line_color="orange", line_dash="dot")
    fig.add_vline(x=50, line_color="red", line_dash="dot")
    fig.update_layout(
        template="plotly_white", height=max(420, 22 * len(d)),
        title="Pct of debt due within 2 years",
        xaxis=dict(title="% of disclosed debt due in next 24 months"),
        margin=dict(t=60, b=40, l=80, r=180),
        showlegend=False,
    )
    return fig


def chart_refi_vs_fcf(summary: pd.DataFrame) -> go.Figure:
    d = summary.dropna(subset=["fcf"]).copy()
    d["due_2y_b"] = d["due_within_2y"] / 1e9
    d["fcf_b"] = d["fcf"] / 1e9
    d["debt_b"] = d["total_debt"].fillna(0) / 1e9
    d["bubble"] = d["debt_b"].clip(lower=1) ** 0.6 * 8
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=d["fcf_b"], y=d["due_2y_b"], mode="markers+text",
        marker=dict(size=d["bubble"],
                    color=d["stress_score"], colorscale="RdYlGn_r",
                    cmin=20, cmax=90, showscale=True,
                    colorbar=dict(title="Stress<br>score"),
                    line=dict(width=1, color="white")),
        text=d["ticker"], textposition="top center", textfont=dict(size=9),
        customdata=d[["entity_name", "debt_b", "stress_score"]].values,
        hovertemplate=("<b>%{text}</b> — %{customdata[0]}<br>"
                       "Total debt: $%{customdata[1]:.1f}B<br>"
                       "Latest FCF: $%{x:.1f}B<br>"
                       "Due within 2y: $%{y:.1f}B<br>"
                       "Stress score: %{customdata[2]:.0f}<extra></extra>"),
    ))
    # 1:1 reference (FCF = 2y refi)
    rng = max(abs(d["fcf_b"].min()), d["fcf_b"].max(), d["due_2y_b"].max()) * 1.1
    fig.add_shape(type="line", x0=0, x1=rng, y0=0, y1=rng,
                  line=dict(color="gray", dash="dot", width=1))
    fig.add_annotation(x=rng * 0.85, y=rng * 0.9, text="2y refi = FCF",
                        showarrow=False, font=dict(size=10, color="gray"))
    fig.update_layout(
        template="plotly_white", height=520,
        title="Refi wall (next 2y) vs annual FCF — points above the diagonal can't self-fund the wall",
        xaxis=dict(title="Latest annual FCF (USD B)"),
        yaxis=dict(title="Maturities due within 2 years (USD B)"),
        margin=dict(t=60, b=40, l=60, r=20),
        showlegend=False,
    )
    return fig


def chart_per_ticker_ladder(summary: pd.DataFrame) -> go.Figure:
    d = summary.copy()
    d = d.sort_values("total_in_table", ascending=True)
    fig = go.Figure()
    for b in BUCKETS:
        fig.add_trace(go.Bar(
            y=d["ticker"], x=d[b].fillna(0) / 1e6, orientation="h",
            name=BUCKET_LABELS[b], marker_color=BUCKET_COLORS[b],
            hovertemplate="%{y} " + BUCKET_LABELS[b] + " $%{x:,.0f}M<extra></extra>",
        ))
    fig.update_layout(
        template="plotly_white", height=max(420, 24 * len(d)),
        title="Per-issuer maturity ladder (USD M, stacked)",
        barmode="stack",
        xaxis=dict(title="USD millions"),
        margin=dict(t=60, b=40, l=80, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                     xanchor="right", x=1),
    )
    return fig


def chart_most_stressed_with_maturity(summary: pd.DataFrame, panel: pd.DataFrame,
                                        watch_nore: pd.DataFrame, n: int = 12) -> go.Figure:
    """For top-N stressed tickers (with maturity data) show a year-by-year
    refi schedule overlaid with their latest FCF as a horizontal capacity line."""
    have_mat = set(summary["ticker"])
    candidates = watch_nore[watch_nore["ticker"].isin(have_mat)]
    top = candidates.nlargest(n, "stress_score")["ticker"].tolist()
    n_cols = 3
    n_rows = (len(top) + n_cols - 1) // n_cols
    titles = []
    for tk in top:
        row = candidates[candidates["ticker"] == tk].iloc[0]
        nm = (row["name"] or tk)[:30]
        titles.append(f"<b>{tk}</b> — {nm}")

    fig = make_subplots(rows=n_rows, cols=n_cols, subplot_titles=titles,
                         vertical_spacing=0.12, horizontal_spacing=0.07)
    for i, tk in enumerate(top):
        r, c = i // n_cols + 1, i % n_cols + 1
        s = summary[summary["ticker"] == tk].iloc[0]
        anchor_year = pd.Timestamp(s["period_end"]).year if s.get("period_end") else None
        x_labels = []
        y_vals = []
        for j, b in enumerate(["y1", "y2", "y3", "y4", "y5"]):
            v = s.get(b)
            if pd.notna(v):
                yr = anchor_year + j + 1 if anchor_year else f"y{j+1}"
                x_labels.append(str(yr))
                y_vals.append(v / 1e6)
        v5 = s.get("yGT5")
        if pd.notna(v5):
            x_labels.append(f">{anchor_year+5}" if anchor_year else ">y5")
            y_vals.append(v5 / 1e6)
        fig.add_trace(go.Bar(
            x=x_labels, y=y_vals, marker_color="#d62728",
            name="Maturity", showlegend=(i == 0),
            hovertemplate=f"{tk} %{{x}}: $%{{y:,.0f}}M<extra></extra>",
        ), row=r, col=c)
        # FCF capacity line
        fcf_m = (s.get("fcf") or 0) / 1e6
        if fcf_m:
            fig.add_hline(y=fcf_m, row=r, col=c, line_color="#2ca02c",
                          line_dash="dash",
                          annotation_text=f"FCF ${fcf_m:,.0f}M",
                          annotation_position="top right",
                          annotation_font=dict(size=9, color="#2ca02c"))

    fig.update_layout(
        template="plotly_white", height=max(300, 240 * n_rows),
        title=f"Top {n} stressed names (ex-REIT): maturity schedule vs FCF capacity",
        margin=dict(t=80, b=40, l=40, r=40),
        showlegend=False,
    )
    fig.update_xaxes(tickfont=dict(size=10))
    fig.update_yaxes(title_text="USD M", title_font=dict(size=10),
                      tickfont=dict(size=9))
    return fig


def render(data: dict, out_html: Path) -> None:
    summary = data["summary"]
    watch_nore = data["watch_nore"]
    panel = data["panel"]

    n_cov = len(summary)
    total_disclosed = summary["total_in_table"].sum() / 1e9
    due_2y_total = summary["due_within_2y"].sum() / 1e9
    due_5y_total = summary["due_within_5y"].sum() / 1e9
    pct_2y_agg = due_2y_total / total_disclosed * 100 if total_disclosed else float("nan")
    median_pct_2y = (summary["pct_due_within_2y"] * 100).median()

    figs = [
        ("Aggregate refi wall",
         chart_aggregate_wall(summary),
         "Stack of all watchlist names' disclosed maturities by year-bucket from each company's latest 10-K balance-sheet date."),
        ("Pct due within 2 years (per issuer)",
         chart_pct_within_2y(summary),
         "Names above 50% (red line) face the heaviest near-term refi pressure."),
        ("Refi wall vs FCF",
         chart_refi_vs_fcf(summary),
         "X = latest annual FCF, Y = maturities due in next 2y. Points above the dotted diagonal can't self-fund the wall from FCF — they need to roll."),
        ("Per-issuer maturity ladder",
         chart_per_ticker_ladder(summary),
         "Full disclosed schedule, stacked. Hover for bucket-level detail."),
        ("Most-stressed names + FCF capacity",
         chart_most_stressed_with_maturity(summary, panel, watch_nore, n=12),
         "Top 12 by stress score (ex-REITs) with maturity schedule. Green dashed line = latest annual FCF — when bars exceed it, the company can't self-fund that year's maturity."),
    ]

    body_parts = []
    for i, (title, fig, sub) in enumerate(figs):
        include_plotly = (i == 0)
        html = fig.to_html(full_html=False,
                            include_plotlyjs="cdn" if include_plotly else False,
                            div_id=f"chart-{i}")
        body_parts.append(
            f'<section class="chart"><h2>{title}</h2>'
            f'<p class="sub">{sub}</p>{html}</section>'
        )

    # Top-15 refi-wall table
    table = summary.copy()
    table["debt_b"] = (table["total_debt"].fillna(0) / 1e9).round(1)
    table["y1_m"] = (table["y1"].fillna(0) / 1e6).round(0).astype(int)
    table["y2_m"] = (table["y2"].fillna(0) / 1e6).round(0).astype(int)
    table["due_2y_m"] = (table["due_within_2y"] / 1e6).round(0).astype(int)
    table["pct_2y"] = (table["pct_due_within_2y"] * 100).round(1)
    table["fcf_m"] = (table["fcf"].fillna(0) / 1e6).round(0).astype(int)
    table["score"] = table["stress_score"].fillna(0).round(0).astype(int)
    table = table.sort_values("pct_2y", ascending=False)
    cols = {"ticker": "Ticker", "entity_name": "Name", "sector": "Sector",
             "period_end": "BS date", "debt_b": "Debt $B",
             "y1_m": "Y1 $M", "y2_m": "Y2 $M",
             "due_2y_m": "Due 2y $M", "pct_2y": "Due 2y %",
             "fcf_m": "FCF $M", "score": "Stress"}
    table_html = (table[list(cols.keys())].rename(columns=cols)
                  .head(20).to_html(index=False, escape=False, classes="watch", border=0))

    page = dedent(f"""\
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <title>S&amp;P 600 Refi-Wall Tracker</title>
          <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                    Helvetica, Arial, sans-serif; margin: 0; background: #fafafa;
                    color: #222; }}
            header {{ background: #1a1a2e; color: #eee; padding: 24px 40px; }}
            header h1 {{ margin: 0 0 6px 0; font-size: 24px; }}
            header .sub {{ color: #aaa; font-size: 13px; }}
            .chip-row {{ display: flex; gap: 12px; padding: 18px 40px 0 40px; }}
            .chip {{ background: white; padding: 14px 20px; border-radius: 6px;
                     box-shadow: 0 1px 3px rgba(0,0,0,0.08); flex: 1; }}
            .chip .label {{ font-size: 11px; text-transform: uppercase; color: #777;
                            letter-spacing: 0.5px; }}
            .chip .value {{ font-size: 22px; font-weight: 600; margin-top: 4px;
                            color: #1a1a2e; }}
            .chip .delta {{ font-size: 12px; color: #555; margin-top: 2px; }}
            .warning {{ background: #fff3cd; border-left: 4px solid #f0ad4e;
                          padding: 14px 20px; margin: 20px 40px; font-size: 14px;
                          color: #664d03; }}
            .hyp {{ background: #eef6fc; border-left: 4px solid #4a90e2;
                     padding: 14px 20px; margin: 0 40px 0 40px; font-size: 14px;
                     color: #214162; }}
            main {{ padding: 0 40px 40px 40px; }}
            section.chart {{ background: white; margin: 20px 0;
                              box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 14px 18px; }}
            section.chart h2 {{ font-size: 17px; margin: 4px 0 4px 0; color: #333; }}
            section.chart p.sub {{ font-size: 13px; color: #666; margin: 0 0 8px 0; }}
            table.watch {{ width: 100%; border-collapse: collapse; background: white;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.08); font-size: 12px; }}
            table.watch th, table.watch td {{ padding: 7px 10px; text-align: left;
                                                  border-bottom: 1px solid #eee; }}
            table.watch th {{ background: #f7f7fb; font-weight: 600; }}
            table.watch td:nth-child(n+5) {{ text-align: right;
                                              font-variant-numeric: tabular-nums; }}
            footer {{ padding: 20px 40px 40px 40px; font-size: 12px; color: #777; }}
            footer ul {{ margin: 8px 0 0 0; padding-left: 20px; }}
            footer li {{ margin: 4px 0; }}
            h2.section-title {{ margin-top: 28px; font-size: 18px; color: #333; }}
          </style>
        </head>
        <body>
          <header>
            <h1>S&amp;P 600 Refi-Wall Tracker</h1>
            <div class="sub">When does the watchlist's debt come due? &middot;
              {n_cov} issuers with SEC XBRL maturity disclosures &middot; built {AS_OF}</div>
          </header>

          <div class="chip-row">
            <div class="chip"><div class="label">Disclosed maturities</div>
              <div class="value">${total_disclosed:.0f}B</div>
              <div class="delta">across {n_cov} top-decile issuers</div></div>
            <div class="chip"><div class="label">Due within 2 years</div>
              <div class="value">${due_2y_total:.0f}B</div>
              <div class="delta">{pct_2y_agg:.1f}% of total disclosed</div></div>
            <div class="chip"><div class="label">Due within 5 years</div>
              <div class="value">${due_5y_total:.0f}B</div>
              <div class="delta">{due_5y_total/total_disclosed*100:.1f}% of total disclosed</div></div>
            <div class="chip"><div class="label">Median issuer 2y exposure</div>
              <div class="value">{median_pct_2y:.0f}%</div>
              <div class="delta">half the cohort has more than this share due in 24 months</div></div>
          </div>

          <div class="hyp">
            <strong>The refi-wall test:</strong> 1) Aggregate maturity disclosure for the
            high-debt cohort. 2) Identify firms where the next-2-year wall exceeds
            annual FCF — they cannot self-fund and must roll into a much higher-rate
            market. 3) Watch for downgrades, covenant trips, or distressed exchanges
            in those names.
          </div>

          <div class="warning">
            <strong>SEC XBRL coverage caveats.</strong> Source =
            <code>us-gaap:LongTermDebtMaturitiesRepaymentsOfPrincipal*</code> tags from
            each company's latest 10-K, fetched via SEC's free Company Facts API.
            Coverage = {n_cov}/47 watchlist names. Misses are mostly mortgage-REITs
            and recent spinoffs that don't tag the standard table. The disclosed total
            does not always match EODHD <code>totalDebt</code> — the maturity table
            reports principal-only, excludes discounts/premiums, capital leases, and
            sometimes revolver balances.
          </div>

          <main>
            <h2 class="section-title">Top issuers by 2-year refi exposure</h2>
            <p style="font-size: 13px; color: #666;">
              Sorted by % of disclosed debt due in next 24 months.
            </p>
            {table_html}

            {''.join(body_parts)}
          </main>

          <footer>
            <strong>Method:</strong> SEC's free
            <code>https://data.sec.gov/api/xbrl/companyfacts/CIK&lt;CIK&gt;.json</code>
            endpoint exposes every us-gaap fact a company has tagged in any filing.
            We pull the standard maturity-of-long-term-debt tags from each company's
            most recent 10-K and align them to the balance-sheet date. No HTML
            scraping; no paid data sources.
            <ul>
              <li><strong>y1</strong> = next-twelve-months from balance-sheet date</li>
              <li><strong>y2..y5</strong> = subsequent fiscal years</li>
              <li><strong>yGT5</strong> = "thereafter" bucket from the table</li>
            </ul>
            <strong>Known gaps:</strong>
            <ul>
              <li>11/47 watchlist names don't expose XBRL maturity tags (mostly
                  mortgage-REITs, securitized-debt structures, recent spinoffs).
                  For those, 10-K HTML parsing is needed.</li>
              <li>Maturity-table principal totals exclude discounts, premiums,
                  fair-value adjustments, capital leases, and operating leases.
                  Don't expect them to tie to EODHD <code>totalDebt</code> exactly.</li>
              <li>This is a snapshot; the maturity schedule moves as companies refi.
                  Re-run <code>scripts/fetch_sec_maturities.py --force</code> to refresh.</li>
            </ul>
          </footer>
        </body>
        </html>
    """)
    out_html.write_text(page)
    print(f"  -> {out_html}")


def main() -> int:
    data = load()
    out = DASH / "refi_wall.html"
    print("building refi-wall dashboard")
    print(f"  issuers with maturity data: {len(data['summary'])}")
    render(data, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
