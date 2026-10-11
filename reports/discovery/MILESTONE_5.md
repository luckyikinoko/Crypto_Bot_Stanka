# Milestone 5 — registered strategy discovery

**No candidate passes. selected_strategy=null.** No strategy is promoted
to formal validation, paper trading or live execution.

## Registration and scope

Rules and gates were committed before computing new candidate outcomes in
[fe71eb7](https://github.com/luckyikinoko/Crypto_Bot_Stanka/commit/fe71eb70fa95804eca8271a1af34636b96214714).
See the [registry](../../research/discovery/REGISTRY.json) and
[protocol](../../research/discovery/PROTOCOL.md). Milestone 4 results were
already known; this is adaptive exploratory research, not independent confirmation.
There was no parameter sweep, alternate-exit selection or relaxation of gates.

The three long-only BTCUSDT Spot hypotheses use 15m decisions: trend-confirmed
resistance breakouts, trend-confirmed retests, and RSI recovery through 30 in
ranging markets. All share five-minute delayed entry, a 2-ATR stop, 3-ATR
target, 24h maximum hold and conservative stop-first intrabar treatment.
Previously implemented features, labels, costs and statistical tools are reused.

## Results after costs

Standard fees and spread/slippage assumptions are unchanged from Milestone 4.
2018–2023 is the screening pool; 2024–2026 Q1 is already reused stability data,
not clean out-of-sample validation. Returns below are per overlapping observation.

| Candidate | Training n | Mean net | Stressed mean | Recent n | Recent mean net |
|---|---:|---:|---:|---:|---:|
| trend_breakout | 326 | -0.494% | -0.554% | 240 | -0.275% |
| trend_retest | 209 | -0.474% | -0.534% | 135 | -0.272% |
| range_rsi_recovery | 38 | +0.094% | +0.034% | 26 | -0.288% |

Training 95% calendar-block intervals:

- trend_breakout: -0.668% to -0.348%.
- trend_retest: -0.691% to -0.314%.
- range_rsi_recovery: not reported: fewer than 30 active blocks.

Both trend candidates lose after costs in both pools. The RSI candidate has
positive training expectancy but insufficient occurrences and negative recent
results. No hypothesis earns promotion. These results concern the registered
definitions, not every possible version of these trading ideas.

## Risk and nonoverlap diagnostics

| Candidate | Training nonoverlap n | Mean net | Mean return / planned risk |
|---|---:|---:|---:|
| trend_breakout | 115 | -0.408% | -0.416 R |
| trend_retest | 94 | -0.491% | -0.391 R |
| range_rsi_recovery | 37 | +0.133% | -0.060 R |

The diagnostic scheduler locks out decisions through the full maximum hold
plus 60 minutes, even after an early barrier exit. Closed-trade drawdown,
dispersion, yearly results and fee scenarios are in results.json. These
diagnostics use complete paths; they are not a portfolio backtest through outages.
R normalizes returns by planned stop loss including stressed costs; gaps can
exceed that loss. It is not an annualized Sharpe or optimal sizing claim.

The registered research risk proposal is 0.5% equity risk, 25% capital cap, one
position, 60-minute cooldown and 2% daily loss including unrealized P&L. A
tested pure helper accounts for stressed stop costs and available cash. Exchange
rounding, minimum notional and daily-loss enforcement remain later validation
work. No order executor, daily-loss governor or trailing stop is activated.

## Rejection record

- **trend_breakout**: positive_net_ci, positive_excess_ci, multiplicity, positive_stress, positive_training_years, positive_nonoverlap, recent_standard, recent_stress.
- **trend_retest**: positive_net_ci, positive_excess_ci, multiplicity, positive_stress, positive_training_years, positive_nonoverlap, recent_standard, recent_stress.
- **range_rsi_recovery**: training_count, training_nonoverlap_count, active_blocks, positive_net_ci, positive_excess_ci, multiplicity, recent_count, recent_standard, recent_stress.

All 28 Milestone 4 tests plus the three new comparisons remain in the 31-test
exploratory BY correction. Ineligible tests use p=1. This accounting cannot
undo adaptive reuse, nonstationarity or uncertainty in bootstrap calibration.

## Benchmarks

Unconditional barrier longs, unfiltered breakouts and unfiltered RSI recovery
are descriptive ablations. Fixed-24h exits are secondary descriptions only.
Buy-and-hold is separate period-total-return context, not a per-trade mean:

| Period | Buy-and-hold total net | Observed 15m close drawdown |
|---|---:|---:|
| training | +207.548% | -81.559% |
| reused_recent | +61.105% | -52.182% |

One purchase and sale with standard costs; drawdown omits missing/intrabar
prices. Exposure and units differ from candidate diagnostics. Portfolio-level
risk-adjusted comparison remains Milestone 6 work, not a basis for promotion here.

## Tests, recovery and reproducibility

84 tests pass, including the 74 previous tests. New tests cover exact entry
conditions, unknown regimes, gap-safe RSI crossings, prefix invariance, ignoring
future-label columns, timestamp rejection, cooldown, primary-exit selection,
rejection gates, empty samples and cost-aware sizing/caps.
Artifact verification checks hashes, keys, chronological boundaries, 31-test
accounting and non-activation. Full replay is byte-identical.
Workspace maintenance removed the initial uncommitted implementation and data.
The registered GitHub rules were preserved. Code and datasets were reconstructed
and rerun; recovery.json documents comparisons with earlier data and numerical
results. No raw or reserved data is committed. No prior tracked report is replaced.

Snapshot: `b675865f382ec1658faab6d798c7aade8c697a3e77a5cf1370fad7e21344dad1`.

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -q
python -m research.discovery
python -m research.discovery.verify
python -m research.discovery.report
```

Requires a verified Milestone 4 data snapshot. See results.json, verification.json,
replay.json and recovery.json for evidence.

## Next review

Milestone 5 is complete with no eligible candidate. Stop before formal strategy
validation or paper trading. Further discovery would require a separately
registered mechanism and updated experiment ledger; do not tune these failed
rules until something looks profitable. Reserved data stays blocked; live trading
remains inactive.
