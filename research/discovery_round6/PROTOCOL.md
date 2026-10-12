# Round 6 — confirmed double bottom

Registration and synthetic detector tests only. No historical signal scan, label generation or returns. This is a proposed mathematical definition, not a claim that it is the universal double-bottom definition or profitable.

## Causal formation

Use completed Binance BTCUSDT Spot 1h candles, restricted to the pinned repaired development snapshot. Reuse canonical candle validation, indicator calculation and the existing event schema. The new detector is isolated in `research.patterns.double_bottom`; the original pattern catalog and historical events are unchanged.

1. A swing low at bar j must be strictly lower than both preceding lows and both following lows. It becomes known only at the close of j+2. Equal lows are not pivots.
2. Pair only consecutive confirmed swing lows i and j. Require 6–48 bars between pivot timestamps. A newly confirmed low always cancels the previous pending pair, even when the replacement pair fails its criteria. At most one pair is pending per contiguous segment.
3. Freeze Wilder ATR14 at the first pivot's confirmation close i+2. Require a finite positive value and at least 12 prior candles before i. Gap resets and indicator warm-up are retained.
4. The two lows differ by at most 0.5 frozen ATR. Define neckline N as the maximum high strictly between i and j. Require N minus the higher low to be at least 1 frozen ATR.
5. Require the maximum high of the 12 bars preceding i minus low(i) to be at least 2 frozen ATR. This is a prior-drop amplitude proxy, not a fitted downtrend or a claim about directional causality.
6. A pair becomes available after j+2 closes. Reject it if any close after j but before j+2 already exceeded N + 0.1 ATR. Breakout at the j+2 close itself may qualify. No retrospective entry is created for an early breakout.
7. Cancel if any low after j through confirmation falls strictly below min(low(i),low(j)) − 0.25 ATR. Continue applying that condition while pending. Invalidation wins when the same candle both breaches the floor and closes above the neckline.
8. Confirm once when previous close ≤ N + 0.1 ATR and current close > N + 0.1 ATR, at formation recognition or within the following 12 bars inclusive. After that, expire the pair. Equality at the threshold does not confirm. Emit at most one event per pair; later prices never withdraw or backdate an emitted event.
9. Any missing hourly candle resets pivots, ATR warm-up and pending state. No pair bridges a gap.

The event's `available_at` is the actual confirming candle close. `formation_start` is the first low's candle open; `formation_end` is the second low's confirmation close. Metrics include both pivot timestamps and recognition times, both lows, neckline, frozen ATR, separation, waiting time, prior-drop/rebound/similarity ratios and breakout distance. Context includes causal ATR, RSI, EMA50 and EMA200; missing context is null and imposes no extra filter. Only confirmed events are emitted. Volume, trend and volatility filters are not added.

## Registered future research

Candidate: `confirmed_double_bottom_1h`, long-only. A later authorized outcome screen would enter at the 5m open five minutes after event availability and exit after a fixed 24h hold. Use complete 5m decision-to-entry and entry-to-exit paths; purge split-crossing labels. There is no alternate holding period, stop, target, trailing exit or position-size optimization. Nonoverlap diagnostics use a 60-minute cooldown after the planned exit.

The unconditional comparison includes all 1h decisions with finite positive prior-bar ATR14 and at least 16 completed candles in the segment, without a pattern predicate. The feature-only stage uses the first eligible baseline decision's UTC day as block origin. If execution-path exclusions later change that origin, preserve the registered origin explicitly rather than silently changing block alignment.

Training remains 2018–2023; 2024–2026 Q1 is reused recent history. Data from 2026-04-01 onward stays sealed. Costs, bootstrap settings and acceptance gates are copied unchanged from the prior registry and fixed numerically in REGISTRY.json. Standard fees are primary; the BNB discount is conditional, and stress-cost positivity remains required. These are research assumptions, not verified historical account fees.

Feature feasibility requires 100 training signals, 50 scheduled nonoverlapping training events, 30 active training 28-day blocks and 30 reused-recent signals after timing boundary exclusions. These are not a power calculation. Report frequency by year and missing context without choosing filters. If feasibility fails, stop without returns or threshold changes. A later outcome screen must recheck minimum counts after complete-path exclusions and pass all existing net/excess confidence, multiple-testing, stress, stability and recent-performance gates.

The ledger remains at 36 return tests during registration and feasibility. Append exactly one test (37) only if this candidate's primary outcome is evaluated. Earlier adaptive work and legacy experiments remain disclosed; correction cannot convert reused development data into independent confirmation.

## Review boundary

This commit defines the detector and tests synthetic examples, including delayed recognition, historical-prefix invariance, gaps, equality boundaries, invalidation, expiry and premature breakouts. It does not inspect the detector's historical frequency or returns. Next checkpoint is feature-only feasibility after review. Do not optimize on attractive historical formations, enable execution, or automatically proceed into outcomes. No strategy is selected.
