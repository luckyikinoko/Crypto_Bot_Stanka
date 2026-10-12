# Round 5 — trend pullback reclaim

Status: registered, not evaluated. One candidate: `trend_pullback_reclaim_1h`.

The hypothesis is that a short pullback followed by recovery may precede renewed buying within an upward trend. This is a proposed mechanism, not evidence of an edge. The rule differs from the earlier unconditional lower-band re-entry and high-breakout candidates. It does not tune their parameters.

## Frozen entry and outcome

Use completed 1-hour candles. A signal occurs when all of these conditions hold:

1. Current EMA50 is strictly above current EMA200.
2. Previous close is at or below previous EMA20.
3. Current close is strictly above current EMA20.
4. The two candles are consecutive, belong to the same contiguous segment, and have finite required features.

Use existing SMA-seeded EMA definitions and gap resets. EMA200 needs 200 contiguous completed candles. Current equality with EMA20 or EMA50 equality with EMA200 does not qualify. Consecutive closes already above EMA20 do not create repeated signals. No RSI, ADX, volume, volatility or higher-timeframe filter is added.

The registered future outcome is a fixed 24-hour long-only hold, entering at the 5m open five minutes after decision. Exit is the last 5m close in that holding window. There is no stop, target, trailing rule or secondary horizon in this screen. Require complete execution paths; exclude boundary-crossing labels. Scheduling diagnostics impose a 60-minute cooldown after exit. This measures a signal; it is not a deployable risk policy.

Standard costs per side are fee 0.001, half-spread 0.00005 and slippage 0.00015. Conditional BNB uses fee 0.00075; stress uses fee 0.001, half-spread 0.0001 and slippage 0.0004. These are the existing frozen research scenarios, not verified account-specific historical fees. Standard is primary and positive stress expectancy is required.

The baseline is every causally eligible 1h decision, with identical warm-up/continuity availability, costs, execution and holding period, but without the trend/reclaim predicates. Buy-and-hold remains a separate exposure benchmark. Neither baseline average nor event-average return is a portfolio return.

## Dataset and accounting

Use only the reviewed repaired market snapshot pinned in REGISTRY.json. Training remains 2018–2023; 2024–2026 Q1 is reused recent history, not fresh validation. All data from 2026-04-01 onward remains blocked.

Registration and feature feasibility add no return tests. The existing revised ledger still has 35 tests. If outcomes are later evaluated, append exactly test 36 and retain all earlier p-values. Use 28-day paired calendar blocks, 7-day sensitivity, 4,999 bootstrap draws, seed 20261011, and BY correction across the expanded family. The earlier legacy project experiments are still outside this family. Adaptive research choices and repeated history use remain limitations despite the correction.

## Review checkpoints and stopping rules

This checkpoint registers the JSON specification and causal rule, tested only on synthetic features. It does not scan historical occurrences or outcomes.

Next is feature-only feasibility. Require at least 100 timing-eligible training observations, 50 scheduled nonoverlapping training events, 30 signal-active 28-day training blocks and 30 timing-eligible reused-recent observations. Report yearly counts and purged boundaries. Use the first eligible baseline decision's UTC day as block origin. Timing counts do not check full future paths and are not a statistical power calculation. Any failure stops the round without loosening thresholds.

Only after a separate review should outcomes be evaluated. The existing acceptance gates are retained: adequate complete sample counts, positive lower bounds of both net and baseline-excess 95% intervals, BY q < 0.05, positive stressed and nonoverlap training means, at least four positive training years, and positive standard/stress reused-recent means. Recheck sample gates after incomplete-path exclusions. Regime/year summaries are descriptive and must not select retrospective filters.

No parameter grid, alternative hold, stop/target search, automatic next round, holdout access, paper trading or live activation is part of this registration. A failed candidate is reported as failed. A passing screen would only justify proposing separate portfolio and walk-forward validation, not claiming profitability.
