"""Canonical UTC candle contract and validation independent of trading code."""
import numpy as np
import pandas as pd

MINUTES={'5m':5,'15m':15,'1h':60,'4h':240,'1d':1440}
VALUES=['open','high','low','close','volume','quote_volume','trades','taker_base','taker_quote']
COLUMNS=['open_time','available_at',*VALUES]

def utc(value):
    t=pd.Timestamp(value)
    return t.tz_localize('UTC') if t.tzinfo is None else t.tz_convert('UTC')

def duration(interval):
    return pd.Timedelta(minutes=MINUTES[interval])

def empty():
    f=pd.DataFrame({k:pd.Series(dtype='float64') for k in VALUES})
    f['trades']=f.trades.astype('int64')
    for c in ['open_time','available_at']:f[c]=pd.Series(dtype='datetime64[ns, UTC]')
    return f[COLUMNS]

def normalize(rows, interval, cutoff, quarantine=None):
    """Archive/API 12-field klines. Return complete canonical rows and drop count."""
    if not len(rows):return empty(),0
    a=pd.DataFrame(rows).copy()
    if a.shape[1]!=12:raise ValueError('Expected 12 Binance kline fields')
    a.columns=['open_time','open','high','low','close','volume','close_time','quote_volume','trades','taker_base','taker_quote','ignore']
    op=pd.to_numeric(a.open_time,errors='raise').astype('int64')
    cl=pd.to_numeric(a.close_time,errors='raise').astype('int64')
    # Source epoch values can use milliseconds or microseconds; preserve precision.
    micro=op>10**14
    opns=np.where(micro,op*1000,op*1000000)
    clns=np.where(micro,cl*1000,cl*1000000)
    expected=opns+duration(interval).value-np.where(micro,1000,1000000)
    bad_close=clns!=expected
    off_grid=opns%duration(interval).value!=0
    bad=bad_close|off_grid
    if bad.any() and quarantine is None:raise ValueError('Invalid source candle timestamp/boundary')
    if bad.any():
        for i in np.flatnonzero(bad):
            quarantine.append({'open_time_raw':int(op.iloc[i]),'close_time_raw':int(cl.iloc[i]),
                               'open_time_utc':str(pd.to_datetime(opns[i],unit='ns',utc=True)),
                               'reason':'off_grid_open' if off_grid[i] else 'nonstandard_close_boundary'})
    a['open_time']=pd.to_datetime(opns,unit='ns',utc=True)
    a['available_at']=a.open_time+duration(interval)
    a=a.loc[~bad].copy()
    for c in VALUES:a[c]=pd.to_numeric(a[c],errors='raise')
    if ((a.trades%1)!=0).any():raise ValueError('Non-integer trade count')
    a['trades']=a.trades.astype('int64')
    for c in set(VALUES)-{'trades'}:a[c]=a[c].astype('float64')
    a=a[COLUMNS]
    # Structural integrity also checked for incomplete rows before dropping them.
    validate(a,interval,allow_duplicates=True)
    dropped=int((a.available_at>utc(cutoff)).sum())
    return a.loc[a.available_at<=utc(cutoff)].reset_index(drop=True),dropped

def validate(a,interval,allow_duplicates=False):
    if list(a.columns)!=COLUMNS:raise ValueError('Unexpected candle schema')
    for c in ['open_time','available_at']:
        if str(a[c].dtype)!='datetime64[ns, UTC]' or a[c].isna().any():raise ValueError('UTC timestamp dtype required')
    if a.empty:return
    step=duration(interval)
    if ((a.open_time.astype('int64')%step.value)!=0).any():raise ValueError('Off-grid candle timestamp')
    if not (a.available_at==a.open_time+step).all():raise ValueError('Incorrect availability boundary')
    if not np.isfinite(a[VALUES].to_numpy()).all():raise ValueError('Non-finite candle value')
    if (a[['open','high','low','close']]<=0).any().any():raise ValueError('Nonpositive price')
    if (a[['volume','quote_volume','trades','taker_base','taker_quote']]<0).any().any():raise ValueError('Negative volume/trades')
    if ((a.trades%1)!=0).any():raise ValueError('Non-integer trade count')
    if (a.high<a[['open','low','close']].max(axis=1)).any() or (a.low>a[['open','high','close']].min(axis=1)).any():raise ValueError('Inconsistent OHLC')
    if (a.taker_base>a.volume+1e-7).any() or (a.taker_quote>a.quote_volume+1e-5).any():raise ValueError('Taker volume exceeds total')
    if not allow_duplicates and (a.open_time.duplicated().any() or not a.open_time.is_monotonic_increasing):raise ValueError('Duplicate/unordered candles')

