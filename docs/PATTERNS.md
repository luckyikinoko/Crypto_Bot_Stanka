# Chart pattern recognition — definitions version 1

Milestone 3 starts with three small families: bull flags, resistance breakouts and
retests, and bullish/bearish engulfing candles. Bearish events are context only;
there is no short-selling or execution interface. Other flags, tops/bottoms,
head-and-shoulders, wedges, triangles and channels are deferred. These selected
rules are reproducible hypotheses, not universal definitions or proven signals.
No thresholds were fitted to historical returns or pattern counts.

## Reproduce and access

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -q
python -m research.patterns
```

Requires a Milestone 1 snapshot at `data/research`. Options: `--source`,
`--destination`, `--start`, `--end`, `--config` (JSON overrides), `--report`.
Default development range: 2018-01-01 through 2026-03-31 UTC candle opens, all five
timeframes. Data from April 2026 onward is rejected. No exchange keys are used.

`detect(candles, interval, Config())` returns a typed event table. The builder
stores one content-addressed Parquet file per timeframe, with checksums, source
snapshot, code hashes, configuration, dependency versions and counts in an atomic
catalog. `research.patterns.store.read_events` verifies checksums and selects a
half-open **availability-time** range. An event confirmed exactly at the upper
boundary is excluded by that reader; the full stored snapshot can include events
confirmed at the final source candle's close. All feature calculations reuse
Milestone 2's definitions and gap resets. Rebuilds replay the source history and
reuse identical output files. Pending state is not persisted between builds.

## Shared timing and event schema

H,L,O,C,V denote completed candle high, low, open, close and BTC base volume.
A[t-1] is ATR14 from the preceding candle, strictly positive and fully warmed.
Every detector operates within a contiguous segment. Missing candles clear pending
retests and prevent patterns bridging a gap. Events appear only after the confirming
candle closes, at its `available_at`; a future simulation must model fills afterward.

Each event stores:

- Stable ID; parent breakout ID for retests.
- Pattern, direction, timeframe, `status=confirmed`.
- Formation start (first candle open), formation end (exclusive close), availability.
- Exact parameter JSON, numeric geometric/volume strength metrics, contemporaneous
  ATR, RSI, EMA50/200, relative volume and historical volatility (null if unwarmed).

Formation timestamps describe geometry; **only availability is a signal timestamp**.
No provisional event is later rewritten as successful, failed or confirmed. Pending
and rejected candidates are internal state only. Event IDs depend on pattern,
timeframe, start, confirmation, parameters and parent ID, not future dataset length.
Multiple patterns and overlapping formations can coexist. Counts are dependent
observations, not independent trials. Strength metrics are measurements, not
calibrated success probabilities. Regime classification and outcome labels belong
to Milestone 4, separately from this causal context.

## Resistance breakout and retest

At t, R=max(H[t-20:t]) excludes the current candle. Confirm a breakout when
C[t] > R + 0.1*A[t-1] and C[t-1] <= R. The prior 20 candles form the reference
range. Record R, ATR at breakout and the close's ATR distance above R. Successive
breakouts at different rolling levels are allowed and have separate IDs.

For each breakout, freeze R and A. Starting on the next candle and through bar 12
inclusive, invalidate if the close is below R-0.25*A; otherwise confirm the first
retest when the candle range intersects [R-0.25*A,R+0.25*A] and C>R. A deep lower
wick is allowed if the close recovers. The retest records age in bars, frozen level,
ATR and close distance. Invalidation precedes confirmation. Expired/invalidated
states emit no event. A retest is never assumed to occur on the breakout candle;
intracandle ordering is therefore unnecessary for this detector. Confirming a retest
does not change the original breakout event. Up to 12 pending states are possible.

## Bull flag

A fixed eight-bar pole immediately precedes a fixed six-bar flag; candle t is the
breakout confirmation. Let b=t-6 and s=b-8 (inclusive pole start).

1. Pole height P=C[b-1]-C[s-1] must be >=3*A[s-1], using ATR before the pole.
2. Pole high Q=max(H[s:b]); flag high U=max(H[b:t]); flag low D=min(L[b:t]).
3. Flag cannot exceed the pole high: U<=Q.
4. Retracement (Q-D)/P must lie in [0,0.5].
5. Flag range width (U-D)/P must be <=0.5.
6. Ordinary least-squares slope of the six flag closes against indices 0..5
   must be nonpositive. This is a close-price centerline proxy; parallel boundary
   lines, goodness of fit and strict monotonicity are not required in version 1.
7. Mean flag volume / mean pole volume must be <=1; zero pole volume rejects it.
8. Breakout close C[t] > U+0.1*A[t-1].

Store pole height in ATRs, retracement, width fraction, slope in ATRs/bar, volume
ratio, breakout level and breakout distance. Duration is fixed by config; this
release deliberately does not sweep multiple durations or optimize thresholds.
The detector does not assert that all human-drawn flags fit these rules.

## Engulfing candles

Bullish: previous body bearish (Cprev<Oprev), current body bullish (C>O),
O<=Cprev and C>=Oprev. Bearish is symmetric. At least one engulfing boundary must
be strict; equal bodies and doji predecessors are rejected. Current absolute body
must be >=0.5*A[t-1]. Wicks need not be engulfed. No prior-trend filter is imposed;
these are two-candle shapes, not a claim of trend reversal. Record both body sizes
in prior ATRs. Both candles belong to the same contiguous segment.

## Validation and limits

Synthetic references cover all event types, exact timestamps, parent links, delayed
retests, invalidation, expiry, gaps, rejected flags, flat/no-event inputs and
parameter validation. Prefix-invariance tests compare every prefix of known
examples to the corresponding full-history events. Storage checks cover exact
Parquet roundtrips, deterministic replay, checksum corruption and reserved access.
Historical reports contain frequencies only. No fee-adjusted expectancy, success
rate, significance or profitability is inferred. Those require future outcomes,
realistic execution costs and dependence-aware statistical testing in later stages.
