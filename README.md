# Terrible Macro Hypothesis 📉

A two-lens dashboard for monitoring U.S. corporate debt stress — the
top-down macro picture and a bottom-up issuer-level view of the S&P 600
SmallCap.

> Working from the hypothesis that something terrible is brewing in
> corporate balance sheets — refinancing-wall pressure, weakening cash
> cushions, and a private-credit black box. This repo lets you check.

Implements the research plan in
[`us_corporate_debt_research_plan.md`](us_corporate_debt_research_plan.md).

## What's in here

Two independent dashboards, same repo:

| Lens | Output | Source |
|---|---|---|
| **Macro** (top-down aggregate) | `dashboard/index.html` | FRED Z.1, ICE BofA, Moody's, SIFMA, U.S. Courts, Fitch |
| **Issuer** (bottom-up S&P 600) | `dashboard/issuer.html` | EODHD fundamentals (one JSON per ticker) |

Both are static HTML files with Plotly via CDN — open them in a browser.

## Headline numbers (FY2019 → latest)

**Macro lens** (`dashboard/index.html`):
- U.S. nonfinancial corporate debt: $14.2T (+35% since 2019, FRED BCNSDODNS)
- Moody's Baa yield: 5.99% (+1.6pp vs 2019 avg)
- BBB OAS: 0.99% (compressed vs 2023)

**Issuer lens** (`dashboard/issuer.html`, 479 non-financial S&P 600 names):
- Aggregate total debt: **$611B → $819B (+34%)**
- Aggregate cash: **$173B → $167B (-3%)** — cushion eroding
- Aggregate interest expense: **$28.8B → $43.4B (+51%)** — rate-shock real money

## Layout

```
.
├── scripts/
│   ├── fetch_fred.sh                   # FRED API + CSV fallback (9 series, since 2005)
│   ├── build_dashboard.py              # → dashboard/index.html (macro)
│   ├── fetch_sp600_universe.py         # Wikipedia → data/sp600/sp600_current.csv
│   ├── fetch_eodhd_fundamentals.py     # EODHD JSON cache per ticker
│   ├── build_issuer_panel.py           # Flatten JSON → long/wide CSV panels
│   └── build_issuer_dashboard.py       # → dashboard/issuer.html (bottom-up)
├── data/
│   ├── fred/                           # FRED raw CSVs
│   ├── manual/                         # Curated SIFMA/Moody's/AOUSC/Fitch + SOURCES.md
│   ├── sp600/                          # Universe CSV + raw/{TICKER}.json (git-ignored)
│   ├── issuer/                         # Long & wide panels, meta, exclusions
│   └── summary.csv                     # Macro one-row-per-metric snapshot
├── dashboard/
│   ├── index.html                      # Macro dashboard
│   └── issuer.html                     # Issuer dashboard
├── charts/                             # Reserved for PNG snapshots
├── .env.example                        # Copy to .env and add FRED + EODHD keys
└── us_corporate_debt_research_plan.md  # The original spec
```

## Setup

```bash
# 1. clone + create .env
cp .env.example .env
# fill in FRED_API_KEY (https://fred.stlouisfed.org/docs/api/api_key.html)
# and EODHD_API_KEY (https://eodhd.com/financial-apis/)

# 2. install python deps (use python3.11 or any 3.11+)
pip install pandas plotly
```

## Refresh workflow

### Macro dashboard
```bash
bash scripts/fetch_fred.sh                   # pull latest FRED series
python3.11 scripts/build_dashboard.py        # rebuild macro
open dashboard/index.html
```

### Issuer dashboard
```bash
python3.11 scripts/fetch_sp600_universe.py             # current S&P 600 + 20-ticker pilot
python3.11 scripts/fetch_eodhd_fundamentals.py --pilot # pilot first
python3.11 scripts/build_issuer_panel.py --pilot
python3.11 scripts/build_issuer_dashboard.py --pilot
# review pilot dashboard then full run:
python3.11 scripts/fetch_eodhd_fundamentals.py
python3.11 scripts/build_issuer_panel.py
python3.11 scripts/build_issuer_dashboard.py
open dashboard/issuer.html
```

The full S&P 600 pull is ~600 tickers × ~2s = ~20 minutes; per-ticker JSONs
are cached in `data/sp600/raw/` so re-runs skip already-fetched names.
Pass `--force` to re-download.

## Issuer-lens design choices

- **Universe**: current S&P 600 SmallCap constituents that reported FY2018
  or FY2019 annual financials (proxy for "in the index since 2019" — true
  historical membership reconstruction is out of scope).
- **Financial Services excluded** (105 banks/insurers): for those firms the
  income-statement "interest expense" line is overwhelmingly *deposit /
  policy interest*, not the cost of funded debt — leaving them in distorts
  the cost-of-debt picture.
- **Sanity clamp**: rows with implied interest rate > 50% (interest_expense /
  total_debt) are nulled out. These are almost always EODHD scale errors —
  e.g. GOLF FY2025 stored as $87B instead of $87M.
- **Debt field fallback**: prefer `totalDebt`, then `shortLongTermDebtTotal`,
  then `shortTermDebt + longTermDebt`. Cash uses
  `cashAndShortTermInvestments` with fallback to `cash`.

## Known limitations (carry through both dashboards)

1. **FRED retains only ~3yr of ICE BofA daily history** (their licensing
   constraint). For pre-2023 IG/BBB/HY work the dashboard falls back to
   Moody's Aaa/Baa as long-history proxies (since 2005).
2. **SIFMA IG/HY outstanding split** sits in xlsx/PDFs. The dashboard uses
   IG+HY issuance instead, with a manual companion CSV.
3. **Moody's monthly default rate** is paywalled — manual CSV is sparse,
   datapoint-by-datapoint from secondary coverage. Treat as discrete points
   not a continuous series.
4. **Fitch PCDR** launched Aug 2024; there is no pre-2024 private-credit
   default series.
5. **Survivorship bias** in the issuer lens: firms that left the index
   (bankruptcies, acquisitions, reshuffles) are gone from the panel.
6. **Issuer aggregation ≠ macro total**: S&P 600 is a thin slice of the
   U.S. corporate universe; the bottom-up sums are NOT comparable to FRED
   BCNSDODNS. The dashboard banner is explicit about this.

## Data lineage

Every manual-source row carries a `source_note` column; each CSV ships
with a `.md` companion file; `data/manual/SOURCES.md` is the master
manifest. EODHD raw JSON caches preserve the per-ticker source-of-truth.
