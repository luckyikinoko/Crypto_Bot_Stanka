# Repaired development market snapshot v1

**240 additions and seven corrections applied to a separate snapshot. Original market data and all original research results are preserved.**

| Interval | Added candles | Corrected candles | Missing before | Missing after |
|---|---:|---:|---:|---:|
| 5m | 240 | 7 | 1860 | 1620 |
| 15m | 80 | 3 | 627 | 547 |
| 1h | 20 | 2 | 168 | 148 |
| 4h | 4 | 1 | 67 | 63 |
| 1d | 0 | 0 | 32 | 32 |

## Warm-up coverage impact

| Interval / pool | Unknown volatility before | Unknown volatility after | Decisions before | Decisions after |
|---|---:|---:|---:|---:|
| 15m / training | 7872 | 7952 | 209708 | 209788 |
| 15m / reused_recent | 0 | 0 | 78816 | 78816 |
| 1h / training | 7081 | 7101 | 52415 | 52435 |
| 1h / reused_recent | 0 | 0 | 19704 | 19704 |
| 4h / training | 5595 | 5599 | 13078 | 13082 |
| 4h / reused_recent | 0 | 0 | 4926 | 4926 |

More candles do not necessarily reduce unknown-indicator counts: newly recovered short segments can add observations that still lack warm-up. No indicator definition or warm-up requirement was relaxed. Residual gaps remain documented and are not filled.

## Validation and provenance

API response hashes, the staged addition-file hash, exact correction decimal values, parent snapshot identity and repair-plan digest are checked before publication. Float64 comparisons permit only representation noise (relative tolerance 1e-14); parent file hashes pin the exact stored preimage. No row outside the approved additions/corrections or their higher-timeframe buckets may change.

Every timeframe is rebuilt from repaired 5m candles, written as UTC Parquet partitions, and read back through the checksum-verifying research reader. The original catalog bytes remain identical. Provenance includes the parent, daily/API evidence, repair plan and changed-row timestamps.

## Research checkpoint

This is a data revision, not a new strategy result. Existing reported returns, uncertainty and rejected-candidate decisions refer to the original snapshot until affected experiments are replayed with their registered rules unchanged. Preserve those original reports and label revised reports explicitly.

The default research input is not switched automatically. The next step is a controlled replay of affected feature, pattern and outcome calculations on this repaired snapshot, followed by a delta report. No parameter search, reserved evaluation, paper trading or live execution is part of this repair.

Reproduce into a fresh destination: python -m research.diagnostics.apply_repair --destination data/research_repaired_replay --report-dir data/repair_replay_report

Parent: ed2167a0ac3a875972f5cead7bdfc7b332a0b436ca2db8b84eb06fef9ff1a44d

Repaired: 70bcba5fa72e2290b889ebaa8f7ac9a7abed5a321d3dbff56dff801156e3d999
