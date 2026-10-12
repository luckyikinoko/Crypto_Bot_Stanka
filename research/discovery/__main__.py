"""Run the frozen three-candidate discovery screen on development labels only."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import numpy as np
import pandas as pd
from market_data.schema import utc
from market_data.store import read_market, writer_lock, RESERVED_FROM
from market_data.source import atomic_bytes
from research.statistics.store import read
from research.statistics.metrics import describe, drawdown, block_compare, adjust_by
from research.statistics.outcomes import Costs
from research.statistics.__main__ import save_frame
from .engine import CANDIDATES, entry_masks, scheduled, evaluate_gates


def primary(frame):
    f=frame.copy()
    for name in ('standard','bnb_conditional','stress'):f['net_'+name]=f['barrier_net_'+name]
    return f


def summarize(frame):
    result={name:describe(frame,'net_'+name) for name in ('standard','bnb_conditional','stress')}
    chosen=scheduled(frame)
    result['nonoverlap']={**describe(chosen),'closed_trade_drawdown':drawdown(chosen.net_standard)}
    result['years']={str(y):describe(g) for y,g in frame.groupby(frame.decision_at.dt.year)}
    result['positive_years']=sum(s['mean']>0 for s in result['years'].values())
    if 'planned_loss_fraction' in frame:
        result['mean_return_per_planned_risk']=float((frame.net_standard/frame.planned_loss_fraction).mean()) if len(frame) else None
    result['return_std']=float(frame.net_standard.std(ddof=1)) if len(frame)>1 else None
    return result


def buy_hold(source,start,end):
    a=read_market(source,'15m',start,end,allow_gaps=True)
    cost=Costs();entry=float(a.open.iloc[0]);exit=float(a.close.iloc[-1])
    values=np.r_[1.,1+cost.net(entry,a.close.to_numpy())]
    return {'start_open':str(a.open_time.iloc[0]),'last_close':str(a.available_at.iloc[-1]),
            'period_total_net':cost.net(entry,exit),'observed_close_drawdown':float((values/np.maximum.accumulate(values)-1).min()),
            'note':'One purchase/one sale, no 5m signal delay. Observed 15m liquidation-value marks; gaps/intrabar extremes omitted. Different exposure from candidate diagnostics.'}


def run(stats_root,market_root,out,report_dir,prior_report=None):
    stats_root,market_root,out,report_dir=map(Path,(stats_root,market_root,out,report_dir))
    if out.resolve() in (stats_root.resolve(),market_root.resolve()):raise ValueError('Separate destination required')
    registry_path=Path(__file__).with_name('REGISTRY.json')
    registry_bytes=registry_path.read_bytes();registry=json.loads(registry_bytes)
    source_bytes=(stats_root/'catalog.json').read_bytes();source=json.loads(source_bytes)
    market_bytes=(market_root/'catalog.json').read_bytes();market=json.loads(market_bytes)
    if market['snapshot_id']!=source['source_snapshot']:raise ValueError('Market/research snapshot mismatch')
    repo=Path(__file__).resolve().parents[2]
    old_path=Path(prior_report) if prior_report is not None else repo/'reports/statistics/results.json'
    old_bytes=old_path.read_bytes();old=json.loads(old_bytes)
    # Recovery may change runtime/source provenance. Require exact data file identities.
    if old['snapshot']['snapshot_id']!=source['snapshot_id']:
        for key in ('features','labels'):
            if old['snapshot'][key]!=source[key]:raise ValueError('Prior ledger data mismatch')
    if (source['stop_atr'],source['take_atr'],source['entry_delay_minutes'])!=(2,3,5):raise ValueError('Execution mismatch')
    expected=registry['primary_exit']
    if (expected['stop_atr'],expected['take_atr'],expected['maximum_hours'],expected['entry_delay_minutes'])!=(2,3,24,5):
        raise ValueError('Implementation supports registered V1 only')
    with writer_lock(out):
        features=read(stats_root,'2018-01-01',RESERVED_FROM)
        entries=features[['observation_id','available_at']].join(entry_masks(features))
        files={'entries':save_frame(out,'entries',entries)}
        labels=read(stats_root,'2018-01-01',RESERVED_FROM,24)
        valid=labels[(labels.status=='complete')&(labels.barrier_status=='complete')]
        joined=valid.merge(entries.drop(columns='available_at'),on='observation_id',validate='one_to_one')
        frame=primary(joined).merge(features[['observation_id','atr']],on='observation_id',validate='one_to_one')
        stressed=Costs(**source['costs']['stress'])
        frame['planned_loss_fraction']=-stressed.net(frame.entry_raw,frame.entry_raw-2*frame.atr)
        periods={'training':(utc('2018-01-01'),utc('2024-01-01')),'reused_recent':(utc('2024-01-01'),RESERVED_FROM)}
        cohorts=['unconditional',*CANDIDATES,'unfiltered_breakout','unfiltered_rsi_recovery']
        results={c:{} for c in cohorts};comparisons={};quality={};selected_rows=[]
        for period,(start,end) in periods.items():
            baseline=frame[(frame.decision_at>=start)&(frame.label_end<=end)]
            for candidate in cohorts:
                group=baseline if candidate=='unconditional' else baseline[baseline[candidate]]
                results[candidate][period]=summarize(group)
                ids=set(group.observation_id)
                results[candidate][period]['secondary_fixed24_standard']=describe(joined[joined.observation_id.isin(ids)])
                decisions=entries[(entries.available_at>=start)&(entries.available_at<end)]
                count=len(decisions) if candidate=='unconditional' else int(decisions[candidate].sum())
                quality[candidate+'/'+period]={'signal_decisions':count,'complete_primary_labels':len(group),'excluded_or_boundary_purged':count-len(group)}
                if candidate in CANDIDATES:
                    selected_rows.append(group[['observation_id','decision_at','label_end','net_standard','net_stress','barrier_exit']].assign(candidate=candidate,pool=period))
                    if period=='training':
                        comparisons[candidate]={str(days):block_compare(group,baseline,days,registry['bootstrap']['draws'],registry['bootstrap']['seed']) for days in (28,7)}
        old_tests=[(r['signal']+'/'+str(r['hours'])+'h',r.get('inference28',{}).get('p_one_sided',1.)) for r in old['summaries'] if r['signal']!='unconditional']
        if len(old_tests)!=28:raise ValueError('Incomplete prior test family')
        ledger=[{'id':'M4/'+name,'p':p} for name,p in old_tests]
        ledger += [{'id':'M5/'+c,'p':comparisons[c]['28'].get('p_one_sided',1.)} for c in CANDIDATES]
        for test,q in zip(ledger,adjust_by([t['p'] for t in ledger])):test['by_q']=q
        gates={c:evaluate_gates(results[c]['training'],results[c]['reused_recent'],comparisons[c]['28'],ledger[28+i]['by_q'],registry) for i,c in enumerate(CANDIDATES)}
        eligible=[c for c in CANDIDATES if gates[c]['passed']]
        files['candidate_observations']=save_frame(out,'labels',pd.concat(selected_rows,ignore_index=True))
        benchmark={p:buy_hold(market_root,start,end) for p,(start,end) in periods.items()}
        if source_bytes!=(stats_root/'catalog.json').read_bytes() or market_bytes!=(market_root/'catalog.json').read_bytes():raise RuntimeError('Input snapshot changed')
        if registry_bytes!=registry_path.read_bytes() or old_bytes!=old_path.read_bytes():raise RuntimeError('Protocol/ledger changed')
        codepaths=['research/discovery/engine.py','research/discovery/__main__.py','research/statistics/metrics.py','research/statistics/store.py','research/statistics/outcomes.py','market_data/store.py']
        provenance={'source_snapshot':source['snapshot_id'],'market_snapshot':market['snapshot_id'],
                    'registry_sha256':hashlib.sha256(registry_bytes).hexdigest(),'prior_ledger_sha256':hashlib.sha256(old_bytes).hexdigest(),
                    'code_sha256':{p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in codepaths},
                    'runtime':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__},'files':files}
        report={'provenance':provenance,'registry':registry,'quality':quality,'results':results,
                'comparisons':comparisons,'test_ledger':ledger,'gates':gates,'buy_and_hold_context':benchmark,
                'eligible_for_later_validation':eligible,'selected_strategy':None,
                'decision':'no_candidate_passes' if not eligible else 'candidates_require_separate_validation'}
        report['snapshot_id']=hashlib.sha256(json.dumps(report,sort_keys=True,allow_nan=False).encode()).hexdigest()
        payload=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode()
        atomic_bytes(out/'manifests'/(report['snapshot_id']+'.json'),payload);atomic_bytes(out/'catalog.json',payload)
        atomic_bytes(report_dir/'results.json',payload)
        print(json.dumps({'snapshot_id':report['snapshot_id'],'gates':gates,'decision':report['decision']}),flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',default='data/research_statistics');p.add_argument('--market',default='data/research')
    p.add_argument('--destination',default='data/research_discovery');p.add_argument('--report-dir',default='reports/discovery')
    a=p.parse_args();run(a.source,a.market,a.destination,a.report_dir)

if __name__=='__main__':main()
