# Experiment 002 — Reject candidate

Rules were frozen in commit `8e2c202ef4f8113158cb3068f52ad8ec78247730` before candidate execution.
Only the entry logic changed: a volume-confirmed 15-minute breakout in a rising
hourly trend. Original stops, sizing, fees, risk halts, targets, and time exits
remain. See `research/EXPERIMENT_002.md` for all rules and gates.

## Continuous development simulation

January 2024–March 2026, starting with 1,000 USDT. Permanent drawdown halts
remain in force, and cash is held thereafter. No forced restart.

| Variant | Trades | Final equity, USDT | Net return | Drawdown halt, UTC |
|---|---:|---:|---:|---|
| baseline | 68 | 955.46 | -4.45% | 2024-03-21 07:21:00+00:00 |
| breakout | 116 | 953.20 | -4.68% | 2024-05-05 15:31:00+00:00 |
| breakout_stress | 103 | 952.66 | -4.73% | 2024-04-07 16:16:00+00:00 |

## Eight independent quarterly episodes

April 2024–March 2026; each quarter starts flat at 1,000 USDT. These episodes
are not a continuously compounded account and are reused development data.

| Variant | Trades | Profitable quarters | Mean quarterly P&L, USDT | Mean net R | Net profit factor | Halted quarters |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 304 | 0/8 | -26.09 | -0.284 | 0.390 | 0 |
| breakout | 369 | 0/8 | -31.71 | -0.286 | 0.368 | 0 |
| breakout_stress | 370 | 0/8 | -35.77 | -0.317 | 0.313 | 0 |

## Predefined gates

- positive_expectancy: FAIL
- profit_factor_above_1_20: FAIL
- improves_net_pnl: FAIL
- stress_positive: FAIL
- at_least_200_trades: PASS
- continuous_positive_no_halt: FAIL

Decision: **Reject candidate**. No live trading or paper-trading progression is approved.
All 21 unit tests pass. Historical baseline replay reproduces the saved original
result; default baseline code and the engine are unchanged by this experiment.

The final April–September 2026 holdout remains unaccessed. These reused periods
are exploratory research, not fresh out-of-sample proof. We tried exactly one
candidate here, with no post-result tuning. The results do not establish that all
breakout approaches fail; they concern this exact rule set and cost model.

Minute-bar ordering, fee-currency equivalence, price ticks, partial fills, latency,
and missing news-calendar data remain the limitations documented in README.
The seven-day circular block bootstrap is recorded in `results.json`; it describes
realized episode P&L conditional on these simulated paths, not future trading risk.

Detailed quarter results, parameters, hashes, and trade ledgers are preserved.
Reproduce with `python breakout_experiment.py` and then
`python research/render_experiment_002.py`.
