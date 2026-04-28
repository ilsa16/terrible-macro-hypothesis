# U.S. Corporate Debt Research Plan (Agent Spec)

**Status:** Approved draft for execution  
**Geographic scope:** United States  
**Primary focus:** U.S. nonfinancial corporates  
**Time period:** 2019 to latest available, with 2026 updates where available  
**As-of date for this plan:** 2026-04-23

---

## 1) Objective

Build a lean, credible, repeatable research workflow to answer the following questions for the United States:

1. What are the **levels of corporate debt** in the latest available period, and how have they changed since 2019?
2. What is the **cost of debt**, and how has it evolved since 2019?
3. How is corporate debt distributed by **credit quality**?
4. What are the trends in **default rates**, **business bankruptcies**, and **private credit defaults** since 2019?

This plan is designed to be:
- **source-disciplined**
- **automation-friendly**
- **simple enough for agents to execute reliably**

---

## 2) Scope decisions

### In scope for the core version
- Aggregate U.S. nonfinancial corporate debt
- Cost of debt using market-based public credit proxies
- Broad credit-quality split using public corporate bond market data
- Public default rate
- Business bankruptcy filings
- Private credit default rate

### Explicitly deferred from the core version
- Full debt breakdown by **firm size**
- Deep debt breakdown by **granular rating bucket** (AAA/AA/A/BBB/BB/B/CCC)
- Full issuer-level public-company debt panel

These are deferred because they either require licensed data, partial-coverage surveys, or complex entity-level aggregation that would make the first version less robust.

---

## 3) Source hierarchy

Agents should follow this hierarchy in order of priority.

### Tier 1: Primary sources for the core dashboard
1. **Federal Reserve / FRED**
   - Use for aggregate U.S. nonfinancial corporate debt
   - Canonical series: `BCNSDODNS`
2. **FRED ICE BofA credit series**
   - Use for market-implied cost of debt
   - Canonical series:
     - `BAMLC0A0CMEY` = U.S. Corporate IG Effective Yield
     - `BAMLC0A4CBBBEY` = BBB Effective Yield
     - `BAMLH0A0HYM2EY` = U.S. High Yield Effective Yield
     - optional: `BAMLC0A4CBBB` = BBB OAS
3. **SIFMA U.S. Corporate Bond Statistics**
   - Use for broad public bond market mix, especially IG vs HY
4. **Moody's or S&P Global Ratings**
   - Use for public speculative-grade default rates
   - One provider should be chosen as the primary default-rate series for consistency
5. **U.S. Courts**
   - Use for business bankruptcy filings
6. **Fitch**
   - Use for private credit default rates

### Tier 2: Later add-on source
7. **EODHD All-In-One API**
   - Use later for issuer-level public-company debt, interest expense, and bottom-up monitoring
   - Not to be used as the primary source for aggregate debt, bankruptcy counts, public default rates, or private credit default rates

---

## 4) Core research workflow

Agents should execute the research in the following order.

### Step 1: Aggregate corporate debt level and trend

#### Goal
Measure total U.S. nonfinancial corporate debt and its trend since 2019.

#### Source
- FRED / Federal Reserve Z.1
- Series: `BCNSDODNS`

#### Method
1. Pull quarterly observations from **2019-12-31** onward.
2. Use latest available observation as the current debt-stock level.
3. Calculate:
   - level
   - YoY growth
   - cumulative growth since 2019
   - CAGR since 2019
4. Present as the main debt stock chart.

#### Output
- Chart 1: **U.S. nonfinancial corporate debt stock since 2019**

#### Notes
- This is the anchor series for the entire project.
- It is official, clean, and far more reliable than bottom-up public-company aggregation for the macro question.

#### Limitations
- Quarterly frequency
- Latest official debt-stock data may lag the calendar year
- Aggregate only; does not provide firm size or granular rating mix

---

### Step 2: Cost of debt since 2019

#### Goal
Track how the market cost of corporate debt has changed.

#### Source
- FRED ICE BofA credit index yield series

#### Required series
- `BAMLC0A0CMEY` (U.S. Corporate IG Effective Yield)
- `BAMLC0A4CBBBEY` (BBB Effective Yield)
- `BAMLH0A0HYM2EY` (U.S. High Yield Effective Yield)

#### Optional series
- `BAMLC0A4CBBB` (BBB OAS)

