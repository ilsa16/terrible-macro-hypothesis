"""Bottom-up debt-concentration & stress dashboard.

Tests the hypothesis: small-cap firms that levered up during 2018-21 low rates
are now squeezed by 2x interest cost. Looks at top-decile S&P 600 debtors and
shows their 5-year debt / cash / interest / coverage / FCF trajectories.

Reads:
  data/issuer/credit_panel_annual.csv
  data/issuer/credit_meta.csv
  data/issuer/top_debtors_watchlist.csv
  data/issuer/top_debtors_watchlist_no_re.csv
  data/issuer/concentration_summary.csv

Writes:
  dashboard/credit.html

Usage:
    python3.11 scripts/build_credit_dashboard.py
"""
from __future__ import annotations

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


def load() -> dict:
    panel = pd.read_csv(ISSUER / "credit_panel_annual.csv")
    panel["period_end"] = pd.to_datetime(panel["period_end"])
    meta = pd.read_csv(ISSUER / "credit_meta.csv")
    panel = panel.merge(meta[["ticker", "name", "sector", "industry"]],
                        on="ticker", how="left")
    watch = pd.read_csv(ISSUER / "top_debtors_watchlist.csv")
    watch_nore = pd.read_csv(ISSUER / "top_debtors_watchlist_no_re.csv")
    conc = pd.read_csv(ISSUER / "concentration_summary.csv")
    return {"panel": panel, "meta": meta, "watch": watch,
            "watch_nore": watch_nore, "conc": conc}


def chart_concentration(conc: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[f"Top {p}%" for p in conc["pct"]],
        y=conc["share"],
        text=[f"{s:.1f}%<br>${b:.0f}B<br>n={n}" for s, b, n in
              zip(conc["share"], conc["debt_usd_b"], conc["n"])],
        textposition="outside",
        marker_color=["#b30000", "#e34a33", "#fc8d59", "#fdbb84",
                       "#fdd49e", "#bdbdbd"],
        hovertemplate="%{x}<br>%{y:.1f}% of total debt<br>$%{text}<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_white", height=380, showlegend=False,
        title="S&P 600 non-financial debt concentration (cumulative %)",
        yaxis=dict(title="Cumulative share of total debt (%)", range=[0, 110]),
        margin=dict(t=60, b=40, l=60, r=20),
    )
    return fig


