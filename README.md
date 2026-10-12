## Current research checkpoint

Four discovery rounds are complete: seven registered candidates, none passing the statistical criteria. The cumulative Research Engine ledger contains 35 tests; earlier project experiments are disclosed separately.

See the [consolidated evidence review](reports/research_review/REVIEW.md) for results and limitations. The [coverage audit](reports/coverage_audit/COVERAGE.md) is now complete: 30 development gaps, exact higher-timeframe reaggregation, and substantial post-gap warm-up loss. The [daily-archive cross-check](reports/daily_recovery/RECOVERY.md) found 240 staged missing-candle candidates and seven conflicting existing candles. The [public-API reconciliation](reports/api_reconciliation/RECONCILIATION.md) confirms all 240 additions and supports the daily values for all seven conflicts. The [repaired snapshot](reports/repair_v1/REPAIR.md) now contains those changes in data/research_repaired_v1, with the original snapshot preserved. Missing 5m candles fell from 1,860 to 1,620. The [controlled research replay](reports/research_revision_v1/REPLAY.md) is complete: all seven candidates remain rejected, with unchanged mean returns and acceptance decisions. The revised 35-test ledger and reports are stored separately; default research inputs still point to the original data. Reserved data remains blocked. No strategy is selected and paper/live trading is inactive.

## Next registered research hypothesis (round 5)

[Trend pullback reclaim protocol](research/discovery_round5/PROTOCOL.md): one completed 1h close crossing above EMA20 while EMA50 > EMA200, with a fixed 24h outcome planned. Registration only; no historical occurrences or outcomes evaluated. The repaired market snapshot, revised 35-test prior ledger, costs and unchanged acceptance gates are pinned in [REGISTRY.json](research/discovery_round5/REGISTRY.json). Next checkpoint: feature-only feasibility, then review before outcomes. No candidate is selected for trading.

## Initial discovery checkpoint (round 1)

Milestone 5 is complete: **none of the three registered candidates passed**.
[Results and rejection reasons](reports/discovery/MILESTONE_5.md). No strategy is
selected for paper/live trading; reserved data remains blocked.

## Statistical research checkpoint

Milestone 4 is complete. [Results and charts](reports/statistics/MILESTONE_4.md)
show no established robust profitable edge. See the
[research protocol](docs/STATISTICAL_RESEARCH.md). Reserved data remains blocked.

## Chart-pattern checkpoint

Milestone 3 is complete: bull flags, resistance breakouts/retests and engulfing
candles. See [results](reports/patterns/MILESTONE_3.md) and
[definitions](docs/PATTERNS.md). Run `python -m research.patterns` and
`python -m research.patterns.verify`. Frequencies are not profitability evidence.

## Technical indicator checkpoint

Milestone 2 is complete. See [results](reports/indicators/MILESTONE_2.md) and
[definitions and usage](docs/INDICATORS.md). Build development-only features with
`python -m research.indicators`. Reserved data remains blocked; no live trading.

# BTC Research Engine V1 — current development priority

Milestone 1 adds a separate historical market database while preserving the
original strategy experiments below. No live trading is enabled.

- [Milestone 1 coverage, gaps and verification results](reports/market_database/MILESTONE_1.md)
- [Architecture, existing-code assessment and roadmap](docs/RESEARCH_ENGINE_PLAN.md)
- [Database commands, schema and integrity policy](docs/MARKET_DATABASE.md)
- `python -m market_data sync --start 2018-01-01`
- `python -m market_data.verify --native`

The database stores UTC 5m/15m/1h/4h/1d candles as monthly Parquet partitions.
Mechanical ingestion can include reserved dates; the research reader blocks them.
2024–2025 and 2026 Q1 are already-used development data, not clean validation.
Later milestones require user review; no indicators or patterns are added here.

---

# Crypto Bot Stanka — BTC Spot V1 research

Offline, long-only BTCUSDT backtester starting with **1,000 USDT**. No live trading,
API keys, leverage, shorting, or authenticated exchange endpoints. A profitable
strategy has **not** been established.