#### Method
1. Pull daily data from **2019-01-01** onward.
2. Convert to monthly averages for charting consistency.
3. Compare:
   - IG yields
   - BBB yields
   - HY yields
4. If OAS is included, separate spread widening from Treasury-rate changes.

#### Output
- Chart 2: **IG vs BBB vs HY effective yields since 2019**
- Optional Chart 2B: **BBB OAS since 2019**

#### Notes
- This is the preferred core methodology because it is liquid-market based and easy to update.

#### Limitations
- Represents traded public bond market pricing
- Not the exact weighted-average cash interest cost for all U.S. corporates
- Underrepresents private loans and bespoke private-credit structures

#### Strong alternative
- Census QFR-based interest burden analysis using interest expense / debt, but only as a secondary cross-check

---

### Step 3: Broad credit-quality split of debt

#### Goal
Answer where debt sits by credit quality without overcomplicating the first version.

#### Source
- SIFMA U.S. Corporate Bond Statistics

#### Method
1. Pull latest available public corporate bond statistics.
2. Use **investment grade vs high yield** as the default credit split.
3. Prefer outstanding debt if available; otherwise use issuance as a fallback and clearly label it.
4. Do not attempt granular rating-bucket reconstruction in the core version.

#### Output
- Chart 3: **IG vs HY corporate bond mix**

#### Notes
- This is intentionally high-level.
- The goal is to answer the rating composition question in a robust, maintainable way.

#### Limitations
- Mainly public corporate bond market, not all corporate debt
- Broad split only, not AAA/AA/A/BBB/BB/B/CCC

#### Strong alternative
- Later move to FISD / Capital IQ / Compustat / similar licensed sources for granular rating buckets

---

### Step 4: Public default rates

#### Goal
Track distress in the rated speculative-grade public credit universe.

#### Primary source
- Choose **one** provider as the canonical series:
  - Moody's, or
  - S&P Global Ratings

#### Method
1. Use one consistent trailing-12-month U.S. speculative-grade default-rate series.
2. Pull observations from 2019 onward.
3. Maintain a manual history table if the source is not API-friendly.
4. Record exact methodology notes from the provider.

#### Output
- Chart 4: **U.S. speculative-grade default rate since 2019**

#### Notes
- Do not combine Moody's and S&P into one blended series.
- Pick one provider and stay consistent.

#### Limitations
- Reflects rated speculative-grade issuers, not all corporates
- Not the same as bankruptcy filings

#### Strong alternative
- Keep the second provider as a cross-check appendix, not in the main chart

---

### Step 5: Business bankruptcies

#### Goal
Track legal business distress separately from credit-market default events.

#### Source
- U.S. Courts bankruptcy filing tables

#### Method
1. Pull business bankruptcy filings from 2019 onward.
2. Use annual or quarterly totals depending on data availability and consistency.
3. Keep this chart separate from public default rates.

#### Output
- Chart 5: **U.S. business bankruptcy filings since 2019**

#### Notes
- Bankruptcy and default are different concepts and must not be merged.

#### Limitations
- Less automation-friendly than FRED
- Legal events rather than bond/loan default events

---

### Step 6: Private credit defaults

#### Goal
Track distress in U.S. private credit.

#### Source
- Fitch private credit default publications

#### Method
1. Use Fitch as the primary private credit default series.
2. Pull historical observations from 2019 onward or earliest comparable starting point.
3. Preserve Fitch methodology notes alongside the chart.
4. If the source is report-based rather than API-based, maintain a manually updated source table.

#### Output
- Chart 6: **U.S. private credit default rate since 2019**

#### Notes
- This series is important because public speculative-grade defaults alone will not capture private-credit stress.

#### Limitations
- Coverage is portfolio-based, not a full census of the market
- Methodology may differ from public default-rate definitions

#### Strong alternative
- PitchBook or LCD if licensed access becomes available later

---

## 5) Deferred module: issuer-level public-company analysis using EODHD

This module is **not part of the first core dashboard**.

### Why it is deferred
EODHD is useful for issuer-level public-company analysis, but it is **not** the right primary source for:
- aggregate U.S. corporate debt stock
- broad market default-rate history
- business bankruptcy filings
- private credit default rates

It is best used later as a **bottom-up supplement**.