def chart_aggregate_lines(panel: pd.DataFrame, top_tickers: set[str],
                           label_top: str, label_rest: str) -> go.Figure:
    panel = panel.dropna(subset=["fiscal_year"])
    panel = panel[panel["fiscal_year"].between(2018, 2025)]
    g_top = panel[panel["ticker"].isin(top_tickers)].groupby("fiscal_year")[[
        "total_debt", "interest_expense", "ebitda", "fcf", "cash_and_equivalents"
    ]].sum(min_count=1) / 1e9
    g_rest = panel[~panel["ticker"].isin(top_tickers)].groupby("fiscal_year")[[
        "total_debt", "interest_expense", "ebitda", "fcf", "cash_and_equivalents"
    ]].sum(min_count=1) / 1e9

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("Total Debt (USD B)", "Interest Expense (USD B)",
                         "EBITDA (USD B)", "Free Cash Flow (USD B)"),
        vertical_spacing=0.13, horizontal_spacing=0.10,
    )

    def add(metric, row, col):
        fig.add_trace(go.Scatter(
            x=g_top.index, y=g_top[metric], mode="lines+markers",
            name=label_top, legendgroup="top", showlegend=(row == 1 and col == 1),
            line=dict(color="#d62728", width=3),
            hovertemplate=f"{label_top} %{{x}}<br>$%{{y:.1f}}B<extra></extra>",
        ), row=row, col=col)
        fig.add_trace(go.Scatter(
            x=g_rest.index, y=g_rest[metric], mode="lines+markers",
            name=label_rest, legendgroup="rest", showlegend=(row == 1 and col == 1),
            line=dict(color="#999", width=2, dash="dot"),
            hovertemplate=f"{label_rest} %{{x}}<br>$%{{y:.1f}}B<extra></extra>",
        ), row=row, col=col)

    add("total_debt", 1, 1)
    add("interest_expense", 1, 2)
    add("ebitda", 2, 1)
    add("fcf", 2, 2)

    fig.update_layout(
        template="plotly_white", height=600,
        title="Top-decile debtors vs everyone else: 2018–2025 trends",
        margin=dict(t=80, b=40, l=60, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
    )
    return fig


def chart_interest_growth_distribution(watch: pd.DataFrame) -> go.Figure:
    d = watch.dropna(subset=["interest_5y_pct"]).sort_values("interest_5y_pct")
    colors = ["#d62728" if x > 100 else "#fc8d59" if x > 50 else "#1a9850"
              for x in d["interest_5y_pct"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=d["interest_5y_pct"], y=d["ticker"], orientation="h",
        marker_color=colors,
        text=[f"{v:+.0f}%" for v in d["interest_5y_pct"]],
        textposition="outside",
        hovertemplate="%{y}<br>Interest expense FY2020→latest: %{x:+.0f}%<extra></extra>",
    ))
    fig.add_vline(x=0, line_color="black", line_width=1)
    fig.update_layout(
        template="plotly_white", height=max(400, 22 * len(d)),
        title="Interest-expense growth FY2020 → FY2025, top decile of debtors",
        xaxis=dict(title="% change in interest expense"),
        margin=dict(t=60, b=40, l=80, r=80),
        showlegend=False,
    )
    return fig


def chart_stress_scatter(watch: pd.DataFrame) -> go.Figure:
    d = watch.copy()
    # Cap leverage at 15x for plot, mark off-scale ones
    d["nde_capped"] = d["net_debt_to_ebitda"].clip(upper=15)
    d["cov_capped"] = d["interest_coverage_ebit"].clip(lower=-3, upper=10)
    d["debt_b"] = d["total_debt"] / 1e9
    d["bubble"] = d["debt_b"].clip(lower=1) ** 0.6 * 8

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=d["cov_capped"], y=d["nde_capped"],
        mode="markers+text",
        marker=dict(
            size=d["bubble"],
            color=d["stress_score"], colorscale="RdYlGn_r",
            cmin=20, cmax=90, showscale=True,
            colorbar=dict(title="Stress score"),
            line=dict(width=1, color="white"),
        ),
        text=d["ticker"], textposition="top center", textfont=dict(size=9),
        customdata=d[["name", "debt_b", "stress_score", "fcf_to_debt"]].values,
        hovertemplate=("<b>%{text}</b> — %{customdata[0]}<br>"
                        "Debt: $%{customdata[1]:.1f}B<br>"
                        "Interest cov (EBIT): %{x:.2f}x<br>"
                        "Net debt / EBITDA: %{y:.1f}x<br>"
                        "FCF / debt: %{customdata[3]:.1%}<br>"
                        "Stress score: %{customdata[2]:.0f}<extra></extra>"),
    ))
    fig.add_hline(y=4, line_color="orange", line_dash="dash",
                   annotation_text="ND/EBITDA = 4x", annotation_position="right")
    fig.add_vline(x=2, line_color="orange", line_dash="dash",
                   annotation_text="cov = 2x", annotation_position="top")
    fig.update_layout(
        template="plotly_white", height=560,
        title="Top-decile debtors: leverage vs interest coverage (bubble = total debt)",
        xaxis=dict(title="EBIT / interest expense (x), capped at [-3, 10]"),
        yaxis=dict(title="Net debt / EBITDA (x), capped at 15x", range=[-1, 16]),
        margin=dict(t=60, b=40, l=60, r=20),
        showlegend=False,
    )
    return fig


