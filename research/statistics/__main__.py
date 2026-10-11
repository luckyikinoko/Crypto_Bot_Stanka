"""Frozen Milestone 4 descriptive research on development data only."""
import hashlib
import json
from pathlib import Path
import argparse
import platform
import numpy as np
import pandas as pd
import pyarrow
from market_data.schema import utc, align_available
from market_data.store import read_market, writer_lock, RESERVED_FROM, frame_hash
from market_data.source import atomic_bytes
from research.regimes import classify
from research.patterns.store import read_events
from .outcomes import label_paths, SCENARIOS
from .metrics import describe, nonoverlapping, drawdown, block_compare, adjust_by

PATTERNS=['bull_flag','resistance_breakout','resistance_retest','bullish_engulfing','bearish_engulfing']
SIGNALS=PATTERNS+['trend_rsi_volume','trend_rsi_volume_flag']


def make_features(source, patterns, start, end):
    primary=read_market(source,'15m',start,end,allow_gaps=True)
    f=classify(primary,'15m')
    for interval in ('1h','4h'):
        higher=classify(read_market(source,interval,start,end,allow_gaps=True),interval)
        aligned=align_available(f.available_at,higher,['trend','volatility'],interval)
        f['trend_'+interval]=aligned.trend.fillna('unknown').to_numpy()
        f['volatility_'+interval]=aligned.volatility.fillna('unknown').to_numpy()
    events=read_events(patterns,'15m',start,end)
    for pattern in PATTERNS:
        times=events.loc[events.pattern==pattern,'available_at']
        f[pattern]=f.available_at.isin(times)
    f['trend_rsi_volume']=((f.ema_50>f.ema_200)&f.rsi.between(48,65)&(f.relative_volume>1.3)
                           &(f.trend_1h=='bullish')&(f.trend_4h=='bullish')&(f.volatility=='normal'))
    f['trend_rsi_volume_flag']=f.trend_rsi_volume&f.bull_flag
    f['regime']=f.trend+'/'+f.volatility
    f['observation_id']=f.available_at.astype('int64').astype(str)
    f['pool']=np.where(f.available_at<utc('2024-01-01'),'research_2018_2023','reused_2024_2026Q1')
    return f


def save_frame(root,name,frame):
    payload=frame.to_parquet(index=False,compression='zstd')
    digest=hashlib.sha256(payload).hexdigest()
    path=Path(name)/ (digest+'.parquet')
    target=root/path
    if not target.exists():atomic_bytes(target,payload)
    if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise ValueError('Corrupt research file')
    pd.testing.assert_frame_equal(frame,pd.read_parquet(target))
    return {'path':str(path),'sha256':digest,'rows':len(frame)}


