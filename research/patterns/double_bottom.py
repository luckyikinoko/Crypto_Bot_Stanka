"""Causal double-bottom V1, isolated from the existing pattern catalog."""
import hashlib
import json
import numpy as np
from market_data.schema import validate
from market_data.store import RESERVED_FROM
from research.indicators import calculate
from .engine import event_frame

PARAMETERS = {'pivot_left':2,'pivot_right':2,'minimum_separation':6,'maximum_separation':48,
    'prior_window':12,'minimum_prior_drop_atr':2.,'low_tolerance_atr':.5,
    'minimum_rebound_atr':1.,'breakout_buffer_atr':.1,'invalidation_buffer_atr':.25,
    'confirmation_expiry_bars':12}


def detect(candles, interval='1h'):
    """Emit once at confirmation close; never backdate a confirmed pivot or signal."""
    if interval!='1h':raise ValueError('Only the registered 1h definition is supported')
    validate(candles,interval)
    if (candles.available_at>=RESERVED_FROM).any():raise ValueError('Reserved data blocked')
    p=PARAMETERS
    features=calculate(candles,interval)
    rows=[];params=json.dumps(p,sort_keys=True)
    for _,a in candles.reset_index(drop=True).groupby(features.segment_id,sort=False):
        f=features.loc[a.index].reset_index(drop=True);a=a.reset_index(drop=True)
        low=a.low.to_numpy();high=a.high.to_numpy();close=a.close.to_numpy();atr=f.atr.to_numpy()
        previous_pivot=None;pending=None
        for t in range(len(a)):
            j=t-p['pivot_right']
            # Strict local minimum, known only after both right-hand candles close.
            pivot=(j>=p['pivot_left'] and low[j]<min(low[j-2:j]) and low[j]<min(low[j+1:j+3]))
            if pivot:
                i=previous_pivot
                # Every newly confirmed pivot supersedes any pending pair.
                pending=None;previous_pivot=j
                if i is not None and p['minimum_separation']<=j-i<=p['maximum_separation'] and i>=p['prior_window']:
                    scale=atr[i+p['pivot_right']]
                    if np.isfinite(scale) and scale>0:
                        neck=float(max(high[i+1:j]));floor=float(min(low[i],low[j]))
                        prior_drop=float(max(high[i-p['prior_window']:i])-low[i])
                        similar=abs(low[j]-low[i])<=p['low_tolerance_atr']*scale
                        rebound=neck-max(low[i],low[j])>=p['minimum_rebound_atr']*scale
                        threshold=neck+p['breakout_buffer_atr']*scale
                        invalid=floor-p['invalidation_buffer_atr']*scale
                        # A breakout before the second pivot is recognizable is rejected.
                        premature=np.any(close[j+1:t]>threshold)
                        breached=np.any(low[j+1:t+1]<invalid)
                        if similar and rebound and prior_drop>=p['minimum_prior_drop_atr']*scale and not premature and not breached:
                            pending={'first':i,'second':j,'ready':t,'atr':float(scale),'neckline':neck,
                                     'threshold':threshold,'invalid':invalid,'prior_drop':prior_drop}
            if pending is None:continue
            s=pending
            if t-s['ready']>p['confirmation_expiry_bars'] or low[t]<s['invalid']:
                pending=None;continue
            # Low breach wins if both invalidation and breakout occur in one candle.
            if t>0 and close[t-1]<=s['threshold'] and close[t]>s['threshold']:
                i,j=s['first'],s['second']
                identity='|'.join([interval,'double_bottom_v1',str(a.open_time.iloc[i]),
                                   str(a.open_time.iloc[j]),str(a.available_at.iloc[t]),params])
                metrics={'first_low_time':str(a.open_time.iloc[i]),'second_low_time':str(a.open_time.iloc[j]),
                    'first_pivot_known_at':str(a.available_at.iloc[i+2]),'second_pivot_known_at':str(a.available_at.iloc[s['ready']]),
                    'first_low':float(low[i]),'second_low':float(low[j]),'neckline':s['neckline'],
                    'frozen_atr':s['atr'],'separation_bars':j-i,'confirmation_wait_bars':t-s['ready'],
                    'low_difference_atr':float(abs(low[j]-low[i])/s['atr']),
                    'rebound_atr':float((s['neckline']-max(low[i],low[j]))/s['atr']),
                    'prior_drop_atr':s['prior_drop']/s['atr'],
                    'breakout_distance_atr':float((close[t]-s['neckline'])/s['atr'])}
                context={key:float(f[key].iloc[t]) if np.isfinite(f[key].iloc[t]) else None for key in ('atr','rsi','ema_50','ema_200')}
                rows.append({'formation_start':a.open_time.iloc[i],'formation_end':a.available_at.iloc[s['ready']],
                    'available_at':a.available_at.iloc[t],'event_id':hashlib.sha256(identity.encode()).hexdigest(),
                    'parent_event_id':'','pattern':'double_bottom_v1','direction':'bullish','status':'confirmed','interval':interval,
                    'parameters':params,'metrics':json.dumps(metrics,sort_keys=True,allow_nan=False),
                    'context':json.dumps(context,sort_keys=True,allow_nan=False)})
                pending=None
    return event_frame(rows)
