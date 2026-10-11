"""Definitions and warm-up conventions are versioned in docs/INDICATORS.md."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from market_data.schema import MINUTES, duration, validate


@dataclass(frozen=True)
class Config:
    ema_periods: tuple = (20, 50, 100, 200)
    slope: int = 5
    wilder: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    roc: int = 12
    window: int = 20
    bands: float = 2.0
    pivot: int = 2

    def __post_init__(self):
        periods = (*self.ema_periods, self.slope, self.wilder, self.macd_fast,
                   self.macd_slow, self.macd_signal, self.roc, self.window, self.pivot)
        if not self.ema_periods or any(type(n) is not int or n < 1 for n in periods):
            raise ValueError('Periods must be positive integers')
        if self.window < 2 or self.macd_fast >= self.macd_slow:
            raise ValueError('Require window >= 2 and MACD fast < slow')
        if not np.isfinite(self.bands) or self.bands <= 0:
            raise ValueError('Band multiplier must be finite and positive')


def smooth(series, period, alpha):
    """SMA seed after period consecutive values, then recursive smoothing."""
    x = series.to_numpy(dtype=float)
    out = np.full(len(x), np.nan)
    finite = np.flatnonzero(np.isfinite(x))
    if not len(finite):
        return pd.Series(out, index=series.index)
    first = finite[0]
    if not np.isfinite(x[first:]).all():
        raise ValueError('Internal missing values must be segmented before smoothing')
    seed = first + period - 1
    if seed < len(x):
        out[seed] = x[first:seed + 1].mean()
        # pandas recursion starts from our explicit SMA seed.
        tail = pd.Series(np.r_[out[seed], x[seed + 1:]])
        out[seed:] = tail.ewm(alpha=alpha, adjust=False).mean().to_numpy()
    return pd.Series(out, index=series.index)


def _segment(a, interval, cfg):
    c, h, l, v = a.close, a.high, a.low, a.volume
    f = a[['open_time', 'available_at']].copy()
    for n in cfg.ema_periods:
        e = smooth(c, n, 2 / (n + 1))
        f[f'ema_{n}'] = e
        f[f'ema_{n}_slope'] = e / e.shift(cfg.slope) - 1
    n = cfg.wilder
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    f['atr'] = smooth(tr, n, 1/n)
    delta = c.diff()
    gain = smooth(delta.clip(lower=0), n, 1/n)
    loss = smooth((-delta).clip(lower=0), n, 1/n)
    f['rsi'] = 100 * gain / (gain + loss)
    f.loc[(gain == 0) & (loss == 0), 'rsi'] = 50
    up, down = h.diff(), -l.diff()
    plus = up.where((up > down) & (up > 0), 0.0)
    minus = down.where((down > up) & (down > 0), 0.0)
    # First candle contributes range but no directional movement.
    p, m = smooth(plus, n, 1/n), smooth(minus, n, 1/n)
    f['plus_di'] = (100*p/f.atr).mask(f.atr == 0, 0)
    f['minus_di'] = (100*m/f.atr).mask(f.atr == 0, 0)
    dx = (100*(p-m).abs()/(p+m)).mask((p+m) == 0, 0)
    f['adx'] = smooth(dx, n, 1/n)
    f['macd'] = smooth(c, cfg.macd_fast, 2/(cfg.macd_fast+1)) - smooth(c, cfg.macd_slow, 2/(cfg.macd_slow+1))
    f['macd_signal'] = smooth(f.macd, cfg.macd_signal, 2/(cfg.macd_signal+1))
    f['macd_histogram'] = f.macd - f.macd_signal
    f['roc'] = c / c.shift(cfg.roc) - 1
    w = cfg.window
    f['bb_middle'] = c.rolling(w).mean()
    sd = c.rolling(w).std(ddof=0)
    f['bb_upper'], f['bb_lower'] = f.bb_middle + cfg.bands*sd, f.bb_middle - cfg.bands*sd
    f['bb_width'] = (f.bb_upper-f.bb_lower)/f.bb_middle
    f['historical_volatility'] = np.log(c/c.shift()).rolling(w).std(ddof=1)*np.sqrt(365*1440/MINUTES[interval])
    f['volume_ma'] = v.rolling(w).mean()
    baseline = v.shift().rolling(w).mean()
    f['relative_volume'] = v/baseline.replace(0, np.nan)
    f['obv'] = (np.sign(delta).fillna(0)*v).cumsum()
    f['resistance'] = h.shift().rolling(w).max()
    f['support'] = l.shift().rolling(w).min()
    f['breakout'] = (c > f.resistance).astype(float).where(f.resistance.notna())
    f['breakdown'] = (c < f.support).astype(float).where(f.support.notna())
    f['distance_from_high'] = c/f.resistance-1
    f['distance_from_low'] = c/f.support-1
    k = cfg.pivot
    # At row t, test t-k against the preceding and following k bars, all closed.
    ph, pl = h.shift(k), l.shift(k)
    is_high, is_low = ph.notna(), pl.notna()
    for offset in range(2*k+1):
        if offset != k:
            is_high &= ph > h.shift(offset)
            is_low &= pl < l.shift(offset)
    f['swing_high'] = ph.where(is_high)
    f['swing_low'] = pl.where(is_low)
    f['last_swing_high'] = f.swing_high.ffill()
    f['last_swing_low'] = f.swing_low.ffill()
    return f


def calculate(candles, interval, config=None):
    """One output per complete input candle, available only at its close boundary."""
    validate(candles, interval)
    cfg = config or Config()
    a = candles.reset_index(drop=True)
    segments = a.open_time.diff().ne(duration(interval)).cumsum()
    outputs = []
    for segment, part in a.groupby(segments, sort=False):
        f = _segment(part.reset_index(drop=True), interval, cfg)
        f['segment_id'] = int(segment)
        f['bars_since_gap'] = np.arange(1, len(f)+1)
        outputs.append(f)
    if not outputs:
        f = _segment(a, interval, cfg)
        f['segment_id'] = pd.Series(dtype='int64')
        f['bars_since_gap'] = pd.Series(dtype='int64')
        return f
    result = pd.concat(outputs, ignore_index=True)
    if np.isinf(result.select_dtypes('number').to_numpy()).any():
        raise ValueError('Nonfinite indicator output')
    return result
