"""Build the U.S. corporate debt monitoring dashboard.

Reads:
  data/fred/*.csv         - FRED series (nonfinancial corp debt, IG/BBB/HY yields, BBB OAS)
  data/manual/*.csv       - Manually-curated SIFMA, Moody's, US Courts, Fitch data

Writes:
  dashboard/index.html    - Standalone HTML dashboard (Plotly CDN)
  charts/*.png            - Optional PNG snapshots (if kaleido is installed)
  data/summary.csv        - One-row-per-metric summary table

The dashboard is deliberately self-contained: one HTML file with embedded
Plotly JS via CDN, readable offline-ish (needs CDN for first load).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from textwrap import dedent

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent.parent
FRED = ROOT / "data" / "fred"
MANUAL = ROOT / "data" / "manual"
OUT_HTML = ROOT / "dashboard" / "index.html"
OUT_SUMMARY = ROOT / "data" / "summary.csv"
CHARTS = ROOT / "charts"
CHARTS.mkdir(exist_ok=True)

AS_OF = "2026-04-23"

PLOTLY_COLORS = {
    "ig": "#1f77b4",
    "bbb": "#ff7f0e",
    "hy": "#d62728",
    "oas": "#9467bd",
    "debt": "#2ca02c",
    "bankruptcy": "#8c564b",
    "moodys": "#e377c2",
    "fitch": "#17becf",
    "sifma_ig": "#1f77b4",
    "sifma_hy": "#d62728",
}


# ---------- loaders ----------

def load_fred_series(series_id: str) -> pd.DataFrame:
    path = FRED / f"{series_id}_raw.csv"
    if not path.exists():
        return pd.DataFrame(columns=["date", "value"])
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns={"observation_date": "date", series_id.lower(): "value"})
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna().reset_index(drop=True)


def load_manual(name: str) -> pd.DataFrame:
    path = MANUAL / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


# ---------- derived metrics ----------

def pct_change(a: float, b: float) -> float:
    if b == 0 or pd.isna(a) or pd.isna(b):
        return float("nan")
    return (a / b - 1) * 100


def cagr(end: float, start: float, years: float) -> float:
    if start <= 0 or end <= 0 or years <= 0:
        return float("nan")
    return ((end / start) ** (1 / years) - 1) * 100


# ---------- chart builders ----------

def chart_debt_stock(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["value"] / 1000,  # $M -> $B
        mode="lines+markers", name="Nonfin. corp. debt",
        line=dict(color=PLOTLY_COLORS["debt"], width=2.5),
        hovertemplate="%{x|%Y-%m-%d}<br>$%{y:,.0f}B<extra></extra>",
    ))
    fig.update_layout(
        title="1. U.S. Nonfinancial Corporate Debt Stock since 2005 (FRED BCNSDODNS, quarterly, $B)",
        xaxis_title="Quarter",
        yaxis_title="Debt outstanding, $B",
        template="plotly_white", height=380, margin=dict(l=60, r=20, t=60, b=40),
    )
    return fig


def chart_yields_long(daaa: pd.DataFrame, dbaa: pd.DataFrame,
                       ig: pd.DataFrame, bbb: pd.DataFrame, hy: pd.DataFrame) -> go.Figure:
    """Long-history cost-of-debt: Moody's Aaa/Baa since 2005, with ICE IG/BBB/HY overlaid for recent 3yrs."""
    fig = go.Figure()
    # Long-history Moody's series
    for df, key, label in [
        (daaa, "ig", "Moody's Aaa Corp (DAAA, daily)"),
        (dbaa, "bbb", "Moody's Baa Corp (DBAA, daily)"),
    ]:
        if df.empty:
            continue
        m = df.set_index("date")["value"].resample("M").mean().dropna()
        fig.add_trace(go.Scatter(
            x=m.index, y=m.values, mode="lines", name=label,
            line=dict(color=PLOTLY_COLORS[key], width=2),
            hovertemplate=f"%{{x|%Y-%m}}<br>{label}: %{{y:.2f}}%<extra></extra>",
        ))
    # Recent-only ICE BofA (3yr) as dashed overlay
    for df, key, label in [
        (ig, "ig", "ICE BofA IG eff. yield (C0A0, 3yr only)"),
        (bbb, "bbb", "ICE BofA BBB eff. yield (C0A4, 3yr only)"),
        (hy, "hy", "ICE BofA HY eff. yield (H0A0, 3yr only)"),
    ]:
        if df.empty:
            continue
        m = df.set_index("date")["value"].resample("M").mean().dropna()
        fig.add_trace(go.Scatter(
            x=m.index, y=m.values, mode="lines", name=label,
            line=dict(color=PLOTLY_COLORS[key], width=1.5, dash="dash"),
            opacity=0.85,
            hovertemplate=f"%{{x|%Y-%m}}<br>{label}: %{{y:.2f}}%<extra></extra>",
        ))
    fig.update_layout(
        title="2. Cost of Debt — Moody's Aaa/Baa since 2005 (solid) + ICE BofA IG/BBB/HY (dashed, 3yr only)",
        xaxis_title="Month", yaxis_title="Yield, %",
        template="plotly_white", height=440, margin=dict(l=60, r=20, t=80, b=40),
        legend=dict(orientation="h", y=-0.22),
        annotations=[dict(
            xref="paper", yref="paper", x=0, y=1.08, showarrow=False,
            text="Note: FRED retains only ~3yr of ICE BofA daily history due to ICE licensing. Moody's Aaa/Baa used as long-history IG/BBB proxy. No long-history HY substitute on FRED.",
            font=dict(size=10, color="#666"),
        )],
    )
    return fig