## Run

Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
python btc_backtest.py download --from-month 2023-11 --to-month 2026-03
python btc_backtest.py run --start 2024-01-01 --end 2026-04-01 --out reports/baseline
python btc_backtest.py run --start 2024-01-01 --end 2026-04-01 --slippage 0.0004 --out reports/stress
```

On Windows activate with `.venv\Scripts\activate`. All dates use UTC; `--end` is
exclusive. Downloads are official Binance monthly one-minute klines with SHA256
verification. Timestamp units switch from milliseconds to microseconds in 2025.
The importer normalizes both, rejects duplicate/missing minutes and invalid OHLCV,
and verifies checksums again on load. Raw market data stays out of Git.

**Holdout:** April–September 2026 is reserved and must not be downloaded for
strategy development. The January 2024–March 2026 run is a development baseline,
not out-of-sample evidence. November–December 2023 supplies indicator warm-up.

## Frozen V1 rules

Only closed candles inform decisions. Bars are UTC-aligned and right-labeled by
completion time. A signal at 12:05 uses data strictly before 12:05, then buys at
the 12:05 one-minute open with adverse execution cost. EMA uses alpha 2/(n+1);
RSI14 and ATR14 use Wilder smoothing with an initial arithmetic-mean seed.
At least 1,000 hours of input precede scored trading.

All entry conditions must hold:

- Hourly close above EMA200; EMA200 above its value five hours earlier.
- 15-minute EMA20 above EMA50; close above EMA50.
- At least one preceding three 5-minute candles has low <= its EMA20.
- Current 5-minute close above EMA20 and previous candle high.
- RSI14 in [45,65] and increasing.
- Volume >= 1.2 times mean volume of the preceding 20 five-minute candles.

Stop = min(lowest low of latest three 5-minute candles minus 0.1 ATR,
signal close minus 1.5 ATR). Accept only 0.4–1.2% stop distance, checked both at
signal close and next-minute reference entry. One position at a time, no scaling.

Risk budget = 0.25% of equity; entry notional <=35% of equity; available cash caps
size. Quantity is rounded down to the configured step. Sizing uses expected stop
execution and both fees, rather than a price-distance-only shortcut. The target
produces 1.5 times planned stop loss **net of modeled costs**. Fees default to
0.10% per side, combined spread/slippage to 0.02% per side. These are assumptions,
not verified account fees. Stress doubles execution costs while retaining fees.

Exit at stop, target, hourly close below EMA200, 180 minutes, or at 60 minutes if
net liquidation profit <0.3 times planned risk. The 60-minute test happens once.
Wait three full five-minute candles after an exit before re-entry.

## Execution and accounting assumptions

- All fills are market-like, adverse-price fills; targets also incur modeled
  slippage and taker fees. No guaranteed maker fills or queue priority.
- Both barriers inside one minute: stop first. A stop gapped through fills at the
  open, not the stop. Intraminute exits are timestamped at minute end because exact
  ordering is unknown. Partial fills and latency are not simulated.
- Fees use a **quote-currency equivalent model**. Actual Binance buy commissions
  deducted in BTC or paid in BNB are not yet reproduced. No BNB discount assumed.
- Quantity step 0.00001 BTC and minimum notional 5 USDT are research assumptions,
  not historical/current exchange metadata. Price tick rounding is not modeled.
  A live adapter must fetch symbol filters and use actual fee-asset accounting.
- Equity is marked to liquidation value, including modeled sell costs. Daily
  equity reference resets at UTC midnight. A 1% daily loss closes exposure and
  pauses until midnight; three consecutive net losses pause entries for the day.
  A 5% equity-peak drawdown closes exposure and permanently halts that simulation.
- Peak equity is sampled at minute opens/closes; intraminute highs do not raise
  the peak. Risk thresholds are checked against minute lows conservatively before
  profit targets. Gaps can exceed any loss threshold.
- Signals skipped during pauses/cooldowns are not queued. New signals are needed.
- Open positions are liquidated at the scoring period end and tagged accordingly.

Optional `--events events.csv` accepts a `time` column of UTC scheduled event
announcements. It blocks new entries from 30 minutes before to 30 minutes after.
No event dataset ships with this version; default runs have **no news filter**.
Historical event records must have been knowable at decision time.

## Outputs and research gates

Each run writes trade-level `trades.csv`, `daily_equity.csv`, and `summary.json`
with parameters and input hashes. Equity, net returns, net R expectancy, fees,
profit factor, drawdown, and exposure are included. Full-exposure buy-and-hold
with equivalent costs and cash are benchmarks; their risk differs from the bot.
Tests cover causality, stop/target ordering, gaps, risk limits, cash conservation,
fee-adjusted targets, Wilder initialization, and input validation.

Before any paper/live progression: walk-forward evaluation on development data,
block-bootstrap uncertainty, sensitivity checks, and one final sealed holdout
run. Provisional gates: positive unseen net expectancy; profit factor >1.20;
max drawdown <5%; positive expectancy under doubled execution costs; >=200 unseen
trades. Meeting thresholds is not proof of future profitability. Do not repeatedly
retune on the final holdout. This checkpoint implements the baseline simulator;
it does not claim the complete validation program is finished.

## Sources

- https://github.com/binance/binance-public-data
- https://github.com/binance/binance-spot-api-docs/blob/master/faqs/commission_faq.md
- https://github.com/binance/binance-spot-api-docs/blob/master/filters.md

## Experiment 001 — time-exit diagnostic

The single candidate disables only the 60-minute early exit. Default `Config()`
retains original V1. `Config(early_time_exit=False)` selects the research candidate.
The exact protocol was committed before candidate evaluation:
[research/EXPERIMENT_001.md](research/EXPERIMENT_001.md).

```bash
python research_experiment.py
```

This runs original V1 and the candidate over continuous development history, plus
fixed independent quarterly episodes for original V1, candidate, and stressed
candidate. Each episode resets to 1,000 USDT and retains risk halts. Pooled episode
results are diagnostic and must not be presented as a continuous strategy return.
A seeded seven-day block bootstrap describes realized-P&L uncertainty; it does
not reconstruct unobserved trades after risk halts. The runner rejects archives
from the reserved holdout or later dates. See `reports/experiment_001` for outputs.

Experiment 001 outcome: **rejected**. Both versions lost in all eight later
development quarters; removing the early exit worsened net results.
See [the experiment report](reports/experiment_001/RESULTS.md).

## Experiment 002 — trend-breakout entry

`python breakout_experiment.py` tests one pre-registered replacement entry:
15-minute close above the preceding 20-bar high, volume >=1.2 times its prior
20-bar average, and a rising hourly EMA200 with EMA50 above EMA200. All original
exit/risk rules remain, including the 60-minute exit. Baseline stays unchanged.

Protocol: [research/EXPERIMENT_002.md](research/EXPERIMENT_002.md).
These are **reused development periods**, not fresh out-of-sample evidence.
The six-month final holdout remains sealed. Results go to `reports/experiment_002`.

Experiment 002 outcome: **rejected**. The breakout candidate lost in all eight
quarterly episodes and hit its drawdown halt in the continuous run. See
[the breakout report](reports/experiment_002/RESULTS.md). No tested candidate
has met the research gates; original V1 remains only a reproducible reference.

## Execution/cost audit

Run `python cost_audit.py` for fee scenarios and reconciled fixed-trade cost
attribution. This is not a zero-cost strategy rerun. See
[the audit](reports/execution_audit/AUDIT.md). Actual account rates are still
unverified. Drawdown reporting now uses the risk engine's observed open/close
peak instead of close-only peaks; old result snapshots remain preserved.

## User-reported BNB fee setting

The account settings supplied imply a conditional 0.075% standard spot fee per
side, assuming discount eligibility and sufficient BNB. Stored as research
metadata in `config/binance_fee_assumptions.json`; historical defaults remain
unchanged. A complete V1 rerun using `--fee 0.00075` is preserved in
[the BNB fee report](reports/bnb_fee_v1/RESULTS.md). It still fails the screen.
BNB balances and depletion are not modeled; fees remain quote-equivalent costs.
