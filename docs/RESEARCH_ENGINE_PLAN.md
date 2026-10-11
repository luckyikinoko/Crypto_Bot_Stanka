# BTC Research Engine V1 — architecture and milestone plan

Status: **Milestones 1–3 complete**. See `INDICATORS.md`, `PATTERNS.md` and the milestone
reports. No strategy search, outcome analysis, live execution, or automatic
milestone progression. The assessment below records the original pre-Milestone-1 state.

## Existing implementation assessment

Existing root scripts provide BTCUSDT one-minute ZIP ingestion, SHA256 validation,
UTC candle aggregation, a long-only simulator, accounting/risk controls, research
experiments, and 25 regression tests. Data is currently cached under `data/` for
November 2023–March 2026. There is no reusable multi-timeframe database, incremental
Parquet catalog, complete gap inventory, or safe research read interface.

Preserve the existing scripts, outputs and interfaces. Reuse their verified design
choices (Binance public archives, checksum verification, completed-candle UTC
semantics, numpy/pandas). `btc_backtest.bars`, `wilder`, and cost functions remain
candidates for Milestone 2/6; they are not imported into ingestion. The old validator
requires uninterrupted one-minute data; new history needs explicit gaps rather
than deleting or inventing observations. Hence ingestion gets a separate module.

## Proposed modules

- `market_data/`: official source client, canonical schema/validation, UTC
  aggregation, Parquet snapshot store, protected readers, CLI.
- `research/indicators/`: later causal features with warm-up definitions.
- `research/patterns/`: later confirmation-time pattern events.
- `research/regimes/`: later independent trend/volatility labels.
- `research/statistics/`: later outcome labels, uncertainty, dependent samples and
  multiple-hypothesis accounting. Outcome files remain separate from features.
- Existing backtester remains until a tested adapter is warranted. Later move to
  `backtest/` only if beneficial; no cosmetic rebuild now.
- `strategy/`: later frozen candidate definitions. `execution/`: later market-data
  only paper adapter, followed by separately approved live execution, if justified.
- `data/raw/`: cached official ZIP/checksum pairs and REST snapshots.
- `data/processed/`: content-addressed monthly Parquet partitions and atomic
  snapshot catalogs. Development and reserved data are logically separated by
  reader policy. Data is excluded from Git; reports/manifests are small and tracked.

## Milestone 1 data design

Instrument fixed to Binance BTCUSDT Spot. Base interval 5m, from 2018-01-01.
Prefer monthly official archives; use daily archives for an unpublished/current
month and supported public REST klines for the tail. Downloads cache verified raw
bytes and support bounded retries; rate-limit responses respect Retry-After.
Incremental updates reuse cached history and unchanged content-addressed partitions.
Explicit refresh permits archive corrections and records new source hashes.

Derived intervals: 15m (primary), 1h, 4h, 1d, UTC calendar-aligned. All expected
5m members must exist before a derived bar is stored. Never forward-fill gaps.
Cross-check samples with native archives. Keep original quote volume, trade count,
and taker buy volumes as well as OHLCV. Open time is the unique key per interval;
`available_at` is the exclusive close boundary, not the inclusive exchange close
field. REST/ZIP ingestion drops rows not completed by a captured UTC cutoff.

Reject malformed rows, invalid OHLCV, off-grid timestamps, conflicting duplicates,
or checksum mismatches. Identical overlapping rows deduplicate deterministically.
Report missing ranges (including requested boundary gaps), zero-volume counts,
dropped incomplete rows, source provenance and last completed time per timeframe.
Gaps are never silently repaired. A snapshot with gaps may be stored for audit,
but readers fail closed on missing intervals unless the caller explicitly allows
segmented data; calculations must reset warm-up after gaps in later milestones.

Publish a complete catalog by atomic rename only after all partition files exist.
Single writer lock; readers see either the old or new catalog. Orphan partitions
from interrupted updates are harmless and reusable. UTC timestamp Parquet schema;
Zstandard compression; per-month source and content hashes. Latest is defined by
the exchange server cutoff captured at sync start, not by a moving clock.

## Split policy and contamination history

- 2018–2023: research/training pool (newly acquired).
- 2024–2025 and 2026 Q1: **already reused development data**; cannot be described
  as clean validation/out-of-sample evidence after the prior experiments.
- 2026-04-01 onward: reserved evaluation pool. Ingestion performs mechanical
  integrity checks only. No return analysis, feature exploration, patterns or
  optimization on that pool in this milestone. Reader blocks overlap by default.

The user's full-history acquisition request authorizes storing and validating the
reserved data. This does not authorize researching its price outcomes. Thus
'untouched' now means unexamined for predictive/outcome research, not undownloaded.
Finalize a sealed evaluation protocol before accessing this pool for later tests.

## Testable roadmap (review required between milestones)

1. **Market database:** official acquisition, Parquet snapshots, incremental sync,
   gap/integrity reports, causal time alignment helpers, deterministic tests and
   sample native-timeframe checks. Gate: validated coverage or documented gaps,
   unchanged replay on repeated input, no partial candles, no historical files in Git.
2. **Indicators:** documented definitions/warm-up for requested indicators and
   multi-timeframe availability; reference values, prefix-invariance and gap tests.
3. **Patterns:** start with few objective definitions, confirmation timestamps,
   known examples and no repainting. Store parameters and strength, not promises.
4. **Statistical research:** causal regime features; separate future outcome paths
   at 1/4/12/24h, MFE/MAE, barriers, cost scenarios; chronological splits, overlapping
   event controls, dependence-aware intervals and hypothesis register/corrections.
5. **Strategy discovery:** small predeclared families, explicit sizing/exits and
   no-trade regimes. Report no edge if evidence is insufficient.
6. **Validation:** realistic backtesting, walk-forward, baselines, cost stress,
   final sealed test only after freeze. Account for all prior experiments.
7. **Paper trading:** only after evidence/review; market-data-only simulation,
   reconcile real-time fills/latency assumptions, never submit real orders.
8. **Controlled live:** separate explicit user approval after paper success;
   limited capital, monitoring and safeguards. Not implemented here.

Each milestone must preserve earlier behavior, have meaningful tests, a GitHub
checkpoint, and a report of scope, evidence, limitations and next review decision.