### Intended use cases for EODHD later
1. Build a public-company debt panel for U.S. listed issuers
2. Estimate issuer-level debt burden over time
3. Compare sectors and single-name leverage trends
4. Create an issuer-level effective cost-of-debt proxy

### Candidate EODHD fields
Agents should verify field names before implementation, but likely relevant items include:
- `shortTermDebt`
- `shortLongTermDebt`
- `shortLongTermDebtTotal`
- `longTermDebt`
- `longTermDebtTotal`
- `netDebt`
- `interestExpense`
- `netBorrowings`

### Example issuer-level methodology
For a given public company:
1. Pull annual and quarterly fundamentals
2. Build debt as:
   - total debt proxy from short-term and long-term debt fields
3. Estimate effective cost of debt as:
   - `interestExpense / average debt`
4. Aggregate across a defined public-company universe later if needed

### Important warning
Bottom-up EODHD aggregation should **not** be presented as the official U.S. corporate debt total.
It is a **public-company lens**, not a macro-sector accounting series.

---

## 6) Expected final deliverables

### Core deliverables
Agents should produce the following six charts:

1. **U.S. nonfinancial corporate debt stock since 2019**
2. **IG vs BBB vs HY effective yields since 2019**
3. **IG vs HY corporate bond mix**
4. **U.S. speculative-grade default rate since 2019**
5. **U.S. business bankruptcy filings since 2019**
6. **U.S. private credit default rate since 2019**

### Summary output
Agents should also produce a one-page summary with:
- latest reading for each series
- change since 2019
- brief interpretation of what has worsened, improved, or shifted
- source notes and methodology caveats

---

## 7) Data handling rules for agents

1. **Prefer official or canonical sources over convenience sources**
2. **Do not mix incompatible definitions in one series**
3. **Keep bankruptcy, public defaults, and private credit defaults separate**
4. **Use one provider consistently for public default rates**
5. **State clearly when data are report-based or manually maintained**
6. **Do not overstate the coverage of EODHD**
7. **Flag any change in source methodology immediately**

---

## 8) Automation guidance

### Fully automatable now
- FRED debt stock series
- FRED credit yield series

### Semi-automatable or manual ingestion likely required
- SIFMA bond mix tables
- Moody's or S&P default-rate history
- U.S. Courts bankruptcy tables
- Fitch private credit default history

### Later automation module
- EODHD issuer-level public-company debt and interest expense monitor

---

## 9) Python implementation roadmap

This section is for the later coding phase.

### Phase 1: Core script
Build a Python script that:
1. fetches FRED series
2. stores them in tidy long-form tables
3. computes monthly/quarterly transformations
4. outputs standardized charts
5. exports CSV snapshots

### Phase 2: Manual-source ingestion layer
Add CSV templates for:
- public default rates
- business bankruptcy filings
- private credit default rates

These CSVs should be version-controlled and refreshed when source publications update.

### Phase 3: EODHD issuer-level module
Later add a separate module that:
1. takes an API key
2. fetches fundamentals for a defined U.S. public-company universe
3. extracts debt and interest-expense fields
4. calculates issuer-level debt burden metrics
5. outputs sector and issuer charts

### Design principle
Keep the **macro dashboard** and the **issuer-level EODHD module** separate.
Do not merge them into a single source-of-truth table.

---

## 10) Minimal execution checklist

Before concluding the work, agents must verify:

- [ ] FRED debt-stock series starts in 2019 and latest point is correctly labeled
- [ ] FRED yield series are converted to monthly averages consistently
- [ ] SIFMA chart is clearly labeled as IG vs HY bond market mix
- [ ] Public default series uses only one canonical provider
- [ ] Bankruptcy chart is sourced from U.S. Courts, not a press summary unless necessary
- [ ] Private credit default chart includes methodology notes
- [ ] EODHD is excluded from the core dashboard and only described as a later add-on

---

## 11) Agent instructions for citations and transparency

Agents must:
- cite each chart to its underlying source
- state the observation frequency (daily, monthly, quarterly, annual)
- state whether the series is official, market-based, survey-based, or report-based
- identify any manual data maintenance required
- avoid presenting derived estimates as official statistics

---

## 12) Recommended next step

After plan approval, create:
1. a Python data scaffold for FRED pulls and chart generation
2. CSV schemas for manual default/bankruptcy/private-credit updates
3. a later EODHD issuer-level module specification

