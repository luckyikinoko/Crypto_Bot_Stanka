# Milestone 5 — discovery registration

Commit this registry before calculating new candidate outcomes. Inputs and code
from Milestone 4 have already been inspected; this is transparent adaptive research,
not an untouched preregistration or independent confirmation. Only three hypotheses
are added. Trend confirmation may help breakouts/retests; range RSI recovery tests
a distinct mean-reversion mechanism. These motivations do not establish an edge.

All candidates are long-only BTCUSDT Spot on 15m decisions. Thresholds and gates
are fixed in REGISTRY.json. Reuse completed 5m paths and prior cost scenarios,
including conditional BNB; standard fees are primary. No additional horizon, stop,
target, trend filter or indicator threshold is swept. No new outcome labels are
needed: the frozen 24h labels already include the specified barrier exit.

Use 2018–2023 for screening; label paths must end by 2024-01-01. Show 2024–2026 Q1
separately as previously reused stability evidence, never OOS. Unknown regimes,
warm-ups, gaps, nonpositive ATR and incomplete paths are excluded explicitly.
Never read reserved prices/features/outcomes from 2026-04-01 onward.

Inference compares candidate primary barrier net returns to unconditional barrier
long returns at the same 15m opportunities, using the same entry/exit/cost model.
Reuse paired 28-day block bootstrap, with 7 days as sensitivity. Net and excess
95% lower bounds must both exceed zero. Combine old 28 M4 tests and three new
screening comparisons for exploratory BY correction. This accounting cannot undo
adaptivity or guarantee calibrated significance under nonstationarity.

Require 100 training observations, 50 nonoverlapping observations, 30 active
28-day blocks, positive stressed and nonoverlap means, four positive training
years (of six; absent years count as not positive), and at least 30 recent
observations with positive standard and stressed means. Report every failure.
No success can be inferred solely from the recent pool or the best-performing year.

Nonoverlap diagnostics conservatively lock out new decisions through the full
24h label end even after an earlier stop/target; add a 60-minute cooldown. This
is outcome-independent scheduling, not an optimized execution engine. Report
per-trade dispersion and closed-trade drawdown; do not present a trade-count
Sharpe as calendar risk-adjusted performance. Simple unfiltered breakout and RSI
recovery cohorts are ablation baselines, descriptive only. Buy-and-hold has
separate period-total-return and 15m close drawdown units; it is not compared
numerically with per-trade means as if the units matched.

If any candidate merits later validation, propose—not calibrate—risk of 0.5% of
capital per trade, 25% capital cap, one position, 60-minute cooldown and 2% daily
loss including unrealized P&L. Size using stop distance plus both-sided stressed
friction/fees, cap by available capital, and round down to exchange lot rules in
Milestone 6. This is a research risk budget, not an evidence-based optimal size.
No trailing stop. A gap can exceed the planned stop loss. Skip unknown regimes,
missing prices, unavailable data, insufficient funds, and any breached risk limit.
No risk governor or order executor is activated in this milestone.

Even a passing screen is only a candidate for subsequent user-approved validation.
If none pass, record selected_strategy=null and stop. Do not force discovery.