def chart_oas(oas: pd.DataFrame) -> go.Figure | None:
    if oas.empty:
        return None
    m = oas.set_index("date")["value"].resample("M").mean().dropna()
    fig = go.Figure(go.Scatter(
        x=m.index, y=m.values, mode="lines",
        line=dict(color=PLOTLY_COLORS["oas"], width=2),
        hovertemplate="%{x|%Y-%m}<br>BBB OAS: %{y:.2f}%<extra></extra>",
        name="BBB OAS",
    ))
    fig.update_layout(
        title="2B. BBB Corporate OAS (BAMLC0A4CBBB, monthly avg, %)",
        xaxis_title="Month", yaxis_title="Option-adjusted spread, %",
        template="plotly_white", height=320, margin=dict(l=60, r=20, t=60, b=40),
    )
    return fig


def chart_sifma(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()
    plot = df[df["ig_issuance_usd_bn"].notna() | df["hy_issuance_usd_bn"].notna()].copy()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=plot["period"], y=plot["ig_issuance_usd_bn"],
        name="IG issuance", marker_color=PLOTLY_COLORS["sifma_ig"],
        hovertemplate="%{x}<br>IG: $%{y}B<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=plot["period"], y=plot["hy_issuance_usd_bn"],
        name="HY issuance", marker_color=PLOTLY_COLORS["sifma_hy"],
        hovertemplate="%{x}<br>HY: $%{y}B<extra></extra>",
    ))
    fig.update_layout(
        title="3. SIFMA U.S. Corporate Bond Issuance — IG vs HY ($B, annual)",
        barmode="stack",
        xaxis_title="Year", yaxis_title="Issuance, $B",
        template="plotly_white", height=380, margin=dict(l=60, r=20, t=60, b=40),
        legend=dict(orientation="h", y=-0.2),
        annotations=[dict(
            xref="paper", yref="paper", x=0, y=1.08, showarrow=False,
            text="Note: issuance shown (not outstanding). Coverage sparse for 2019-2022 — see data/manual/sifma_ig_hy_issuance.md.",
            font=dict(size=10, color="#666"),
        )],
    )
    return fig


