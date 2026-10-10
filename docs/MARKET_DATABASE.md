# Milestone 1 operating guide

Python 3.11+, `pip install -r requirements.txt` (pandas, numpy, pyarrow).
Run from the repository root. Only public market-data URLs are used; no API keys.

```bash
python -m unittest discover -s tests -v
python -m market_data sync --start 2018-01-01
python -m market_data.verify --native
# Later incremental update, preserving start and existing history:
python -m market_data sync
```

Default root: `data/research/`. Existing `data/BTCUSDT-1m-*.zip` caches and old
backtest interfaces are preserved. Git excludes the entire data directory.
Use `--root` for a separate database; `--report-dir` for separate quality reports.
`--cutoff 2026-10-10T18:00:00Z` permits a reproducible complete-candle cutoff;
cutoffs after server time and shrinking an existing snapshot are refused.

First acquisition downloads monthly five-minute archives since 2018, daily
archives for the current/unpublished month, then REST for the last UTC day.
Subsequent runs reuse verified cached archives and unchanged Parquet partitions.
They reread history to validate it and fetch at most the current daily tail plus
new archives. Network work is incremental; full quality scanning remains intentional.
`--refresh` rechecks published archive checksums/corrections; it may redownload
history. No unattended scheduler is installed. Retry-After above 30s stops a run
for later retry instead of waiting indefinitely. Resume by rerunning the command.

## Storage contract

`data/research/catalog.json` points to an immutable snapshot of monthly
`processed/{interval}/{month}-{content_hash}.parquet` files. Versions of a changed
month coexist; only catalog-listed files belong to the current snapshot. A new
catalog is published atomically after files pass round-trip checks. Do not glob
all partitions to read a dataset, as that would include old versions.

Raw ZIPs and CHECKSUM sidecars preserve acquisition provenance. REST response
bodies are stored by SHA256. Historical raw cache files can be refreshed; processed
content-addressed snapshot versions remain. Sources and file/content hashes are
recorded in the catalog, `manifests/`, and a portable Git report (no price data).
A single-writer lock prevents overlapping syncs. If a process crashes, confirm it
has ended before deleting a stale `sync.lock`; do not remove a live writer's lock.

Schema: `open_time` and `available_at` are nanosecond UTC timestamps. Remaining
columns: open, high, low, close, base volume, quote volume, number of trades,
taker-buy base volume and taker-buy quote volume. Prices/volumes are float64;
trade counts int64. Symbol and interval are catalog/partition metadata. Source
inclusive close timestamps are validated, then normalized to exclusive
`available_at = open_time + interval`. No price analysis is performed at ingestion.

A 15m bar with open time 12:00 becomes available at 12:15. A decision at 12:14
cannot use it. `align_available` joins backward on availability and expires a
higher-timeframe value when the next bar should have become available but is
missing. Ingestion cannot enforce arbitrary downstream code: later feature tests
must preserve these boundaries and reset indicator warm-up across gaps.

## Research access and gaps

```python
from market_data.store import read_market
candles = read_market('data/research', '15m', '2024-01-01', '2024-02-01')
```

Dates select candle **open times**, with end exclusive. Default reader blocks
2026-04-01 onward and requests outside acquired coverage. It verifies file hashes
and fails on missing candles. `allow_gaps=True` explicitly permits segmented
history; never run rolling indicators across those gaps without a reset policy.
Milestone 2 will implement feature warm-up; no indicators are added in Milestone 1.

A missing source candle is neither zero volume nor an invitation to interpolate.
Zero-volume valid candles are retained and counted separately. Higher intervals
are derived only from complete five-minute groups, so some native higher bars may
be excluded around source gaps. Quality reports list exact missing UTC ranges and
counts, including leading/trailing coverage gaps. Gap presence is reported, not
hidden by silently truncating dates. It does not by itself prove source corruption
or an exchange outage; no cause is asserted without evidence.

## Verification outputs

- `quality.json`: requested bounds, last completed candle per interval, rows,
  gaps, incomplete rows removed, duplicates and fallback events.
- `manifest.json`: source URLs/SHA256, Parquet logical/file hashes, runtime version.
- `verification.json`: re-read checks plus native archive comparisons on Jan 2018,
  Jan 2024 and Jan 2025 across 15m/1h/4h/1d; no reserved-period crosschecks.
- Incremental replay test uses the same cutoff and compares all partition hashes.

Native comparisons use rtol 1e-9 / atol 1e-7 for float aggregation and exact trade
counts. Native-only rows near gaps are disclosed. These sampled comparisons do
not prove every archive has independently correct market values. Raw REST data
has a locally recorded hash, not Binance's published archive checksum.

## Research boundary

2024–2025 and 2026 Q1 have already informed failed strategy experiments. They are
reused development data, not a clean validation set. The newer pool is acquired
and mechanically checked because full-history storage is now requested, but no
patterns, outcomes, returns or optimization use it. No research-reader override
is exposed for that pool in this milestone. This is a programmatic guard, not an
OS access-control mechanism.

No live execution, paper trading, indicators or strategy discovery is implemented.
Milestone 2 begins only after the user reviews Milestone 1.

### Observed early-archive irregular timestamps

The acquisition encountered published 2018 records with off-grid open times or
shortened inclusive close boundaries. Strict normalization rejects them. The
archive collector explicitly quarantines these timestamp anomalies: raw ZIPs
retain the original row, and `quarantined_timestamp_rows` records source URL,
original timestamp integers, normalized UTC time and rejection reason. They are
excluded from standard-interval Parquet data and appear as gaps. No price/volume
values from an irregular candle are spread into neighboring candles. Other
structural errors (bad OHLCV, non-finite values, conflicting duplicates) still
fail acquisition. Native sample checks disclose their own quarantined-row counts.