def merge_frames(frames,interval):
    a=pd.concat(frames,ignore_index=True) if frames else empty()
    if a.empty:return empty(),0
    duplicate_rows=a[a.open_time.duplicated(keep=False)]
    if not duplicate_rows.empty and (duplicate_rows.groupby('open_time')[COLUMNS[1:]].nunique(dropna=False)>1).any().any():
        raise ValueError('Conflicting candles at same open time')
    count=int(a.open_time.duplicated().sum())
    a=a.drop_duplicates('open_time').sort_values('open_time').reset_index(drop=True)
    validate(a,interval)
    return a,count

def aggregate(base,interval):
    validate(base,'5m')
    if interval=='5m':return base.copy()
    n=MINUTES[interval]//5
    b=base.set_index('open_time')
    freq=f'{MINUTES[interval]}min'
    rules={'open':'first','high':'max','low':'min','close':'last','volume':'sum','quote_volume':'sum','trades':'sum','taker_base':'sum','taker_quote':'sum'}
    res=b.resample(freq,origin='epoch',closed='left',label='left').agg(rules)
    counts=b.close.resample(freq,origin='epoch',closed='left',label='left').count()
    res=res[counts==n].reset_index()
    res['available_at']=res.open_time+duration(interval)
    res['trades']=res.trades.astype('int64')
    res=res[COLUMNS];validate(res,interval)
    return res

def quality(a,interval,start,cutoff):
    validate(a,interval)
    step=duration(interval)
    start=utc(start).ceil(f'{MINUTES[interval]}min')
    end=utc(cutoff).floor(f'{MINUTES[interval]}min')
    expected=pd.date_range(start,end,freq=step,inclusive='left')
    missing=expected.difference(pd.DatetimeIndex(a.open_time))
    ranges=[]
    if len(missing):
        begins=np.r_[0,np.flatnonzero(np.diff(missing.asi8)!=step.value)+1]
        ends=np.r_[begins[1:]-1,len(missing)-1]
        ranges=[{'start':str(missing[b]),'end_exclusive':str(missing[e]+step),'candles':int(e-b+1)} for b,e in zip(begins,ends)]
    return {'interval':interval,'rows':len(a),'expected_rows':len(expected),'missing_candles':len(missing),'gaps':ranges,
            'zero_volume_candles':int((a.volume==0).sum()),'first_open':str(a.open_time.iloc[0]) if len(a) else None,
            'last_available_at':str(a.available_at.iloc[-1]) if len(a) else None,
            'quality_status':'gaps_documented' if len(missing) else 'complete'}

def align_available(decisions,features,columns,interval):
    """Backward as-of join with expiry: a missing next higher bar yields NaN."""
    if features.available_at.duplicated().any():raise ValueError('Duplicate feature availability')
    left=pd.DataFrame({'decision_at':pd.to_datetime(decisions,utc=True)}).sort_values('decision_at')
    right=features[['available_at',*columns]].sort_values('available_at')
    result=pd.merge_asof(left,right,left_on='decision_at',right_on='available_at',direction='backward',allow_exact_matches=True)
    stale=(result.decision_at-result.available_at)>=duration(interval)
    result.loc[stale,columns]=np.nan
    result.loc[stale,'available_at']=pd.NaT
    return result
