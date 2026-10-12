# Round 6 — registered outcome screen

Adaptive exploratory research; recent data reused. Event means are not portfolio returns. Missing paths excluded. Reserved data remains sealed. No strategy or trading activated.

Entry: confirmed 1h double bottom with the frozen causal pivot and neckline definition. Entry delayed five minutes; fixed 24h exit; no alternative horizons or parameters tested. Standard costs are primary; BNB is conditional and stress costs are retained.

| Pool | Complete signals | Standard mean net | Stress mean net | Nonoverlap n | Nonoverlap mean net |
|---|---:|---:|---:|---:|---:|
| training | 170 | -0.1728% | -0.2327% | 161 | -0.1596% |
| reused_recent | 63 | 0.0119% | -0.0481% | 61 | -0.0086% |

Decision: **candidate_rejected**.

Failed criteria: positive_net_ci, positive_excess_ci, multiplicity, positive_stress, positive_nonoverlap, recent_stress.

Training standard net mean 95% block interval: [-0.0074960275631173225, 0.004735317165421171]. Training excess-over-baseline 95% interval: [-0.005913457839084222, 0.005568461411020625]. These JSON values are return fractions (multiply by 100 for percent).
Primary p-value: 0.57; BY-adjusted q across 37 tests: 1.0.

The prior 36 revised-ledger IDs and p-values are preserved. This adds one primary hypothesis test. Seven-day blocks are a sensitivity check, not an alternate selection test. Earlier legacy experiments remain outside this ledger. No claim of independent confirmation follows from multiple-testing correction.

Full-path exclusions and boundary purges, annual performance, MFE/MAE summaries, cost scenarios and the unconditional matched baseline are in outcomes.json. Buy-and-hold is an exposure context, not directly comparable with signal-average returns. Scheduled closed-trade drawdown omits intratrade portfolio risk.

Stop for review. A failed screen does not authorize parameter tuning or use of the reserved pool. A pass only proposes separate portfolio and walk-forward validation.

Reproduce with `python -m research.discovery_round6.outcomes --destination <fresh-data-directory> --report-dir <fresh-report-directory>`.
