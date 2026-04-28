# Sources manifest — manual U.S. corporate debt data

**Access date for all sources: 2026-04-23**

This file inventories every source used to populate the four CSVs in `data/manual/`. For per-file caveats and coverage see the companion `.md` next to each CSV.

---

## 1. SIFMA — `sifma_ig_hy_issuance.csv`

- SIFMA US Corporate Bonds Statistics page — https://www.sifma.org/research/statistics/us-corporate-bonds-statistics
- SIFMA Research Quarterly Fixed Income Outstanding 2Q25 (PDF) — https://www.sifma.org/wp-content/uploads/2025/09/SIFMA-Research-Quarterly-Fixed-Income-O-2Q25.pdf *(binary — not parsed)*
- SIFMA Research Quarterly 1Q25 (PDF) — https://www.sifma.org/wp-content/uploads/2025/01/SIFMA-Research-Quarterly-Fixed-Income-IT-1Q25.pdf
- SIFMA 2024 Capital Markets Fact Book (PDF) — https://www.sifma.org/wp-content/uploads/2023/07/2024-SIFMA-Capital-Markets-Factbook.pdf *(binary — not parsed)*
- CME OpenMarkets summary of SIFMA 2024 data — https://www.cmegroup.com/openmarkets/interest-rates/2025/Corporate-Bond-Issuance-Grows-Along-with-Economic-Risks.html
- VanEck 2025 Corporate Bond Market Trends — https://www.vaneck.com/us/en/blogs/income-investing/corporate-bond-market-trends-and-insights-a-2025-investors-guide/

**Note:** The originally cited URL `https://www.sifma.org/resources/research/us-corporate-bonds-statistics/` returned HTTP 404. Canonical location is `https://www.sifma.org/research/statistics/us-corporate-bonds-statistics`.

