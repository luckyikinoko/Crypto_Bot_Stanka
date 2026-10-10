"""Mechanical snapshot checks and optional native-timeframe cross-checks."""
import argparse
import hashlib
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
from .schema import VALUES,utc,validate,quality
from .source import archive,parse_archive,atomic_bytes
from .store import frame_hash


def verify_snapshot(root):
    root=Path(root);cat=json.loads((root/'catalog.json').read_text());by={};checked=0
    for p in cat['partitions']:
        path=root/p['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=p['file_sha256']:raise ValueError('File checksum mismatch')
        f=pd.read_parquet(path);validate(f,p['interval'])
        if frame_hash(f)!=p['logical_sha256'] or len(f)!=p['rows']:raise ValueError('Logical content mismatch')
        by.setdefault(p['interval'],[]).append(f);checked+=1
    for tf,frames in by.items():
        a=pd.concat(frames,ignore_index=True);q=quality(a,tf,cat['start'],cat['cutoff'])
        if q!=cat['quality']['intervals'][tf]:raise ValueError('Quality report mismatch: '+tf)
    return {'snapshot_id':cat['snapshot_id'],'partitions_verified':checked,'all_hashes_schema_quality_match':True}


def native_checks(root):
    root=Path(root);cat=json.loads((root/'catalog.json').read_text())
    jobs=[(m,t) for m in ['2018-01','2024-01','2025-01'] for t in ['15m','1h','4h','1d']]
    def job(pair):
        m,tf=pair
        path,meta=archive(root,m,tf)
        quarantine=[]
        native,_=parse_archive(path,tf,utc(m+'-01')+pd.offsets.MonthBegin(1),quarantine=quarantine)
        matching=[p for p in cat['partitions'] if p['month']==m and p['interval']==tf]
        if len(matching)!=1:raise ValueError('Missing native-check partition')
        derived=pd.read_parquet(root/matching[0]['path'])
        both=derived.merge(native,on='open_time',suffixes=('_derived','_native'),validate='one_to_one')
        mismatches={}
        for c in VALUES:
            ok=np.isclose(both[c+'_derived'],both[c+'_native'],rtol=1e-9 if c!='trades' else 0,atol=1e-7 if c!='trades' else 0)
            mismatches[c]=int((~ok).sum())
        result={'month':m,'interval':tf,'derived_rows':len(derived),'native_rows':len(native),
                'shared_rows':len(both),'derived_missing_in_native':len(derived)-len(both),
                'native_only_rows':len(native)-len(both),'mismatches':mismatches,
                'native_quarantined_rows':len(quarantine),'source_sha256':meta['sha256'],'source_url':meta['url'],
                'values_match':not any(mismatches.values()) and len(derived)==len(both)}
        print(m,tf,'match' if result['values_match'] else 'MISMATCH',flush=True)
        return result
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(job,jobs))
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default='data/research');p.add_argument('--native',action='store_true');p.add_argument('--report',default='reports/market_database/verification.json');a=p.parse_args()
    r=verify_snapshot(a.root)
    if a.native:r['native_crosschecks']=native_checks(a.root)
    atomic_bytes(a.report,(json.dumps(r,indent=2)+'\n').encode())
    print(json.dumps({k:v for k,v in r.items() if k!='native_crosschecks'},indent=2))
    if a.native and not all(x['values_match'] for x in r['native_crosschecks']):raise SystemExit('Native value mismatch: inspect report')

if __name__=='__main__':main()
