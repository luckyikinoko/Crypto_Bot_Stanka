"""Causal re-entry definition and frequency checks."""
import numpy as np
import pandas as pd
from market_data.store import RESERVED_FROM
from research.discovery.engine import scheduled


def signal_mask(f):
    t=f.available_at
    if str(t.dt.tz)!='UTC' or t.isna().any() or t.duplicated().any() or not t.is_monotonic_increasing:
        raise ValueError('Sorted unique UTC decisions required')
    if (t>=RESERVED_FROM).any() or f.observation_id.duplicated().any():
        raise ValueError('Reserved or duplicate observations')
    previous=f.groupby('segment_id',sort=False)[['close','bb_lower']].shift()
    consecutive=t.diff().eq(pd.Timedelta(hours=1))
    valid=np.isfinite(f.close)&np.isfinite(f.bb_lower)&np.isfinite(previous.close)&np.isfinite(previous.bb_lower)
    return (valid & consecutive & previous.close.lt(previous.bb_lower) & f.close.ge(f.bb_lower)).fillna(False).astype(bool)


def frequency(f,start,end):
    if end>RESERVED_FROM or start>=end:
        raise ValueError('Invalid pool')
    mask=signal_mask(f)&f.available_at.ge(start)&f.available_at.lt(end)
    selected=f.loc[mask,['observation_id','available_at']].rename(columns={'available_at':'decision_at'})
    selected['label_end']=selected.decision_at+pd.Timedelta(hours=24,minutes=5)
    kept=selected[selected.label_end<=end]
    return {'raw':len(selected),'timing_eligible':len(kept),'boundary_purged':len(selected)-len(kept),
            'scheduled_nonoverlap':len(scheduled(kept)),
            'active_28day_blocks':int(((kept.decision_at-start.floor('D')).dt.total_seconds()//(28*86400)).nunique())}
