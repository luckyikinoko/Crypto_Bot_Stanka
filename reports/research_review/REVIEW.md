# BTC Research Engine — consolidated discovery review

**No statistically robust trading edge has been established. All seven registered discovery candidates failed their screening criteria. No strategy advances to portfolio validation, paper trading or live execution.**

This review reconciles four completed discovery rounds. It adds no hypothesis tests, changes no rules, and reads no market or reserved outcome data.

## Evidence at a glance

| Candidate | Decision / exit | Train n | Train net mean | Stress mean | Recent n | Recent net mean |
|---|---|---:|---:|---:|---:|---:|
| trend_breakout | 15m; 2ATR stop/3ATR take; max24h | 326 | -0.494% | -0.554% | 240 | -0.275% |
| trend_retest | 15m; 2ATR stop/3ATR take; max24h | 209 | -0.474% | -0.534% | 135 | -0.272% |
| range_rsi_recovery | 15m; 2ATR stop/3ATR take; max24h | 38 | +0.094% | +0.034% | 26 | -0.288% |
| trend_breakout_4h | 4h; fixed72h | 51 | +3.105% | +3.043% | 48 | +0.729% |
| trend_rsi_recovery_4h | 4h; fixed72h | 24 | +0.975% | +0.914% | 22 | -1.365% |
| unfiltered_breakout_4h | 4h; fixed72h | 598 | +0.729% | +0.669% | 265 | +0.377% |
| lower_band_reentry_1h | 1h; fixed24h | 1554 | -0.131% | -0.191% | 612 | +0.023% |

Means are per potentially overlapping observation after costs. Different holding periods and exits prevent a direct ranking by these means. They are not annual returns, portfolio equity growth, or risk-adjusted performance.

## Why candidates failed

| Candidate | Training nonoverlap n | Active 28-day blocks | Training mean net 95% interval | Main limitation |
|---|---:|---:|---|---|
| trend_breakout | 115 | 38 | -0.668% to -0.348% | Negative net expectancy in both pools |
| trend_retest | 94 | 37 | -0.691% to -0.314% | Negative net expectancy in both pools |
| range_rsi_recovery | 37 | 25 | Unavailable: insufficient active blocks | Sparse training and negative recent result |
| trend_breakout_4h | 23 | 16 | Unavailable: insufficient active blocks | Too few independent episodes |
| trend_rsi_recovery_4h | 16 | 13 | Unavailable: insufficient active blocks | Sparse; negative recent and nonoverlap training result |
| unfiltered_breakout_4h | 232 | 78 | -0.204% to +1.627% | Net/excess intervals cross zero; multiple-testing gate fails |
| lower_band_reentry_1h | 860 | 79 | -0.321% to +0.068% | Negative training expectancy; recent result fails stressed costs |

The positive 4h breakout average is an uncertain exploratory result. It is not a selected strategy or evidence that its parameters should be optimized. The lower-band re-entry test had ample occurrences and still failed after costs. These results reject the specified rules under the stated assumptions; they do not establish that all momentum or mean-reversion approaches are unprofitable.

## Research accounting

- 28 Milestone 4 signal/horizon tests plus seven discovery candidates make the current 35-test exploratory family.
- The reconciliation verifies that every earlier ID and p-value survives unchanged in later ledgers; q-values are recalculated as the family grows.
- Earlier baseline, Experiment 001, Experiment 002 and BNB scenario work predates this family. The 35-test correction is not a claim to cover all historical project experimentation.
- Adaptive choice of new rules after seeing old results is not undone by BY correction. It cannot manufacture independent confirmation.

Training is 2018–2023. The 2024–2026 Q1 period has been repeatedly reused and must not be called fresh validation. Data from 2026-04-01 onward remains sealed. No final holdout should be opened to rescue a failed candidate.

## Data and execution limitations

The sample audit found 5,595 of 13,078 training 4h decisions (42.8%) without a volatility classification, with 31 contiguous segments. Repeated gap resets and warm-up materially reduce usable feature history. That is a coverage limitation, not evidence to waive warm-up. The simple breakout avoids this volatility filter but still fails the statistical screen.

All screens require complete 5m execution paths. Missing paths are excluded, creating potential selection bias if outages coincide with unusual conditions. A future portfolio simulator must define what an already-open position does through an outage; these event screens do not solve that execution problem.

Standard per-side costs are 0.10% fee, 0.005% half-spread and 0.015% slippage. The BNB scenario uses 0.075% fees conditionally; stress adds wider spread/slippage. Account-specific and historical fee eligibility are not proven. BNB inventory/depletion and realistic market impact are not modeled.

Nonoverlap scheduling reduces duplicated exposure but does not guarantee independent observations. Calendar-block intervals are approximate, particularly in changing regimes. Closed-trade drawdown omits intratrade portfolio marks. Buy-and-hold period totals cannot be compared directly with event-average returns.

## Recommended next checkpoint: coverage audit

Pause new strategy hypotheses for one development-only data-quality checkpoint:

1. Inventory missing 5m, 1h and 4h intervals and every segment reset from 2018 through 2026 Q1. Reconcile higher-timeframe omissions with missing or rejected 5m members.
2. Classify documented causes: source/archive absence, quarantined rows, aggregation requirements or confirmed exchange gaps. Leave unresolved causes explicitly unknown.
3. Recover only candles verifiable from official sources. Never synthesize prices, forward-fill gaps, bridge unverified missing periods or shorten warm-up to improve results.
4. Report decision coverage before/after warm-up by year and timeframe without calculating new strategy returns. Preserve old snapshots; version any verified repair.
5. If data changes, reproduce affected experiments under their unchanged rules and label those runs as data revisions. Preserve the original negative results and disclose the extra analysis.

After that audit, decide whether to stop discovery or register a bounded new family with an economic rationale, minimum sample plan and explicit stopping rule. Further parameter search on the current candidates is not the recommended next action. The audit recommendation is not authorization for live trading or opening reserved data.

## Implementation status

| Area | Current status |
|---|---|
| Historical database / indicators | Implemented; development coverage audit recommended |
| Pattern engine | Initial subset implemented; not the full requested pattern catalog |
| Outcomes and statistical screening | Implemented with costs, path checks and cumulative ledger |
| Strategy discovery | Four rounds completed; no candidate selected |
| Milestone 6 formal candidate validation | No candidate promoted; earlier legacy backtests remain reference work |
| Paper / live trading | Inactive |

The latest implementation checkpoint passed 104 unit tests and byte-identical round-four replay. This consolidation additionally verifies report digests, counts, ledger continuity and corrected q-values; it does not rerun market calculations.

## Source reports

- [reports/discovery/results.json](../discovery/results.json) — snapshot b675865f382ec1658faab6d798c7aade8c697a3e77a5cf1370fad7e21344dad1.
- [reports/discovery_round2/results.json](../discovery_round2/results.json) — snapshot e723d225549faf2ca16d4eb688093168810d0d71aa4adef3642ff5d2cfdbee9b.
- [reports/discovery_round3/outcomes.json](../discovery_round3/outcomes.json) — snapshot a41476e1527d37d9c386b6b2f03567781e05b45e4c25370d1da2408445fc0579.
- [reports/discovery_round4/results.json](../discovery_round4/results.json) — snapshot 831b82f75c2e12f5b8ddc206df6fb661599c18e667152aae0a82b69a43709461.

Machine-readable evidence: [evidence.json](evidence.json). Reproduce: python -m research.diagnostics.consolidate.
