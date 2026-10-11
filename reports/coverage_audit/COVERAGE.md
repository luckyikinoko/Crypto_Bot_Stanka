# Development data coverage and warm-up audit

Market data and strategy results are unchanged. No outcome labels or reserved observations were read. Scope: 2018-01-01 through 2026-03-31 UTC.

## Candle integrity

| Interval | Stored candles | Missing candles | Gap ranges |
|---|---:|---:|---:|
| 5m | 865596 | 1860 | 30 |
| 15m | 288525 | 627 | 30 |
| 1h | 72120 | 168 | 30 |
| 4h | 18005 | 67 | 30 |
| 1d | 2980 | 32 | 28 |

All 99 development monthly archive files match their recorded hashes and checksum sidecars. Stored partitions pass checksum/schema validation. Reaggregation of every 15m/1h/4h/1d candle from 5m inputs matches stored values exactly. Every higher-timeframe omission contains missing 5m members.

## Source evidence for missing 5m slots

| Classification | Missing slots |
|---|---:|
| quarantined_exact_open | 13 |
| absent_from_cached_archive | 1606 |
| overlaps_quarantined_off_grid_row | 241 |

Classifications are mutually exclusive: a valid archived row takes priority, then a quarantined exact open, then temporal overlap with an off-grid rejected row, then absence. An overlapping off-grid candle cannot be shifted or rounded onto the UTC grid without inventing a price path.

Reparsing affected monthly archives reproduces 254 quarantined timestamp rows. The per-gap evidence, source URLs, yearly coverage and all segment resets are in results.json. Exchange outage causes remain unconfirmed. The reserved 2026-04-01 daily source listed in historical metadata was explicitly skipped.

## Decision coverage after warm-up

| Interval / pool | Decisions | Unknown trend | Unknown volatility | Both ready |
|---|---:|---:|---:|---:|
| 15m / training | 209708 | 5958 | 7872 | 201836 |
| 15m / reused_recent | 78816 | 0 | 0 | 78816 |
| 1h / training | 52415 | 5448 | 7081 | 45334 |
| 1h / reused_recent | 19704 | 0 | 0 | 19704 |
| 4h / training | 13078 | 4464 | 5595 | 7483 |
| 4h / reused_recent | 4926 | 0 | 0 | 4926 |

The current definitions reset all indicator state after a missing bar. EMA200 requires 200 contiguous bars; trend is unavailable on the first 199. ATR14 plus 252 preceding ATR/close values makes volatility unavailable on the first 265 bars of each segment. At 4h that is over 44 days per fully warmable segment. Gaps close together can prevent readiness entirely. Unknown trend and volatility counts overlap and must not be added.

The audit does not treat reset-related loss as a software bug or recommend bypassing it. Indicators carried across gaps would be a different definition needing separate justification. Recent history has better continuity, so coverage is not uniform across research periods.

## Next recovery checkpoint

Use official daily archives or the public API only for the 30 documented development gap ranges. Compare exact timestamps, boundaries and OHLCV with the frozen monthly evidence; require valid complete candles and record provenance/conflicts. If sources agree the data is absent or malformed, retain the gap. Do not label the entire gap an exchange outage without supporting evidence.

Any verified additions must create a new market snapshot. Re-run affected feature calculations and registered experiments without changing their rules; keep original results. A recovery investigation may find no usable additions. This audit itself makes no repairs.

Official source format/checksum reference: https://github.com/binance/binance-public-data (checked 2026-10-11). Millisecond and microsecond source timestamps remain supported; the timestamp unit transition is not treated as a gap.

Reproduce: python -m research.diagnostics.coverage_audit

Source snapshot: ed2167a0ac3a875972f5cead7bdfc7b332a0b436ca2db8b84eb06fef9ff1a44d
