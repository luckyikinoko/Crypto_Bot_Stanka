"""Validate revised artifacts and quantify changes against preserved reports."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
from market_data.source import atomic_bytes
from market_data.store import RESERVED_FROM
from research.patterns.verify import verify as patterns_verify
from research.statistics.verify import verify as statistics_verify
from research.discovery.verify import verify as round1_verify
from research.discovery_round2.verify import verify as round2_verify
from research.statistics.metrics import adjust_by
from research.discovery.engine import evaluate_gates


def run(root='data/research_revision_v1',report_dir='reports/research_revision_v1',market='data/research_repaired_v1'):
    root,report_dir,market=map(Path,(root,report_dir,market))
    repo=Path(__file__).resolve().parents[2]
    checks={'patterns':patterns_verify(market,root/'patterns'),
        'statistics':statistics_verify(root/'statistics',report_dir/'statistics'),
        'round1':round1_verify(root/'round1',report_dir/'round1'),
        'round2':round2_verify(root/'round2',report_dir/'round2')}
    for stage,hold,tests in [('round3',72,34),('round4',24,35)]:
        r=json.loads((root/stage/'catalog.json').read_text())
        payload=dict(r);payload.pop('snapshot_id')
        if hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()!=r['snapshot_id']:
            raise ValueError('Invalid snapshot identity')
        for name,meta in r['provenance']['files'].items():
            path=root/stage/meta['path']
            if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:
                raise ValueError('Checksum mismatch')
            frame=pd.read_parquet(path)
            if len(frame)!=meta['rows']:
                raise ValueError('Wrong row count')
            if name=='features':
                if (frame.available_at>=RESERVED_FROM).any() or any(x.startswith('net_') for x in frame):
                    raise ValueError('Feature boundary or leakage failure')
            else:
                complete=frame[frame.status=='complete'] if 'status' in frame else frame
                if not complete.entry_at.eq(complete.decision_at+pd.Timedelta(minutes=5)).all():
                    raise ValueError('Wrong entry delay')
                if not complete.label_end.eq(complete.entry_at+pd.Timedelta(hours=hold)).all() or (complete.label_end>RESERVED_FROM).any():
                    raise ValueError('Label timing or reserved boundary failure')
                if 'pool' in complete:
                    train=complete[complete.pool=='training'];recent=complete[complete.pool=='reused_recent']
                    if (train.label_end>pd.Timestamp('2024-01-01',tz='UTC')).any() or (recent.decision_at<pd.Timestamp('2024-01-01',tz='UTC')).any():
                        raise ValueError('Split leakage')
        ledger=r['test_ledger']
        if len(ledger)!=tests or [x['by_q'] for x in ledger]!=adjust_by([x['p'] for x in ledger]):
            raise ValueError('Hypothesis accounting failure')
        registry=json.loads((repo/('research/discovery_'+stage)/'REGISTRY.json').read_text())
        gate_key='outcome_gates_if_later_authorized' if stage=='round3' else 'outcome_gates'
        gate=evaluate_gates(r['results']['training']['candidate'],r['results']['reused_recent']['candidate'],
                           r['comparisons']['28'],ledger[-1]['by_q'],{'gates':registry[gate_key]})
        if gate!=r['gates'] or r['selected_strategy'] is not None:
            raise ValueError('Decision inconsistency')
        checks[stage]={'status':'passed','files':len(r['provenance']['files']),'tests':tests}
    comparison=json.loads((report_dir/'comparison.json').read_text())
    for path,value in comparison['protected_sha256'].items():
        if hashlib.sha256((repo/path).read_bytes()).hexdigest()!=value:
            raise ValueError('Original evidence modified')
    original=json.loads((repo/'reports/statistics/results.json').read_text())
    revised=json.loads((report_dir/'statistics/results.json').read_text())
    index={(r['signal'],r['hours']):r for r in original['summaries']}
    deltas=[]
    for row in revised['summaries']:
        old=index[(row['signal'],row['hours'])]
        deltas.append({'signal':row['signal'],'hours':row['hours'],
            'before':old['costs']['standard'],'after':row['costs']['standard'],
            'inference_before':old.get('inference28'),'inference_after':row.get('inference28')})
    result={'status':'passed','checks':checks,'statistical_cohort_comparisons':deltas,
        'originals_preserved':True,'recent_candidate_statistics_unchanged':all(
            row['periods']['reused_recent']['before']==row['periods']['reused_recent']['after'] for row in comparison['candidates']),
        'new_hypotheses':0,'selected_strategy':None}
    atomic_bytes(report_dir/'validation.json',(json.dumps(result,indent=2,allow_nan=False)+'\n').encode())
    print(json.dumps({'status':result['status'],'recent_unchanged':result['recent_candidate_statistics_unchanged']}))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',default='data/research_revision_v1')
    p.add_argument('--report-dir',default='reports/research_revision_v1')
    p.add_argument('--market',default='data/research_repaired_v1')
    a=p.parse_args();run(a.root,a.report_dir,a.market)
