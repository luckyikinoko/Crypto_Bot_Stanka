# Round 3 — standalone 4h breakout outcomes

**Decision: candidate_rejected. No strategy selected.**

The user authorized this outcome screen after the feature-only checkpoint. The rule and future execution were registered in 4571eae; feasibility was saved in c43a33a. The original registry remains unchanged as a record of that earlier scope.

A completed 4h close above the preceding 20 highs triggers an observation. Entry is delayed five minutes; exit is after a fixed 72 hours. There are no extra indicator filters or alternate exits. This screen reuses checksum-verified 5m path labels from round 2, verifies their timing, and independently recomputes cost-adjusted returns from entry and exit prices.

## Per-observation returns

| Pool | Complete signals | Mean net | Stress mean | Unconditional mean net | Nonoverlap n | Nonoverlap mean net |
|---|---:|---:|---:|---:|---:|---:|
| training | 598 | +0.729% | +0.669% | +0.047% | 232 | +0.202% |
| reused_recent | 265 | +0.377% | +0.317% | +0.004% | 100 | +0.153% |

Training is 2018–2023; reused recent is 2024–2026 Q1. Observations can overlap. Nonoverlap uses the full 72-hour hold plus 60-minute cooldown. These means are not portfolio returns.

## Statistical decision

- Training mean net 95% interval: -0.204% to +1.627%.
- Excess over unconditional 4h decisions: +0.682%; 95% interval -0.043% to +1.393%.
- Primary 28-day bootstrap: 78 active blocks, 4999 draws; approximate one-sided p=0.0306; cumulative 34-test BY q=1.000.
- Seven-day sensitivity net interval: -0.152% to +1.612%.
- Failed registered gates: positive_net_ci, positive_excess_ci, multiplicity.

Positive sample averages do not establish a robust edge: both primary intervals include zero and the multiple-testing criterion fails. No threshold, hold duration or exit was changed after observing results. Adaptive reuse remains even after BY correction; none of this is fresh out-of-sample confirmation.

## Integrity and costs

17 training breakout observations are excluded for missing 5m path candles, leaving 598. All 265 reused-recent signals have complete paths. Signals crossing split boundaries are excluded. Missing candles are never filled.

Standard per-side assumptions: 0.10% fee plus 0.005% half-spread and 0.015% slippage. Conditional BNB fee is 0.075%; it is not assumed always available. Stress uses 0.10% fee, 0.01% half-spread and 0.04% slippage. Detailed cost scenarios, yearly summaries, MFE/MAE distributions, win rates, profit factors and quality exclusions are in outcomes.json.

Buy-and-hold context is preserved from the earlier report. Its period-total return is not comparable directly to a per-observation mean. Closed-trade drawdown is descriptive and omits intratrade portfolio marks; this is not Milestone 6 portfolio validation.

100 tests pass. Verification checks snapshot/file hashes, recomputes candidate summaries and all gates, confirms 34-test accounting, and checks timing and pool boundaries. A separate replay is recorded in outcome_replay.json.

## Review checkpoint

The registered breakout candidate is rejected for promotion. The next useful decision is whether to pause discovery or authorize a materially different, independently motivated hypothesis. Do not tune this candidate to rescue its historical results. Reserved data from 2026-04-01 onward remains sealed; paper and live trading remain inactive.

Reproduce: python -m research.discovery_round3.outcomes; python -m research.discovery_round3.review

Snapshot: a41476e1527d37d9c386b6b2f03567781e05b45e4c25370d1da2408445fc0579
