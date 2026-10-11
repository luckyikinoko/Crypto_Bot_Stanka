# Round 4 — lower Bollinger Band re-entry

**Decision: candidate_rejected. No strategy selected.**

Registered in c7cbd1a before feature counts or outcomes. One fixed rule was evaluated: prior 1h close below its lower Bollinger Band, followed by current close at or above the current lower band, within the same uninterrupted segment. Bands use 20 closes, two population standard deviations (ddof=0). No additional indicator filters or alternative exits.

Entry is five minutes after recognition; primary exit is 24 hours after entry. A full contiguous 5m path is required. Gaps are not filled. Features and future labels are stored separately. Nonoverlap locks the 24-hour hold plus a 60-minute cooldown.

## Feature feasibility

| Pool | Raw signals | Timing eligible | Nonoverlap | Active 28-day blocks |
|---|---:|---:|---:|---:|
| training | 1578 | 1578 | 874 | 79 |
| reused_recent | 613 | 612 | 334 | 30 |

## Outcomes after costs

| Pool | Complete signals | Mean net | Stress mean | Unconditional mean | Nonoverlap n | Nonoverlap mean |
|---|---:|---:|---:|---:|---:|---:|
| training | 1554 | -0.131% | -0.191% | -0.121% | 860 | -0.146% |
| reused_recent | 612 | +0.023% | -0.037% | -0.153% | 334 | +0.149% |

Training 95% interval for mean net: -0.321% to +0.068%. Excess over unconditional 1h decisions: -0.010%, interval -0.174% to +0.167%.

Primary 28-day block comparison: 79 active blocks, 4999 draws; approximate one-sided p=0.5332; 35-test BY q=1.000. Seven-day sensitivity net interval: -0.366% to +0.108%.

Failed gates: positive_net_ci, positive_excess_ci, multiplicity, positive_stress, positive_training_years, positive_nonoverlap, recent_stress. No rules or thresholds were adjusted.

## Data exclusions

- training/lower_band_reentry_1h: incomplete paths {'path_gap': 23, 'missing_entry': 1}; complete paths crossing split boundary 0; usable 1554.
- reused_recent/lower_band_reentry_1h: incomplete paths {'insufficient_future': 1}; complete paths crossing split boundary 0; usable 612.

## Interpretation and limitations

The registered statistical gates determine rejection or eligibility for later review. Sample frequency alone does not establish an edge. Training is 2018–2023; recent data is 2024–2026 Q1 and has been reused. This adaptive discovery is not independent OOS confirmation, even after multiple-testing correction.

Standard per-side costs: 0.10% fee, 0.005% half-spread, 0.015% slippage. Conditional BNB fee: 0.075%, only when applicable. Stress: 0.10% fee, 0.01% half-spread, 0.04% slippage. Results are per overlapping observation, not portfolio returns. Buy-and-hold period totals and closed-trade drawdown are context, not direct risk-adjusted portfolio comparisons.

Detailed yearly summaries, conditional-BNB results, win rates, profit factors, MFE/MAE distributions, uncertainty and all 35 p-values are in results.json. Fixed-hold labels require no ATR; no stop or take-profit alternative was evaluated.

104 unit tests passed, including new re-entry, equality, gap, warm-up, prefix-invariance and boundary tests. Snapshot verification checks hashes, recalculates signals, costs, candidate summaries and gates, and verifies the cumulative test ledger. Replay status is in replay.json.

## Review checkpoint

Stop this round here. A rejected rule is not promoted to Milestone 6, paper trading or live execution. Review the accumulated findings before deciding whether another distinct hypothesis is worth testing. Reserved data from 2026-04-01 onward remains blocked.

Reproduce: python -m research.discovery_round4; python -m research.diagnostics.review_round4

Snapshot: 831b82f75c2e12f5b8ddc206df6fb661599c18e667152aae0a82b69a43709461
