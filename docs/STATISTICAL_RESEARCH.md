# Milestone 4 — frozen exploratory research protocol

Version 1 is specified before outcome inspection. The execution and indicator
parameters below are hypotheses, not an optimized strategy. Primary observations
are **15-minute decision times**. Pattern detection on other timeframes remains
available, but this experiment does not sweep their outcome statistics.

## Cohorts and causal features

Seven predeclared signal cohorts: bull flag, resistance breakout, resistance retest,
bullish engulfing, bearish engulfing, and two combinations:

1. EMA50>EMA200, RSI in [48,65], relative volume>1.3, normal 15m volatility,
   bullish trend on both completed 1h and 4h bars.
2. The same combination AND confirmed bull flag.

All returns are long-only; bearish engulfing is a contextual long-return cohort,
not a short strategy. The baseline includes every 15m decision, using identical
execution/horizon assumptions. Its overlapping returns are descriptive market
exposure, not a tradable simultaneous-position portfolio.

Trend and volatility are separate axes. Trend is bullish/bearish when EMA50 is
above/below EMA200 and ADX14>=25; otherwise ranging. Any unavailable input gives
unknown. Volatility uses ATR14/close compared with the 25th/75th quantiles of the
**preceding** 252 ratios, excluding current: low below the lower quantile, high
above the upper, normal otherwise. Warm-ups and gaps give unknown and reset state.
Thresholds are rolling, never fitted on the entire dataset. 1h/4h context uses
Milestone 1 availability joins with stale-bar expiry.

Features are stored separately from labels. Features contain no realized future
return, stop/take result or future regime. BNB eligibility is not an entry feature.
Research 2018–2023 and already-reused 2024–2025/2026 Q1 are reported separately.
Labels crossing the 2024 boundary have a separate `boundary_purged` pool instead
of contributing to either period-specific estimate. No part of this experiment is
clean out-of-sample validation. The reserved pool
beginning 2026-04-01 remains blocked; paths crossing its boundary are unavailable.

## Execution and path labels

Decision at the 15m exclusive close; entry at the 5m candle open **five minutes
later**, a deliberate bar-based latency assumption. Entry is not the signal close.
Exit after 1,4,12,24 hours measured from entry, at the final 5m candle close.
Missing entry, execution-delay gaps, internal path gaps or incomplete future paths
are labeled explicitly and excluded from return summaries, never filled. Incomplete
paths are excluded even if an early barrier hit exists, to use a common fully
observable horizon cohort. This is conservative censoring, not survival analysis.

Costs per side: standard fee .10%; conditional BNB fee .075%; stress fee .10%.
Base half-spread .005% plus slippage .015% per side; stress .01% plus .04%.
These are fixed user/project research assumptions, not verified historical account
fees, spreads or measured order-book impact. Both legs pay taker-equivalent fees.
BNB discount requires eligibility and funds; standard fees are the primary case.
No BNB inventory or tax/special commissions are modeled. Net return is
`exit_raw*(1-friction)*(1-fee)/(entry_raw*(1+friction)*(1+fee))-1`.

MFE=max(high)/raw_entry-1; MAE=min(low)/raw_entry-1. Times to the first extrema
are measured by 5m bar-end offsets (upper bounds, not exact tick times).
Potential stop/take levels are raw entry minus 2 entry-known ATR and plus 3 ATR.
Record whether each level is reached anywhere in the complete horizon and first
hit-bar times; these are not both realized exits. Separate barrier outcomes use
first hit, stop-first if both can be hit in the same 5m candle. A stop gap fills at
min(stop, bar open); take profit receives its level, without favorable gap credit.
Apply the same adverse friction and fees to these exits. No trailing stops or
position-size rules are optimized. Stops at nonpositive prices are invalid.

## Statistics and uncertainty

For each cohort/horizon/cost scenario: count, win rate, average/median return,
profit factor (undefined when no losses), average winner/loser, return quantiles,
MFE/MAE quantiles. Report regime, year and data-pool slices descriptively; no p-value
claims are made for those exploratory slices. Cost sensitivity and barrier outcomes
are separate; tests are not repeated to pick the best cost assumption or exit.

Primary inference tests **net excess mean over unconditional long returns**, not
just positivity during a rising BTC market. Calendar blocks of 28 days are sampled
with replacement, preserving all signal/baseline observations inside each block,
including their overlap. Report percentile 95% CIs for mean net return and excess;
center the bootstrap excess distribution for an approximate one-sided p-value.
Use 4,999 replicates, seed 20261011. A 7-day block result is sensitivity analysis,
not a second chance to select significance. Fewer than 30 signal-active 28-day
blocks gives no inferential claim; rare bull flags may remain ineligible.

The full family is seven signals times four horizons = 28 tests. Missing/ineligible
tests receive p=1; Benjamini-Yekutieli controls exploratory FDR under arbitrary
hypothesis dependence if marginal p-values are valid. Bootstrap inference remains
approximate: dependence beyond block boundaries and nonstationary BTC regimes can
invalidate its calibration. These are pointwise CIs, not simultaneous bands. An
adjusted q<.05 is not proof of a persistent or out-of-sample tradable edge.

Nonoverlap diagnostics greedily accept the earliest event whose decision is at or
after the previous label end. Compounded fully invested trade returns and maximum
drawdown at **closed-trade** times are diagnostics only: no mark-to-market path,
capital constraints, position sizing or risk limits. Open-trade drawdown may be
worse. These are not the strategy backtest of Milestone 6. Buy-and-hold and proper
portfolio benchmarks remain requirements of that later validation milestone.

## Reproduce

`python -m unittest discover -s tests -q`

`python -m research.statistics`

Requires restored `data/research` and `data/research_patterns` snapshots with matching
source IDs. Outputs go to ignored `data/research_statistics` with separate feature,
horizon-label and diagnostic Parquet files and an atomic provenance catalog.
Compact results, definitions and plots are tracked in `reports/statistics`.
No live order API is imported. Milestone 5 requires user review after this report.

Read using `research.statistics.store.read`: features when hours=None, labels when
a horizon is supplied. Label reads purge paths ending after the requested boundary.
Repeated analysis reuses checksum-verified labels only when source snapshot,
outcome/indicator code hashes and exact ID/time/ATR inputs match.

Verification: `python -m research.statistics.verify`. Figures: `python -m research.statistics.render`.