**Not reached / paywalled:** SIFMA raw xlsx with IG/HY outstanding split was not opened (binary PDF from WebFetch couldn't be parsed). User should download manually.

---

## 2. Moody's — `moodys_spec_grade_default_rate.csv`

- Moody's US Credit Review & Outlook — July 2025 (PDF) — https://www.moodys.com/web/en/us/insights/resources/us-report-july-2025.pdf *(binary — not parsed)*
- Moody's Q1 2024 US Credit Review (PDF) — https://www.moodys.com/web/en/us/insights/resources/us-credit-review-and-outlook-q1-2024.pdf *(HTTP 403 via WebFetch)*
- Moody's US Credit Review — cycle bottom elusive (PDF) — https://www.moodys.com/web/en/us/site-assets/us-corp-credit-report-cycle-bottom-elusive-for-corporate-credit.pdf
- Moody's December 2023 Default Report — https://dkf1ato8y5dsg.cloudfront.net/uploads/52/504/december-2023-default-report.pdf *(binary — not parsed)*
- Moody's data story: US corporate default risk in 2025 — https://www.moodys.com/web/en/us/insights/data-stories/us-corporate-default-risk-in-2025.html
- Moody's Ratings LinkedIn (forecasts, Jul 2025) — https://www.linkedin.com/posts/moodys-ratings_below-are-moodys-ratings-default-rate-forecasts-activity-7354131972526415872-PdWs
- S&P Global Market Intelligence summary (2021 peak forecast) — https://www.spglobal.com/marketintelligence/en/news-insights/latest-news-headlines/us-speculative-grade-default-rate-to-peak-at-9-1-in-march-8211-moody-s-62225076
- S&P Global MI: Global spec-grade ends 2020 at 6.7% — https://www.spglobal.com/marketintelligence/en/news-insights/latest-news-headlines/global-default-rate-for-speculative-grade-firms-ends-2020-at-6-7-8212-moody-8217-s-62377291
- CFODive: Moody's sees 2022 default rate rising — https://www.cfodive.com/news/default-rate-rise-2022-moodys/618900/
- Charles Schwab: High-Yield Defaults — https://www.schwab.com/learn/story/high-yield-defaults-canary-coal-mine

**Not reached / paywalled:** Moody's full monthly Default Report PDF series behind a paywall / binary-only via WebFetch. Primary data came from secondary press summaries.

---

## 3. U.S. Courts — `us_courts_business_bankruptcies.csv`

- AOUSC bankruptcy filings statistics hub — https://www.uscourts.gov/data-news/reports/statistical-reports/bankruptcy-filings-statistics
- Press release Jan 28, 2020 (CY2019) — https://www.uscourts.gov/data-news/judiciary-news/2020/01/28/bankruptcy-filings-increase-slightly
- Press release Jan 28, 2021 (CY2020) — https://www.uscourts.gov/data-news/judiciary-news/2021/01/28/annual-bankruptcy-filings-fall-297-percent
- Press release Feb 4, 2022 (CY2021) — https://www.uscourts.gov/data-news/judiciary-news/2022/02/04/bankruptcy-filings-drop-24-percent
- Press release Feb 6, 2023 (CY2022) — https://www.uscourts.gov/data-news/judiciary-news/2023/02/06/bankruptcy-filings-drop-63-percent
- Press release Jan 26, 2024 (CY2023) — https://www.uscourts.gov/data-news/judiciary-news/2024/01/26/bankruptcy-filings-rise-168-percent
- Press release Feb 4, 2025 (CY2024) — https://www.uscourts.gov/data-news/judiciary-news/2025/02/04/bankruptcy-filings-rise-14-2-percent
- Press release May 1, 2025 (TTM Mar 2025) — https://www.uscourts.gov/data-news/judiciary-news/2025/05/01/bankruptcies-rise-131-percent-over-previous-year
- Press release Jul 31, 2025 (TTM Jun 2025) — https://www.uscourts.gov/data-news/judiciary-news/2025/07/31/bankruptcy-filings-rise-115-percent-over-previous-year
- Press release Nov 24, 2025 (TTM Sep 2025) — https://www.uscourts.gov/data-news/judiciary-news/2025/11/24/bankruptcy-filings-increase-10-6-percent
- Press release Feb 4, 2026 (CY2025) — https://www.uscourts.gov/data-news/judiciary-news/2026/02/04/bankruptcy-filings-rise-11-percent
- Table F-2 PDF (Dec 31, 2024) — https://www.uscourts.gov/sites/default/files/2025-01/bf_f2_1231.2024.pdf *(binary — not parsed)*

**Not reached:** Business-by-chapter breakdowns (columns `chapter_7`, `chapter_11`, `chapter_13` in the CSV) — these are not in the press-release text; require manual pull from Table F-2 xlsx.

---

## 4. Fitch — `fitch_private_credit_default_rate.csv`

- Bloomberg (Sep 26, 2024): Private Credit Default Rate at 5% in August — https://www.bloomberg.com/news/articles/2024-09-26/fitch-ratings-says-private-credit-default-rate-stands-at-5
- Funds Society: U.S. Private Credit Default Rate Continues to Climb — https://www.fundssociety.com/en/news/alternatives/u-s-private-credit-default-rate-continues-to-climb/
- Private Debt Investor: Fitch 5.7% in February 2025 — https://www.privatedebtinvestor.com/fitch-us-private-credit-default-rate-hit-5-7-in-february/
- Fitch Ratings LinkedIn (Aug 2025 post, PCDR 5.2% in July) — https://www.linkedin.com/posts/fitch-ratings_privatecredit-default-activity-7364280299968512000-vZY-
- dmarketforces: US Private Credit Defaults Broaden Across Sectors, Rises To 5.7% — https://dmarketforces.com/us-private-credit-defaults-broaden-across-sectors-rises-to-5-7/
- dmarketforces: U.S. Private Credit Defaults Hit New Highs — https://dmarketforces.com/u-s-private-credit-defaults-hit-new-highs/
- Connect Money: U.S. Private Credit Default Rate Eases but Remains Elevated — https://www.connectmoney.com/stories/u-s-private-credit-default-rate-eases-but-remains-elevated/
- Alternative Credit Investor: Fitch US private credit defaults to rise in 2024 — https://alternativecreditinvestor.com/2024/07/02/fitch-us-private-credit-defaults-to-rise-in-2024/
- LinkedIn Bridge Business Credit: US Private Credit Defaults Hit Record 9.2% (PMR CY2025) — https://www.linkedin.com/posts/bridge-business-credit_us-private-credit-defaults-hit-record-92-activity-7443280941738938369-M8Wd
- LSTA Fitch Ratings Commentary Page (index) — https://www.lsta.org/content/fitch-ratings-commentary-page/ *(HTTP 403)*

**Not reached:** Direct Fitch Ratings pages on fitchratings.com for PCDR monthly releases — most require registration or are indexed only via secondary summaries. The LSTA Fitch commentary page returned 403.

---

## Overall reliability and recommended follow-ups

1. **Re-pull Moody's default rate** from the paid Default Report series to get a clean monthly spec-grade TTM series back to 2019.
2. **Download SIFMA xlsx** to get IG/HY *outstanding* (not issuance) split — the series the plan originally asked for.
3. **Extract Table F-2 xlsx** for business-chapter breakdowns (Ch 7 / 11 / 13) in the bankruptcy CSV.
4. **Dashboard should clearly flag** which rows are realized vs. forecast (Moody's 2025-12 and 2026-Q1 are forecasts).
