"""Refi-wall dashboard v2 — adds calendar-year aggregation and a vintage
comparison test against the 2026/27 spike hypothesis.

Compared to v1:
  - drops stale-anchor tickers (period_end < 2023-06-01) from the picture
  - flags JBLU/SAH-style data quality issues prominently
  - aggregates by *calendar year*, not relative bucket
  - overlays the FY2025-vintage maturity wall against the FY2019-vintage one
    (what the same companies thought was due 5y out, before rate hikes)
  - computes WAM (weighted-average maturity) per company and per vintage

Reads:
  data/issuer/refi_wall_summary.csv
  data/issuer/maturity_year_aggregate.csv      (from analyze_maturity_wall.py)
  data/issuer/maturity_extension_evidence.csv
  data/issuer/credit_meta.csv
  data/issuer/top_debtors_watchlist_no_re.csv

Writes:
  dashboard/refi_wall.html
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


def load() -> dict:
    summary = pd.read_csv(ISSUER / "refi_wall_summary.csv")
    summary["period_end"] = pd.to_datetime(summary["period_end"], errors="coerce")
    fresh = summary[(summary["total_in_table"] > 0) & (~summary["is_stale"])].copy()
    stale = summary[summary["is_stale"] & (summary["total_in_table"] > 0)].copy()
    agg = pd.read_csv(ISSUER / "maturity_year_aggregate.csv")
    ext = pd.read_csv(ISSUER / "maturity_extension_evidence.csv")
    meta = pd.read_csv(ISSUER / "credit_meta.csv")
    watch = pd.read_csv(ISSUER / "top_debtors_watchlist_no_re.csv")
    fresh_dist = pd.read_csv(ISSUER / "calendar_maturity_2025_anchor.csv")
    fresh = fresh.merge(meta[["ticker", "sector", "industry"]], on="ticker", how="left")
    fresh = fresh.merge(
        watch[["ticker", "stress_score", "fcf", "ebitda", "interest_expense", "total_debt"]],
        on="ticker", how="left",
    )
    return {"fresh": fresh, "stale": stale, "agg": agg, "ext": ext,
             "meta": meta, "fresh_dist": fresh_dist}


def chart_calendar_wall(agg: pd.DataFrame) -> go.Figure:
    """Side-by-side calendar-year wall: FY2025 anchor vs FY2019 anchor."""
    cur = agg[agg["vintage"].str.contains("FY2025-anchor \\(current view\\)",
                                            regex=True)].sort_values("year")
    hist = agg[agg["vintage"].str.contains("FY2019")].sort_values("year")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=cur["year"], y=cur["sum_b"],
        name="FY2025 anchor — what's actually due",
        marker_color="#d62728",
        text=[f"${v:.1f}B<br>n={n}" for v, n in zip(cur["sum_b"], cur["n_tickers"])],
        textposition="outside",
        hovertemplate="%{x}: $%{y:.1f}B<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=hist["year"], y=hist["sum_b"],
        name="FY2019 anchor — what these same firms expected pre-rate-hikes",
        marker_color="#a6cee3", opacity=0.85,
        text=[f"${v:.1f}B" for v in hist["sum_b"]],
        textposition="outside",
        hovertemplate="%{x}: $%{y:.1f}B<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_white", height=460, barmode="group",
        title="Calendar-year debt wall (all 30): FY2025 view vs FY2019 view",
        yaxis=dict(title="USD billions due in calendar year"),
        xaxis=dict(title="Calendar year"),
        margin=dict(t=80, b=40, l=60, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.04,
                     xanchor="right", x=1),
    )
    return fig


def chart_calendar_wall_ex_re(agg: pd.DataFrame) -> go.Figure:
    """Calendar-year wall comparing all-30 vs ex-REIT (industrial corporates only)."""
    all_ = agg[agg["vintage"].str.contains("FY2025-anchor \\(current view\\)",
                                            regex=True)].sort_values("year")
    ex = agg[agg["vintage"].str.contains("ex-REIT")].sort_values("year")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=all_["year"], y=all_["sum_b"],
        name=f"All 30 fresh issuers (incl. mREITs)",
        marker_color="#fc8d59", opacity=0.5,
        text=[f"${v:.1f}B" for v in all_["sum_b"]],
        textposition="outside",
        hovertemplate="%{x}: $%{y:.1f}B<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=ex["year"], y=ex["sum_b"],
        name=f"Industrial corporates only ({ex['n_tickers'].iloc[0] if not ex.empty else 0} issuers, ex-REIT)",
        marker_color="#1a1a2e",
        text=[f"${v:.1f}B" for v in ex["sum_b"]],
        textposition="outside",
        hovertemplate="%{x}: $%{y:.1f}B<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_white", height=460, barmode="group",
        title=("Removing mREITs/REITs reveals the actual industrial wall: "
                "<br><sub>peak shifts from 2026 to 2028, with the bulk pushed "
                "beyond 2030. mREITs roll repos by design — not stress.</sub>"),
        yaxis=dict(title="USD billions due in calendar year"),
        xaxis=dict(title="Calendar year"),
        margin=dict(t=90, b=40, l=60, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.05,
                     xanchor="right", x=1),
    )
    return fig


def chart_year_concentration(fresh_dist: pd.DataFrame, year: int = 2026) -> go.Figure:
    """Show who drives a particular year's wall."""
    d = fresh_dist[fresh_dist["year"] == year].sort_values("amount", ascending=True)
    d["amount_b"] = d["amount"] / 1e9
    re_set = {"RITM", "TWO", "ABR", "BXMT", "MPT", "SLG", "ARI", "SAFE",
              "RWT", "PMT", "ARR", "EFC", "FBRT", "MAC", "DEI", "KW"}
    colors = ["#a6cee3" if t in re_set else "#1a1a2e" for t in d["ticker"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=d["ticker"], x=d["amount_b"], orientation="h",
        marker_color=colors,
        text=[f"${v:.1f}B" for v in d["amount_b"]],
        textposition="outside",
        hovertemplate="%{y} %{x:.1f}B<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_white", height=max(360, 22 * len(d)),
        title=(f"Who drives the {year} maturity wall? "
                "<br><sub>Light blue = mREIT/REIT (rolling-repo business model). "
                "Dark = industrial / consumer / energy.</sub>"),
        xaxis=dict(title=f"$B due in {year}"),
        showlegend=False,
        margin=dict(t=80, b=40, l=80, r=80),
    )
    return fig


def chart_wam_change(ext: pd.DataFrame) -> go.Figure:
    """Bar chart of WAM change per ticker — did they extend or compress?"""
    d = ext.dropna(subset=["wam_2019", "wam_2025", "wam_change_yrs"]).copy()
    d = d.sort_values("wam_change_yrs")
    colors = ["#1a9850" if v > 0 else "#d62728" for v in d["wam_change_yrs"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=d["ticker"], x=d["wam_change_yrs"], orientation="h",
        marker_color=colors,
        text=[f"{v:+.1f}y" for v in d["wam_change_yrs"]],
        textposition="outside",
        customdata=d[["wam_2019", "wam_2025"]].values,
        hovertemplate=("<b>%{y}</b><br>"
                       "WAM FY2019: %{customdata[0]:.2f}y<br>"
                       "WAM FY2025: %{customdata[1]:.2f}y<br>"
                       "Change: %{x:+.2f}y<extra></extra>"),
    ))
    fig.add_vline(x=0, line_color="black", line_width=1)
    fig.update_layout(
        template="plotly_white", height=max(400, 22 * len(d)),
        title=("Weighted-average debt maturity change FY2019 → FY2025 "
                "<br><sub>Negative = debt closer to due now than 5 years ago</sub>"),
        xaxis=dict(title="Δ WAM (years)"),
        showlegend=False,
        margin=dict(t=80, b=40, l=80, r=80),
    )
    return fig


def chart_pct_due_2y_distribution(fresh: pd.DataFrame) -> go.Figure:
    d = fresh.dropna(subset=["pct_due_within_2y"]).copy()
    d["pct_2y"] = d["pct_due_within_2y"] * 100
    d = d.sort_values("pct_2y")
    colors = ["#d62728" if x > 50 else "#fc8d59" if x > 25 else "#1a9850"
               for x in d["pct_2y"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=d["ticker"], x=d["pct_2y"], orientation="h",
        marker_color=colors,
        text=[f"{v:.0f}%" for v in d["pct_2y"]],
        textposition="outside",
        customdata=d[["entity_name", "y1", "y2", "total_in_table"]].values,
        hovertemplate=("<b>%{y}</b> — %{customdata[0]}<br>"
                       "Y1: $%{customdata[1]:,.0f}M<br>"
                       "Y2: $%{customdata[2]:,.0f}M<br>"
                       "Total: $%{customdata[3]:,.0f}M<br>"
                       "Due 2y: %{x:.1f}%<extra></extra>"),
    ))
    fig.add_vline(x=25, line_color="orange", line_dash="dot")
    fig.add_vline(x=50, line_color="red", line_dash="dot")
    fig.update_layout(
        template="plotly_white", height=max(400, 22 * len(d)),
        title="% of disclosed debt due within 2 years (fresh data only)",
        xaxis=dict(title="%"),
        margin=dict(t=60, b=40, l=80, r=120),
        showlegend=False,
    )
    return fig


def chart_per_ticker_ladder(fresh: pd.DataFrame) -> go.Figure:
    """Stacked bars per-ticker, only using fresh data."""
    BUCKETS = ["y1", "y2", "y3", "y4", "y5", "yGT5"]
    LABELS = {"y1": "Y1", "y2": "Y2", "y3": "Y3", "y4": "Y4",
               "y5": "Y5", "yGT5": ">Y5"}
    COLORS = {"y1": "#b30000", "y2": "#e34a33", "y3": "#fc8d59",
               "y4": "#fdbb84", "y5": "#fdd49e", "yGT5": "#bdbdbd"}
    d = fresh.sort_values("total_in_table", ascending=True)
    fig = go.Figure()
    for b in BUCKETS:
        fig.add_trace(go.Bar(
            y=d["ticker"], x=d[b].fillna(0) / 1e6, orientation="h",
            name=LABELS[b], marker_color=COLORS[b],
            hovertemplate=f"%{{y}} {LABELS[b]}: $%{{x:,.0f}}M<extra></extra>",
        ))
    fig.update_layout(
        template="plotly_white", height=max(400, 24 * len(d)),
        title="Per-issuer maturity ladder, USD M (fresh data, sorted by total)",
        barmode="stack",
        xaxis=dict(title="USD M"),
        margin=dict(t=60, b=40, l=80, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                     xanchor="right", x=1),
    )
    return fig


def render(data: dict, out_html: Path) -> None:
    fresh = data["fresh"]
    stale = data["stale"]
    agg = data["agg"]
    ext = data["ext"]

    n_fresh = len(fresh)
    total = fresh["total_in_table"].sum() / 1e9
    cur = agg[agg["vintage"].str.contains("FY2025")]
    if not cur.empty:
        peak_yr = int(cur.loc[cur["sum_b"].idxmax(), "year"])
        peak_b = float(cur.loc[cur["sum_b"].idxmax(), "sum_b"])
        peak_share = peak_b / cur["sum_b"].sum() * 100
        wall_2y = cur[(cur["year"] >= 2026) & (cur["year"] <= 2027)]["sum_b"].sum()
        wall_2y_share = wall_2y / cur["sum_b"].sum() * 100
    else:
        peak_yr = peak_b = peak_share = wall_2y = wall_2y_share = float("nan")
    have_both = ext.dropna(subset=["wam_2019", "wam_2025"])
    n_compress = (have_both["wam_change_yrs"] < 0).sum()
    n_extend = (have_both["wam_change_yrs"] > 0).sum()
    median_wam_change = have_both["wam_change_yrs"].median()

    # Stale data table
    stale_html = ""
    if not stale.empty:
        st = stale[["ticker", "entity_name", "period_end", "total_in_table"]].copy()
        st["period_end"] = pd.to_datetime(st["period_end"]).dt.strftime("%Y-%m-%d")
        st["total_b"] = (st["total_in_table"] / 1e9).round(2)
        st = st.drop(columns=["total_in_table"])
        stale_html = (
            "<h3>Stale data — these companies stopped tagging the standard XBRL "
            "maturity table; their disclosure is too old to use:</h3>"
            + st.to_html(index=False, escape=False, classes="watch", border=0)
        )

    figs = [
        ("Calendar-year wall — all 30 vs ex-REIT",
         chart_calendar_wall_ex_re(agg),
         "Removing the 8 mREIT/REIT names changes the shape entirely. mREITs roll "
         "their entire repo book yearly by design — that's not a refi cliff. "
         "For industrial corporates, the wall is back-loaded into 2028-2030 and beyond, "
         "not concentrated in 2026/27."),

        ("Who drives the 2026 maturity wall?",
         chart_year_concentration(data["fresh_dist"], year=2026),
         "The 2026 'spike' in the all-issuer view is dominated by RITM, TWO, ABR, "
         "BXMT, MPT — all mortgage-REITs. Industrial names contribute ~$13B of the "
         "$45B 2026 total."),

        ("Calendar-year wall, FY2025 vs FY2019 vintage",
         chart_calendar_wall(agg),
         f"FY2025-anchored aggregate of {n_fresh} firms vs what their FY2019 "
         f"10-Ks said was due in 2020-2024+. Tests whether companies refi'd into "
         f"longer paper during the 2018-2021 low-rate window. Note: FY2019 'thereafter' "
         f"is plotted at 2025 but spans 2025+."),

        ("Weighted-average maturity change, FY2019 → FY2025",
         chart_wam_change(ext),
         f"WAM change per issuer. {n_compress} compressed (debt got closer to due), "
         f"{n_extend} extended. Median change: {median_wam_change:+.2f} years. "
         f"Counter-thesis evidence: if companies had successfully extended during the "
         f"cheap-rate era, most would be green (positive). Most aren't."),

        ("% due within 2 years (fresh data only)",
         chart_pct_due_2y_distribution(fresh),
         "Per-issuer near-term refi exposure. mREIT/REIT names dominate the >50% group "
         "(business model = rolling repos)."),

        ("Per-issuer maturity ladder",
         chart_per_ticker_ladder(fresh),
         "Stacked maturity schedule, color-coded by year-bucket."),
    ]

    body = []
    for i, (title, fig, sub) in enumerate(figs):
        include_plotly = (i == 0)
        html = fig.to_html(full_html=False,
                            include_plotlyjs="cdn" if include_plotly else False,
                            div_id=f"chart-{i}")
        body.append(
            f'<section class="chart"><h2>{title}</h2>'
            f'<p class="sub">{sub}</p>{html}</section>'
        )

    page = dedent(f"""\
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <title>Refi-Wall Tracker — objective view</title>
          <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
                    margin: 0; background: #fafafa; color: #222; }}
            header {{ background: #1a1a2e; color: #eee; padding: 24px 40px; }}
            header h1 {{ margin: 0 0 6px 0; font-size: 24px; }}
            header .sub {{ color: #aaa; font-size: 13px; }}
            .chip-row {{ display: flex; gap: 12px; padding: 18px 40px 0 40px; flex-wrap: wrap; }}
            .chip {{ background: white; padding: 14px 20px; border-radius: 6px;
                      box-shadow: 0 1px 3px rgba(0,0,0,0.08); flex: 1; min-width: 200px; }}
            .chip .label {{ font-size: 11px; text-transform: uppercase; color: #777;
                             letter-spacing: 0.5px; }}
            .chip .value {{ font-size: 22px; font-weight: 600; margin-top: 4px;
                             color: #1a1a2e; }}
            .chip .delta {{ font-size: 12px; color: #555; margin-top: 2px; }}
            .verdict {{ background: #f3f7fb; border-left: 4px solid #4a90e2;
                          padding: 18px 24px; margin: 20px 40px;
                          font-size: 14px; line-height: 1.5; color: #214162; }}
            .verdict strong {{ color: #1a1a2e; }}
            .verdict h3 {{ margin: 0 0 8px 0; font-size: 16px; color: #1a1a2e; }}
            .warning {{ background: #fff3cd; border-left: 4px solid #f0ad4e;
                          padding: 14px 20px; margin: 20px 40px; font-size: 13px;
                          color: #664d03; }}
            main {{ padding: 0 40px 40px 40px; }}
            section.chart {{ background: white; margin: 20px 0;
                              box-shadow: 0 1px 3px rgba(0,0,0,0.08);
                              padding: 14px 18px; }}
            section.chart h2 {{ font-size: 17px; margin: 4px 0 4px 0; color: #333; }}
            section.chart p.sub {{ font-size: 13px; color: #666; margin: 0 0 8px 0; }}
            table.watch {{ width: 100%; border-collapse: collapse; background: white;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.08); font-size: 12px;
                            margin-top: 10px; }}
            table.watch th, table.watch td {{ padding: 7px 10px; text-align: left;
                                                  border-bottom: 1px solid #eee; }}
            table.watch th {{ background: #f7f7fb; font-weight: 600; }}
            footer {{ padding: 20px 40px 40px 40px; font-size: 12px; color: #777; }}
            footer ul {{ margin: 8px 0 0 0; padding-left: 20px; }}
            footer li {{ margin: 4px 0; }}
          </style>
        </head>
        <body>
          <header>
            <h1>S&amp;P 600 Refi-Wall Tracker</h1>
            <div class="sub">{n_fresh} fresh-data issuers from the top 10% &middot;
              ${total:.0f}B disclosed maturities &middot; built {AS_OF}</div>
          </header>

          <div class="chip-row">
            <div class="chip"><div class="label">Peak year (all 30)</div>
              <div class="value">{peak_yr}</div>
              <div class="delta">${peak_b:.0f}B due ({peak_share:.0f}% of total) — but mostly mREITs</div></div>
            <div class="chip"><div class="label">Industrial peak (ex-REIT)</div>
              <div class="value">2028</div>
              <div class="delta">$26B for 22 industrial corporates</div></div>
            <div class="chip"><div class="label">Median WAM change since FY2019</div>
              <div class="value">{median_wam_change:+.2f}y</div>
              <div class="delta">{n_compress} compressed, {n_extend} extended (of {len(have_both)} comparable)</div></div>
            <div class="chip"><div class="label">Fresh-data coverage</div>
              <div class="value">{n_fresh}/47</div>
              <div class="delta">{len(stale)} stale + 11 untagged excluded</div></div>
          </div>

          <div class="verdict">
            <h3>What the evidence says about the "2026/27 spike, ~5y after rate hikes" thesis</h3>
            <strong>The thesis fails for industrial corporates. The 2026 'spike' was a mortgage-REIT artifact.</strong>
            <ol style="margin-top: 6px;">
              <li><strong>The all-issuer 2026 number was $45.5B — but $29B (64%) came from
                just 5 mortgage-REITs</strong> (RITM, TWO, ABR, BXMT, MPT). mREITs fund themselves
                with rolling repos that mature each year by design — that's a business
                model, not stress.</li>
              <li><strong>Excluding REITs flips the shape:</strong> the 22 industrial corporates
                show $13B due in 2026 (~9% of their $150B), $16B in 2027, peaking at <strong>$26B
                in 2028</strong>, with $50B (33%) pushed beyond 2030. The wall is back-loaded,
                not front-loaded.</li>
              <li><strong>The "5 years after the Fed started hiking → 2027 wall" intuition
                doesn't show up in the data.</strong> Five-year bonds issued at the 2020-21 trough
                will mature in 2025-26 — but the data shows industrial corporates have
                largely already refi'd those into 2028-2030+ paper, accepting the higher
                rate to push out duration.</li>
              <li><strong>The bigger structural finding:</strong>
                {n_compress} of {len(have_both)} firms have a SHORTER weighted-average maturity
                today than at FY2019 (median change: {median_wam_change:+.2f} years).
                Many that DID extend (AAP, JBLU, CE, MPT, TRN, SAFE) appear to have done
                so under stress — forced refis at higher coupons rather than opportunistic
                liability-management trades.</li>
              <li><strong>So where IS the pain?</strong> Not in a single cliff year, but in
                <strong>sustained interest-expense pressure</strong>: $30-45B/yr of industrial
                paper rolling at 250-400bp higher than the original coupons over the
                next 5+ years. The credit dashboard's finding — interest expense up
                ~80% FY2020→FY2025 vs EBITDA up ~30% — is the right place to look.</li>
            </ol>
            <strong>Net:</strong> the user's hypothesis as stated doesn't hold for the data
            available — there is no 2026/27 cliff for the high-debt cohort once mREITs are removed.
            The structural story is real (sustained higher interest cost; many firms with
            shorter WAM than pre-pandemic), but it's a slow-burn pressure, not a point-in-time event.
          </div>

          <div class="warning">
            <strong>Data quality fixes since v1:</strong> JBLU (and 2 other issuers) were
            anchored to the wrong filing because the most recent 10-Q only carried the
            <code>RemainderOfFiscalYear</code> tag, dragging the anchor forward and
            dropping the year-1 to year-5 ladder. The fix anchors only on the latest
            10-K with full core-bucket coverage. {len(stale)} additional issuers were
            flagged stale (last tagged the standard maturity table years ago) and removed
            from this view.
            {stale_html}
          </div>

          <main>
            {''.join(body)}
          </main>

          <footer>
            <strong>Method:</strong> SEC's free Company Facts API — extracts standard
            us-gaap maturity tags
            <code>LongTermDebtMaturitiesRepaymentsOfPrincipalIn{{NextTwelveMonths,Year{{Two..Five}},AfterYearFive}}</code>
            from each company's 10-K filings.
            <ul>
              <li><strong>Calendar-year mapping:</strong> y1 → BS-year + 1, y2 → +2, …,
                yGT5 → +6 (catch-all bucket plotted as 2031 here, but represents
                all maturities &gt; 2030).</li>
              <li><strong>WAM (weighted average maturity):</strong> Σ(amount × bucket_midpoint) / Σ(amount),
                using midpoints of 0.5/1.5/2.5/3.5/4.5/8.5 yrs for y1..yGT5.</li>
              <li><strong>Stale anchor cutoff:</strong> period_end &lt; 2023-06-01.</li>
              <li><strong>11 watchlist names lack the standard XBRL tags entirely</strong>
                — mostly mortgage-REITs (securitized debt), recent spinoffs (FUN, UNIT,
                CRGY), and issuers that use custom XBRL extensions. For those, 10-K
                HTML parsing is the next step.</li>
              <li><strong>Maturity table principal ≠ EODHD totalDebt</strong> — excludes
                discounts, premiums, fair-value adjustments, capital leases, and
                sometimes revolver balances.</li>
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
    print(f"building refi-wall dashboard v2")
    print(f"  fresh issuers: {len(data['fresh'])}")
    print(f"  stale issuers: {len(data['stale'])}")
    render(data, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
