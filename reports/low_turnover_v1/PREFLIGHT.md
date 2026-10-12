# Daily EMA200 coverage preflight

Specification registered in d1a56421a01d7154341281927498cdbb7c9042e6. Only indicator availability was counted; no entry rules, trades, portfolio returns or hypothesis tests were evaluated.

| Pool | Calendar days | Eligible daily decisions | Coverage | Required |
|---|---:|---:|---:|---:|
| training | 2191 | 337 | 15.38% | 50% |
| reused_recent | 821 | 821 | 100.00% | 80% |

Training active 28-day blocks: 14; required: 30.

Decision: **stop_insufficient_data_coverage**.

EMA200 requires 200 complete contiguous daily candles after each reset. Sparse historical gaps can therefore remove substantially more indicator-ready days than the number of missing candles alone. No warm-up was shortened, price filled, period changed or replacement data acquired.

The registered stopping rule applies: do not build the portfolio runner or run this backtest. Close this bounded experiment as insufficient data coverage, not as a losing strategy. The prior nine strategy rejections remain unchanged. Further work would require a new scope decision; no automatic replacement candidate.

The return-test ledger remains at 37. No portfolio, paper-trading or live-execution code was added. Reserved data stays sealed.

Counts use decision availability timestamps in half-open UTC pools; denominator includes every calendar day, including missing data and warm-up. Latest boundary candle is not a decision within the pool.

Reproduce: `python -m research.low_turnover_v1.preflight`.
