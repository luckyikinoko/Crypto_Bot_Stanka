"""Causal trend and volatility axes; no future fitting."""
import numpy as np
import pandas as pd
from research.indicators import calculate


def classify(candles, interval):
    f = calculate(candles, interval)
    trend = pd.Series('unknown', index=f.index, dtype='string')
    ready = f[['ema_50','ema_200','adx']].notna().all(axis=1)
    trend.loc[ready] = 'ranging'
    trend.loc[ready & (f.ema_50 > f.ema_200) & (f.adx >= 25)] = 'bullish'
    trend.loc[ready & (f.ema_50 < f.ema_200) & (f.adx >= 25)] = 'bearish'
    ratio = f.atr/candles.reset_index(drop=True).close
    vol = pd.Series('unknown', index=f.index, dtype='string')
    for _, idx in f.groupby('segment_id').groups.items():
        r = ratio.loc[idx]
        lo = r.shift().rolling(252).quantile(.25)
        hi = r.shift().rolling(252).quantile(.75)
        valid = lo.notna() & hi.notna() & r.notna()
        vol.loc[idx[valid]] = 'normal'
        vol.loc[idx[valid & (r < lo)]] = 'low'
        vol.loc[idx[valid & (r > hi)]] = 'high'
    return f.assign(trend=trend, volatility=vol)
