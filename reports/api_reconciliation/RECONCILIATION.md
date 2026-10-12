# Public API reconciliation

**Decision: reconciliation_complete_review_evidence.**

Requested 4 complete UTC development days to adjudicate 247 target candles. Both startTime and endTime are bounded; no reserved dates or account/order endpoints are used.

| Verdict | Candles |
|---|---:|
| api_confirms_daily_addition | 240 |
| api_supports_daily | 7 |

Comparisons use exact Decimal values from original archive/API strings for all nine price, volume and trade-count fields. The existing timestamp/OHLCV validator first excludes malformed or incomplete rows. This avoids treating floating-point parsing differences as source conflicts.

The API response bytes, retrieval times and SHA256 digests are cached separately. A digest establishes local integrity, not an exchange-signed authenticity guarantee. Every archive must still match its previously recorded checksum.

## Review checkpoint

The market database and all strategy results remain unchanged. Only API-confirmed additions or explicitly corroborated corrections may be proposed for a new immutable snapshot. Retain unresolved contradictions. A response error is not evidence that a candle is absent.

A confirmed repair requires rebuilding affected timeframes and features and repeating affected registered analyses under their unchanged rules. Preserve the old data snapshot and negative results. This comparison has not assessed effects on strategy outcomes.

API and archive agreement may reflect common upstream data. The remaining missing slots were not evaluated by this bounded request and must not be described as recovered.

Endpoint reference: https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints

Reproduce: python -m research.diagnostics.api_reconcile (reuses hash-verified responses).

Source snapshot: ed2167a0ac3a875972f5cead7bdfc7b332a0b436ca2db8b84eb06fef9ff1a44d
