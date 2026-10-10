"""Experiment 002 entry signals; uses unchanged V1 exits and position risk."""
import pandas as pd
from btc_backtest import bars, indicators


def breakout_conditions(m, h):
    ema200=h.close.ewm(span=200,adjust=False).mean()
    ema50=h.close.ewm(span=50,adjust=False).mean()
    trend=(h.close>ema200) & (ema200>ema200.shift(5)) & (ema50>ema200)
    prior_high=m.high.shift(1).rolling(20,min_periods=20).max()
    prior_volume=m.volume.shift(1).rolling(20,min_periods=20).mean()
    return ((m.close>prior_high) & (m.volume>=1.2*prior_volume) &
            trend.reindex(m.index,method='ffill').astype('boolean').fillna(False))


def breakout_signals(df):
    result=indicators(df)  # Keep baseline stop/reference/regime-exit definitions.
    m,h=bars(df,15),bars(df,60)
    signal=breakout_conditions(m,h)
    # No forward fill: a breakout signal is eligible only at its 15-minute close.
    result['signal']=signal.reindex(result.index).astype('boolean').fillna(False)
    return result
