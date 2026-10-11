# Milestone 5 — discovery round 2

**Neither candidate passes. No strategy selected.**

Two four-hour hypotheses and unchanged screening gates were registered before evaluation in commit 725762d. Each uses a fixed 72-hour hold and five-minute delayed entry. The 2-ATR stop / 3-ATR target is descriptive only. See research/discovery_round2/PROTOCOL.md and REGISTRY.json.

Training is 2018–2023. Recent history is 2024–2026 Q1 and has already been reused. This is adaptive exploration, not independent out-of-sample validation. Reserved data from 2026-04-01 onward remains blocked.

## Primary results after standard costs

Means are per completed, potentially overlapping observation; they are not portfolio returns.

| Candidate | Train n | Train mean | Stress mean | Recent n | Recent mean |
|---|---:|---:|---:|---:|---:|
| trend_breakout_4h | 51 | +3.105% | +3.043% | 48 | +0.729% |
| trend_rsi_recovery_4h | 24 | +0.975% | +0.914% | 22 | -1.365% |

## Evidence limits

- trend_breakout_4h: 23 nonoverlapping training observations, 16 active 28-day blocks. Failed gates: training_count, training_nonoverlap_count, active_blocks, positive_net_ci, positive_excess_ci, multiplicity, positive_training_years.
- trend_rsi_recovery_4h: 16 nonoverlapping training observations, 13 active 28-day blocks. Failed gates: training_count, training_nonoverlap_count, active_blocks, positive_net_ci, positive_excess_ci, multiplicity, positive_training_years, positive_nonoverlap, recent_count, recent_standard, recent_stress.

Both fail the minimum 100 training observations, 50 nonoverlapping observations and 30 active blocks. Neither is eligible for a bootstrap confidence interval or significance claim. The seven-day sensitivity also has fewer than 30 active blocks. Ineligible p-values are set to 1 in the cumulative 33-test BY ledger. Correction does not undo adaptive reuse.

The breakout mean is positive but concentrated in too few episodes. RSI recovery has negative nonoverlapping training expectancy and negative recent expectancy. No threshold was relaxed and no alternate exit was selected.

## Execution, integrity and reproducibility

Standard per-side assumptions: 0.10% fee, 0.005% half-spread and 0.015% slippage. Conditional BNB scenario: 0.075% fee only when applicable; stress: 0.10% fee, 0.01% half-spread and 0.04% slippage. These are frozen research assumptions, not verified account charges.

18,004 completed 4h decisions were evaluated. Label status counts: {'complete': 17470, 'path_gap': 514, 'insufficient_future': 18, 'missing_entry': 2}. Missing paths are excluded, never filled. Pool-crossing labels are purged; exclusion counts are in results.json. Features and future labels are saved separately in checksum-verified Parquet files.

The fixed hold uses all 864 five-minute candles after entry. Nonoverlap diagnostics lock the full hold plus a 60-minute cooldown. Closed-trade drawdown omits intratrade portfolio mark-to-market and is not a portfolio risk estimate. Buy-and-hold context is retained from the earlier report; period-total returns are not directly comparable to per-observation means.

89 unit tests pass, including new 72h execution, missing-path, boundary-purge, causal-prefix and gap-reset checks. Verification checks file hashes, timestamps, causal entry masks, all 33 tests and gate decisions. A separate output-directory replay is compared byte-for-byte; see replay.json.

~~~bash
python -m unittest discover -s tests -q
python -m research.discovery_round2
python -m research.discovery_round2.verify
python -m research.discovery_round2 --destination data/research_discovery_round2_replay --report-dir data/research_discovery_round2_replay/report
~~~

## Review checkpoint

No candidate advances to Milestone 6. Paper and live trading remain inactive. Review the evidence and limited sample size before authorizing further discovery. Do not use the reserved pool to rescue these candidates.

Snapshot: e723d225549faf2ca16d4eb688093168810d0d71aa4adef3642ff5d2cfdbee9b