def chart_moodys(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()
    plot = df[df["us_spec_grade_default_rate_pct"].notna()].copy()
    plot["date"] = pd.to_datetime(plot["period"].astype(str).str.replace("-Q1", "-03-31").str.replace("-Q2", "-06-30").str.replace("-Q3", "-09-30").str.replace("-Q4", "-12-31"), errors="coerce")
    plot = plot.dropna(subset=["date"]).sort_values("date")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=plot["date"], y=plot["us_spec_grade_default_rate_pct"],
        mode="lines+markers",
        line=dict(color=PLOTLY_COLORS["moodys"], width=2),
        marker=dict(size=9),
        hovertemplate="%{x|%Y-%m}<br>Moody's SG default rate: %{y:.1f}%<extra></extra>",
        name="Moody's US spec-grade default rate",
    ))
    fig.update_layout(
        title="4. Moody's U.S. Speculative-Grade Default Rate (TTM, %) — SPARSE",
        xaxis_title="Date", yaxis_title="TTM default rate, %",
        template="plotly_white", height=380, margin=dict(l=60, r=20, t=60, b=40),
        annotations=[dict(
            xref="paper", yref="paper", x=0, y=1.08, showarrow=False,
            text="Note: free summaries only. 2019/2020/2021/2024 year-end figures missing. 2025-12 & 2026-Q1 are projections.",
            font=dict(size=10, color="#666"),
        )],
    )
    return fig


def chart_bankruptcies(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()
    plot = df[df["business_filings"].notna()].copy()
    annual = plot[plot["frequency"] == "annual"].copy()
    ttm = plot[plot["frequency"] == "trailing12m"].copy()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=annual["period"].str.slice(0, 4), y=annual["business_filings"],
        name="Annual business filings", marker_color=PLOTLY_COLORS["bankruptcy"],
        hovertemplate="%{x}<br>%{y:,} filings<extra></extra>",
    ))
    if not ttm.empty:
        fig.add_trace(go.Scatter(
            x=ttm["period"], y=ttm["business_filings"], mode="lines+markers",
            name="Trailing 12M", line=dict(color="#333", dash="dash"),
            hovertemplate="%{x}<br>%{y:,} filings<extra></extra>",
        ))
    fig.update_layout(
        title="5. U.S. Business Bankruptcy Filings (annual & trailing-12M)",
        xaxis_title="Period", yaxis_title="Filings",
        template="plotly_white", height=380, margin=dict(l=60, r=20, t=60, b=40),
        legend=dict(orientation="h", y=-0.2),
    )
    return fig


def chart_fitch(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()
    monthly = df[df["frequency"] == "monthly"].copy()
    monthly["date"] = pd.to_datetime(monthly["period"], format="%Y-%m", errors="coerce")
    monthly = monthly.dropna(subset=["date", "us_private_credit_default_rate_pct"]).sort_values("date")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly["date"], y=monthly["us_private_credit_default_rate_pct"],
        mode="lines+markers", name="Fitch PCDR (TTM)",
        line=dict(color=PLOTLY_COLORS["fitch"], width=2),
        marker=dict(size=8),
        hovertemplate="%{x|%Y-%m}<br>PCDR: %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        title="6. Fitch U.S. Private Credit Default Rate (PCDR, TTM, %)",
        xaxis_title="Month", yaxis_title="TTM default rate, %",
        template="plotly_white", height=380, margin=dict(l=60, r=20, t=60, b=40),
        annotations=[dict(
            xref="paper", yref="paper", x=0, y=1.08, showarrow=False,
            text="Note: PCDR series launched Aug 2024 — no earlier comparable observations exist.",
            font=dict(size=10, color="#666"),
        )],
    )
    return fig


# ---------- summary ----------

