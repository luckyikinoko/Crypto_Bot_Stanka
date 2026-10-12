# Round 5 — feature-only feasibility

Registered in commit 86fa4489e823f13e13a1c0125309ab7c2c1df9cd. Uses the pinned repaired market snapshot and unchanged EMA-reclaim rule. No historical outcome labels were loaded or calculated. The prior report was checked only by byte hash.

| Pool | Raw signals | Boundary purged | Timing eligible | Scheduled nonoverlap | Active 28-day blocks |
|---|---:|---:|---:|---:|---:|
| training | 1603 | 0 | 1603 | 589 | 74 |
| reused_recent | 680 | 0 | 680 | 266 | 29 |

Feasibility passed: **True**.

These timing counts are not independent sample sizes or power estimates. Full 5m execution paths have not been checked; usable counts can fall after that check. Feature warm-up and gap resets remain enforced. Annual counts, baseline coverage and block origins are in feasibility.json.

Training is 2018–2023. Recent 2024–2026 Q1 history is reused, not fresh validation. Reserved data from 2026-04-01 remains blocked. No return, win rate, expectancy, confidence interval or profitability conclusion is produced. The return-test ledger remains at 35.

Next checkpoint: review these counts, then evaluate only the registered 24h outcome under the unchanged costs and acceptance gates. Append test 36 only if outcomes are evaluated.

Reproduce with `python -m research.discovery_round5 --destination <fresh-data-directory> --report-dir <fresh-report-directory>`. The output includes only causal features and feasibility metadata. No strategy is selected and no trading is activated.
