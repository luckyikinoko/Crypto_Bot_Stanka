"""Descriptive summaries and calendar-block bootstrap comparisons."""
import numpy as np
import pandas as pd


def describe(frame, column='net_standard'):
    r=frame[column].dropna().to_numpy()
    if not len(r): return {'n':0}
    win=r[r>0];lose=r[r<0]
    result={'n':len(r),'win_rate':float((r>0).mean()),'mean':float(r.mean()),'median':float(np.median(r)),
            'average_winner':float(win.mean()) if len(win) else None,
            'average_loser':float(lose.mean()) if len(lose) else None,
            'profit_factor':float(win.sum()/-lose.sum()) if len(lose) else None,
            'p05':float(np.quantile(r,.05)),'p95':float(np.quantile(r,.95))}
    for name in ('mfe','mae'):
        if name in frame:
            result[name+'_median']=float(frame[name].median())
            result[name+'_p05']=float(frame[name].quantile(.05))
            result[name+'_p95']=float(frame[name].quantile(.95))
    return result


def nonoverlapping(frame):
    chosen=[]; end=None
    for row in frame.sort_values(['decision_at','observation_id']).itertuples():
        if end is None or row.decision_at>=end:
            chosen.append(row.Index);end=row.label_end
    return frame.loc[chosen].copy()


def drawdown(returns):
    equity=np.r_[1.,np.cumprod(1+np.asarray(returns))]
    return float((equity/np.maximum.accumulate(equity)-1).min())


def block_compare(signal, baseline, block_days=28, draws=4999, seed=20261011):
    """Paired calendar-block resampling of signal and unconditional baseline sums/counts.

    Percentile CIs and centered one-sided bootstrap p-values are approximate.
    Requires >=30 signal-active blocks; no iid event bootstrap.
    """
    if signal.empty or baseline.empty:return {'eligible':False,'reason':'empty'}
    origin=baseline.decision_at.min().floor('D')
    def aggregate(f):
        block=((f.decision_at-origin).dt.total_seconds()//(block_days*86400)).astype(int)
        return f.groupby(block).net_standard.agg(['sum','count'])
    b=aggregate(baseline);s=aggregate(signal)
    index=np.arange(int(b.index.min()),int(b.index.max())+1)
    bv=b.reindex(index,fill_value=0).to_numpy();sv=s.reindex(index,fill_value=0).to_numpy()
    active=int((sv[:,1]>0).sum())
    result={'eligible':False,'block_days':block_days,'active_blocks':active,'calendar_blocks':len(index)}
    if active<30:return {**result,'reason':'fewer_than_30_active_blocks'}
    observed=sv[:,0].sum()/sv[:,1].sum()-bv[:,0].sum()/bv[:,1].sum()
    rng=np.random.default_rng(seed); net=[];excess=[]
    for begin in range(0,draws,250):
        picks=rng.integers(0,len(index),(min(250,draws-begin),len(index)))
        ss=sv[picks].sum(axis=1);bb=bv[picks].sum(axis=1)
        valid=(ss[:,1]>0)&(bb[:,1]>0)
        means=ss[valid,0]/ss[valid,1]
        net.extend(means);excess.extend(means-bb[valid,0]/bb[valid,1])
    net=np.asarray(net);excess=np.asarray(excess)
    return {**result,'eligible':True,'net_ci95':np.quantile(net,[.025,.975]).tolist(),
            'excess_mean':float(observed),'excess_ci95':np.quantile(excess,[.025,.975]).tolist(),
            'p_one_sided':float((1+((excess-observed)>=observed).sum())/(len(excess)+1)),
            'draws':len(excess)}


def adjust_by(pvalues):
    """Benjamini-Yekutieli FDR correction under arbitrary test dependence."""
    p=np.asarray(pvalues,dtype=float)
    if not len(p):return []
    order=np.argsort(p);m=len(p);factor=np.sum(1/np.arange(1,m+1))
    q=np.minimum.accumulate((p[order]*m*factor/np.arange(1,m+1))[::-1])[::-1]
    result=np.empty(m);result[order]=np.minimum(q,1)
    return result.tolist()
