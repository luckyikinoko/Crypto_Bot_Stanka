"""Verify stored feature/label separation, timing, checksums and path counts."""
import hashlib
import json
from pathlib import Path
import pandas as pd
from market_data.schema import utc
from market_data.source import atomic_bytes
from market_data.store import RESERVED_FROM


def verify(root='data/research_statistics',report_dir='reports/statistics'):
    root=Path(root);catalog=json.loads((root/'catalog.json').read_text())
    def load(meta):
        path=root/meta['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('Checksum mismatch')
        f=pd.read_parquet(path)
        if len(f)!=meta['rows']:raise ValueError('Wrong row count')
        return f
    features=load(catalog['features'])
    if any(c.startswith(('net_','barrier_','gross_return','mfe','mae','label_end')) for c in features):
        raise ValueError('Future labels in feature table')
    if features.observation_id.duplicated().any():raise ValueError('Duplicate features')
    results={}
    for hours,meta in catalog['labels'].items():
        f=load(meta);complete=f[f.status=='complete']
        if f.observation_id.duplicated().any() or set(f.observation_id)!=set(features.observation_id):raise ValueError('Label keys mismatch')
        if not (complete.entry_at==complete.decision_at+pd.Timedelta('5min')).all():raise ValueError('Entry timing mismatch')
        if not (complete.label_end==complete.entry_at+pd.Timedelta(hours=int(hours))).all():raise ValueError('Exit timing mismatch')
        if not (complete.label_end<=RESERVED_FROM).all():raise ValueError('Reserved boundary crossed')
        if not ((complete.mae<=complete.mfe)&(complete.time_to_mfe_minutes<=int(hours)*60)&(complete.time_to_mae_minutes<=int(hours)*60)).all():raise ValueError('Invalid excursion')
        if not ((complete.net_bnb_conditional>=complete.net_standard)&(complete.net_standard>=complete.net_stress)).all():raise ValueError('Cost monotonicity failure')
        results[hours]={'rows':len(f),'complete':len(complete),'excluded':len(f)-len(complete),'status':'passed'}
    load(catalog['diagnostics'])
    result={'snapshot_id':catalog['snapshot_id'],'features_rows':len(features),'horizons':results,'status':'passed'}
    atomic_bytes(Path(report_dir)/'verification.json',(json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps(result))
    return result

if __name__=='__main__':verify()
