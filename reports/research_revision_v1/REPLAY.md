# Repaired-data research replay

Data revision sensitivity analysis, not independent replication or fresh out-of-sample evidence. 2024-2026Q1 is reused. Reserved data from 2026-04-01 remains blocked.

All existing rules, execution costs, bootstrap settings and acceptance criteria were retained. Original reports and data are preserved. This replay adds no hypotheses; the existing ledger still contains 35 tests. Earlier project experiments remain outside this ledger, as previously disclosed.

| Candidate | Training n before → after | Training mean net before → after | Recent mean net before → after | Pass after |
|---|---:|---:|---:|---|
| trend_breakout | 326 → 326 | -0.494381% → -0.494381% | -0.275065% → -0.275065% | False |
| trend_retest | 209 → 209 | -0.474400% → -0.474400% | -0.272092% → -0.272092% | False |
| range_rsi_recovery | 38 → 38 | 0.094160% → 0.094160% | -0.287774% → -0.287774% | False |
| trend_breakout_4h | 51 → 51 | 3.105091% → 3.105091% | 0.729357% → 0.729357% | False |
| trend_rsi_recovery_4h | 24 → 24 | 0.974626% → 0.974626% | -1.365184% → -1.365184% | False |
| unfiltered_breakout_4h | 598 → 598 | 0.729339% → 0.729339% | 0.376829% → 0.376829% | False |
| lower_band_reentry_1h | 1554 → 1554 | -0.130888% → -0.130888% | 0.023057% → 0.023057% | False |

No strategy is selected. These are overlapping signal outcome statistics, not portfolio returns. Detailed uncertainty, costs, non-overlap diagnostics and failed criteria are in comparison.json and each stage report.

Reproduce from the repository root with `python -m research.diagnostics.replay_repair`. Existing output directories are rejected; use `--destination` and `--report-dir` with fresh paths for another run. Reconstruct the parent and repaired market snapshots first if local ignored datasets are absent.

## Data revision effects

| Outcome horizon | Complete labels before | Complete labels after | Added |
|---|---:|---:|---:|
| 1 hours | 288,380 | 288,455 | 75 |
| 4 hours | 288,008 | 288,071 | 63 |
| 12 hours | 287,016 | 287,047 | 31 |
| 24 hours | 285,538 | 285,538 | 0 |

The recovered segment adds 80 primary-timeframe decisions. More decisions also encounter the surrounding gaps, so excluded-label counts can rise while coverage improves. No additional full 24-hour paths become usable. Existing candle corrections produce small changes in some descriptive statistics. All seven candidate mean returns are exactly unchanged; their failed acceptance criteria are also unchanged. The existing bearish-engulfing/1-hour comparison still has BY-adjusted q = 0.0290 for excess return over its unconditional baseline. Its average net return remains negative, so that relative result does not establish a profitable long strategy. None of the seven strategy candidates passes its acceptance criteria.

## Validation

119 unit tests passed. Stored patterns passed checksum, timing, parent-event and historical-prefix checks across all five timeframes. Feature/label separation, entry/exit timing, split boundaries, reserved-data boundaries, hypothesis accounting and decision gates passed verification. All original protected report, registry and market-catalog hashes remained unchanged. Recent candidate statistics are exactly unchanged.

Run artifact checks with `python -m research.diagnostics.verify_replay`. Machine-readable comparisons for all 32 descriptive cohorts (28 registered tests plus four unconditional baselines) are in `validation.json`.

## Next checkpoint

Review a small, explicitly registered next research family before evaluating outcomes. Existing candidates remain rejected; parameter tuning or use of the reserved pool is not justified by this repair. Paper and live trading remain inactive.
