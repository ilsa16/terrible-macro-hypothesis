# SIFMA IG/HY corporate bond data

**File:** `sifma_ig_hy_issuance.csv` (renamed from `sifma_ig_hy_mix.csv` — see note below)

**Access date:** 2026-04-23

## Key caveat: outstanding vs. issuance

The research plan requested IG vs. HY *outstanding*. SIFMA's free public summaries consistently report:

- **Total** corporate bonds outstanding (not broken out by IG/HY in the free tier). Example: $11.0T in 2024, $11.4T in 2Q25, $11.5T in 3Q25.
- **Issuance** broken out by IG vs. HY annually.

The SIFMA Research Quarterly Fixed Income Outstanding PDFs do contain IG/HY outstanding breakdowns in internal tables, but the PDFs did not parse via WebFetch (binary content returned). An IG/HY *outstanding* split would require downloading the source xlsx / PDFs manually and extracting the tables.

Therefore the CSV holds what can be verified: total outstanding + IG/HY issuance. This file is named `sifma_ig_hy_issuance.csv` per the fallback instruction in the task brief.

## Sources

1. **SIFMA US Corporate Bonds Statistics landing page**
   https://www.sifma.org/research/statistics/us-corporate-bonds-statistics
   (The original URL in the task brief — `https://www.sifma.org/resources/research/us-corporate-bonds-statistics/` — returned 404 on 2026-04-23.)

2. **SIFMA Research Quarterly Fixed Income Outstanding 2Q25 (PDF, Sep 2025)**
   https://www.sifma.org/wp-content/uploads/2025/09/SIFMA-Research-Quarterly-Fixed-Income-O-2Q25.pdf
   (Binary fetch — not parsed. Summary: corporate bonds outstanding $11.4T in 2Q25.)

3. **Industry summary (CME OpenMarkets, Aug 2025)** — aggregates SIFMA data:
   https://www.cmegroup.com/openmarkets/interest-rates/2025/Corporate-Bond-Issuance-Grows-Along-with-Economic-Risks.html
   Reports 2024 total issuance $2.0T (+30.6% YoY), IG ~$1.5T (+24% YoY), HY $302bn, total outstanding $11T.

4. **VanEck 2025 Corporate Bond Market Trends**
   https://www.vaneck.com/us/en/blogs/income-investing/corporate-bond-market-trends-and-insights-a-2025-investors-guide/
   Cited for 2023 HY issuance $183.6bn.

5. **SIFMA Research Quarterly 1Q25 (PDF)**
   https://www.sifma.org/wp-content/uploads/2025/01/SIFMA-Research-Quarterly-Fixed-Income-IT-1Q25.pdf

## Gaps to flag in the dashboard

- No 2019-2022 IG/HY split in this dataset (not extracted from free tier SIFMA).
- No direct IG/HY *outstanding* split at any date (only total).
- To fill this gap, download the raw xlsx from https://www.sifma.org/research/statistics/us-fixed-income-securities-statistics and extract manually.
