# Experiment 002: 15-minute trend breakout

Frozen before execution, 10 October 2026; parent 75a9b59.

Research hypothesis: a close above an established intraday range, within a rising
hourly trend and accompanied by volume, may offer more follow-through than the
rejected short pullback entry. This is an unproven hypothesis, not trading advice.

One candidate, no grid search:
- Signal evaluated only when a 15-minute candle has closed.
- Latest completed hourly close > EMA200; EMA200 > its value five hours earlier;
  hourly EMA50 > EMA200.
- Completed 15-minute close > maximum high of the PRECEDING 20 completed
  15-minute candles (exclude the signal candle).
- Signal candle volume >= 1.2 times the mean volume of the preceding 20
  15-minute candles (exclude the signal candle).
- Remove the original pullback/RSI/15-minute EMA setup checks from the entry.
- Keep the original 5-minute ATR/swing stop, 0.4–1.2% stop-distance eligibility,
  next-minute entry, risk sizing, 1.5R net target, 60-minute and 180-minute exits,
  cooldown, fees, slippage, daily limits and permanent drawdown halt.

Evaluation: baseline, breakout, breakout with doubled execution costs. Same
continuous January 2024–March 2026 runs and eight independently reset quarters
April 2024–March 2026 as Experiment 001. Identical provisional gates, plus require
positive net P&L and no drawdown halt on continuous baseline/stress candidate runs
before calling the candidate promising. Original V1 remains the default.

All these development periods have now influenced research choices. The quarterly
comparisons are REUSED DEVELOPMENT DATA, not untouched out-of-sample validation.
Record all failures and do not tune another candidate in this experiment.
The reserved April–September 2026 holdout remains sealed regardless of results.
A promising result would require further robustness work before a one-time final
holdout evaluation; it would not authorize trading.

Bootstrap retains Experiment 001's fixed seven-day circular blocks, 2,000 draws,
seed 1001, and its limitations. No new market data is required or downloaded.
