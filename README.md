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

Three dashboards, same repo:

| Lens | Output | Focus |
|---|---|---|
| **Macro** (top-down aggregate) | `dashboard/index.html` | FRED Z.1 + ICE BofA + Moody's + SIFMA + U.S. Courts + Fitch |
| **Issuer** (bottom-up S&P 600) | `dashboard/issuer.html` | Aggregate / median / sector view of all 479 nonfinancial names |
| **Credit stress tracker** | `dashboard/credit.html` | Top-decile debtors, 5yr trends, stress-score watchlist |

All three are static HTML files with Plotly via CDN — open in a browser.

## Headline numbers (FY2019 → latest)

**Macro lens** (`dashboard/index.html`):
- U.S. nonfinancial corporate debt: $14.2T (+35% since 2019, FRED BCNSDODNS)
- Moody's Baa yield: 5.99% (+1.6pp vs 2019 avg)
- BBB OAS: 0.99% (compressed vs 2023)

**Issuer lens** (`dashboard/issuer.html`, 479 non-financial S&P 600 names):
- Aggregate total debt: **$611B → $819B (+34%)**
- Aggregate cash: **$173B → $167B (-3%)** — cushion eroding
- Aggregate interest expense: **$28.8B → $43.4B (+51%)** — rate-shock real money

**Credit-stress lens** (`dashboard/credit.html`, top 10% by debt):
- **Top 1% (5 issuers) hold 14.4% of debt; top 10% (47 issuers) hold 52.5%** — concentration is real
- Watchlist median net debt / EBITDA: ~6x; median EBIT interest coverage: ~1.7x
- Top-decile interest expense FY2020 → FY2025: **+median ~80%** vs EBITDA ~+30%
- Most-stressed names (ex-REITs): HTZ, JBLU, FUN, AAP, CE, RUN, SABR, VSAT

## Layout

```
.
├── scripts/
│   ├── fetch_fred.sh                   # FRED API + CSV fallback (9 series, since 2005)
│   ├── build_dashboard.py              # → dashboard/index.html (macro)
│   ├── fetch_sp600_universe.py         # Wikipedia → data/sp600/sp600_current.csv
│   ├── fetch_eodhd_fundamentals.py     # EODHD JSON cache per ticker
│   ├── build_issuer_panel.py           # Flatten JSON → long/wide CSV panels
│   ├── build_issuer_dashboard.py       # → dashboard/issuer.html (bottom-up)
│   ├── build_credit_panel.py           # Richer panel: BS+IS+CF + debt ratios
│   ├── build_credit_watchlist.py       # Top-decile debtors + stress score
│   └── build_credit_dashboard.py       # → dashboard/credit.html (concentration)
├── data/
│   ├── fred/                           # FRED raw CSVs
│   ├── manual/                         # Curated SIFMA/Moody's/AOUSC/Fitch + SOURCES.md
│   ├── sp600/                          # Universe CSV + raw/{TICKER}.json (git-ignored)
│   ├── issuer/                         # Long & wide panels, meta, exclusions
│   └── summary.csv                     # Macro one-row-per-metric snapshot
├── dashboard/
│   ├── index.html                      # Macro dashboard
│   ├── issuer.html                     # Issuer dashboard
│   └── credit.html                     # Credit-stress tracker
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

### Credit-stress tracker

```bash
python3.11 scripts/build_credit_panel.py        # rich panel (BS + IS + CF + ratios)
python3.11 scripts/build_credit_watchlist.py    # top 10% by FY2025 total debt
python3.11 scripts/build_credit_watchlist.py --exclude-re   # ex-REIT watchlist
python3.11 scripts/build_credit_dashboard.py
open dashboard/credit.html
```

Outputs:
- `data/issuer/credit_panel_annual.csv` — 39 columns, 3,851 ticker-years
- `data/issuer/concentration_summary.csv` — top 1/5/10/25/50/100% cumulative debt share
- `data/issuer/top_debtors_watchlist.csv` — 47-name watchlist with stress score
- `data/issuer/top_debtors_watchlist_no_re.csv` — same, REITs filtered

**Stress score** is a 0-100 composite of: interest coverage (EBIT/interest),
leverage (net_debt/EBITDA), FCF coverage of debt, and 5-year interest-expense
growth. Higher = more stressed.

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
7. **Debt-maturity schedule is NOT in EODHD fundamentals.** The
   credit-stress dashboard tracks levels and ratios over time, but doesn't
   show *when* the debt is due. For the refi-wall analysis you asked
   about — when does the high-debt cohort have to roll? — you'd need:
   - SEC 10-K parsing (notes-to-financials section "Long-term debt /
     Maturity of long-term debt")
   - Bloomberg DDIS function or DDDM (debt distribution by maturity)
   - S&P Capital IQ → Capital Structure → Debt Maturity Schedule
   - Moody's CreditView issuer page (rating + maturity wall)

   None of these are in EODHD's standard fundamentals payload. Bond-level
   data IS available via separate EODHD marketplace endpoints (PRAAMS bond
   analytics) but per-ISIN, not per-issuer. A 10-K parser is the most
   practical path; flagged here as a follow-up module.

## Data lineage

Every manual-source row carries a `source_note` column; each CSV ships
with a `.md` companion file; `data/manual/SOURCES.md` is the master
manifest. EODHD raw JSON caches preserve the per-ticker source-of-truth.
