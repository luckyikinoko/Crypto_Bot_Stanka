# Five-round evidence review

**All eight candidates remain rejected. No robust profitable edge has been established and no strategy is promoted.**

This review uses the repaired-data replay for rounds 1–4 and the registered round-5 result. It preserves the earlier original-data review and every negative result. No new market scan or hypothesis test is performed.

| Candidate | Train n | Standard net mean | Conditional BNB mean | Stress mean | Recent standard mean |
|---|---:|---:|---:|---:|---:|
| trend_breakout | 326 | -0.494% | -0.445% | -0.554% | -0.275% |
| trend_retest | 209 | -0.474% | -0.425% | -0.534% | -0.272% |
| range_rsi_recovery | 38 | +0.094% | +0.144% | +0.034% | -0.288% |
| trend_breakout_4h | 51 | +3.105% | +3.157% | +3.043% | +0.729% |
| trend_rsi_recovery_4h | 24 | +0.975% | +1.025% | +0.914% | -1.365% |
| unfiltered_breakout_4h | 598 | +0.729% | +0.780% | +0.669% | +0.377% |
| lower_band_reentry_1h | 1554 | -0.131% | -0.081% | -0.191% | +0.023% |
| trend_pullback_reclaim_1h | 1594 | -0.170% | -0.120% | -0.230% | -0.179% |

Means describe potentially overlapping events, not portfolio performance. Round 1 uses 15m signals with 2ATR/3ATR barriers and a 24h limit; rounds 2–3 use 4h signals and 72h holds; rounds 4–5 use 1h signals and 24h holds. Different exposures prevent ranking strategies by these means alone.

## Sample size versus uncertainty

| Candidate | Train nonoverlap n | Active 28-day blocks | Training net mean 95% interval | Sample gate failed? |
|---|---:|---:|---|---|
| trend_breakout | 115 | 38 | -0.668% to -0.348% | False |
| trend_retest | 94 | 37 | -0.691% to -0.314% | False |
| range_rsi_recovery | 37 | 25 | Unavailable: insufficient blocks | True |
| trend_breakout_4h | 23 | 16 | Unavailable: insufficient blocks | True |
| trend_rsi_recovery_4h | 16 | 13 | Unavailable: insufficient blocks | True |
| unfiltered_breakout_4h | 232 | 78 | -0.204% to +1.627% | False |
| lower_band_reentry_1h | 860 | 79 | -0.321% to +0.068% | False |
| trend_pullback_reclaim_1h | 585 | 74 | -0.437% to +0.088% | False |

Three candidates fail at least one registered sample requirement: range RSI recovery, filtered 4h breakout and filtered 4h RSI recovery. Their positive training averages cannot override sparse evidence. The unfiltered 4h breakout has a positive mean but its net/excess intervals cross zero and its multiplicity criterion fails. The two 1h recovery candidates have substantial samples, yet negative training net averages. More occurrences alone would not establish an edge.

## Transaction-cost attribution

The existing proportional cost formula can be inverted algebraically to recover mean gross return from mean net return. This adds no return test. It does not simulate a fee-free strategy, maker fills or market impact.

| 1h candidate / pool | Implied gross mean | Standard net mean | Conditional BNB net mean |
|---|---:|---:|---:|
| lower_band_reentry_1h / training | +0.109% | -0.131% | -0.081% |
| lower_band_reentry_1h / reused_recent | +0.263% | +0.023% | +0.073% |
| trend_pullback_reclaim_1h / training | +0.070% | -0.170% | -0.120% |
| trend_pullback_reclaim_1h / reused_recent | +0.061% | -0.179% | -0.129% |

Round 5 has small positive gross averages but negative net averages in both periods, including the conditional BNB scenario. That suggests cost drag exceeds its observed average move; it does not prove the gross relationship is statistically reliable. Reducing fees in a spreadsheet is not evidence that better execution is attainable. Do not waive standard/stress gates to rescue a rule.

## Statistical accounting

The ledger contains 28 descriptive signal/horizon comparisons and eight discovery candidates: 36 tests. Earlier IDs and p-values survive unchanged along the revised-report chain; BY q-values are recalculated as the family grows. Data revisions remain explicitly separate from original results. Earlier legacy experiments fall outside this family. Adaptive rule choice and repeated data reuse are not cured by the correction.

One descriptive comparison still has q < 0.05: bearish engulfing at 1h versus its unconditional baseline. Its net average is negative. Relative outperformance of a losing baseline is not a profitable long strategy. None of the eight candidates passes its full gate set.

Training is 2018–2023. Recent 2024–2026 Q1 has been reused repeatedly and is not fresh validation. Data from 2026-04-01 onward stays sealed.

## Data and execution limits

The verified repair added 240 5m candles and corrected seven, leaving 1,620 missing 5m candles. It did not increase fully warmed trend/volatility decision coverage. Replaying the first seven candidates preserved their mean returns and rejection decisions. Round 5 excluded nine training signals because of incomplete 5m paths. Excluding missing paths can create selection bias; none of these screens models managing an open position through an outage.

Nonoverlap schedules reduce repeated exposure but do not guarantee independent observations. Bootstrap intervals are approximate in changing markets. Closed-trade drawdowns omit intratrade portfolio risk. Conditional BNB fees depend on eligibility and inventory; actual historical fees, depth, market impact and maker fills are not established. Buy-and-hold is retained as exposure context, not comparable to event-average returns.

## Decision and next checkpoint

Close this eight-candidate set without parameter tuning or trading promotion. This result does not show that all BTC opportunities are absent; it shows these specified rules have not met the evidence requirements.

If research continues, the next bounded proposal is to expand the objective chart-pattern catalog with one causal definition, such as a confirmed double bottom, and test its recognition on synthetic examples before scanning history. First register confirmation timing, tolerances, warm-up, outcome horizon, costs and stopping rules. Do not choose parameters from favorable historical examples. Sparse feasibility should stop that candidate; sufficient frequency would only justify a separate outcome review. This review does not register or implement that next hypothesis.

No live/paper trading, holdout opening, automatic search or strategy selection is part of this checkpoint.

Machine-readable evidence: [evidence.json](evidence.json). Reproduce: `python -m research.diagnostics.review_round5`.