def build_summary(
    debt: pd.DataFrame, ig: pd.DataFrame, bbb: pd.DataFrame, hy: pd.DataFrame,
    oas: pd.DataFrame, sifma: pd.DataFrame, moodys: pd.DataFrame,
    bk: pd.DataFrame, fitch: pd.DataFrame,
    daaa: pd.DataFrame, dbaa: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict] = []

    def add(metric, latest, latest_date, since_2005, since_2019, unit, source, freq, notes=""):
        rows.append({
            "metric": metric, "latest": latest, "latest_date": latest_date,
            "change_since_2005": since_2005, "change_since_2019": since_2019,
            "unit": unit, "source": source, "frequency": freq, "notes": notes,
        })

    def baseline_value(df: pd.DataFrame, year: int) -> float:
        yr = df[df["date"].dt.year == year]
        return yr["value"].mean() if not yr.empty else float("nan")

    # 1. Debt stock
    if not debt.empty:
        d_latest = debt.iloc[-1]
        b19 = debt[debt["date"].dt.year == 2019]["value"].iloc[0] if not debt[debt["date"].dt.year == 2019].empty else float("nan")
        b05 = debt[debt["date"].dt.year == 2005]["value"].iloc[0] if not debt[debt["date"].dt.year == 2005].empty else float("nan")
        years19 = (d_latest["date"] - pd.Timestamp("2019-01-01")).days / 365.25
        years05 = (d_latest["date"] - pd.Timestamp("2005-01-01")).days / 365.25
        since_05 = (f"{pct_change(d_latest['value'], b05):+.1f}% (CAGR {cagr(d_latest['value'], b05, years05):.1f}%)"
                    if not pd.isna(b05) else "n/a")
        since_19 = (f"{pct_change(d_latest['value'], b19):+.1f}% (CAGR {cagr(d_latest['value'], b19, years19):.1f}%)"
                    if not pd.isna(b19) else "n/a")
        add(
            "U.S. nonfinancial corporate debt",
            f"${d_latest['value']/1000:,.0f}B",
            f"{d_latest['date'].year}-Q{((d_latest['date'].month - 1)//3) + 1}",
            since_05, since_19,
            "USD billions", "FRED BCNSDODNS (Federal Reserve Z.1)", "quarterly",
            "Official aggregate; latest point may lag 1-2 quarters.",
        )

    # 2. Yields — long-history Moody's Aaa/Baa (since 2005) + recent ICE BofA (3yr only)
    for df, label, sid in [
        (daaa, "Moody's Aaa corporate yield", "DAAA"),
        (dbaa, "Moody's Baa corporate yield", "DBAA"),
    ]:
        if df.empty:
            continue
        d_latest = df.iloc[-1]
        b05 = baseline_value(df, 2005)
        b19 = baseline_value(df, 2019)
        add(
            label,
            f"{d_latest['value']:.2f}%",
            d_latest["date"].strftime("%Y-%m-%d"),
            f"{d_latest['value'] - b05:+.2f}pp vs 2005 avg" if not pd.isna(b05) else "n/a",
            f"{d_latest['value'] - b19:+.2f}pp vs 2019 avg" if not pd.isna(b19) else "n/a",
            "percent", f"FRED {sid}", "daily",
            "Long-history IG/BBB cost-of-debt proxy.",
        )

    for df, label, sid in [
        (ig, "ICE BofA IG yield", "BAMLC0A0CMEY"),
        (bbb, "ICE BofA BBB yield", "BAMLC0A4CBBBEY"),
        (hy, "ICE BofA HY yield", "BAMLH0A0HYM2EY"),
    ]:
        if df.empty:
            continue
        d_latest = df.iloc[-1]
        b19 = baseline_value(df, 2019)
        b23 = baseline_value(df, 2023)
        add(
            label,
            f"{d_latest['value']:.2f}%",
            d_latest["date"].strftime("%Y-%m-%d"),
            "n/a (series starts 2023)",
            f"{d_latest['value'] - b19:+.2f}pp" if not pd.isna(b19) else f"{d_latest['value'] - b23:+.2f}pp vs 2023 avg",
            "percent", f"FRED {sid}", "daily",
            "FRED retains only ~3yr of ICE BofA daily history.",
        )

    # 2B OAS
    if not oas.empty:
        d_latest = oas.iloc[-1]
        b23 = baseline_value(oas, 2023)
        add(
            "BBB OAS",
            f"{d_latest['value']:.2f}%",
            d_latest["date"].strftime("%Y-%m-%d"),
            "n/a",
            f"{d_latest['value'] - b23:+.2f}pp vs 2023 avg" if not pd.isna(b23) else "n/a",
            "percent", "FRED BAMLC0A4CBBB", "daily",
            "Separates spread from Treasury-rate moves. 3yr history only.",
        )

    # 3. SIFMA
    if not sifma.empty:
        out = sifma[sifma["total_outstanding_usd_bn"].notna()]
        latest = out.iloc[-1] if not out.empty else None
        if latest is not None:
            add(
                "Total corporate bonds outstanding (SIFMA)",
                f"${latest['total_outstanding_usd_bn']:,.0f}B",
                str(latest["period"]),
                "n/a (2024+ only in free summary)",
                "n/a (2024+ only in free summary)",
                "USD billions", "SIFMA Research Quarterly", "quarterly",
                "Bond market only; excludes loans & private credit.",
            )
        iss = sifma[sifma["total_issuance_usd_bn"].notna()]
        if not iss.empty:
            latest_iss = iss.iloc[-1]
            add(
                "Annual IG+HY issuance",
                f"${latest_iss['total_issuance_usd_bn']:,.0f}B",
                str(latest_iss["period"]),
                "sparse back-history",
                "sparse back-history",
                "USD billions", "SIFMA", "annual",
                "See data/manual/sifma_ig_hy_issuance.md.",
            )

    # 4. Moody's
    if not moodys.empty:
        realised = moodys[moodys["us_spec_grade_default_rate_pct"].notna() & ~moodys["source_note"].str.contains("project", case=False, na=False)]
        if not realised.empty:
            latest = realised.iloc[-1]
            add(
                "Moody's U.S. spec-grade default rate (TTM)",
                f"{latest['us_spec_grade_default_rate_pct']:.1f}%",
                str(latest["period"]),
                "n/a (series sparse)",
                "n/a (series sparse)",
                "percent", "Moody's Investors Service", "monthly (sparse)",
                "Many gaps; free summaries do not cover every month.",
            )

    # 5. Bankruptcies
    if not bk.empty:
        annual = bk[bk["frequency"] == "annual"].dropna(subset=["business_filings"])
        if not annual.empty:
            latest = annual.iloc[-1]
            b19 = annual[annual["period"].str.startswith("2019")]["business_filings"]
            b19v = b19.iloc[0] if not b19.empty else float("nan")
            add(
                "U.S. business bankruptcy filings (annual)",
                f"{latest['business_filings']:,.0f}",
                str(latest["period"]),
                "n/a (manual CSV starts 2019)",
                f"{pct_change(latest['business_filings'], b19v):+.1f}% vs 2019" if not pd.isna(b19v) else "n/a",
                "filings", "U.S. Courts (AOUSC press releases)", "annual",
                "Full 2019-2025 coverage. Extend via uscourts.gov Table F-2 archive for 2005+.",
            )

    # 6. Fitch
    if not fitch.empty:
        monthly = fitch[(fitch["frequency"] == "monthly") & fitch["us_private_credit_default_rate_pct"].notna()]
        if not monthly.empty:
            monthly = monthly.copy()
            monthly["date"] = pd.to_datetime(monthly["period"], format="%Y-%m", errors="coerce")
            monthly = monthly.dropna(subset=["date"]).sort_values("date")
            latest = monthly.iloc[-1]
            first = monthly.iloc[0]
            delta = f"{latest['us_private_credit_default_rate_pct'] - first['us_private_credit_default_rate_pct']:+.1f}pp since series launch ({first['period']})"
            add(
                "Fitch U.S. private credit default rate (PCDR, TTM)",
                f"{latest['us_private_credit_default_rate_pct']:.1f}%",
                str(latest["period"]),
                "n/a (launched Aug 2024)",
                delta,
                "percent", "Fitch Ratings", "monthly",
                "Series launched Aug 2024 — no pre-2024 comparable.",
            )

    return pd.DataFrame(rows)


