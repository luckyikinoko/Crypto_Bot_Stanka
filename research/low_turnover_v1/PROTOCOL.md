# Final bounded experiment — daily EMA200 trend baseline

**Specification only. No strategy code, historical signal scan or backtest has been run for this experiment.** One candidate, one primary comparison, no parameter search. Registration follows nine rejected candidates; this is adaptive exploratory research, not fresh confirmation.

## Duplicate check and reuse

No equivalent daily EMA200 position-state experiment was found in the inspected repository. The original `btc_backtest.py` uses hourly EMA200 context with 5m/15m signals, stops/targets and a 180-minute maximum hold. Experiment 001 removes a 60-minute early exit but retains that maximum. Experiment 002 changes intraday entries, retaining short exits. Discovery rounds 1–6 cover nine candidates with barrier or fixed 24h/72h outcomes. Buy-and-hold is already a benchmark, not the proposed daily switching rule. This search establishes no claim about experiments outside this repository.

Reuse the repaired Parquet data, UTC validation, reserved-data guard, SMA-seeded EMA calculation, cost scenarios, hashing and statistical helpers. Reuse portfolio accounting only after checking its assumptions. Do not copy the legacy 180-minute exit, 5% permanent drawdown halt, 1% daily loss halt, quarterly resets, stop/target logic or sizing into this distinct research baseline. Any eventual live strategy would require a separate risk policy.

## One frozen rule

- BTCUSDT Spot, long/cash only, daily decisions. Use complete 1d candles already derived from complete 5m members.
- Compute the existing EMA200: 200-close SMA seed, then alpha=2/201. Reset after a missing daily candle. Do not shorten warm-up, fill missing prices or download replacement datasets within this budget.
- At each completed UTC daily candle: desired position is long if close > EMA200; otherwise cash. Equality exits. When EMA is unavailable, remain cash or request an exit. The first eligible close can enter without requiring an earlier crossover.
- Enter or exit at the 5m open five minutes after the daily decision. Trade only when desired state changes; no daily rebalance while holding. Hold until the opposite state, missing-signal safety exit or pool end. No take-profit, stop, maximum holding time, trailing exit or cooldown search.
- Start each evaluation pool flat with 1,000 USDT. On entry invest all available cash including the buy fee; use fractional BTC for this idealized research baseline, no leverage. This is a normalized comparison, not an approved capital-allocation policy. Cash earns zero; taxes, funding and BNB inventory are not modeled.
- Charge frozen standard, conditional BNB and stress costs on each side. Standard is primary. BNB eligibility is conditional; it cannot rescue a failed standard/stress screen.

## Cheap preflight before portfolio implementation

Use only the pinned repaired snapshot, 2018-01-01 through 2026-04-01 exclusive. Training: 2018–2023. Reused recent: 2024–2026 Q1. Indicator warm-up may use earlier development candles, but no future candle. Never access the reserved pool from 2026-04-01.

Before building a runner, count daily decisions with a finite EMA200, without testing strategy returns. Require eligible daily decisions on at least **50% of all calendar days in training** and **80% in reused recent**, plus eligible decisions in at least **30 distinct 28-day training blocks**, anchored to 2018-01-01 UTC. These are coverage requirements, not power calculations. The existing data has 32 missing daily candles and repeated segment resets, so this gate may fail. If it fails, stop and report **insufficient data coverage**. Do not change EMA length, acquire more data, alter the split or start another candidate to bypass it.

## Portfolio paths and benchmarks, only if preflight passes

Run two separate continuous portfolios: training and reused recent. Do not reset quarterly or discard bad periods. Each pool begins flat and is liquidated at the last available 5m close strictly within its boundary. A final-day signal whose intended execution is outside the pool is ignored.

Missing prices are not silently removed. If a scheduled fill is missing, queue the desired action for the first available 5m open at or after its intended timestamp, charging normal costs and recording the delay. A missing daily candle makes desired state cash at its expected completion time; exit with the same five-minute delay/queue rule. Do not fill retrospectively before a gap. Keep any pre-existing position through an unobservable interval until an executable exit is available; never delete that trade.

Mark cash plus BTC at modeled liquidation value on every observed 5m close. Persist missing intervals and stale marks explicitly. **Any unobserved 5m interval while invested makes drawdown evidence incomplete and blocks promotion**, even if observed returns pass. Report the run as inconclusive due to data quality, without claiming a worst-case loss bound. This policy may end the experiment; it does not authorize a repair project.

Comparators share dates, capital and cost scenarios:
1. Full buy-and-hold BTC, buying at pool start plus five minutes, with the same fill queue and terminal liquidation.
2. Cash at zero yield.

Report total return/CAGR, daily and observed 5m maximum drawdown, Calmar, exposure, turnover, fees, spread/slippage drag, trade count and holding durations, annual returns, equity/drawdown charts and missing-data diagnostics. Keep the periods separate. Event win rate is not the selection metric.

## Frozen portfolio-level decision

The prior event-count gates are unsuitable for a low-turnover portfolio. The following new gates are declared before seeing this strategy's data; prior rejected results and gates remain unchanged.

Primary statistic: **training Calmar difference versus buy-and-hold**, with Calmar = CAGR / absolute maximum drawdown from UTC daily liquidation-value equity, including starting equity. Nonpositive or undefined drawdown/Calmar is inconclusive, not an automatic pass. Report observed 5m drawdown separately.

Uncertainty: paired circular moving-block bootstrap of strategy and buy-and-hold daily simple-return vectors, including cash days. Use 90-day blocks, 4,999 draws, seed 20261012; truncate sampled sequences to the original length and reconstruct equity to recalculate Calmar. No alternate block length is used for selection. The one-sided centered bootstrap p-value is `(1 + count(delta_boot - delta_observed >= delta_observed)) / (draws + 1)`. Require all bootstrap statistics finite; otherwise inconclusive. Intervals are approximate and do not establish stationarity or independence.

To merit a later, separate validation proposal, require ALL:
- The coverage gate and complete invested-path evidence pass in both pools.
- Standard and stress CAGR are positive in both pools.
- Daily maximum drawdown is at most 75% of the buy-and-hold drawdown in both pools.
- Standard CAGR retains at least 50% of positive buy-and-hold CAGR in each pool; if buy-and-hold CAGR is nonpositive, positive strategy CAGR is still required.
- The training 95% bootstrap lower bound for the Calmar difference is positive, and BY-adjusted q < 0.05 after appending this single primary comparison as test 38 to the pinned 37-test ledger.
- Reused-recent Calmar difference is positive; do not use that repeatedly reused period for parameter selection or label it fresh validation.

These are research selection thresholds, not guarantees or a deployable risk policy. A pass does not authorize opening the reserved pool, paper trading or live trading. A failure ends this candidate and this bounded search round, without tuning or a replacement hypothesis.

## Budget and deliverables

Two checkpoints only: this specification, then one result checkpoint. At the result checkpoint, perform the cheap coverage preflight first. Only if it passes, implement one narrow offline portfolio runner and validate its accounting with synthetic tests before one registered evaluation. Reuse existing modules; no refactoring project, dashboard, new pattern engine, external-data acquisition, grid search or automatic extra round. Correctness fixes may require a rerun, with the reason disclosed; they may not change strategy parameters or selection rules after results are seen.

No monetary credit cap has been specified, and actual account credit use is not visible to the assistant. This is a scope cap, not a promised price. Deliver one report with a reproducible manifest and one GitHub checkpoint, whether the result is failed preflight, rejected, inconclusive or eligible for a separate validation proposal.
