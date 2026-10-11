"""Fixed definitions version 1; see docs/PATTERNS.md before interpreting events."""
from dataclasses import dataclass, asdict
import hashlib
import json
import numpy as np
import pandas as pd
from market_data.schema import validate, duration
from research.indicators import calculate


@dataclass(frozen=True)
class Config:
    pole: int = 8
    flag: int = 6
    pole_atr: float = 3.0
    retracement: float = .5
    flag_width: float = .5
    volume_ratio: float = 1.0
    breakout_window: int = 20
    breakout_buffer_atr: float = .1
    retest_bars: int = 12
    retest_tolerance_atr: float = .25
    engulf_body_atr: float = .5

    def __post_init__(self):
        for name in ('pole', 'flag', 'breakout_window', 'retest_bars'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 2:
                raise ValueError(name+' must be an integer >= 2')
        for name, value in asdict(self).items():
            if not np.isfinite(value) or value <= 0:
                raise ValueError(name+' must be finite and positive')
        if self.retracement > 1 or self.flag_width > 1 or self.volume_ratio > 1:
            raise ValueError('Flag ratios must not exceed one')


TIME_COLUMNS = ['formation_start', 'formation_end', 'available_at']
TEXT_COLUMNS = ['event_id', 'parent_event_id', 'pattern', 'direction', 'status', 'interval', 'parameters', 'metrics', 'context']
COLUMNS = TIME_COLUMNS + TEXT_COLUMNS


def event_frame(rows):
    f = pd.DataFrame(rows, columns=COLUMNS)
    for c in TIME_COLUMNS:
        f[c] = pd.to_datetime(f[c], utc=True)
    for c in TEXT_COLUMNS:
        f[c] = f[c].astype('string')
    return f.sort_values(['available_at', 'pattern', 'event_id']).reset_index(drop=True)


def detect(candles, interval, config=None):
    """Confirmed events only. Pending/rejected candidates are not retrospectively labeled."""
    validate(candles, interval)
    cfg = config or Config()
    features = calculate(candles, interval)
    rows = []
    parameters = json.dumps(asdict(cfg), sort_keys=True)
    groups = candles.reset_index(drop=True).groupby(features.segment_id, sort=False)
    for _, a in groups:
        f = features.loc[a.index].reset_index(drop=True)
        a = a.reset_index(drop=True)
        o, h, l, c, v = (a[key].to_numpy() for key in ('open', 'high', 'low', 'close', 'volume'))
        atr = f.atr.to_numpy()

        def emit(pattern, direction, start, end, t, metrics, parent=''):
            context = {key: float(f[key].iloc[t]) if pd.notna(f[key].iloc[t]) else None
                       for key in ('atr', 'rsi', 'ema_50', 'ema_200', 'relative_volume', 'historical_volatility')}
            # Identity does not depend on later observations or dataset length.
            identity = '|'.join([interval, pattern, str(a.open_time.iloc[start]),
                                 str(a.available_at.iloc[t]), parameters, parent])
            eid = hashlib.sha256(identity.encode()).hexdigest()
            rows.append(dict(formation_start=a.open_time.iloc[start], formation_end=a.available_at.iloc[end],
                             available_at=a.available_at.iloc[t], event_id=eid, parent_event_id=parent,
                             pattern=pattern, direction=direction, status='confirmed', interval=interval,
                             parameters=parameters, metrics=json.dumps(metrics, sort_keys=True, allow_nan=False),
                             context=json.dumps(context, sort_keys=True, allow_nan=False)))
            return eid

        window = cfg.breakout_window
        resistance = a.high.shift().rolling(window).max().to_numpy()
        x = np.arange(cfg.flag, dtype=float)
        weights = (x-x.mean())/((x-x.mean())**2).sum()
        pending = []
        for t in range(1, len(a)):
            prior_atr = atr[t-1]
            if not np.isfinite(prior_atr) or prior_atr <= 0:
                continue
            # Old breakouts use their frozen level and ATR, never the moving resistance.
            keep = []
            for state in pending:
                age = t-state['t']
                level, tolerance = state['level'], state['atr']*cfg.retest_tolerance_atr
                if age > cfg.retest_bars or c[t] < level-tolerance:
                    continue
                if l[t] <= level+tolerance and h[t] >= level-tolerance and c[t] > level:
                    emit('resistance_retest', 'bullish', state['start'], state['t'], t,
                         {'level': level, 'breakout_atr': state['atr'], 'age_bars': age,
                          'close_distance_atr': (c[t]-level)/state['atr']}, state['id'])
                else:
                    keep.append(state)
            pending = keep
            if t >= window and c[t] > resistance[t]+cfg.breakout_buffer_atr*prior_atr and c[t-1] <= resistance[t]:
                level = float(resistance[t])
                eid = emit('resistance_breakout', 'bullish', t-window, t-1, t,
                           {'level': level, 'breakout_atr': float(prior_atr),
                            'close_distance_atr': (c[t]-level)/prior_atr})
                pending.append({'id': eid, 't': t, 'start': t-window, 'level': level, 'atr': float(prior_atr)})
            body = abs(c[t]-o[t])
            if body >= cfg.engulf_body_atr*prior_atr:
                bull = c[t-1] < o[t-1] and c[t] > o[t] and o[t] <= c[t-1] and c[t] >= o[t-1]
                bear = c[t-1] > o[t-1] and c[t] < o[t] and o[t] >= c[t-1] and c[t] <= o[t-1]
                strict = o[t] != c[t-1] or c[t] != o[t-1]
                if strict and (bull or bear):
                    emit('bullish_engulfing' if bull else 'bearish_engulfing', 'bullish' if bull else 'bearish', t-1, t, t,
                         {'body_atr': body/prior_atr, 'previous_body_atr': abs(c[t-1]-o[t-1])/prior_atr})
            p, k = cfg.pole, cfg.flag
            s, b = t-k-p, t-k
            if s < 1 or not np.isfinite(atr[s-1]) or atr[s-1] <= 0:
                continue
            height = c[b-1]-c[s-1]
            if height < cfg.pole_atr*atr[s-1]:
                continue
            pole_high = h[s:b].max()
            flag_high, flag_low = h[b:t].max(), l[b:t].min()
            retrace = (pole_high-flag_low)/height
            width = (flag_high-flag_low)/height
            slope = float(np.dot(c[b:t], weights))
            pole_volume = v[s:b].mean()
            ratio = v[b:t].mean()/pole_volume if pole_volume > 0 else np.nan
            if (0 <= retrace <= cfg.retracement and width <= cfg.flag_width and slope <= 0
                    and flag_high <= pole_high and ratio <= cfg.volume_ratio
                    and c[t] > flag_high+cfg.breakout_buffer_atr*prior_atr):
                emit('bull_flag', 'bullish', s, t-1, t,
                     {'pole_height_atr': height/atr[s-1], 'retracement_fraction': retrace,
                      'flag_width_fraction': width, 'channel_slope_atr_per_bar': slope/prior_atr,
                      'flag_to_pole_volume': ratio, 'breakout_level': float(flag_high),
                      'breakout_distance_atr': (c[t]-flag_high)/prior_atr})
    return event_frame(rows)
