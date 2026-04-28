# Fitch US Private Credit Default Rate

**File:** `fitch_private_credit_default_rate.csv`
**Access date:** 2026-04-23

## Key caveats

- **Fitch's Private Credit Default Rate (PCDR) was launched in August 2024** — no pre-August 2024 values exist in this series. The research plan asked for data "from 2019 (or earliest available) onward"; earliest available is Aug 2024.
- **Two distinct series:**
  1. **PCDR** (trailing 12-month, monthly, issuer-count basis). All monthly rows in the CSV.
  2. **Private Monitored Ratings (PMR) calendar-year default rate** (8.1% in 2024, 9.2% in 2025). Included as two "annual" rows. These are NOT directly comparable to the monthly TTM figures.
- **Gaps are real, not fabricated.** The monthly values come from scattered press releases and Fitch social-media posts; Fitch publishes periodically but not every month is picked up by secondary summaries. Months with no reliable secondary summary are left blank.

## Sources

1. **Bloomberg: Private Credit Default Rate Stood at 5% in August** (Sep 26, 2024)
   https://www.bloomberg.com/news/articles/2024-09-26/fitch-ratings-says-private-credit-default-rate-stands-at-5

2. **Funds Society: U.S. Private Credit Default Rate Continues to Climb**
   https://www.fundssociety.com/en/news/alternatives/u-s-private-credit-default-rate-continues-to-climb/
   (Used for Dec 2025 = 5.6%, Jan 2026 = 5.8%)

3. **Private Debt Investor: Fitch US private credit default rate hit 5.7% in February**
   https://www.privatedebtinvestor.com/fitch-us-private-credit-default-rate-hit-5-7-in-february/

4. **Fitch Ratings LinkedIn (Aug 2025): PCDR drops to 5.2% in July**
   https://www.linkedin.com/posts/fitch-ratings_privatecredit-default-activity-7364280299968512000-vZY-

5. **dmarketforces: US Private Credit Defaults Broaden Across Sectors, Rises To 5.7%** (Nov 2025 data)
   https://dmarketforces.com/us-private-credit-defaults-broaden-across-sectors-rises-to-5-7/

6. **dmarketforces: U.S. Private Credit Defaults Hit New Highs**
   https://dmarketforces.com/u-s-private-credit-defaults-hit-new-highs/

7. **Connect Money: U.S. Private Credit Default Rate Eases but Remains Elevated**
   https://www.connectmoney.com/stories/u-s-private-credit-default-rate-eases-but-remains-elevated/

8. **LinkedIn: US Private Credit Defaults Hit Record 9.2%** (Reuters summary, for calendar-year 2025 PMR)
   https://www.linkedin.com/posts/bridge-business-credit_us-private-credit-defaults-hit-record-92-activity-7443280941738938369-M8Wd

9. **Alternative Credit Investor: Fitch: US private credit defaults to rise in 2024**
   https://alternativecreditinvestor.com/2024/07/02/fitch-us-private-credit-defaults-to-rise-in-2024/

10. **LSTA Fitch Ratings Commentary Page** (index)
    https://www.lsta.org/content/fitch-ratings-commentary-page/

## Gaps to flag

- Oct 2024, Jan/Mar/Apr/May 2025, Aug/Sep 2025 monthly values missing.
- No data before Aug 2024 (series didn't exist).
- Dashboard should clearly distinguish monthly PCDR from calendar-year PMR — they are different default rates.
