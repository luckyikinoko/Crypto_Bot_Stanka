# Initial development baseline — 10 October 2026

**Decision: reject V1 for progression to paper/live trading.** These are historical
simulations under documented assumptions, not actual trading results or forecasts.

| Metric | Baseline | Doubled spread/slippage |
|---|---:|---:|
| Starting equity | 1,000 USDT | 1,000 USDT |
| Final equity | 955.46 USDT | 953.56 USDT |
| Net return | -4.45% | -4.64% |
| Closed trades | 68 | 64 |
| Net win rate | 26.47% | 26.56% |
| Net profit factor | 0.488 | 0.447 |
| Mean net R per trade | -0.268 | -0.297 |
| Maximum drawdown | 5.04% | 5.00% |
| Modeled fees | 40.15 USDT | 36.21 USDT |
| Drawdown halt (UTC) | 2024-03-21 07:21 | 2024-03-13 20:04 |

Requested scoring range: 2024-01-01 through 2026-03-31. Each run permanently
stopped entering trades at its drawdown halt and remained in cash for the rest of
the range. **This does not represent 27 months of active strategy trading.**
The baseline exceeded 5% slightly because risk exits can gap through the threshold.
No reset was applied to make subsequent results look better.

Data: 29 checksum-verified monthly Binance BTCUSDT one-minute archives, November
2023 through March 2026. November/December 2023 are warm-up. April–September 2026
remain sealed and were not downloaded. All source hashes are in each summary.
Python 3 runtime with pandas 2.2.3 and numpy 2.3.5; run commands are in README.

The baseline's gross trade P&L after modeled execution-price costs but before
explicit fees was approximately -4.39 USDT; fees then contributed 40.15 USDT to the
net loss. Thus the evidence does not support an underlying positive edge even
before explicit commissions. The most frequent exit was the time rule (33/68).
These observations are diagnostic; they do not prove any single parameter caused
the failure or that removing it would improve unseen performance.

The news filter was disabled: no historical scheduled-event dataset was supplied.
Fee assets, price ticks, partial fills, and latency remain approximations as
explained in README. No optimization, full walk-forward program, bootstrap
confidence claim, or holdout evaluation was performed. The baseline already fails
the preliminary expectancy/profit-factor/drawdown gates and has insufficient
out-of-sample evidence. The 14 automated tests verify selected implementation
properties; they do not establish profitability.

Next research step: diagnose losing and time-exit trades on development data,
pre-register a small, economically motivated alternative, and evaluate it with
chronological walk-forward tests before opening the holdout. Preserve this baseline
and keep transaction costs in every experiment.
