"""Long-only path labels on complete contiguous 5m candles."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from market_data.schema import validate, duration


@dataclass(frozen=True)
class Costs:
    fee: float = .001
    half_spread: float = .00005
    slippage: float = .00015

    def __post_init__(self):
        if any(not np.isfinite(x) or x < 0 or x >= .1 for x in (self.fee,self.half_spread,self.slippage)):
            raise ValueError('Invalid per-side costs')

    @property
    def friction(self): return self.half_spread+self.slippage

    def net(self, entry, exit):
        return exit*(1-self.friction)*(1-self.fee)/(entry*(1+self.friction)*(1+self.fee))-1


SCENARIOS = {'standard':Costs(), 'bnb_conditional':Costs(fee=.00075),
             'stress':Costs(fee=.001,half_spread=.0001,slippage=.0004)}


def label_paths(observations, candles, horizons=(1,4,12,24), stop_atr=2., take_atr=3., entry_delay_minutes=5):
    validate(candles,'5m')
    if any(type(h) is not int or h <= 0 for h in horizons) or stop_atr <= 0 or take_atr <= 0:
        raise ValueError('Positive horizons and barrier multiples required')
    if type(entry_delay_minutes) is not int or entry_delay_minutes < 0 or entry_delay_minutes % 5:
        raise ValueError('Entry delay must be a nonnegative multiple of five minutes')
    if observations.observation_id.duplicated().any(): raise ValueError('Duplicate observation IDs')
    a=candles.reset_index(drop=True)
    times=a.open_time.astype('int64').to_numpy()
    op,hi,lo,cl=(a[k].to_numpy() for k in ('open','high','low','close'))
    step=duration('5m').value
    # A gap prefix sum makes full-horizon continuity checks constant-time.
    gaps=np.r_[0,np.cumsum(np.diff(times)!=step)]
    rows=[]
    for obs in observations.itertuples():
        t=pd.Timestamp(obs.available_at)
        if t.tzinfo is None: raise ValueError('UTC-aware decision time required')
        entry_at=t+pd.Timedelta(minutes=entry_delay_minutes)
        index=int(np.searchsorted(times,entry_at.value))
        decision_index=int(np.searchsorted(times,t.value))
        for hours in horizons:
            n=hours*12; end=index+n
            row={'observation_id':obs.observation_id,'hours':hours,'decision_at':t,
                 'entry_at':entry_at,'label_end':entry_at+pd.Timedelta(hours=hours)}
            if index>=len(a) or times[index]!=entry_at.value:
                row['status']='missing_entry'; rows.append(row);continue
            if decision_index>=len(a) or times[decision_index]!=t.value or gaps[index]!=gaps[decision_index]:
                row['status']='execution_gap';rows.append(row);continue
            if end>len(a):
                row['status']='insufficient_future';rows.append(row);continue
            if gaps[end-1]!=gaps[index]:
                row['status']='path_gap';rows.append(row);continue
            entry=float(op[index]); exit=float(cl[end-1]); highs=hi[index:end]; lows=lo[index:end]
            row.update(status='complete', entry_raw=entry, exit_raw=exit, gross_return=exit/entry-1,
                       mfe=float(highs.max()/entry-1),mae=float(lows.min()/entry-1),
                       time_to_mfe_minutes=int((np.argmax(highs)+1)*5),
                       time_to_mae_minutes=int((np.argmin(lows)+1)*5))
            for name,cost in SCENARIOS.items(): row['net_'+name]=cost.net(entry,exit)
            atr=float(obs.atr)
            if np.isfinite(atr) and atr>0:
                sl=entry-stop_atr*atr;tp=entry+take_atr*atr
                if sl<=0: row['barrier_status']='invalid_stop'
                else:
                    stop_hits=np.flatnonzero(lows<=sl); take_hits=np.flatnonzero(highs>=tp)
                    s=int(stop_hits[0]) if len(stop_hits) else n
                    p=int(take_hits[0]) if len(take_hits) else n
                    row.update(stop_hit=s<n,take_hit=p<n,
                               time_to_stop_minutes=(s+1)*5 if s<n else np.nan,
                               time_to_take_minutes=(p+1)*5 if p<n else np.nan)
                    first=min(s,p)
                    if first==n: reason='time_exit';px=exit
                    elif s<=p: reason='stop';px=min(sl,float(op[index+first]))
                    else: reason='take';px=tp
                    row.update(barrier_status='complete',barrier_exit=reason,
                               ambiguous_same_bar=bool(s==p and s<n),barrier_exit_raw=px,
                               barrier_minutes=(first+1)*5 if first<n else hours*60)
                    for name,cost in SCENARIOS.items():row['barrier_net_'+name]=cost.net(entry,px)
            else: row['barrier_status']='missing_atr'
            rows.append(row)
    return pd.DataFrame(rows)
