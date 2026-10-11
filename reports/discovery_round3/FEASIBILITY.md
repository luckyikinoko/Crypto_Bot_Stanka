# Round 3 — standalone breakout feasibility

Hypothesis: a completed 4h close above the preceding 20 highs may predict continued buying over a 72-hour hold. Existing causal breakout definitions, gap resets and warm-up are reused. There are no EMA, ADX, RSI or volatility entry filters.

Registered before this feasibility run in commit 4571eae. Prior candidate returns and raw breakout frequency were already known; this is explicitly adaptive research.

| Pool | Raw signals | Boundary purged | Timing eligible | Nonoverlap | Active 28-day blocks |
|---|---:|---:|---:|---:|---:|
| training | 615 | 0 | 615 | 241 | 78 |
| reused_recent | 265 | 0 | 265 | 100 | 29 |

Feature-count gates: at least 100 training observations, 50 scheduled nonoverlapping observations, 30 active 28-day blocks, and 30 reused-recent observations.

**Feature feasibility: PASS.**

Counts use a five-minute delayed entry and a planned 72-hour hold; labels crossing a pool boundary are purged. A greedy single-position schedule includes a 60-minute cooldown. These counts do not verify future execution-path completeness. Actual eligible counts may be lower, and the schedule may change when missing paths are removed.

Blocks start at each pool start. A later outcome screen must use its actual complete unconditional baseline origin and recount active blocks. Passing frequency thresholds is not a power calculation, profitability evidence or a strategy-selection decision.

Only observation ID, decision availability time and breakout feature columns were read from Parquet. The source manifest was used for integrity metadata; no label file was opened and no returns, win rates, confidence intervals or p-values were calculated.

Training: 2018–2023. Reused recent: 2024–2026 Q1, not fresh validation. Data from 2026-04-01 onward remains blocked. Existing 33-test ledger and earlier rules/reports remain unchanged.

## Review checkpoint

If feasibility passes, the next step is a separately reviewed net-outcome screen under the registered standard, conditional-BNB and stress costs. Retain the previous statistical gates, compare with unconditional 4h decisions, and append the candidate as test 34 in the exploratory BY ledger. No alternate exit or parameter grid is registered. No strategy, paper trading or live trading is activated.

Reproduce: python -m research.discovery_round3

Source snapshot: e723d225549faf2ca16d4eb688093168810d0d71aa4adef3642ff5d2cfdbee9b
