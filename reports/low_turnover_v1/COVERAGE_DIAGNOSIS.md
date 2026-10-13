# Daily EMA200 coverage diagnosis

This is a data-quality diagnosis following the closed daily EMA200 preflight, not a reopened experiment or a new strategy test.

## Finding

The stored daily series is derived from 5-minute candles. A day is included only when all 288 expected 5-minute candles exist. The indicator engine resets at every missing daily candle and requires 200 contiguous daily candles to initialize EMA200. These rules explain the low coverage; the audit found no discrepancy between the stored data and the implemented rules.

| Training decision category, 2018–2023 | Days |
|---|---:|
| Eligible EMA200 | 337 |
| Warm-up in the initial contiguous segment | 3 |
| Warm-up after gaps | 1,818 |
| Missing daily decisions plus initial dataset boundary | 33 |
| Total | 2,191 |

There are 32 missing daily candle dates, all explained by incomplete underlying 5-minute buckets. The 33 absent decision dates also include January 1, 2018: the dataset begins that day, so its first daily decision is available January 2. There are 29 contiguous daily segments across the development dataset. The first segment ends before completing warm-up; subsequent gaps repeatedly restart it. Recent-period eligibility remains 821 of 821 days.

## Verification performed

- Read both timeframes through the checksum-verifying market reader using the frozen source catalog hash.
- Rebuilt the daily candles from existing 5-minute data and compared every stored column against the daily dataset.
- Independently reproduced EMA200 availability from contiguous timestamp counts, without using EMA values in that reconstruction.
- Reconciled every missing daily date against incomplete 5-minute buckets and every decision count against the frozen preflight.

All four checks passed. Reproduce with `python -m research.diagnostics.daily_coverage`. Machine-readable segment dates, missing dates and counts are in `coverage_diagnosis.json`.

## Proposed next bounded step

Audit official native BTCUSDT daily candles for 2018–2023 in an isolated source dataset. First inspect the 32 affected dates and adjacent control days. Verify archive checksums, UTC boundaries, OHLCV consistency and agreement with derived candles on complete control days. Where available, compare against a second official exchange endpoint. If the sample is consistent, measure native daily coverage across the training period without calculating strategy returns.

Native daily candles may validly summarize a day containing an exchange interruption, while the strict 5-minute aggregation omits that day. This is a hypothesis to investigate, not a verified finding about those source candles. The current audit cannot distinguish remaining source outages from recoverable archive defects. It also cannot establish that native daily candles meet the coverage gate.

Any replacement would require a separately versioned data policy and snapshot, documented reconciliation and a new registered coverage check. Do not silently substitute native candles into the closed experiment, fabricate missing prices, shorten warm-up, or treat valid daily candles as proof of complete intraday execution paths. The 5-minute execution gaps remain a separate issue.

No new data was downloaded in this diagnosis. No return tests were added; the ledger remains 37. Original datasets, experiment decisions and reserved data from April 1, 2026 onward remain unchanged. No trading execution was activated.
