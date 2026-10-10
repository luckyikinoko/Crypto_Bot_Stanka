"""Run the pre-registered Experiment 002; never downloads or reads holdout archives."""
import hashlib
import json
from pathlib import Path
from breakout_strategy import breakout_signals
import numpy as np
import pandas as pd
from btc_backtest import Config, read_data, indicators, run

OUT = Path('reports/experiment_002')

def bootstrap(quarters, draws=2000, block=7, seed=1001):
    """Resample contiguous weekly blocks within each fixed quarter; retain cash days."""
    rng = np.random.default_rng(seed)
    sums = np.zeros(draws)
    for daily in quarters:
        a = np.asarray(daily, dtype=float)
        n = len(a)
        starts = rng.integers(0, n, size=(draws, int(np.ceil(n/block))))
        ix = (starts[...,None]+np.arange(block)) % n
        sums += a[ix.reshape(draws,-1)[:,:n]].sum(axis=1)
    return {'draws':draws,'block_days':block,'seed':seed,
            'summed_episode_pnl_95pct_interval':np.quantile(sums,[.025,.975]).tolist(),
            'note':'Descriptive circular block bootstrap of daily realized episode P&L; not a compounded portfolio or deployment confidence.'}

def main():
    folder = Path('data')
    if any(p.name[11:18] >= '2026-04' for p in folder.glob('BTCUSDT-1m-*.zip')):
        raise ValueError('Holdout/later archives detected: isolate development data first')
    df = read_data(folder)
    if df.index[-1] >= pd.Timestamp('2026-04-01',tz='UTC'):
        raise ValueError('Holdout data prohibited')
    sig = indicators(df)
    breakout = breakout_signals(df)
    OUT.mkdir(parents=True,exist_ok=True)
    variants = {'baseline':Config(), 'breakout':Config(),
                'breakout_stress':Config(slippage=.0004)}
    continuous = {}
    for name,c in variants.items():
        t,e,s = run(df,c,start='2024-01-01T00:00:00Z',end='2026-04-01T00:00:00Z',signals=sig if name=='baseline' else breakout)
        if name == 'baseline':
            saved=json.loads(Path('reports/baseline/summary.json').read_text())
            assert abs(saved['final_equity']-s['final_equity']) < 1e-8, 'Baseline regression'
            assert saved['trades']==s['trades'], 'Trade count regression'
        t.to_csv(OUT/f'continuous_{name}_trades.csv',index=False)
        continuous[name]=s
        print('continuous',name,s['trades'],round(s['net_profit'],2),flush=True)
    episodes=[]; ledgers={k:[] for k in variants}; daily={k:[] for k in variants}
    for period in pd.period_range('2024Q2','2026Q1',freq='Q'):
        start=period.start_time.tz_localize('UTC')
        end=(period+1).start_time.tz_localize('UTC')
        window=df.loc[(df.index>=start-pd.Timedelta(hours=1000)) & (df.index<end)]
        for name,c in variants.items():
            t,e,s=run(window,c,start=start,end=end,signals=sig if name=='baseline' else breakout)
            s.update(quarter=str(period),variant=name)
            episodes.append(s)
            if len(t):
                t['quarter']=str(period);t['variant']=name
                ledgers[name].append(t)
                realized=t.groupby(t.exit_time.dt.floor('D')).pnl.sum()
                # A terminal fill at next-quarter midnight belongs to this episode's final day.
                if end in realized.index:
                    realized.loc[end-pd.Timedelta(days=1)]=realized.get(end-pd.Timedelta(days=1),0)+realized.loc[end]
                    realized=realized.drop(end)
            else:
                realized=pd.Series(dtype=float)
            days=pd.date_range(start,end-pd.Timedelta(days=1),freq='D')
            daily[name].append(realized.reindex(days,fill_value=0).to_numpy())
            print(period,name,s['trades'],round(s['net_profit'],2),flush=True)
    pooled={}
    for name,parts in ledgers.items():
        t=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
        t.to_csv(OUT/f'quarterly_{name}_trades.csv',index=False)
        pnl=t.pnl if len(t) else pd.Series(dtype=float)
        loss=-pnl[pnl<0].sum()
        qs=[x for x in episodes if x['variant']==name]
        pooled[name]={'trades':len(t),'sum_episode_pnl':float(pnl.sum()),'mean_r':float(t.r.mean()) if len(t) else None,
                      'profit_factor':float(pnl[pnl>0].sum()/loss) if loss else None,
                      'profitable_quarters':sum(x['net_profit']>0 for x in qs),'halted_quarters':sum(x['halted'] for x in qs),
                      'max_episode_drawdown':max(x['max_drawdown'] for x in qs),'bootstrap':bootstrap(daily[name])}
    cand,base,stress=(pooled[k] for k in ['breakout','baseline','breakout_stress'])
    gates={'positive_expectancy':bool(cand['mean_r'] is not None and cand['mean_r']>0),
           'profit_factor_above_1_20':bool(cand['profit_factor'] is not None and cand['profit_factor']>1.2),
           'improves_net_pnl':cand['sum_episode_pnl']>base['sum_episode_pnl'],
           'stress_positive':bool(stress['mean_r'] is not None and stress['mean_r']>0),
           'at_least_200_trades':cand['trades']>=200}
    gates['continuous_positive_no_halt'] = all(continuous[n]['net_profit']>0 and not continuous[n]['halted'] for n in ['breakout','breakout_stress'])
    result={'protocol':'research/EXPERIMENT_002.md','protocol_commit':'8e2c202ef4f8113158cb3068f52ad8ec78247730',
            'engine_sha256':hashlib.sha256(Path('btc_backtest.py').read_bytes()).hexdigest(),
            'strategy_sha256':hashlib.sha256(Path('breakout_strategy.py').read_bytes()).hexdigest(),
            'reused_development_data':True,'pandas':pd.__version__,'numpy':np.__version__,'continuous':continuous,'episodes':episodes,'pooled':pooled,
            'research_gates':gates,'retain_for_research':all(gates.values()),'holdout_accessed':False,
            'data_hashes':json.loads(Path('reports/baseline/summary.json').read_text())['data_sha256']}
    (OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    pd.DataFrame([{k:x[k] for k in ['quarter','variant','trades','net_profit','profit_factor','expectancy_r','max_drawdown','halted']} for x in episodes]).to_csv(OUT/'quarters.csv',index=False)
    print(json.dumps({'pooled':pooled,'gates':gates},indent=2),flush=True)

if __name__=='__main__':main()
