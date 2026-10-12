# Official daily-archive recovery cross-check

**Decision: conflicts_require_review.**

Checked 32 UTC days covering all 30 development gaps. 32 daily archives passed checksum and structural checks; 0 were missing or errored. Existing market data was not changed.

Recovery candidates: **240**. Conflicting overlapping candles: **7**. Comparison uses exact normalized numeric values; conflicts are never silently overwritten.

| Evidence for missing 5m slots | Count |
|---|---:|
| quarantined_exact_open | 12 |
| absent_from_cached_archive | 1608 |
| valid_daily_recovery_candidate | 240 |

Each downloaded ZIP is checked against its official SHA256 sidecar. Timestamps, OHLCV, candle boundaries and day membership are validated using the existing normalizer. Off-grid or partial source candles remain quarantined; they are not rounded, shifted or filled.

Daily archives provide an additional representation of official data, but may share their source with monthly archives. Agreement does not prove an exchange outage or prove no other source can recover the interval.

All daily source URLs, checksums, gap classifications, candidate timestamps and conflicts are recorded in results.json. Downloads and any candidate Parquet file are excluded from Git. The existing market snapshot, strategy reports and 35-test ledger remain unchanged.

## Next checkpoint

Source disagreements must be reconciled with bounded public-API evidence before applying corrections. The report records both stored and daily values for every conflicting field. Candidate candles remain staged and have not been promoted.

If there are no candidates or conflicts, a bounded public-API cross-check of these same development gaps is the remaining recovery option before accepting the documented gaps. If candidates exist, review source agreement and publish only verified additions into a new immutable snapshot, preserving the old one. Missing/error responses are unresolved, never evidence of zero recoverability.

No strategy outcomes were evaluated. Reserved data from 2026-04-01 onward was not requested. Paper and live trading remain inactive.

Reproduce: python -m research.diagnostics.daily_recovery. Cached archives are reverified on every read.

Source snapshot: ed2167a0ac3a875972f5cead7bdfc7b332a0b436ca2db8b84eb06fef9ff1a44d
