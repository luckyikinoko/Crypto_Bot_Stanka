# Discovery round 2: registered before evaluation

Two 4-hour, long-only hypotheses test whether a 72-hour holding period leaves more room after costs. No parameter grid, threshold changes, or replacement of failed primary exits.

Use existing causal indicators: breakout above the preceding 20 highs; bullish means EMA50 > EMA200 and ADX14 >= 25; normal volatility uses current ATR/close against preceding 252-bar quartiles. RSI recovery crosses 40 within a contiguous segment. Require positive finite ATR. Gap resets and warm-up remain unchanged.

At each completed 4h candle, enter five minutes later using the 5m open. The primary exit is the close at 72 hours after entry, with every intervening 5m candle required. MFE/MAE use that full path. Secondary 2-ATR stop / 3-ATR take results are descriptive only; stop first if order is ambiguous.

Compare against unconditional 4h decisions with the same execution path. Reuse standard, conditional-BNB and stress costs. Training is 2018–2023; reused stability is 2024–2026Q1. Purge labels crossing pool boundaries. Never read reserved data from 2026-04-01 onward.

Use existing gates unchanged, paired 28-day bootstrap (7-day sensitivity), 4,999 draws and fixed seed. Nonoverlap schedule locks the full 72h plus 60-minute cooldown. Include all 31 prior exploratory tests in a 33-test BY ledger. The dependence and adaptive reuse limitations remain; no significance claim constitutes fresh OOS evidence.

This round does not authorize a strategy, portfolio backtest, paper trading or live execution. Preserve all earlier reports. Stop after reporting this round.