def chart_per_company_small_multiples(panel: pd.DataFrame, watch: pd.DataFrame,
                                        n_top: int = 12) -> go.Figure:
    """Top-N by stress score: per-company debt + interest dual-axis line plot."""
    top = watch.nlargest(n_top, "stress_score")["ticker"].tolist()
    n_cols = 3
    n_rows = (len(top) + n_cols - 1) // n_cols
    titles = []
    for tk in top:
        row = watch[watch["ticker"] == tk].iloc[0]
        nm = row["name"][:28] if pd.notna(row["name"]) else tk
        titles.append(f"<b>{tk}</b> — {nm}")

    fig = make_subplots(
        rows=n_rows, cols=n_cols, subplot_titles=titles,
        vertical_spacing=0.10, horizontal_spacing=0.08,
        specs=[[{"secondary_y": True}] * n_cols for _ in range(n_rows)],
    )
    for i, tk in enumerate(top):
        r, c = i // n_cols + 1, i % n_cols + 1
        sub = panel[panel["ticker"] == tk].sort_values("fiscal_year")
        sub = sub[sub["fiscal_year"].between(2018, 2025)]
        fig.add_trace(go.Scatter(
            x=sub["fiscal_year"], y=sub["total_debt"] / 1e6,
            mode="lines+markers", line=dict(color="#1f77b4", width=2.5),
            name="Debt ($M)", legendgroup="debt", showlegend=(i == 0),
            hovertemplate=f"{tk} %{{x}}<br>Debt $%{{y:.0f}}M<extra></extra>",
        ), row=r, col=c, secondary_y=False)
        fig.add_trace(go.Scatter(
            x=sub["fiscal_year"], y=sub["interest_expense"] / 1e6,
            mode="lines+markers", line=dict(color="#d62728", width=2, dash="dash"),
            name="Interest ($M)", legendgroup="ie", showlegend=(i == 0),
            hovertemplate=f"{tk} %{{x}}<br>Interest $%{{y:.0f}}M<extra></extra>",
        ), row=r, col=c, secondary_y=True)

    fig.update_layout(
        template="plotly_white", height=max(300, 220 * n_rows),
        title=f"Top {n_top} most-stressed names: 2018–2025 debt and interest trajectory",
        margin=dict(t=80, b=40, l=40, r=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="right", x=1),
    )
    fig.update_xaxes(tickfont=dict(size=10))
    fig.update_yaxes(tickfont=dict(size=9))
    return fig


def chart_sector_concentration(panel: pd.DataFrame, watch: pd.DataFrame) -> go.Figure:
    latest = watch.copy()
    sector_totals = latest.groupby("sector").agg(
        debt=("total_debt", "sum"),
        n=("ticker", "count"),
        median_stress=("stress_score", "median"),
    ).sort_values("debt", ascending=True)
    sector_totals["debt_b"] = sector_totals["debt"] / 1e9

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=sector_totals.index, x=sector_totals["debt_b"], orientation="h",
        marker=dict(
            color=sector_totals["median_stress"], colorscale="RdYlGn_r",
            cmin=20, cmax=90,
            colorbar=dict(title="Median<br>stress<br>score"),
        ),
        text=[f"${v:.0f}B (n={n})" for v, n in
              zip(sector_totals["debt_b"], sector_totals["n"])],
        textposition="outside",
        hovertemplate="%{y}<br>$%{x:.1f}B<br>n=%{text}<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_white", height=max(320, 36 * len(sector_totals)),
        title="Top-decile debt by GICS sector (color = median stress score)",
        xaxis=dict(title="Total debt (USD B)"),
        margin=dict(t=60, b=40, l=160, r=80),
    )
    return fig


