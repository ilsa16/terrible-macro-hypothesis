# Moody's U.S. speculative-grade default rate

**File:** `moodys_spec_grade_default_rate.csv`
**Access date:** 2026-04-23

## Key caveats

- **Mixed series**: Moody's publishes separate trailing-12-month (TTM) default rates for US spec-grade HY *bonds* and US leveraged *loans*. 2025 values diverge materially (bond ~3.7%, loan ~5.9%). The CSV uses the HY bond rate as the canonical "spec-grade default rate" for continuity, per the research plan's "pick ONE" guidance.
- **Free-tier data is sparse**: Moody's full monthly default-rate history requires paid access (Default Report PDFs). Free summaries (S&P Global MI, Reuters, CFODive, LinkedIn) give scattered data points rather than a clean monthly series. Consequently many cells are blank; this is genuine sparsity, not fabrication.
- **Some values are forecasts, not realized.** The 2025-12 value of 3.2% and 2026-Q1 value of 4.0% are Moody's projections from their July 2025 report. Replace with realized data when Moody's publishes the year-end 2025 default report (typically late Jan / early Feb 2026, but I could not confirm its publication on the free web as of access date).
- The Sep 2022 figure of 1.5% is explicitly non-financial spec-grade; it is the closest contemporaneous Moody's-attributed US figure available in free summaries.

## Sources

1. **Moody's US Credit Review & Outlook — July 2025 (PDF)**
   https://www.moodys.com/web/en/us/insights/resources/us-report-july-2025.pdf
   (Binary content — not parsed. Secondary summaries below used for extraction.)

2. **Moody's Q1 2024 Credit Review & Outlook (PDF)**
   https://www.moodys.com/web/en/us/insights/resources/us-credit-review-and-outlook-q1-2024.pdf
   (Returned 403 on WebFetch attempt.)

3. **Moody's US Credit Review — cycle bottom elusive (PDF)**
   https://www.moodys.com/web/en/us/site-assets/us-corp-credit-report-cycle-bottom-elusive-for-corporate-credit.pdf

4. **Moody's December 2023 Default Report (Cloudfront)**
   https://dkf1ato8y5dsg.cloudfront.net/uploads/52/504/december-2023-default-report.pdf

5. **S&P Global Market Intelligence summary: Moody's sees US spec-grade peak 9.1% March 2021**
   https://www.spglobal.com/marketintelligence/en/news-insights/latest-news-headlines/us-speculative-grade-default-rate-to-peak-at-9-1-in-march-8211-moody-s-62225076

6. **S&P Global MI: Global spec-grade rate ended 2020 at 6.7% per Moody's**
   https://www.spglobal.com/marketintelligence/en/news-insights/latest-news-headlines/global-default-rate-for-speculative-grade-firms-ends-2020-at-6-7-8212-moody-8217-s-62377291

7. **CFODive: Moody's sees 2022 default rate rising**
   https://www.cfodive.com/news/default-rate-rise-2022-moodys/618900/

8. **LinkedIn (Moody's Ratings post, Jul 2025): 3.6% global default rate forecast**
   https://www.linkedin.com/posts/moodys-ratings_below-are-moodys-ratings-default-rate-forecasts-activity-7354131972526415872-PdWs

9. **Moody's data story: US corporate default risk in 2025**
   https://www.moodys.com/web/en/us/insights/data-stories/us-corporate-default-risk-in-2025.html

## Gaps to flag in the dashboard

- No reliable monthly or quarterly US spec-grade TTM series from free sources for 2019-2022. Values shown are year-end point estimates from press summaries, not a clean time series.
- 2021-12 and 2024-12 rows blank.
- The 2025 and 2026 figures are projections from mid-2025; the dashboard should flag these as estimates until Moody's releases the actual year-end report.
- For a cleaner series, user should obtain Moody's Default & Recovery Database (paid) or scrape dated PDFs of the monthly Default Reports.
