"""Frozen causal EMA-reclaim rule; no market loading or outcome calculation."""
import numpy as np
import pandas as pd
from market_data.store import RESERVED_FROM

CANDIDATE = 'trend_pullback_reclaim_1h'
FEATURE_COLUMNS = ['observation_id', 'available_at', 'segment_id', 'close',
                   'ema_20', 'ema_50', 'ema_200']


def eligibility_mask(features):
    """Same causal feature eligibility for signal and unconditional baseline."""
    f = features[FEATURE_COLUMNS]
    t = f.available_at
    if str(t.dt.tz) != 'UTC' or t.isna().any() or t.duplicated().any() or not t.is_monotonic_increasing:
        raise ValueError('Sorted unique UTC decisions required')
    if (t >= RESERVED_FROM).any():
        raise ValueError('Reserved data blocked')
    if f.observation_id.isna().any() or f.observation_id.duplicated().any() or f.segment_id.isna().any():
        raise ValueError('Unique observation IDs and nonmissing segment IDs required')
    previous = f[['close', 'ema_20']].shift()
    contiguous = t.diff().eq(pd.Timedelta(hours=1)) & f.segment_id.eq(f.segment_id.shift())
    finite = np.isfinite(f[['close', 'ema_20', 'ema_50', 'ema_200']]).all(axis=1)
    prior_finite = np.isfinite(previous).all(axis=1)
    return (contiguous & finite & prior_finite).fillna(False).astype(bool)


def signal_mask(features):
    eligible = eligibility_mask(features)
    previous = features[['close', 'ema_20']].shift()
    return (eligible & features.ema_50.gt(features.ema_200)
            & previous.close.le(previous.ema_20)
            & features.close.gt(features.ema_20)).fillna(False).astype(bool)
