"""Official public Binance sources, cached checksums and bounded HTTP retries."""
import hashlib
import io
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import pandas as pd
from .schema import normalize, utc, duration

ARCHIVES='https://data.binance.vision/data/spot'
PUBLIC='https://data-api.binance.vision'

class MissingArchive(Exception):pass

def atomic_bytes(path,raw):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    try:
        with open(tmp,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()

def get(url,tries=4):
    for attempt in range(tries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'CryptoBotStankaResearch/1.0'})
            with urllib.request.urlopen(req,timeout=45) as r:return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code==404:raise MissingArchive(url) from exc
            if exc.code in (418,429):
                delay=float(exc.headers.get('Retry-After',min(2**attempt,8)))
                if delay>30:raise RuntimeError('Rate limited; retry sync after Retry-After') from exc
            elif exc.code>=500:delay=min(2**attempt,8)
            else:raise
            if attempt==tries-1:raise
            time.sleep(delay)
        except (urllib.error.URLError,TimeoutError):
            if attempt==tries-1:raise
            time.sleep(min(2**attempt,8))

def server_cutoff():
    return pd.to_datetime(json.loads(get(PUBLIC+'/api/v3/time'))['serverTime'],unit='ms',utc=True)

def archive(root,period,interval='5m',refresh=False):
    """Monthly YYYY-MM or daily YYYY-MM-DD immutable cache; verify every read."""
    pd.Timestamp(period+'-01' if len(period)==7 else period)
    kind='monthly' if len(period)==7 else 'daily'
    name=f'BTCUSDT-{interval}-{period}.zip'
    path=Path(root)/'raw'/kind/interval/name
    side=path.with_suffix('.zip.CHECKSUM')
    url=f'{ARCHIVES}/{kind}/klines/BTCUSDT/{interval}/{name}'
    cached=path.exists() and side.exists() and not refresh
    checksum=side.read_text().split()[0] if cached else get(url+'.CHECKSUM').decode().split()[0]
    raw=path.read_bytes() if cached else get(url)
    actual=hashlib.sha256(raw).hexdigest()
    if actual!=checksum:raise ValueError(f'Checksum mismatch: {name}')
    if not cached:
        atomic_bytes(path,raw);atomic_bytes(side,(checksum+'  '+name+'\n').encode())
    return path,{'url':url,'sha256':actual,'bytes':len(raw),'cached':cached,'path':str(path)}

def parse_archive(path,interval,cutoff,quarantine=None):
    with zipfile.ZipFile(path) as z:
        files=[n for n in z.namelist() if n.endswith('.csv')]
        if len(files)!=1:raise ValueError('Expected one CSV in ZIP')
        a=pd.read_csv(z.open(files[0]),header=None)
    return normalize(a,interval,cutoff,quarantine=quarantine)

def rest_tail(root,start,cutoff):
    cursor=utc(start);cutoff=utc(cutoff);frames=[];sources=[];dropped=0
    while cursor+duration('5m')<=cutoff:
        params=urllib.parse.urlencode({'symbol':'BTCUSDT','interval':'5m','startTime':int(cursor.timestamp()*1000),'endTime':int(cutoff.timestamp()*1000)-1,'limit':1000})
        url=PUBLIC+'/api/v3/klines?'+params
        raw=get(url);rows=json.loads(raw)
        if not isinstance(rows,list):raise ValueError('Unexpected REST payload')
        if not rows:break
        digest=hashlib.sha256(raw).hexdigest();path=Path(root)/'raw'/'rest'/(digest+'.json')
        if not path.exists():atomic_bytes(path,raw)
        frame,n=normalize(rows,'5m',cutoff);frames.append(frame);dropped+=n
        sources.append({'url':url,'sha256':digest,'bytes':len(raw),'path':str(path),'cached':False})
        last=int(rows[-1][0]);last_ts=pd.to_datetime(last,unit='us' if last>10**14 else 'ms',utc=True)
        nxt=last_ts+duration('5m')
        if nxt<=cursor:raise ValueError('REST cursor did not advance')
        cursor=nxt
    return frames,sources,dropped