# ---------- HTML assembly ----------

def fig_to_html(fig: go.Figure, div_id: str) -> str:
    # include_plotlyjs only once; we embed via CDN on the first call
    return fig.to_html(include_plotlyjs=False, full_html=False, div_id=div_id)


def summary_table_html(summary: pd.DataFrame) -> str:
    if summary.empty:
        return "<p><em>Summary unavailable.</em></p>"
    rows = []
    for _, r in summary.iterrows():
        rows.append(
            f"<tr><td><strong>{r['metric']}</strong></td>"
            f"<td>{r['latest']}</td>"
            f"<td>{r['latest_date']}</td>"
            f"<td>{r['change_since_2005']}</td>"
            f"<td>{r['change_since_2019']}</td>"
            f"<td>{r['frequency']}</td>"
            f"<td><small>{r['source']}</small></td>"
            f"<td><small>{r['notes']}</small></td></tr>"
        )
    return (
        "<table class='summary'><thead><tr>"
        "<th>Metric</th><th>Latest</th><th>As of</th>"
        "<th>Change since 2005</th><th>Change since 2019</th>"
        "<th>Freq.</th><th>Source</th><th>Notes</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def build_html(
    summary: pd.DataFrame,
    figs: list[tuple[str, go.Figure | None]],
) -> str:
    built_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    chart_sections = []
    for div_id, fig in figs:
        if fig is None:
            continue
        chart_sections.append(f"<section class='chart'>{fig_to_html(fig, div_id)}</section>")

    interpretation = dedent("""
        <h2>Interpretation</h2>
        <ul>
          <li><strong>Debt stock:</strong> U.S. nonfinancial corporate debt roughly <em>doubled</em> between 2005 ($7.4T) and 2025 ($14.2T), with no sustained deleveraging cycle visible post-GFC or post-COVID in aggregate Z.1 data.</li>
          <li><strong>Cost of debt:</strong> Moody's Baa yield currently ~6% sits meaningfully above its 2019 average (~4.3%) and back near pre-GFC 2005-07 levels (~6-7%), reversing a decade-long decline. For the 3yr window where ICE data is available, IG/BBB/HY yields are all near their post-2008 highs.</li>
          <li><strong>Credit quality:</strong> SIFMA publishes issuance splits (not outstanding) in free summaries. Outstanding IG/HY mix requires the licensed xlsx. HY share of issuance was ~15% in 2024.</li>
          <li><strong>Public defaults:</strong> Moody's data is sparse in free summaries but shows the 2023 peak (5.6%) well above the 2022 trough (~1.5%). 2025-2026 projections point to a modest re-acceleration.</li>
          <li><strong>Bankruptcies:</strong> Business filings bottomed at ~13,481 in 2022 and have risen three consecutive years to 24,737 in 2025 — highest since 2011. This is the <em>clearest</em> distress signal in the data.</li>
          <li><strong>Private credit:</strong> Fitch's PCDR has trended up from 5.0% at launch (Aug 2024) to 5.8% (Jan 2026). The calendar-year PMR rate rose from 8.1% (2024) to a record 9.2% (2025).</li>
        </ul>
    """)

    caveats = dedent("""
        <h2>Data caveats</h2>
        <ul>
          <li><strong>FRED retains only ~3yr of ICE BofA daily history</strong> (ICE licensing change). The dashboard uses Moody's Seasoned Aaa/Baa yields (DAAA/DBAA, since 1986) as the long-history IG/BBB cost-of-debt proxy and overlays the recent ICE series. No free long-history HY substitute exists on FRED — for pre-2023 HY yields, use a Bloomberg (C0A0/H0A0 Index) or FactSet ICE Indices pull.</li>
          <li><strong>SIFMA outstanding IG/HY split</strong> is not in the free web summaries — the xlsx/PDFs are binary and not machine-readable via WebFetch. Fell back to issuance.</li>
          <li><strong>Moody's monthly TTM default rate</strong> is paywalled as a clean series. The chart uses only the datapoints cited in secondary coverage — do not treat as a continuous series.</li>
          <li><strong>US Courts bankruptcies</strong> are complete at annual granularity but chapter breakdowns for business-only filings require parsing Table F-2 PDFs (not done here).</li>
          <li><strong>Fitch PCDR</strong> launched Aug 2024 — there is no pre-2024 comparable observation. The calendar-year PMR series (2024 = 8.1%, 2025 = 9.2%) uses a different methodology and is not on the monthly chart.</li>
          <li><strong>EODHD is excluded from this core dashboard</strong> per the research plan; it is intended for a later issuer-level module only.</li>
        </ul>
    """)

    css = dedent("""
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
               max-width: 1200px; margin: 20px auto; padding: 0 20px; color: #222; }
        h1 { border-bottom: 2px solid #2ca02c; padding-bottom: 8px; }
        h2 { margin-top: 32px; color: #333; }
        .meta { color: #666; font-size: 0.9em; }
        table.summary { border-collapse: collapse; width: 100%; font-size: 0.9em; margin: 20px 0; }
        table.summary th, table.summary td { border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }
        table.summary th { background: #f5f5f5; }
        section.chart { margin: 20px 0; padding: 10px; border: 1px solid #eee; border-radius: 4px; }
        ul li { margin: 6px 0; }
        small { color: #666; }
        .footnote { margin-top: 40px; font-size: 0.85em; color: #666; border-top: 1px solid #ddd; padding-top: 16px; }
    """)

    html = dedent(f"""\
    <!doctype html>
    <html lang='en'>
    <head>
      <meta charset='utf-8'>
      <title>U.S. Corporate Debt Monitor — {AS_OF}</title>
      <script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script>
      <style>{css}</style>
    </head>
    <body>
      <h1>U.S. Corporate Debt Monitor</h1>
      <p class='meta'>As of {AS_OF} · built {built_at} · research plan: <code>us_corporate_debt_research_plan.md</code></p>

      <h2>At a glance</h2>
      {summary_table_html(summary)}

      <h2>Charts</h2>
      {''.join(chart_sections)}

      {interpretation}

      {caveats}

      <div class='footnote'>
        Data: FRED (Federal Reserve Z.1 + ICE BofA indices), SIFMA, Moody's Investors Service,
        U.S. Courts / AOUSC, Fitch Ratings. Manual-source provenance lives in
        <code>data/manual/SOURCES.md</code>. This dashboard is a monitoring aid, not investment advice.
      </div>
    </body>
    </html>
    """)
    return html


