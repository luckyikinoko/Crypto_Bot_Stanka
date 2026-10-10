# Execution and cost audit — 10 October 2026

Scope: review the current offline simulator, reconcile saved trade cash flows,
and measure cost hurdles. No strategy parameters were optimized and no holdout
prices were accessed. Actual account-specific Binance fees remain unknown.

## Break-even price movement

For a reference entry price P, equal per-side fee f and adverse execution s:

`g_break_even = ((1+s)*(1+f))/((1-s)*(1-f)) - 1`

This is the required reference-price increase to cover a complete buy/sell cycle
in our quote-fee equivalent model. It is not a forecast or a profit target.

| Assumed fee per side | Assumed spread/slippage per side | Required move |
|---|---|---|
| 0.100% | 0.020% | 0.2403% |
| 0.075% | 0.020% | 0.1902% |
| 0.050% | 0.020% | 0.1401% |
| 0% | 0.020% | 0.0400% |

All rows are hypothetical sensitivity scenarios, not verified Binance tiers.
At the baseline assumptions, a 0.20% underlying price rise still loses money.
A roughly 250 USDT position pays about 0.60 USDT in round-trip costs when prices
are near entry. Small nominal account size does not eliminate percentage costs.

If the buy fee is deducted from BTC rather than charged in quote currency, replace
`1+f` with `1/(1-f)` for the same desired sellable BTC quantity. Baseline break-even
then becomes 0.2404%. This small difference does not address the observed losses.
Actual fee-asset rounding and residual quantities still require explicit modeling.

## Reconciled fixed-trade decomposition

Eight independent quarterly episodes, April 2024–March 2026. These sums are not
a compounded account. Existing quantities and entry/exit decisions are fixed.

| Strategy | Gross reference-price P&L | Explicit fees | Execution-price cost | Net P&L |
|---|---:|---:|---:|---:|
| Original V1 | +16.60 | 187.75 | 37.55 | -208.70 |
| No 60-minute exit | -15.83 | 180.39 | 36.08 | -232.30 |
| Breakout | +7.32 | 217.52 | 43.50 | -253.71 |

All values are USDT. Identity checked for each ledger:
`gross reference-price P&L - explicit fees - execution-price cost = net P&L`.
Reference prices are recovered by reversing the known execution multipliers.
This is accounting attribution, **not a fresh zero-cost strategy simulation**.
Changing costs in the strategy itself changes sizing, targets, time exits, risk
halts, and the trades subsequently allowed.

Keeping the recorded trades and execution prices fixed, even zero explicit fees
leaves V1 at -20.95 USDT and breakout at -36.19 USDT. A discount alone is therefore
not enough for these recorded paths. This does not prove that a fully rerun lower-
cost strategy would generate the same trades or returns. No such claim is made.

## Execution review

| Area | Finding / status |
|---|---|
| Signal timing | Completed-candle, next-minute entries; causality tests pass. |
| Cash flows | Fees, quantities and realized P&L reconcile under documented quote-fee model. |
| Risk sizing | Both fees and adverse stop execution enter planned risk; losses can exceed it on gaps. |
| Fees | Uniform taker-like assumptions, not actual account rates or historical promotions. |
| Spread/slippage | Fixed 2 basis points per side; stress at 4. No order-book calibration. |
| Stops and targets | Market-like fills; conservative stop-first treatment for ambiguous minute bars. |
| Native order behavior | No exchange-native OCO lifecycle, queueing, partial fills or latency model. |
| Symbol filters | Quantity step/minimum notional assumed; current/historical filters and price ticks unverified. |
| Fee assets | Quote-equivalent approximation, not exact BTC/BNB fee balances and dust. |
| News | No scheduled-event input in existing runs. |
| Drawdown reporting | Corrected the discrepancy below; it changes summary measurement, not orders. |

Do not interpret minute-bar backtests as exchange-exact execution. A future live
adapter needs actual account fees, symbol filters, order reconciliation and a
calibrated execution model; the current code remains offline research only.

## Reporting correction

The risk engine tracks equity peaks at minute opens and closes. Previously, the
reported maximum drawdown used only a running maximum of minute-close equity.
That could omit an observed opening peak and understate drawdown. The report now
uses the engine's tracked peak. The equity export includes a `peak` column.
A regression test constructs an opening spike followed by a lower close.

This is still a sampled mark-to-liquidation drawdown measure: it does not recover
all unobserved intraminute equity peaks/troughs from OHLC bars. Previously saved
reports remain preserved as historical outputs; their drawdown values should be
read with this qualification. Re-running them uses the corrected report formula.
The baseline replay is saved separately; compare its ledger with the original
before treating this as a behavior-preserving reporting fix.

## Verification and next input

25 unit tests pass. Cost-formula tests cover quote-fee and base-fee cash flows;
ledger decomposition is checked numerically. Baseline replay verification is
recorded separately in `replay_verification.json`.

Before selecting a fee model, obtain the BTCUSDT maker/taker rates actually shown
for the user's account and whether BNB fee payment is enabled. A screenshot or
rates typed into chat is enough; no API secret or account access is needed.
The hypothetical scenarios must not be substituted for this missing information.

Sources checked 10 October 2026:
- https://github.com/binance/binance-spot-api-docs/blob/master/faqs/commission_faq.md
  (rates vary by account/symbol and relevant discounts/charges; commission-query
  and test-order methods exist; example rates in documentation are fictional).
- https://github.com/binance/binance-spot-api-docs/blob/master/filters.md
  (symbol price, quantity and notional constraints).

Reproduce attribution: `python cost_audit.py`.
Reproduce corrected baseline: `python btc_backtest.py run --start 2024-01-01
--end 2026-04-01 --out reports/execution_audit/baseline_replay` (one shell line).