def render(data: dict, out_html: Path) -> None:
    panel = data["panel"]
    watch = data["watch"]
    watch_nore = data["watch_nore"]
    conc = data["conc"]

    top_tickers = set(watch["ticker"])
    n_top = len(top_tickers)
    n_total = panel["ticker"].nunique()

    figs = [
        ("Debt concentration",
         chart_concentration(conc),
         "How much of S&P 600 non-financial debt sits in the top X%."),

        ("Top decile vs rest, 2018–2025",
         chart_aggregate_lines(panel, top_tickers,
                                label_top=f"Top {n_top} (top 10%)",
                                label_rest=f"Other {n_total - n_top}"),
         "The top-10% debtor cohort drives almost the entire interest-expense increase."),

        ("Interest-expense growth FY2020 → FY2025",
         chart_interest_growth_distribution(watch),
         "Per-issuer % change in annual interest cost from FY2020 to latest reported FY."),

        ("Leverage vs coverage scatter",
         chart_stress_scatter(watch),
         "Bubble size = total debt. Top-right = comfortably servicing; bottom-right = high leverage but covered; bottom-left = the danger quadrant."),

        ("Top-decile debt by sector",
         chart_sector_concentration(panel, watch),
         "Where the concentrated debt sits."),

        ("Most-stressed names: 5-year trajectory",
         chart_per_company_small_multiples(panel, watch_nore, n_top=12),
         "Top 12 by stress score (REITs excluded since their leverage is structural). Blue = total debt; red = interest expense."),
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

    # Top-15 stress table (no-RE view, more useful)
    table = watch_nore.sort_values("stress_score", ascending=False).head(15).copy()
    table["debt_b"] = (table["total_debt"] / 1e9).round(1)
    table["int_m"] = (table["interest_expense"] / 1e6).round(0)
    table["int_5y"] = table["interest_5y_pct"].round(0)
    table["nde"] = table["net_debt_to_ebitda"].round(1)
    table["cov"] = table["interest_coverage_ebit"].round(2)
    table["fcf_d"] = (table["fcf_to_debt"] * 100).round(1)
    table["score"] = table["stress_score"].round(0)
    cols = {"ticker": "Ticker", "name": "Name", "sector": "Sector",
             "debt_b": "Debt $B", "nde": "ND/EBITDA",
             "cov": "EBIT cov", "fcf_d": "FCF/Debt %",
             "int_5y": "Δ Interest 5y %",
             "score": "Stress (0-100)"}
    table_html = (table[list(cols.keys())].rename(columns=cols)
                  .to_html(index=False, escape=False, classes="watch", border=0))

    # Concentration chip
    top10_share = float(conc[conc["pct"] == 10]["share"].iloc[0])
    top1_share = float(conc[conc["pct"] == 1]["share"].iloc[0])

    page = dedent(f"""\
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <title>S&amp;P 600 Credit Stress Tracker</title>
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
            main {{ padding: 0 40px 40px 40px; }}
            section.chart {{ background: white; margin: 20px 0;
                              box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 14px 18px; }}
            section.chart h2 {{ font-size: 17px; margin: 4px 0 4px 0; color: #333; }}
            section.chart p.sub {{ font-size: 13px; color: #666; margin: 0 0 8px 0; }}
            table.watch {{ width: 100%; border-collapse: collapse; background: white;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.08); font-size: 13px; }}
            table.watch th, table.watch td {{ padding: 8px 12px; text-align: left;
                                                 border-bottom: 1px solid #eee; }}
            table.watch th {{ background: #f7f7fb; font-weight: 600; }}
            table.watch td:nth-child(n+4) {{ text-align: right; font-variant-numeric: tabular-nums; }}
            footer {{ padding: 20px 40px 40px 40px; font-size: 12px; color: #777; }}
            footer ul {{ margin: 8px 0 0 0; padding-left: 20px; }}
            footer li {{ margin: 4px 0; }}
            h2.section-title {{ margin-top: 28px; font-size: 18px; color: #333; }}
            .hyp {{ background: #eef6fc; border-left: 4px solid #4a90e2;
                     padding: 14px 20px; margin: 0 40px 0 40px; font-size: 14px;
                     color: #214162; }}
          </style>
        </head>
        <body>
          <header>
            <h1>S&amp;P 600 Credit Stress Tracker</h1>
            <div class="sub">Bottom-up debt concentration &middot; {n_total} non-financial issuers
              &middot; top {n_top} watchlist &middot; built {AS_OF} from EODHD fundamentals</div>
          </header>

          <div class="chip-row">
            <div class="chip"><div class="label">Top 10% share</div>
              <div class="value">{top10_share:.1f}%</div>
              <div class="delta">${conc[conc['pct']==10]['debt_usd_b'].iloc[0]:,.0f}B of debt held by {n_top} issuers</div></div>
            <div class="chip"><div class="label">Top 1% share</div>
              <div class="value">{top1_share:.1f}%</div>
              <div class="delta">${conc[conc['pct']==1]['debt_usd_b'].iloc[0]:,.0f}B held by 5 issuers</div></div>
            <div class="chip"><div class="label">Watchlist debt growth FY2020 → FY2025</div>
              <div class="value">{watch['debt_5y_pct'].median():.0f}%<small> median</small></div>
              <div class="delta">interest expense median {watch['interest_5y_pct'].median():.0f}%</div></div>
            <div class="chip"><div class="label">Median ND / EBITDA</div>
              <div class="value">{watch['net_debt_to_ebitda'].median():.1f}x</div>
              <div class="delta">EBIT coverage median {watch['interest_coverage_ebit'].median():.1f}x</div></div>
          </div>

          <div class="hyp">
            <strong>Hypothesis:</strong> Small-caps that levered up during the 2018–21
            low-rate window are now squeezed by 2x higher interest cost, with EBITDA
            growth that hasn't kept pace. The top-decile cohort drives the
            concentration of risk in the index — track it through the cycle.
          </div>

          <div class="warning">
            <strong>Bottom-up lens, NOT a macro aggregate.</strong> 105 Financial
            Services issuers (mostly regional banks) excluded — their interest expense
            is deposit interest, not debt interest. See
            <code>dashboard/index.html</code> for the macro view (FRED Z.1 / ICE BofA / Moody's).
          </div>

          <main>
            <h2 class="section-title">Top 15 stressed names (REITs excluded)</h2>
            <p style="font-size: 13px; color: #666;">
              Ranked by composite stress score. Score = mean of: interest-coverage, leverage
              (ND/EBITDA), FCF coverage of debt, and 5y interest-expense growth. 0 = healthy, 100 = severe.
            </p>
            {table_html}

            {''.join(body_parts)}
          </main>

          <footer>
            <strong>Data:</strong> EODHD fundamentals API (annual). Field mapping documented
            in <code>scripts/build_credit_panel.py</code>. Universe = current S&amp;P 600
            constituents reporting since FY2019.
            <br><br>
            <strong>Stress-score formula:</strong>
            <ul>
              <li><strong>Coverage</strong> (0–100): 100 − clamp(EBIT/interest, [0,10]) × 10</li>
              <li><strong>Leverage</strong> (0–100): clamp(net_debt/EBITDA, [0,8]) × 12.5</li>
              <li><strong>FCF</strong> (0–100): 20 − fcf_to_debt × 200, clamped — negative FCF = 100</li>
              <li><strong>Trend</strong> (0–100): clamp(interest growth FY20→latest / 1.5%, [0,100])</li>
            </ul>
            <strong>Known gaps:</strong>
            <ul>
              <li><strong>No debt-maturity schedule</strong> in EODHD fundamentals — for
                  refi-wall analysis you'd need 10-K parsing (notes-to-financials section
                  "Long-term debt") or a commercial source (Bloomberg DDIS, S&amp;P CIQ
                  capital structure, Moody's CreditView).</li>
              <li>EODHD doesn't expose credit ratings, CDS spreads, or bond-level data
                  (offered separately under marketplace endpoints, not in the standard
                  fundamentals payload).</li>
              <li>FY2025 reporters: 463/479 — calendar-year filers complete; non-calendar
                  fiscal years (e.g. KSS Jan-end) may show as FY2026 because their
                  12-month period ended in 2026.</li>
              <li>Sanity clamp: 51 annual rows had implied rate &gt; 50% (data errors)
                  — those interest_expense values nulled.</li>
              <li>Survivorship bias: fallen-out names (bankruptcies, M&amp;A, index
                  reshuffles) are absent.</li>
            </ul>
          </footer>
        </body>
        </html>
    """)
    out_html.write_text(page)
    print(f"  -> {out_html}")


def main() -> int:
    data = load()
    out = DASH / "credit.html"
    print(f"building credit dashboard")
    print(f"  panel: {len(data['panel'])} rows, {data['panel']['ticker'].nunique()} tickers")
    print(f"  watchlist: {len(data['watch'])} names (top 10%)")
    render(data, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