def main() -> int:
    # FRED
    debt = load_fred_series("BCNSDODNS")
    ig = load_fred_series("BAMLC0A0CMEY")
    bbb = load_fred_series("BAMLC0A4CBBBEY")
    hy = load_fred_series("BAMLH0A0HYM2EY")
    oas = load_fred_series("BAMLC0A4CBBB")
    daaa = load_fred_series("DAAA")
    dbaa = load_fred_series("DBAA")

    # Manual
    sifma = load_manual("sifma_ig_hy_issuance.csv")
    moodys = load_manual("moodys_spec_grade_default_rate.csv")
    bk = load_manual("us_courts_business_bankruptcies.csv")
    fitch = load_manual("fitch_private_credit_default_rate.csv")

    figs: list[tuple[str, go.Figure | None]] = [
        ("chart-debt", chart_debt_stock(debt)),
        ("chart-yields", chart_yields_long(daaa, dbaa, ig, bbb, hy)),
        ("chart-oas", chart_oas(oas)),
        ("chart-sifma", chart_sifma(sifma)),
        ("chart-moodys", chart_moodys(moodys)),
        ("chart-bankruptcies", chart_bankruptcies(bk)),
        ("chart-fitch", chart_fitch(fitch)),
    ]

    summary = build_summary(debt, ig, bbb, hy, oas, sifma, moodys, bk, fitch, daaa, dbaa)
    summary.to_csv(OUT_SUMMARY, index=False)
    print(f"summary -> {OUT_SUMMARY} ({len(summary)} rows)")

    OUT_HTML.parent.mkdir(exist_ok=True)
    OUT_HTML.write_text(build_html(summary, figs))
    print(f"dashboard -> {OUT_HTML}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
