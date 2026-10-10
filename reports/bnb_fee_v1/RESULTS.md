# V1 with conditional BNB-discounted fees

The user reports standard maker/taker rates of 0.10% and BNB payment enabled.
Binance documents a 25% discount on eligible standard spot commission when the
setting applies and sufficient BNB is available. This yields a conditional
0.075% per side. The account's actual discount eligibility, BNB balance and extra
charges were not independently verified. See `config/binance_fee_assumptions.json`.

Reproduction:
`python btc_backtest.py run --start 2024-01-01 --end 2026-04-01 --fee 0.00075 --out reports/bnb_fee_v1`

This is a full V1 strategy rerun with recomputed sizing, targets, decisions and
risk halts, not a fee subtraction from fixed trades. No rules were optimized.
Initial equity: 1,000 USDT. Development period: January 2024–March 2026.

| Metric | Conditional discounted run |
|---|---:|
| Trades | 69 |
| Final equity | 955.92 USDT |
| Net return | -4.41% |
| Net profit factor | 0.486 |
| Maximum sampled drawdown | 5.00% |
| Explicit fees | 31.83 USDT |
| Drawdown halt, UTC | 2024-03-24 22:02:00+00:00 |

After the drawdown halt, the account remains in cash for the remainder of the
period. Do not read the requested period as uninterrupted active trading.
The 0.10% original run ended at 955.46 USDT after 68 trades. Final balances across
halted runs are constrained by risk limits; survival time alone is not evidence
of a profitable strategy.

Decision: V1 still fails the profitability/risk screen at discounted costs. The
reserved April–September 2026 holdout remains untouched. This experiment does
not evaluate the other rejected entries under discounted fees.

Execution assumptions: spread/slippage 0.02% per side, market-like fills, fees
charged as quote-equivalent costs. No BNB reserve, BNB price exposure, fee-asset
rounding, depletion or top-up is simulated. Hence this run assumes the discount
remains funded throughout; it is not exact BNB wallet accounting. Existing
minute-bar and exchange-filter limitations remain. No real orders were placed.

Source checked 10 October 2026:
https://www.binance.com/en-AE/support/faq/detail/115000583311
