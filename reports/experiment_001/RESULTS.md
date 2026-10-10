# Experiment 001 — reject the time-exit revision

Protocol was committed at `c8b187b3c30e625b7ae11a850abe1a03965c2fff` before
candidate execution. No parameters were optimized after observing these results.

## Diagnostic observation

The original 68-trade sample included 33 time exits losing 27.57 USDT net.
The hypothesis was that removing the 60-minute early exit would permit trend
follow-through. The three-hour maximum and all other controls were retained.

## Continuous development simulation

January 2024–March 2026, initial equity 1,000 USDT:

| Variant | Trades | Final equity | Drawdown halt (UTC) |
|---|---:|---:|---|
| Original V1 | 68 | 955.46 | 2024-03-21 07:21 |
| No 60-minute exit | 61 | 953.56 | 2024-03-21 13:49 |
| No 60-minute exit; doubled execution cost | 59 | 953.56 | 2024-03-21 02:57 |

All remained in cash after the halt. The equal rounded final balances of the two
candidate runs reflect their risk thresholds, not identical trade outcomes.
Baseline replay reproduced the prior final equity and trade count exactly.

## Later development quarters

Eight independent episodes, 2024 Q2 through 2026 Q1. Each starts flat with
1,000 USDT; these are not a continuously compounded trading account.

| Metric | Original V1 | No 60-minute exit | Candidate, doubled execution cost |
|---|---:|---:|---:|
| Trades across episodes | 304 | 293 | 293 |
| Profitable quarters | 0 / 8 | 0 / 8 | 0 / 8 |
| Mean quarterly P&L, USDT | -26.09 | -29.04 | -32.57 |
| Sum of independent episode P&L, USDT | -208.70 | -232.30 | -260.53 |
| Pooled mean R per trade | -0.284 | -0.329 | -0.363 |
| Pooled net profit factor | 0.390 | 0.455 | 0.406 |
| Highest episode drawdown | 4.31% | 4.61% | 4.85% |
| Sum before explicit fees, USDT | -20.95 | -51.91 | -86.18 |

Before-fee figures still include modeled spread/slippage. Removing explicit fees
alone did not produce a positive total for either version. Profit factor improved
slightly for the candidate but remained far below 1, while net P&L and mean R
worsened. This is why selecting a variant by one metric would be misleading.

Seven-day circular block bootstrap, 2,000 draws, seed 1001: descriptive 95%
intervals for summed episode P&L were [-279.42, -140.44] USDT for V1,
[-318.91, -147.46] for the candidate, and [-347.68, -176.22] under stress.
These are conditional research summaries, not confidence about future deployment
returns; episode resets and hypothetical cash paths limit interpretation.

## Decision and limits

Reject the candidate: it passed only the >=200-trade sample gate and failed
positive expectancy, profit factor >1.20, improvement over baseline, and positive
stressed expectancy. Original V1 remains the code default for reproducibility,
not because it is approved for trading. No candidate progressed to paper/live.

All 18 automated tests pass, including candidate behavior at three hours, continued
stop/regime protection, and bootstrap constant/zero-series checks. Historical
baseline replay also passed. Tests verify selected software properties, not the
existence of an edge.

The final April–September 2026 holdout remains unaccessed. This was fixed temporal
evaluation on development quarters, not a full walk-forward optimization program.
News filtering remains disabled. The engine's documented quote-fee accounting,
price-tick, fill and slippage limitations remain unchanged.

Next research direction: revisit the entry/market-regime hypothesis and executable
cost budget instead of further tuning this exit rule. Pre-register any new candidate
and preserve this negative result. No additional candidate was tested here.

Detailed results: `quarters.csv`, `results.json`, and all six trade ledgers.
Reproduce with `python research_experiment.py` using the README's data download.
