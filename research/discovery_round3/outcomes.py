"""Authorized outcome screen for the single registered round-three rule."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import numpy as np
import pandas as pd
import pyarrow
from market_data.schema import utc
from market_data.store import RESERVED_FROM, writer_lock
from market_data.source import atomic_bytes
from research.statistics.outcomes import SCENARIOS
from research.statistics.metrics import block_compare, adjust_by
from research.statistics.__main__ import save_frame
from research.discovery.__main__ import summarize
from research.discovery.engine import evaluate_gates
from .__main__ import FEATURE_COLUMNS, signal_mask

CANDIDATE = 'unfiltered_breakout_4h'
LABEL_COLUMNS = ['observation_id','decision_at','entry_at','label_end','status',
                 'entry_raw','exit_raw','gross_return','net_standard',
                 'net_bnb_conditional','net_stress','mfe','mae',
                 'time_to_mfe_minutes','time_to_mae_minutes']


def join_observations(features, labels):
    mask = signal_mask(features)
    if labels.observation_id.duplicated().any():
        raise ValueError('Duplicate labels')
    if set(labels.observation_id) != set(features.observation_id):
        raise ValueError('Feature/label identities differ')
    entries = features[FEATURE_COLUMNS].assign(signal=mask)
    joined = entries.merge(labels[LABEL_COLUMNS],on='observation_id',validate='one_to_one')
    if not joined.available_at.equals(joined.decision_at):
        raise ValueError('Decision mismatch')
    if not joined.entry_at.eq(joined.decision_at+pd.Timedelta(minutes=5)).all():
        raise ValueError('Entry delay mismatch')
    if not joined.label_end.eq(joined.entry_at+pd.Timedelta(hours=72)).all():
        raise ValueError('Holding period mismatch')
    return joined


def select_pool(frame, start, end):
    if end > RESERVED_FROM:
        raise ValueError('Reserved pool blocked')
    period = frame[frame.decision_at.ge(start) & frame.decision_at.lt(end)]
    complete = period.status.eq('complete')
    crossing = complete & period.label_end.gt(end)
    return period[complete & ~crossing], {
        'decisions':len(period),
        'incomplete_by_status':period.loc[~complete,'status'].value_counts().to_dict(),
        'complete_boundary_purged':int(crossing.sum()),
        'usable':int((complete & ~crossing).sum())}


def run(source='data/research_discovery_round2', destination='data/research_discovery_round3',
        report_dir='reports/discovery_round3'):
    source,destination,report_dir = map(Path,(source,destination,report_dir))
    if source.resolve()==destination.resolve():
        raise ValueError('Separate destination required')
    repo = Path(__file__).resolve().parents[2]
    registry_bytes = Path(__file__).with_name('REGISTRY.json').read_bytes()
    registry = json.loads(registry_bytes)
    if registry['candidate']['id']!=CANDIDATE or registry['future_execution'] != {
        'fixed_hold_hours':72,'entry_delay_minutes':5,'cooldown_minutes':60,'secondary_exit':None}:
        raise ValueError('Registered execution changed')
    raw = (source/'catalog.json').read_bytes()
    prior = json.loads(raw)
    payload=dict(prior);payload.pop('snapshot_id')
    if hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()!=prior['snapshot_id']:
        raise ValueError('Snapshot hash mismatch')
    frozen_bytes=(repo/'reports/discovery_round2/results.json').read_bytes()
    if raw != frozen_bytes:
        raise ValueError('Source differs from frozen prior experiment')
    if prior['costs'] != {k:vars(v) for k,v in SCENARIOS.items()}:
        raise ValueError('Execution costs changed')
    if len(prior['test_ledger'])!=33:
        raise ValueError('Prior hypothesis ledger incomplete')
    frames={}
    for key,columns in [('features',FEATURE_COLUMNS),('labels',LABEL_COLUMNS)]:
        meta=prior['provenance']['files'][key];path=source/meta['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:
            raise ValueError('Input checksum mismatch')
        frames[key]=pd.read_parquet(path,columns=columns)
        if len(frames[key])!=meta['rows']:
            raise ValueError('Input row count mismatch')
    joined=join_observations(frames['features'],frames['labels'])
    complete=joined[joined.status.eq('complete')]
    for name,cost in SCENARIOS.items():
        if not np.allclose(complete['net_'+name],cost.net(complete.entry_raw,complete.exit_raw),rtol=1e-12,atol=1e-12):
            raise ValueError('Stored return differs from registered costs')
    results={};quality={};comparisons={};observations=[]
    with writer_lock(destination):
        for period,(start,end) in registry['periods'].items():
            start,end=utc(start),utc(end)
            baseline,quality[period+'/unconditional']=select_pool(joined,start,end)
            candidate,quality[period+'/'+CANDIDATE]=select_pool(joined[joined.signal],start,end)
            results[period]={'candidate':summarize(candidate),'unconditional':summarize(baseline)}
            observations.append(candidate.assign(pool=period))
            if period=='training':
                b=registry['bootstrap_if_later_authorized']
                comparisons={str(days):block_compare(candidate,baseline,days,b['draws'],b['seed']) for days in (28,7)}
        ledger=[{'id':t['id'],'p':t['p']} for t in prior['test_ledger']]
        ledger.append({'id':'M5R3/'+CANDIDATE,'p':comparisons['28'].get('p_one_sided',1.)})
        for row,q in zip(ledger,adjust_by([r['p'] for r in ledger])):
            row['by_q']=q
        gate=evaluate_gates(results['training']['candidate'],results['reused_recent']['candidate'],
             comparisons['28'],ledger[-1]['by_q'],{'gates':registry['outcome_gates_if_later_authorized']})
        files={'candidate_observations':save_frame(destination,'labels',pd.concat(observations,ignore_index=True))}
        paths=['research/discovery_round3/outcomes.py','research/discovery_round3/__main__.py',
               'research/discovery/__main__.py','research/discovery/engine.py',
               'research/statistics/metrics.py','research/statistics/outcomes.py']
        report={'candidate':CANDIDATE,'source_snapshot':prior['snapshot_id'],
            'provenance':{'registry_sha256':hashlib.sha256(registry_bytes).hexdigest(),
                'source_report_sha256':hashlib.sha256(raw).hexdigest(),
                'code_sha256':{p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in paths},
                'runtime':{'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,'pyarrow':pyarrow.__version__},
                'files':files},
            'scope':'User authorized the registered outcome screen after feature feasibility; no other rule or exit evaluated.',
            'costs':prior['costs'],'results':results,'quality':quality,'comparisons':comparisons,
            'test_ledger':ledger,'gates':gate,'buy_and_hold_context':prior['buy_and_hold_context'],
            'selected_strategy':None,
            'decision':'requires_separate_validation' if gate['passed'] else 'candidate_rejected'}
        if raw!=(source/'catalog.json').read_bytes() or registry_bytes!=Path(__file__).with_name('REGISTRY.json').read_bytes():
            raise ValueError('Inputs changed')
        report['snapshot_id']=hashlib.sha256(json.dumps(report,sort_keys=True,allow_nan=False).encode()).hexdigest()
        encoded=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode()
        atomic_bytes(destination/'manifests'/(report['snapshot_id']+'.json'),encoded)
        atomic_bytes(destination/'catalog.json',encoded)
        atomic_bytes(report_dir/'outcomes.json',encoded)
    print(json.dumps({'snapshot_id':report['snapshot_id'],'gates':gate,'decision':report['decision']}))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',default='data/research_discovery_round2')
    p.add_argument('--destination',default='data/research_discovery_round3')
    p.add_argument('--report-dir',default='reports/discovery_round3')
    a=p.parse_args()
    run(a.source,a.destination,a.report_dir)
