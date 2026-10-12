"""Verify round-six outcome artifacts against frozen features and prior ledger."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
from market_data.source import atomic_bytes
from market_data.schema import utc
from market_data.store import RESERVED_FROM
from research.statistics.metrics import adjust_by, block_compare
from research.discovery.__main__ import summarize
from research.discovery.engine import evaluate_gates
from research.discovery_round3.outcomes import select_pool
from .outcomes import join_observations, verify_events


def verify(root='data/research_round6_outcomes',features_root='data/research_discovery_round6',report_dir='reports/discovery_round6'):
    root,features_root,report_dir=map(Path,(root,features_root,report_dir))
    repo=Path(__file__).resolve().parents[2]
    r=json.loads((root/'catalog.json').read_text());payload=dict(r);payload.pop('snapshot_id')
    if hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()!=r['snapshot_id']:
        raise ValueError('Snapshot identity mismatch')
    def load(base,meta):
        path=base/meta['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:
            raise ValueError('Checksum mismatch')
        frame=pd.read_parquet(path)
        if len(frame)!=meta['rows']:
            raise ValueError('Row count mismatch')
        return frame
    fmeta=json.loads((features_root/'catalog.json').read_text())
    features=load(features_root,fmeta['files']['features'])
    events=load(features_root,fmeta['files']['events'])
    verify_events(features,events)
    labels=load(root,r['provenance']['files']['labels'])
    observations=load(root,r['provenance']['files']['candidate_observations'])
    joined=join_observations(features,labels)
    reg=r['registry'];selected=[]
    for period,(start,end) in reg['periods'].items():
        start,end=utc(start),utc(end)
        base,bquality=select_pool(joined,start,end)
        group,gquality=select_pool(joined[joined.signal],start,end)
        if r['quality'][period+'/unconditional']!=bquality or r['quality'][period+'/'+r['candidate']]!=gquality:
            raise ValueError('Quality accounting mismatch')
        if r['results'][period]!={'candidate':summarize(group),'unconditional':summarize(base)}:
            raise ValueError('Summary mismatch')
        selected.append(group.assign(pool=period))
        if period=='training':
            b=reg['bootstrap']
            if r['comparisons']!={str(d):block_compare(group,base,d,b['draws'],b['seed']) for d in (28,7)}:
                raise ValueError('Bootstrap mismatch')
    pd.testing.assert_frame_equal(pd.concat(selected,ignore_index=True),observations)
    if (features.available_at>=RESERVED_FROM).any() or (observations.label_end>RESERVED_FROM).any():
        raise ValueError('Reserved boundary violation')
    if observations.observation_id.duplicated().any():
        raise ValueError('Duplicate candidate outcome')
    ledger=r['test_ledger'];prior=json.loads((repo/reg['prior_report']).read_text())['test_ledger']
    if len(ledger)!=37 or [(x['id'],x['p']) for x in ledger[:-1]]!=[(x['id'],x['p']) for x in prior]:
        raise ValueError('Prior tests changed or missing')
    if [x['by_q'] for x in ledger]!=adjust_by([x['p'] for x in ledger]):
        raise ValueError('Multiplicity correction mismatch')
    gates=evaluate_gates(r['results']['training']['candidate'],r['results']['reused_recent']['candidate'],
        r['comparisons']['28'],ledger[-1]['by_q'],{'gates':reg['outcome_gates']})
    if gates!=r['gates'] or r['selected_strategy'] is not None:
        raise ValueError('Decision inconsistency')
    result={'snapshot_id':r['snapshot_id'],'status':'passed','features':len(features),
        'labels':len(labels),'candidate_observations':len(observations),'ledger_tests':37,
        'checks':['checksums','timing','feature eligibility','cost formula','pool boundaries','quality accounting',
                  'summaries','bootstrap recomputation','prior ledger preservation','BY correction','decision gates','nonactivation']}
    atomic_bytes(report_dir/'outcome_verification.json',(json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps(result));return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',default='data/research_round6_outcomes')
    p.add_argument('--features-root',default='data/research_discovery_round6')
    p.add_argument('--report-dir',default='reports/discovery_round6')
    a=p.parse_args();verify(a.root,a.features_root,a.report_dir)
