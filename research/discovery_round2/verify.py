"""Verify discovery files, hypothesis accounting and non-activation."""
import hashlib
import json
from pathlib import Path
import pandas as pd
from market_data.schema import utc
from market_data.store import RESERVED_FROM
from market_data.source import atomic_bytes
from .engine import CANDIDATES
from research.discovery.engine import evaluate_gates
from research.statistics.metrics import adjust_by


def verify(root='data/research_discovery_round2',report_dir='reports/discovery_round2'):
    root=Path(root);r=json.loads((root/'catalog.json').read_text());frames={}
    for name,meta in r['provenance']['files'].items():
        path=root/meta['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('Checksum mismatch')
        f=pd.read_parquet(path)
        if len(f)!=meta['rows']:raise ValueError('Row count mismatch')
        frames[name]=f
    payload=dict(r);payload.pop('snapshot_id')
    if hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()!=r['snapshot_id']:raise ValueError('Snapshot hash mismatch')
    entries=frames['entries'];labels=frames['candidate_observations']
    if entries.observation_id.duplicated().any():raise ValueError('Duplicate decision')
    if (entries.available_at>=RESERVED_FROM).any() or (labels.label_end>RESERVED_FROM).any():raise ValueError('Reserved boundary violation')
    if labels.duplicated(['candidate','observation_id']).any():raise ValueError('Duplicate outcome')
    if not (labels.decision_at<labels.label_end).all():raise ValueError('Invalid timing')
    features=frames['features']
    from .engine import entry_masks
    pd.testing.assert_frame_equal(entries[list(CANDIDATES)],entry_masks(features))
    if (labels.entry_at != labels.decision_at+pd.Timedelta(minutes=5)).any():raise ValueError('Entry timing')
    if (labels.label_end != labels.entry_at+pd.Timedelta(hours=72)).any():raise ValueError('Horizon timing')
    mask=entries.set_index('observation_id')
    for i,candidate in enumerate(CANDIDATES):
        part=labels[labels.candidate==candidate]
        if not mask.loc[part.observation_id,candidate].all():raise ValueError('Outcome without signal')
        train=part[part.pool=='training'];recent=part[part.pool=='reused_recent']
        if (train.label_end>utc('2024-01-01')).any() or (recent.decision_at<utc('2024-01-01')).any():raise ValueError('Split leakage')
        expected=evaluate_gates(r['results'][candidate]['training'],r['results'][candidate]['reused_recent'],
                                r['comparisons'][candidate]['28'],r['test_ledger'][31+i]['by_q'],r['registry'])
        if expected!=r['gates'][candidate]:raise ValueError('Gate mismatch')
    if len(r['test_ledger'])!=33:raise ValueError('Dropped hypotheses')
    if adjust_by([t['p'] for t in r['test_ledger']])!=[t['by_q'] for t in r['test_ledger']]:raise ValueError('Multiplicity mismatch')
    if r['selected_strategy'] is not None:raise ValueError('Screen cannot activate a strategy')
    result={'snapshot_id':r['snapshot_id'],'verified_files':len(frames),'decisions':len(entries),
            'candidate_observations':len(labels),'tests_accounted_for':33,'status':'passed'}
    atomic_bytes(Path(report_dir)/'verification.json',(json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps(result));return result

if __name__=='__main__':verify()
