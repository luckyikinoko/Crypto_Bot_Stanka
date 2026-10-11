# Milestone 2 — Technical Indicator Engine

Completed 2026-10-11. Development features only; no strategy optimization, predictive
outcome analysis, chart formations or trading execution.

Implemented all requested initial indicator families: four EMAs and slopes, ADX/DI,
RSI, MACD, ROC, ATR, Bollinger bands/width, historical volatility, volume average,
relative volume, OBV, delayed swing confirmations, rolling support/resistance,
breakouts/breakdowns and distances from prior highs/lows. Configurable definitions
and initialization rules are documented in `docs/INDICATORS.md`.

Reused the existing validated market reader, gap-aware data, UTC availability
alignment, writer locking, atomic publication and content hashing. Existing trading
and backtest scripts were preserved. Separate smoothing avoids changing historical
backtest results. New features and raw data remain excluded from Git.

## Historical build

Range: 2018-01-01 through 2026-03-31 inclusive (UTC candle opens).
Source snapshot: `a4e0ec967b0f9ca39187429a5011b44d2ba23aa4ac4a61ce51a77196144c9569`.
Feature snapshot: `731876df485256348d5ca6a5ad5a852e4a545022a0e3bb893f08e8dea7aae8e1`.

| Timeframe | Feature rows | Contiguous segments | Rows with EMA200 |
|---|---:|---:|---:|
| 5 minutes | 865,596 | 31 | 859,427 |
| 15 minutes | 288,525 | 31 | 282,567 |
| 1 hour | 72,120 | 31 | 66,672 |
| 4 hours | 18,005 | 31 | 13,541 |
| 1 day | 2,980 | 29 | 1,159 |

Missing source candles are not filled. Every gap restarts indicator state and
warm-up. This materially reduces daily EMA200 availability: only 1,159 daily rows
qualify. Future hypotheses must account for this coverage rather than silently
forward-filling or treating missing indicators as neutral signals. Non-null counts
for every feature are in `quality.json`; swing event counts are not success metrics.

## Verification

- 55 tests passed, including all 44 existing regression/database tests.
- Independent hand-calculated seed, EMA, RSI, ATR, ADX, MACD, Bollinger, ROC,
  volume, OBV, support/resistance and volatility checks.
- Future-prefix invariance, all five timeframe calculations, gap-reset equivalence,
  delayed swing confirmation/ties, warm-ups, flat prices and zero volumes.
- Higher-timeframe close-time availability and expiry after a missing candle.
- Reserved-range guards, Parquet roundtrips, corrupt-file rejection and deterministic
  repeated publication.
- All 495 historical feature partitions checksum verified; rows sorted/unique,
  no infinite numerical outputs, and no rows beyond the development boundary.
- Full repeated build: identical snapshot ID; 495 partitions reused, zero rewritten.

Evidence: `quality.json`, `replay.json`, `verification.json` and
`tests/test_indicators.py`. Run `python -m unittest discover -s tests -q` and
`python -m research.indicators` to reproduce against the source snapshot.

## Limits and next step

Values are validated against explicit definitions and synthetic references, not
claimed to match every vendor's differing initialization convention. Historical
indicator availability does not establish profitability. Builds replay history
before reusing unchanged files; streaming state updates are not implemented.
No indicators were built for the reserved pool beginning 2026-04-01. 2024–2025
and 2026 Q1 remain already reused development data, not clean validation.

Stop for user review. Next is Milestone 3: a small, mathematically specified set
of chart patterns with causal confirmation, stored occurrence parameters, and
non-repainting tests. Statistical outcomes and profitability belong later stages.
