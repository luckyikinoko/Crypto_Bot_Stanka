# Technical indicator engine — Milestone 2

This module computes features only. No outcomes, parameter search, strategy rules,
regime classification, chart formations or order submission are implemented here.
The old simulator and its definitions remain unchanged. New SMA-seeded smoothing
is deliberately separate from the old backtest helper to preserve prior results.

## Reproduce

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -q
python -m research.indicators
```

Requires the Milestone 1 market snapshot in `data/research`. The default range is
2018-01-01 inclusive to 2026-04-01 exclusive, measured by candle open time.
Both builder and feature reader reject reserved evaluation data. The source
reader's integrity checks are reused; missing intervals are explicitly allowed
only so the engine can reset calculations after each gap.

CLI options: `--source`, `--destination`, `--start`, `--end`, `--report`, `--config`.
Config is a JSON object of overrides for the frozen `Config` dataclass. Defaults
are definitions for research, not optimized parameters. Field names are stable
(e.g. `atr`); exact parameter values live in the snapshot manifest.

## Timing and missingness

All times are UTC. Features on a candle are available at its exclusive close
boundary `available_at`, never at its open. A simulated execution must occur
subsequently under a separately specified fill/latency model. Use
`market_data.schema.align_available` to join 1h/4h features to 15m decision times
by backward availability time, never by candle open time. Missing next higher
bars expire the old values; warm-up NaNs remain missing.

Every gap starts a new `segment_id`; all rolling/recursive state, OBV and remembered
pivots reset. `bars_since_gap` is one-based. NaN means unavailable, undefined, or
(for sparse swings) no event; it must not be treated as zero or forward-filled
by consumers. No global readiness flag is imposed: a hypothesis must require
nonmissing values for its actual inputs. A full warm-up makes a feature defined;
it does not imply absence of seed sensitivity or predictive usefulness.

## Exact definitions (default parameters)

Let C,H,L,V be completed candle close, high, low and base BTC volume. Periods count
observations within an uninterrupted segment. Returns and widths are fractions,
not percentages. RSI, ADX and DI are on a 0–100 scale.

| Output | Definition | First valid bar (one-based) |
|---|---|---|
| EMA20/50/100/200 | Seed arithmetic mean of first n closes; then alpha=2/(n+1) recursion | n |
| EMA slopes | EMA(t)/EMA(t-5)-1, a five-bar fractional change | n+5 |
| ATR14 | TR=max(H-L,abs(H-Cprev),abs(L-Cprev)); first TR=H-L. SMA seed, alpha=1/14 | 14 |
| RSI14 | Wilder smoothed gains/(gains+losses)*100; first change is missing | 15 |
| +DI/-DI | Wilder smoothed directional moves / ATR *100. First DM=0; +DM=up if up>down and up>0; -DM symmetric; ties=0 | 14 |
| ADX14 | Wilder mean of DX=100*abs(+DMsmooth--DMsmooth)/(+DMsmooth+-DMsmooth) | 27 |
| MACD | SMA-seeded EMA12-EMA26 | 26 |
| MACD signal/histogram | SMA-seeded EMA9 of MACD; histogram=MACD-signal | 34 |
| ROC12 | C(t)/C(t-12)-1 | 13 |
| Bollinger bands | SMA20 +/-2 population standard deviations (ddof=0) of close | 20 |
| Band width | (upper-lower)/middle | 20 |
| Historical volatility | Sample std (ddof=1) of 20 log returns *sqrt(365*1440/timeframe_minutes) | 21 |
| Volume MA20 | Mean including current candle | 20 |
| Relative volume | Current V / mean of preceding 20 volumes, excluding current | 21 |
| OBV | Starts at zero; adds sign(C-Cprev)*V | 1 |
| Support/resistance | Minimum low/maximum high over preceding 20 candles, excluding current | 21 |
| Breakout/breakdown | 1 if close strictly above resistance/below support, otherwise 0 | 21 |
| Distance from high/low | Close/resistance-1 and close/support-1 | 21 |
| Swing high/low | Strict high/low compared with two bars on each side; ties rejected | Earliest event at 5 |
| Last swing high/low | Most recently confirmed level, held only within the segment | After event |

RSI with no gains or losses is 50; only gains yields 100, only losses yields 0.
Zero TR yields DI=0; zero summed smoothed DM yields DX=0. Zero historical volume
baseline yields undefined relative volume (NaN). Flat volatility is zero.
Swing price is written at **confirmation time**, two bars after the actual pivot;
no past rows are rewritten. The pivot's open time is confirmation open time minus
two timeframe durations. Rolling support/resistance and confirmed swing levels
are distinct definitions. These are elementary structure features, not the
chart-pattern recognition milestone.

## Storage and reproducibility

`data/research_features/{timeframe}/{month}-{content_hash}.parquet` stores all five
timeframes. Atomic, content-addressed snapshots record source snapshot ID, engine
SHA256, configuration, Python/pandas/numpy/pyarrow versions, row/non-null counts,
and logical/file checksums. Read via `research.indicators.store.read_features`.
Feature catalogs never replace market catalogs. All datasets remain excluded from
Git; compact quality reports and code are committed.

Computation currently replays the requested history to preserve exact recursive
state; unchanged partitions are reused, so repeated publication does not rewrite
history. This is not a stateful streaming updater. Start dates define initialization:
use the full-history snapshot and slice via the reader for later research windows,
rather than recomputing at each train/test boundary. Source changes during a build
abort catalog publication. Interrupted builds can leave harmless orphan files.

Tests cover hand-computed values, warm-ups, prefix invariance, delayed pivots,
flat/zero-volume cases, gap resets, higher-timeframe availability/expiry, Parquet
roundtrips, repeat publication, corruption and reserved-range rejection. No claim
about strategy profitability follows from calculating these indicators.
