"""Atomic Parquet snapshot catalog, single-writer protection and research readers."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import os
import pandas as pd
from .schema import COLUMNS, VALUES, MINUTES, utc, duration, validate, quality, empty
from .source import atomic_bytes

RESERVED_FROM=utc('2026-04-01')

@contextmanager
def writer_lock(root):
    path=Path(root)/'sync.lock';path.parent.mkdir(parents=True,exist_ok=True)
    try:fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:raise RuntimeError('Sync lock exists; verify no running writer before removing stale lock')
    try:
        os.write(fd,str(os.getpid()).encode());os.close(fd)
        yield
    finally:path.unlink(missing_ok=True)

def frame_hash(frame):
    # Stable logical digest across local repeated serializations; runtime versions in catalog.
    hashes=pd.util.hash_pandas_object(frame,index=False).to_numpy().tobytes()
    return hashlib.sha256(hashes).hexdigest()

def publish(root,frames,report,sources):
    root=Path(root);parts=[];written=0;reused=0
    for interval,frame in frames.items():
        validate(frame,interval)
        for month,part in frame.groupby(frame.open_time.dt.strftime('%Y-%m'),sort=True):
            part=part.reset_index(drop=True)
            logical=frame_hash(part)
            relative=Path('processed')/interval/(month+'-'+logical[:20]+'.parquet')
            path=root/relative
            if path.exists():
                # Do not trust a file just because its content-derived name matches.
                stored=pd.read_parquet(path)
                if frame_hash(stored)!=logical:raise ValueError('Stored partition is corrupt: '+str(relative))
                reused+=1
            else:
                path.parent.mkdir(parents=True,exist_ok=True)
                tmp=path.with_suffix('.tmp')
                try:
                    part.to_parquet(tmp,index=False,engine='pyarrow',compression='zstd')
                    if frame_hash(pd.read_parquet(tmp))!=logical:raise ValueError('Parquet roundtrip mismatch')
                    os.replace(tmp,path)
                finally:tmp.unlink(missing_ok=True)
                written+=1
            parts.append({'interval':interval,'month':month,'path':str(relative),'rows':len(part),
                          'logical_sha256':logical,'file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                          'start':str(part.open_time.iloc[0]),'last_available_at':str(part.available_at.iloc[-1]),
                          'pool':'reserved' if utc(month+'-01')>=RESERVED_FROM else 'development'})
    import pyarrow
    catalog={'schema_version':1,'symbol':'BTCUSDT','market':'Binance Spot',
             'cutoff':report['cutoff'],'start':report['start'],'reserved_from':str(RESERVED_FROM),
             'runtime':{'pandas':pd.__version__,'pyarrow':pyarrow.__version__},'partitions':parts,
             'quality':report,'sources':sources}
    identity=hashlib.sha256(json.dumps(catalog,sort_keys=True).encode()).hexdigest()
    catalog['snapshot_id']=identity
    snapshot=root/'manifests'/(identity+'.json')
    payload=(json.dumps(catalog,indent=2,allow_nan=False)+'\n').encode()
    atomic_bytes(snapshot,payload)
    atomic_bytes(root/'catalog.json',payload)
    return catalog,{'written_partitions':written,'reused_partitions':reused}

def read_market(root,interval,start,end,allow_gaps=False):
    """Default research access cannot read reserved rows. end is exclusive open time."""
    root=Path(root);start=utc(start);end=utc(end)
    if start>=end:raise ValueError('start must precede end')
    if start>=RESERVED_FROM or end>RESERVED_FROM:raise PermissionError('Reserved evaluation pool: research access disabled in Milestone 1')
    catalog=json.loads((root/'catalog.json').read_text())
    if start<utc(catalog['start']) or end>utc(catalog['cutoff']).floor(f'{MINUTES[interval]}min'):
        raise ValueError('Requested range is outside acquired completed coverage')
    result=[]
    for p in catalog['partitions']:
        if p['interval']!=interval or utc(p['last_available_at'])<=start or utc(p['start'])>=end:continue
        if p['pool']=='reserved':raise PermissionError('Reserved partition')
        path=root/p['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=p['file_sha256']:raise ValueError('Partition checksum mismatch')
        a=pd.read_parquet(path);result.append(a[(a.open_time>=start)&(a.open_time<end)])
    frame=pd.concat(result,ignore_index=True) if result else empty()
    validate(frame,interval)
    q=quality(frame,interval,start,end)
    if q['missing_candles'] and not allow_gaps:raise ValueError(f"Requested research range has {q['missing_candles']} missing candles")
    return frame
