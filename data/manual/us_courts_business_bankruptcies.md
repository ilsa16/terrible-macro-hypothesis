# U.S. Courts business bankruptcy filings

**File:** `us_courts_business_bankruptcies.csv`
**Access date:** 2026-04-23

## Key caveat on chapter breakdowns

The AOUSC press releases report Chapter 7 / 11 / 12 / 13 totals for **all filings (business + nonbusiness combined)**, and a separate single-line total for business filings. They do **not** publish a business-only chapter breakdown in the press-release text. Table F-2 (the underlying PDF / xlsx) does have the breakdown, but the PDFs returned binary content through WebFetch and cannot be parsed here.

The CSV therefore holds only the total business figure per period (which is what's typically tracked in macro dashboards anyway). Chapter 7/11/13 columns are intentionally blank — leave them blank or fill manually from the F-2 xlsx.

An approximate reference (from the 2020 press release): of the 8,333 total Chapter 11 filings in 2020, 7,786 were business reorganizations. This suggests business-Chapter-11 ≈ ~93% of total Chapter 11 in that year, but this ratio is not constant across years and shouldn't be used to impute.

## Coverage

- Annual year-ending-December totals: 2019-2025 (7 complete years)
- Quarterly trailing-12M for 2025: Mar, Jun, Sep, Dec (Q1 '25 from May 1 release)

## Sources

1. **U.S. Courts bankruptcy filings statistics hub**
   https://www.uscourts.gov/data-news/reports/statistical-reports/bankruptcy-filings-statistics

2. **Jan 28, 2020 press release (calendar 2019 data)**
   https://www.uscourts.gov/data-news/judiciary-news/2020/01/28/bankruptcy-filings-increase-slightly

3. **Jan 28, 2021 press release (calendar 2020 data)**
   https://www.uscourts.gov/data-news/judiciary-news/2021/01/28/annual-bankruptcy-filings-fall-297-percent

4. **Feb 4, 2022 press release (calendar 2021 data)**
   https://www.uscourts.gov/data-news/judiciary-news/2022/02/04/bankruptcy-filings-drop-24-percent

5. **Feb 6, 2023 press release (calendar 2022 data)**
   https://www.uscourts.gov/data-news/judiciary-news/2023/02/06/bankruptcy-filings-drop-63-percent

6. **Jan 26, 2024 press release (calendar 2023 data)**
   https://www.uscourts.gov/data-news/judiciary-news/2024/01/26/bankruptcy-filings-rise-168-percent

7. **Feb 4, 2025 press release (calendar 2024 data)**
   https://www.uscourts.gov/data-news/judiciary-news/2025/02/04/bankruptcy-filings-rise-14-2-percent

8. **May 1, 2025 press release (TTM Mar 31, 2025)**
   https://www.uscourts.gov/data-news/judiciary-news/2025/05/01/bankruptcies-rise-131-percent-over-previous-year

9. **Jul 31, 2025 press release (TTM Jun 30, 2025)**
   https://www.uscourts.gov/data-news/judiciary-news/2025/07/31/bankruptcy-filings-rise-115-percent-over-previous-year

10. **Nov 24, 2025 press release (TTM Sep 30, 2025)**
    https://www.uscourts.gov/data-news/judiciary-news/2025/11/24/bankruptcy-filings-increase-10-6-percent

11. **Feb 4, 2026 press release (calendar 2025 data)**
    https://www.uscourts.gov/data-news/judiciary-news/2026/02/04/bankruptcy-filings-rise-11-percent

12. **Table F-2 PDF (Dec 31, 2024)** — for business-by-chapter if manually extracted
    https://www.uscourts.gov/sites/default/files/2025-01/bf_f2_1231.2024.pdf

## Gaps to flag

- Business-by-chapter breakdowns (Chapter 7/11/13) all blank. Requires manual extraction from Table F-2 xlsx files.
- No earlier 2019-2024 quarterly TTM data added — could extend by pulling the May/Jul/Nov press releases from prior years.
