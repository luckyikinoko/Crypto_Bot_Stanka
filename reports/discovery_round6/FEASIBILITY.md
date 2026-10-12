# Round 6 — double-bottom feature feasibility

Registered in commit 4ee7f663dd8107f758bc8d2c4ef1018b91c7267b. Uses the pinned repaired market snapshot, frozen detector and unchanged sample requirements. Only causal features and confirmed events are calculated; no future labels or return statistics.

| Pool | Raw events | Boundary purged | Timing eligible | Scheduled nonoverlap | Active 28-day blocks |
|---|---:|---:|---:|---:|---:|
| training | 172 | 0 | 172 | 163 | 70 |
| reused_recent | 63 | 0 | 63 | 61 | 29 |

Decision: **propose_outcome_screen**.

Requirements: training ≥100 timing-eligible events, ≥50 scheduled nonoverlapping events, ≥30 active 28-day blocks; reused recent ≥30 events. Frequency is not statistical power or proof of profitability. Complete 5m execution paths remain unchecked.

Annual counts, baseline coverage, missing context and block origins are in feasibility.json. Context availability is descriptive and was not used to select new filters. Historical prefixes of 1,000 and 10,000 candles reproduce the same earlier events. Stored tables pass checksum and read-back equality checks.

Training is 2018–2023; 2024–2026 Q1 is reused recent history. Reserved data from 2026-04-01 remains blocked. The prior ledger was verified by byte hash, without loading prior labels. The return-test ledger remains at 36.

Next: review feasibility, then consider only the registered 24h outcome. Append one test only if outcomes are evaluated.

Reproduce using `python -m research.discovery_round6 --destination <fresh-data-directory> --report-dir <fresh-report-directory>`. No strategy is selected and trading remains inactive.
