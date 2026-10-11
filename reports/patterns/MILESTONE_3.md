# Milestone 3 — Chart Pattern Recognition

Completed 2026-10-11. Scope: three initial pattern families; no outcome analysis,
strategy selection or live trading. Definitions are in `docs/PATTERNS.md`.

## Implemented

- Fixed-window bull flags with ATR-adjusted pole, bounded retracement and width,
  nonpositive consolidation slope, volume contraction and close breakout.
- Rolling resistance breakouts and subsequent retests with frozen levels,
  expiry, invalidation and explicit parent event IDs.
- Bullish and bearish engulfing candles with a minimum ATR-adjusted body.
- Confirmed event records, geometric/volume metrics, contemporaneous indicator
  context, configuration/provenance and checksum-verified Parquet access.

Formation start/end timestamps are descriptive only; the confirmation close is
when a signal becomes available. Future bars never rewrite a previous event.
Bearish patterns are stored for context, not permission to sell short.

## Historical occurrences

2018-01-01 through 2026-03-31 UTC source candles; all five timeframes.

| Timeframe | Bull flags | Breakouts | Retests | Bullish engulfing | Bearish engulfing |
|---|---:|---:|---:|---:|---:|
| 5m | 46 | 36,589 | 21,735 | 49,318 | 48,667 |
| 15m | 23 | 10,926 | 6,552 | 15,259 | 15,038 |
| 1h | 10 | 2,693 | 1,587 | 3,352 | 3,381 |
| 4h | 0 | 769 | 465 | 744 | 789 |
| 1d | 0 | 135 | 76 | 150 | 118 |

Total stored events: 218,422.
Counts are overlapping observations, not independent trials or success rates.
The 23 bull flags on the primary 15m timeframe are a small sample. No thresholds
were relaxed to increase counts; none were optimized against returns. Zero flags
on 4h/1d means this exact definition detected none, not that flags cannot exist.

## Tests and verification

- 64 unit/regression tests passed, preserving the prior 55 tests.
- Known examples for every event type, exact confirmation timing and parent links.
- Retest invalidation, expiry, no same-bar retest, gap clearing and rejected flags.
- Prefix invariance across every prefix of known examples; all-timeframe timing.
- Typed Parquet roundtrip, deterministic publication, corruption and reserved guards.
- Full historical file checksums, unique IDs, ordering, timing and retest parents.
- First 1,000 source candles of each timeframe recomputed independently: all event
  records match the corresponding prefix of the full historical build.
- Full historical replay reuses all five files and produces the identical snapshot.

Commands: `python -m unittest discover -s tests -q`, `python -m research.patterns`,
`python -m research.patterns.verify`. Evidence: `quality.json`, `verification.json`,
`replay.json` and `data_recovery.json`.

## Recovery and provenance

Workspace maintenance removed the local datasets. Restored the GitHub checkpoint
and reacquired development history from official Binance archives using the
existing database pipeline. All 495 restored market partitions match the previous
checkpoint's logical hashes. Reserved data was not downloaded or analyzed.
Prior tracked Milestone 1/2 reports are preserved. The local restored source
snapshot ends at 2026-04-01; its narrower scope gives it a new snapshot ID.

Source snapshot: `ed2167a0ac3a875972f5cead7bdfc7b332a0b436ca2db8b84eb06fef9ff1a44d`.
Pattern snapshot: `b3461a92fd0f4f6bd1c9d11956e9b7541cb196cf8d544f9b8e3eb53f766a02d4`.

## Limits and next review

This is the deliberately small first pattern release. Other pattern families remain
deferred. The fixed bull flag is a simplified measurable hypothesis, not a claim
to capture every visual flag. Builds replay history rather than maintain streaming
pending state. Dataset files remain ignored by Git and can be reproduced.
No win rate, net expectancy or profitable edge has been established. No live
execution code was added. Reserved-pool restrictions and prior contamination
of 2024–2025/2026 Q1 remain unchanged.

Stop for review. Next: Milestone 4, separate future outcome labels, causal market
regimes, transaction-cost scenarios and dependence-aware statistical comparisons.
Pattern frequency must not be confused with evidence of profitability.
