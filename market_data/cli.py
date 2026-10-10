"""python -m market_data sync --start 2018-01-01; quality-only acquisition."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import pandas as pd
from .schema import utc, MINUTES, normalize, merge_frames, aggregate, quality
from .source import archive, parse_archive, rest_tail, server_cutoff, MissingArchive, atomic_bytes
from .store import publish, writer_lock, RESERVED_FROM


def collect(root,start,cutoff,workers=6,refresh=False):
    frames=[];sources=[];errors=[];dropped=0;quarantined=[]
    start=utc(start);cutoff=utc(cutoff)
    current=cutoff.strftime('%Y-%m')
    months=[str(m) for m in pd.period_range(start.strftime('%Y-%m'),current,freq='M')]
    def fetch_month(month):
        if month==current:return month,None
        try:return month,archive(root,month,refresh=refresh)
        except MissingArchive:return month,None
    daily=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for month,found in pool.map(fetch_month,months):
            if found:
                path,meta=found;q=[];f,n=parse_archive(path,'5m',cutoff,quarantine=q);frames.append(f);sources.append(meta);dropped+=n
                quarantined.extend({**x,'source':meta['url']} for x in q)
                print('validated monthly',month,len(f),flush=True)
            else:
                begin=max(start,utc(month+'-01'))
                finish=min(cutoff.floor('D'),utc(month+'-01')+pd.offsets.MonthBegin(1))
                daily.extend(d.strftime('%Y-%m-%d') for d in pd.date_range(begin,finish,freq='D',inclusive='left'))
        def fetch_day(day):
            try:return day,archive(root,day,refresh=refresh)
            except MissingArchive:return day,None
        for day,found in pool.map(fetch_day,daily):
            if found:
                path,meta=found;q=[];f,n=parse_archive(path,'5m',cutoff,quarantine=q);frames.append(f);sources.append(meta);dropped+=n
                quarantined.extend({**x,'source':meta['url']} for x in q)
            else:
                # Official REST fallback for unpublished daily files (max one day/request group).
                more,meta,n=rest_tail(root,utc(day),min(utc(day)+pd.Timedelta(days=1),cutoff))
                frames.extend(more);sources.extend(meta);dropped+=n
                errors.append({'date':day,'archive':'unavailable','fallback':'official REST'})
    # The current day's first REST request deliberately covers the entire day;
    # subsequent syncs fetch a small tail while cached archives remain unchanged.
    more,meta,n=rest_tail(root,max(start,cutoff.floor('D')),cutoff)
    frames.extend(more);sources.extend(meta);dropped+=n
    base,duplicates=merge_frames(frames,'5m')
    base=base[(base.open_time>=start)&(base.available_at<=cutoff)].reset_index(drop=True)
    return base,sources,{'identical_duplicates_removed':duplicates,'incomplete_rows_dropped':dropped,'archive_fallbacks':errors,'quarantined_timestamp_rows':quarantined}


def sync(root,start,cutoff,report_dir,workers=6,refresh=False):
    root=Path(root);report_dir=Path(report_dir)
    with writer_lock(root):
        base,sources,extra=collect(root,start,cutoff,workers,refresh)
        if base.empty:raise ValueError('No complete base candles acquired')
        frames={tf:aggregate(base,tf) for tf in MINUTES}
        reports={tf:quality(f,tf,start,cutoff) for tf,f in frames.items()}
        report={'start':str(utc(start)),'cutoff':str(utc(cutoff)),'primary_research_interval':'15m',
                'reserved_from':str(RESERVED_FROM),'reserved_handling':'mechanical integrity only; no predictive/outcome analysis',
                'intervals':reports,**extra}
        catalog,counts=publish(root,frames,report,sources)
        report.update(snapshot_id=catalog['snapshot_id'],**counts)
        report_dir.mkdir(parents=True,exist_ok=True)
        atomic_bytes(report_dir/'quality.json',(json.dumps(report,indent=2)+'\n').encode())
        # Portable provenance strips local absolute paths. No price/volume values exported.
        clean_sources=[{k:v for k,v in s.items() if k!='path'} for s in sources]
        manifest={'snapshot_id':catalog['snapshot_id'],'cutoff':str(utc(cutoff)),
                  'runtime':catalog['runtime'],'sources':clean_sources,'partitions':catalog['partitions']}
        atomic_bytes(report_dir/'manifest.json',(json.dumps(manifest,indent=2)+'\n').encode())
        print(json.dumps({'snapshot_id':catalog['snapshot_id'],'counts':{k:v['rows'] for k,v in reports.items()},
                          'missing':{k:v['missing_candles'] for k,v in reports.items()},**counts},indent=2),flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('sync');s.add_argument('--root',default='data/research');s.add_argument('--start',default=None)
    s.add_argument('--cutoff',help='Reproducible UTC cutoff; cannot exceed server time');s.add_argument('--workers',type=int,default=6)
    s.add_argument('--refresh',action='store_true',help='Re-fetch published archives for source corrections')
    s.add_argument('--report-dir',default='reports/market_database')
    a=p.parse_args()
    if not 1<=a.workers<=8:p.error('workers must be in 1..8')
    server=server_cutoff();cutoff=utc(a.cutoff) if a.cutoff else server
    if cutoff>server:p.error('cutoff is in the future relative to Binance server time')
    root=Path(a.root);start=utc(a.start or '2018-01-01')
    if (root/'catalog.json').exists():
        old=json.loads((root/'catalog.json').read_text())
        if a.start is None:start=utc(old['start'])
        if start>utc(old['start']) or cutoff<utc(old['cutoff']):p.error('Refusing to shrink existing snapshot; use another root for a subset')
    if start!=start.floor('D') or start>=cutoff:p.error('start must be UTC midnight before cutoff')
    sync(root,start,cutoff,a.report_dir,a.workers,a.refresh)

if __name__=='__main__':main()
