"""Feature-only signals, conservative scheduling and explicit rejection gates."""
import numpy as np
import pandas as pd

CANDIDATES=('trend_breakout','trend_retest','range_rsi_recovery')


def entry_masks(f):
    required=['available_at','segment_id','atr','trend','trend_1h','trend_4h','volatility',
              'rsi','resistance_breakout','resistance_retest']
    if any(c not in f for c in required):raise ValueError('Missing causal feature')
    if not f.available_at.is_monotonic_increasing or f.available_at.duplicated().any():
        raise ValueError('Feature timestamps must be sorted and unique')
    valid=f.atr.gt(0)&np.isfinite(f.atr)&f.volatility.isin(['low','normal'])
    bullish=(f.trend_1h=='bullish')&(f.trend_4h=='bullish')
    ranging=(f.trend=='ranging')&(f.trend_1h=='ranging')&(f.trend_4h=='ranging')
    previous=f.groupby('segment_id',sort=False).rsi.shift()
    recovery=previous.lt(30)&f.rsi.ge(30)
    return pd.DataFrame({
        'trend_breakout':valid&bullish&f.resistance_breakout,
        'trend_retest':valid&bullish&f.resistance_retest,
        'range_rsi_recovery':valid&ranging&recovery,
        'unfiltered_breakout':f.atr.gt(0)&f.resistance_breakout,
        'unfiltered_rsi_recovery':f.atr.gt(0)&recovery
    },index=f.index).fillna(False).astype(bool)


def scheduled(frame,cooldown_minutes=60):
    chosen=[];next_time=None
    for row in frame.sort_values(['decision_at','observation_id']).itertuples():
        if next_time is None or row.decision_at>=next_time:
            chosen.append(row.Index)
            next_time=row.label_end+pd.Timedelta(minutes=cooldown_minutes)
    return frame.loc[chosen].copy()


def evaluate_gates(train,recent,inference,q,registry):
    g=registry['gates']
    def positive(value):return value is not None and np.isfinite(value) and value>0
    checks={
        'training_count':train['standard']['n']>=g['minimum_training_observations'],
        'training_nonoverlap_count':train['nonoverlap']['n']>=g['minimum_training_nonoverlap_observations'],
        'active_blocks':inference.get('active_blocks',0)>=g['minimum_active_28day_blocks'],
        'positive_net_ci':positive(inference.get('net_ci95',[None])[0]),
        'positive_excess_ci':positive(inference.get('excess_ci95',[None])[0]),
        'multiplicity':q<g['combined_exploratory_by_q_below'],
        'positive_stress':positive(train['stress'].get('mean')),
        'positive_training_years':train['positive_years']>=g['minimum_positive_training_years'],
        'positive_nonoverlap':positive(train['nonoverlap'].get('mean')),
        'recent_count':recent['standard']['n']>=g['minimum_reused_observations'],
        'recent_standard':positive(recent['standard'].get('mean')),
        'recent_stress':positive(recent['stress'].get('mean'))}
    return {'passed':all(checks.values()),'checks':checks,'failed':[k for k,v in checks.items() if not v]}


def proposed_allocation(equity,available_cash,entry,atr,cost):
    """Research proposal only, without order submission or exchange lot rounding."""
    if any(not np.isfinite(x) or x<=0 for x in (equity,available_cash,entry,atr)):
        raise ValueError('Positive finite sizing inputs required')
    stop=entry-2*atr
    if stop<=0:raise ValueError('Invalid stop')
    loss=-cost.net(entry,stop)
    quote=min(.005*equity/loss,.25*equity,available_cash)
    quantity=quote/(entry*(1+cost.friction)*(1+cost.fee))
    return {'quote_budget':quote,'unrounded_quantity':quantity,'planned_loss_quote':quote*loss,
            'planned_loss_fraction':loss,'requires_exchange_validation':True}