def run(source,patterns,destination,report_dir,draws=4999):
    source,patterns,root,report_dir=map(Path,(source,patterns,destination,report_dir))
    if root.resolve() in (source.resolve(),patterns.resolve()):raise ValueError('Separate output directory required')
    start='2018-01-01';end=str(RESERVED_FROM)
    before={str(p):p.read_bytes() for p in (source/'catalog.json',patterns/'catalog.json')}
    market=json.loads(before[str(source/'catalog.json')]);pattern=json.loads(before[str(patterns/'catalog.json')])
    if market['snapshot_id']!=pattern['source_snapshot']:raise ValueError('Pattern/source snapshot mismatch')
    with writer_lock(root):
        f=make_features(source,patterns,start,end)
        reuse={}
        prior_path=root/'catalog.json'
        if prior_path.exists():
            prior=json.loads(prior_path.read_text())
            code_root=Path(__file__).resolve().parents[2]
            relevant=['research/statistics/outcomes.py','research/indicators/engine.py']
            compatible=(prior['source_snapshot']==market['snapshot_id'] and
                        all(prior['code_sha256'].get(p)==hashlib.sha256((code_root/p).read_bytes()).hexdigest() for p in relevant))
            if compatible:
                meta=prior['features'];path=root/meta['path']
                if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('Corrupt cached features')
                old=pd.read_parquet(path)
                inputs=['observation_id','available_at','atr']
                if frame_hash(old[inputs])==frame_hash(f[inputs]):reuse=prior['labels']
        features_file=save_frame(root,'features',f)
        base=read_market(source,'5m',start,end,allow_gaps=True)
        summaries=[];slices=[];diagnostics=[];files={};quality={}
        for hours in (1,4,12,24):
            if str(hours) in reuse:
                meta=reuse[str(hours)];path=root/meta['path']
                if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('Corrupt cached labels')
                labels=pd.read_parquet(path)
            else:
                labels=label_paths(f[['observation_id','available_at','atr']],base,horizons=(hours,))
            files[str(hours)]=save_frame(root,'labels/'+str(hours),labels)
            quality[str(hours)]={str(k):int(v) for k,v in labels.status.value_counts().items()}
            joined=labels[labels.status=='complete'].merge(f[['observation_id','pool','trend','volatility','regime','trend_1h','trend_4h',*SIGNALS]],on='observation_id',validate='one_to_one')
            crossing=(joined.decision_at<utc('2024-01-01'))&(joined.label_end>utc('2024-01-01'))
            joined.loc[crossing,'pool']='boundary_purged'
            for signal in ['unconditional',*SIGNALS]:
                group=joined if signal=='unconditional' else joined[joined[signal]]
                row={'signal':signal,'hours':hours,'costs':{name:describe(group,'net_'+name) for name in SCENARIOS},
                     'gross':describe(group,'gross_return'),
                     'barriers':{name:describe(group,'barrier_net_'+name) for name in SCENARIOS}}
                if signal!='unconditional':
                    row['inference28']=block_compare(group,joined,28,draws)
                    row['inference7']=block_compare(group,joined,7,draws)
                sample=nonoverlapping(group)
                row['nonoverlap']={**describe(sample),'closed_trade_drawdown':drawdown(sample.net_standard)}
                if hours==24:
                    diagnostics.append(sample[['observation_id','decision_at','label_end','net_standard']].assign(signal=signal))
                for axis in ('pool','trend','volatility','regime','trend_1h','trend_4h'):
                    for value,part in group.groupby(axis):
                        slices.append({'signal':signal,'hours':hours,'axis':axis,'value':str(value),**describe(part)})
                for year,part in group.groupby(group.decision_at.dt.year):
                    slices.append({'signal':signal,'hours':hours,'axis':'year','value':str(year),**describe(part)})
                summaries.append(row)
            print('completed horizon',hours,'hours',quality[str(hours)],flush=True)
        # All 28 predeclared signal/horizon tests remain in the family; ineligible p=1.
        family=[r for r in summaries if r['signal']!='unconditional']
        q=adjust_by([r['inference28'].get('p_one_sided',1.) for r in family])
        for r,value in zip(family,q):r['inference28']['by_q']=value
        diag=pd.concat(diagnostics,ignore_index=True)
        diagnostics_file=save_frame(root,'diagnostics',diag)
        if any(p.read_bytes()!=before[str(p)] for p in (source/'catalog.json',patterns/'catalog.json')):
            raise RuntimeError('Input snapshots changed during research')
        from dataclasses import asdict
        repo=Path(__file__).resolve().parents[2]
        codepaths=['research/regimes/__init__.py','research/indicators/engine.py','market_data/schema.py',
                   'research/statistics/outcomes.py','research/statistics/metrics.py','research/statistics/__main__.py']
        catalog={'schema_version':1,'source_snapshot':market['snapshot_id'],'pattern_snapshot':pattern['snapshot_id'],
                 'start':start,'end_exclusive':end,'features':features_file,'labels':files,'diagnostics':diagnostics_file,
                 'code_sha256':{p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in codepaths},
                 'runtime':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'pyarrow':pyarrow.__version__},
                 'costs':{k:asdict(v) for k,v in SCENARIOS.items()},'entry_delay_minutes':5,
                 'stop_atr':2,'take_atr':3,'bootstrap_draws':draws,'bootstrap_seed':20261011,
                 'features_rows':len(f),'quality':quality}
        catalog['snapshot_id']=hashlib.sha256(json.dumps(catalog,sort_keys=True).encode()).hexdigest()
        payload=(json.dumps(catalog,indent=2)+'\n').encode()
        atomic_bytes(root/'manifests'/(catalog['snapshot_id']+'.json'),payload)
        atomic_bytes(root/'catalog.json',payload)
        report={'snapshot':catalog,'summaries':summaries,'slices':slices}
        atomic_bytes(report_dir/'results.json',(json.dumps(report,indent=2,allow_nan=False)+'\n').encode())
        print('research snapshot',catalog['snapshot_id'],flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',default='data/research');p.add_argument('--patterns',default='data/research_patterns')
    p.add_argument('--destination',default='data/research_statistics');p.add_argument('--report-dir',default='reports/statistics')
    a=p.parse_args();run(a.source,a.patterns,a.destination,a.report_dir)

if __name__=='__main__': main()
