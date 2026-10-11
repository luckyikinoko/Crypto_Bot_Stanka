"""Causal four-hour candidates; no outcome inputs."""
import numpy as np
import pandas as pd

CANDIDATES = ('trend_breakout_4h', 'trend_rsi_recovery_4h')


def entry_masks(f):
    required = ['available_at', 'segment_id', 'atr', 'trend', 'volatility', 'rsi', 'breakout']
    if any(c not in f for c in required):
        raise ValueError('Missing causal feature')
    if not f.available_at.is_monotonic_increasing or f.available_at.duplicated().any():
        raise ValueError('Feature timestamps must be sorted and unique')
    valid = np.isfinite(f.atr) & f.atr.gt(0) & f.trend.eq('bullish') & f.volatility.eq('normal')
    previous = f.groupby('segment_id', sort=False).rsi.shift()
    return pd.DataFrame({
        CANDIDATES[0]: valid & f.breakout.eq(1),
        CANDIDATES[1]: valid & previous.lt(40) & f.rsi.ge(40)
    }, index=f.index).fillna(False).astype(bool)
