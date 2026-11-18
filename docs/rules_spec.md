# Rules spec (v1: listed equity, one financial year)

| Rule | Value | Status |
|---|---|---|
| Long-term holding period | more than 12 months | Verified |
| LTCG | 12.5% above Rs 1,25,000 per FY | Verified for FY 2026-27 |
| STCG (s.111A) | 20% | Verified |
| FIFO per demat account | s.45(2A), Income Tax Act 1961 | Verified for 1961 Act. **TODO: section number in the new Income-tax Act** |
| Cess | 4% | Known |
| Surcharge on equity gains | capped at 15% | **TODO verify.** v1 ignores surcharge |
| Set-off | ST loss vs ST and LT gain; LT loss vs LT gain only; carry forward 8 AYs | **TODO verify** FY 2026-27 carry-forward (conflicting source) |
| Grandfathering (bought before 31 Jan 2018) | caller supplies adjusted unit cost | **TODO confirm formula** |
| Brokerage, STT, DP charges | ignored in v1 (the solver does prefer fewer positions sold when tax ties) | Decision |
| NSE trading calendar | `calendars/nse_2026.json`: 16 weekday holidays + special Sunday sessions (1 Feb, 8 Nov). Sale date rolls to the next trading day. | **TODO verify against NSE circulars NSE/CMTR/71775 and NSE/CMTR/72260; add 2027 when NSE publishes it** |
| Trade date vs settlement date | v1 treats the trade date as the date of transfer; NSE settlement holidays differ from trading holidays | **TODO confirm with a CA** |

Primary sources to check: incometaxindia.gov.in (Act text), Finance Act 2024 and Budget 2026 memoranda.
Every parameter lives in `rules/fy*.json`. Never hardcode.
