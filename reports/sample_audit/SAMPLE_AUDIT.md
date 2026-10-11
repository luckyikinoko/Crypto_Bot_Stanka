# Discovery sample-size audit

This audit preserves the two registered round-two rules. It counts filter, data-quality and overlap losses without comparing returns under alternative rules. No new hypothesis test is added.

| Pool / signal | Raw events | ATR valid | Bullish | Normal volatility | Complete in pool | Nonoverlap |
|---|---:|---:|---:|---:|---:|---:|
| training / trend_breakout_4h | 615 | 615 | 143 | 55 | 51 | 23 |
| training / trend_rsi_recovery_4h | 455 | 455 | 57 | 28 | 24 | 16 |
| reused_recent / trend_breakout_4h | 265 | 265 | 88 | 48 | 48 | 20 |
| reused_recent / trend_rsi_recovery_4h | 194 | 194 | 51 | 22 | 22 | 17 |

Counts are sequential and order-dependent: a loss at a filter is not evidence that removing that filter improves trading performance. Nonoverlap uses the registered 72-hour hold plus 60-minute cooldown.

## Regime availability at events

Trend counts at raw events separate unavailable warm-up from observed bearish/ranging conditions. Volatility counts apply after the bullish filter.

- training / trend_breakout_4h: trend {'unknown': 205, 'ranging': 182, 'bullish': 143, 'bearish': 85}; volatility after bullish {'normal': 55, 'high': 41, 'low': 25, 'unknown': 22}.
- training / trend_rsi_recovery_4h: trend {'unknown': 148, 'bearish': 130, 'ranging': 120, 'bullish': 57}; volatility after bullish {'normal': 28, 'unknown': 11, 'low': 9, 'high': 9}.
- reused_recent / trend_breakout_4h: trend {'ranging': 135, 'bullish': 88, 'bearish': 42}; volatility after bullish {'normal': 48, 'low': 20, 'high': 20}.
- reused_recent / trend_rsi_recovery_4h: trend {'bearish': 77, 'ranging': 66, 'bullish': 51}; volatility after bullish {'normal': 22, 'high': 21, 'low': 8}.

## Data exclusions

- training: 13078 decisions; 31 contiguous segments; unknown trend on 4464 decisions and unknown volatility on 5595 (these can overlap).
  - trend_breakout_4h: incomplete {'path_gap': 4}; complete labels crossing pool boundary 0; overlap/cooldown removes 28.
  - trend_rsi_recovery_4h: incomplete {'path_gap': 4}; complete labels crossing pool boundary 0; overlap/cooldown removes 8.
- reused_recent: 4926 decisions; 1 contiguous segments; unknown trend on 0 decisions and unknown volatility on 0 (these can overlap).
  - trend_breakout_4h: incomplete {}; complete labels crossing pool boundary 0; overlap/cooldown removes 28.
  - trend_rsi_recovery_4h: incomplete {}; complete labels crossing pool boundary 0; overlap/cooldown removes 5.

## Interpretation and next step

The sequential counts distinguish restrictive rules, unavailable regime labels, missing execution paths and overlap. A low number of missing execution paths does not imply full historical coverage: indicator warm-up after gaps can also exclude many decisions. Neither existing candidate is promoted. Filling missing candles, counting overlapping signals as independent trades, or relaxing gates would not supply independent evidence.

Before another outcome screen, preregister a small, simpler family with an explicit economic hypothesis and check feature-only occurrence counts. Sample size is a feasibility check, not proof of an edge. Keep a record of every frequency check and candidate considered, because feature-driven selection is still adaptive. Retain the cumulative test ledger and keep the reserved pool sealed.

## Reproduce

Run python -m research.diagnostics.sample_audit. The command checks input hashes, reconciles all usable/nonoverlap counts against the frozen discovery report, and reads only timing/status columns from future labels. results.json includes yearly and quarterly counts.

Source snapshot: e723d225549faf2ca16d4eb688093168810d0d71aa4adef3642ff5d2cfdbee9b
