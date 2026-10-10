# Milestone 1 — Historical Market Database

**Status: implemented, tested and populated; historical gaps documented.**
No indicators, pattern recognition, outcomes, strategy discovery, paper trading or
live execution were added. Existing scripts and historical experiment results
remain intact. Architecture and roadmap: `docs/RESEARCH_ENGINE_PLAN.md`.
Operating instructions: `docs/MARKET_DATABASE.md`.

## Acquired coverage

Instrument: Binance BTCUSDT Spot. Start: 2018-01-01 00:00 UTC.
Captured exchange cutoff: **2026-10-10 18:31:57.701000+00:00**. Latest completed base bar available
at **2026-10-10 18:30:00+00:00**. The source candle timestamps
use UTC throughout. The cutoff is fixed for this reproducible snapshot; later
completed candles require another incremental sync.

| Interval | Stored candles | Latest availability, UTC | Missing expected candles | Zero-volume candles |
|---|---:|---|---:|---:|
| 5m | 921,114 | 2026-10-10 18:30:00+00:00 | 1,860 | 54 |
| 15m | 307,031 | 2026-10-10 18:30:00+00:00 | 627 | 13 |
| 1h | 76,746 | 2026-10-10 18:00:00+00:00 | 168 | 0 |
| 4h | 19,161 | 2026-10-10 16:00:00+00:00 | 67 | 0 |
| 1d | 3,172 | 2026-10-10 00:00:00+00:00 | 32 | 0 |

Five-minute official monthly/daily archives plus a public REST tail are the source.
15m/1h/4h/1d candles are derived from complete UTC-aligned five-minute groups.
Parquet files use Zstandard compression, monthly partitions and content hashes.
The current snapshot contains 530 partitions. Raw and
processed data occupy approximately 48 MiB and 100 MiB respectively in this run;
versioned files may grow with subsequent updates. These datasets are excluded
from Git; sync commands and source checksums allow reconstruction.

## Quality findings

- Five-minute missing ranges: 30; missing base candles: 1860.
- Nonstandard timestamp records quarantined: 254.
- Identical overlapping rows removed: 0.
- Incomplete source rows excluded at the captured cutoff: 1.
- Original anomalous rows remain in verified raw archives. Their source URLs,
  timestamps and reasons are recorded in `quality.json`; no inferred replacements.
- Example gap: 2018-02-08 00:25 through 2018-02-10 06:15 UTC (end exclusive).
  No cause such as maintenance or outage is asserted without further evidence.
- Missing base candles invalidate their higher-timeframe group. Larger intervals
  therefore also have gaps. Native higher candles may exist for some such groups;
  they are deliberately not substituted into a mixed-definition dataset.

These findings mean the history is not gap-free. Default research reads refuse
ranges containing gaps. A caller can explicitly request segmented history, and
Milestone 2 must define indicator warm-up resets across those gaps.

## Verification evidence

- **44 unit/regression tests passed**, including all 25 previous tests.
- All 530 Parquet files re-read and checked for file hashes,
  logical hashes, row counts, schema validity and exact quality-report agreement.
- **12 native-timeframe checks passed**: January 2018, January 2024 and January
  2025, each at 15m/1h/4h/1d. Comparisons use all shared valid bars and report
  native-only rows. The check compares OHLC, base/quote volume, trade counts and
  taker-buy volume. It is a sampled independent aggregation check, not proof that
  every historical exchange value is economically correct.
- Same-cutoff replay: **530 partitions reused, zero rewritten**;
  every partition byte hash unchanged; all archives read from verified cache.
- Real incremental extension: **2 updated partitions,
  528 reused**. Every previously stored candle was compared
  and remained identical. One new completed 5m and one new completed 15m candle
  became available between the two captured cutoffs.
- Holdout-reader rejection, incomplete candles, timestamp units, conflict detection,
  missing groups, causal as-of joins, locks, corruption and interrupted publication
  behavior have targeted tests. No live orders or credentials are involved.

## Research split

2018–2023 is the training/research pool. **2024–2025 and 2026 Q1 have already
influenced prior experiments and are reused development data**, not clean
validation. From 2026-04-01 onward is reserved. Under the new full-history request
it has been stored and mechanically checked, but no predictive/outcome research
was performed. The default research reader blocks that pool entirely.

No profitable strategy claim is made in this milestone. The next milestone is the
technical indicator framework and its warm-up/reference-value/causality tests,
**only after user review**.

## Reproduce

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m market_data sync --start 2018-01-01
python -m market_data.verify --native
```

Use `--cutoff "2026-10-10 18:31:57.701000+00:00"` with a separate root to reproduce this cutoff.
Raw source corrections can change a later reconstruction; the committed manifest
records the exact source hashes used here. Old processed snapshots remain local.
Public sources: https://github.com/binance/binance-public-data and
https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints.
