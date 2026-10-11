"""Verify discovery files, hypothesis accounting and non-activation."""
import hashlib
import json
from pathlib import Path
import pandas as pd
from market_data.schema import utc
from market_data.store import RESERVED_FROM
from market_data.source import atomic_bytes
from .engine import CANDIDATES, evaluate_gates
from research.statistics.metrics import adjust_by


def verify(root='data/research_discovery',report_dir='reports/discovery'):
    root=Path(root);r=json.loads((root/'catalog.json').read_text());frames={}
    for name,meta in r['provenance']['files'].items():
        path=root/meta['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('Checksum mismatch')
        f=pd.read_parquet(path)
        if len(f)!=meta['rows']:raise ValueError('Row count mismatch')
        frames[name]=f
    entries=frames['entries'];labels=frames['candidate_observations']
    if entries.observation_id.duplicated().any():raise ValueError('Duplicate decision')
    if (entries.available_at>=RESERVED_FROM).any() or (labels.label_end>RESERVED_FROM).any():raise ValueError('Reserved boundary violation')
    if labels.duplicated(['candidate','observation_id']).any():raise ValueError('Duplicate outcome')
    if not (labels.decision_at<labels.label_end).all():raise ValueError('Invalid timing')
    mask=entries.set_index('observation_id')
    for i,candidate in enumerate(CANDIDATES):
        part=labels[labels.candidate==candidate]
        if not mask.loc[part.observation_id,candidate].all():raise ValueError('Outcome without signal')
        train=part[part.pool=='training'];recent=part[part.pool=='reused_recent']
        if (train.label_end>utc('2024-01-01')).any() or (recent.decision_at<utc('2024-01-01')).any():raise ValueError('Split leakage')
        expected=evaluate_gates(r['results'][candidate]['training'],r['results'][candidate]['reused_recent'],
                                r['comparisons'][candidate]['28'],r['test_ledger'][28+i]['by_q'],r['registry'])
        if expected!=r['gates'][candidate]:raise ValueError('Gate mismatch')
    if len(r['test_ledger'])!=31:raise ValueError('Dropped hypotheses')
    if adjust_by([t['p'] for t in r['test_ledger']])!=[t['by_q'] for t in r['test_ledger']]:raise ValueError('Multiplicity mismatch')
    if r['selected_strategy'] is not None:raise ValueError('Screen cannot activate a strategy')
    result={'snapshot_id':r['snapshot_id'],'verified_files':len(frames),'decisions':len(entries),
            'candidate_observations':len(labels),'tests_accounted_for':31,'status':'passed'}
    atomic_bytes(Path(report_dir)/'verification.json',(json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps(result));return result

if __name__=='__main__':verify()
