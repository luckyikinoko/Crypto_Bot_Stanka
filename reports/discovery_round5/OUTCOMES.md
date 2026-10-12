# Round 5 — registered outcome screen

Adaptive exploratory research; recent data reused. Event means are not portfolio returns. Missing paths excluded. Reserved data remains sealed. No strategy or trading activated.

Entry: completed 1h EMA20 reclaim while EMA50 > EMA200. Entry delayed five minutes; fixed 24h exit; no alternative horizons or parameters tested. Standard costs are primary; BNB is conditional and stress costs are retained.

| Pool | Complete signals | Standard mean net | Stress mean net | Nonoverlap n | Nonoverlap mean net |
|---|---:|---:|---:|---:|---:|
| training | 1594 | -0.1702% | -0.2301% | 585 | -0.2020% |
| reused_recent | 680 | -0.1790% | -0.2389% | 266 | -0.1806% |

Decision: **candidate_rejected**.

Failed criteria: positive_net_ci, positive_excess_ci, multiplicity, positive_stress, positive_training_years, positive_nonoverlap, recent_standard, recent_stress.

Training standard net mean 95% block interval: [-0.0043687246951028885, 0.0008842178550402241]. Training excess-over-baseline 95% interval: [-0.0024183657893874374, 0.0017962824267056324]. These JSON values are return fractions (multiply by 100 for percent).
Primary p-value: 0.5894; BY-adjusted q across 36 tests: 1.0.

The prior 35 revised-ledger IDs and p-values are preserved. This adds one primary hypothesis test. Seven-day blocks are a sensitivity check, not an alternate selection test. Earlier legacy experiments remain outside this ledger. No claim of independent confirmation follows from multiple-testing correction.

Full-path exclusions and boundary purges, annual performance, MFE/MAE summaries, cost scenarios and the unconditional matched baseline are in outcomes.json. Buy-and-hold is an exposure context, not directly comparable with signal-average returns. Scheduled closed-trade drawdown omits intratrade portfolio risk.

Stop for review. A failed screen does not authorize parameter tuning or use of the reserved pool. A pass only proposes separate portfolio and walk-forward validation.

Reproduce with `python -m research.discovery_round5.outcomes --destination <fresh-data-directory> --report-dir <fresh-report-directory>`.
