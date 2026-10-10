# Experiment 001: remove the 60-minute early exit

Frozen before candidate results, 10 October 2026. Parent: 49c1cd8.

Observed diagnostic sample: original V1's 68 trades, January–March 2024.
Time exits: 33 trades, -27.57 USDT net, -8.41 USDT before explicit fees
(after execution-price costs). This suggests testing whether premature exits harm
trend follow-through, but does not establish causation or justify the change.

One candidate only: disable the once-at-60-minutes exit for profit below 0.3R.
Keep the 180-minute maximum, entry signals, stops, fee-adjusted 1.5R targets,
position sizing, cooldown, daily limits, and permanent 5% drawdown halt unchanged.
No parameter search. Baseline remains the default configuration.

Evaluation planned before running:
1. Candidate continuous simulation January 2024–March 2026 at baseline and doubled
   execution costs; drawdown halts remain permanent, without account resets.
2. Eight fixed quarterly episodes April 2024–March 2026. Run original V1,
   candidate, and candidate with doubled execution costs in each quarter.
   Each episode starts flat at 1,000 USDT, with 1,000 hours of warm-up and all
   risk rules enabled. These independent research episodes are not one investable
   equity curve. Do not sum their percentages as compounded returns.
3. Report every episode, pooled per-trade expectancy/profit factor, and the
   number of profitable/ halted quarters. A fixed-seed seven-day moving-block
   bootstrap of daily realized P&L within quarters gives descriptive uncertainty;
   zero-trade days remain included. It is conditional on halted paths and not
   a risk forecast or proof of independence.

Retain candidate for further research only if its quarterly pooled net expectancy
is positive, profit factor >1.20, net P&L improves over V1, stressed pooled net
expectancy stays positive, and at least 200 trades exist across later quarters.
Even then, no deployment approval: quarterly resets cannot establish continuous
risk acceptability, and final holdout validation remains required.
If candidate fails, reject it. Do not tune another candidate in this experiment.

April–September 2026 is sealed: do not read or download it. Later development
quarters are temporal validation for this predeclared candidate, not the final
holdout, and must not be represented as a complete walk-forward optimization.
