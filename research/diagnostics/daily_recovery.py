"""Cross-check development gaps against independently downloaded daily archives."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import pandas as pd
from market_data.schema import utc,quality,COLUMNS,VALUES,empty
from market_data.store import read_market,RESERVED_FROM
from market_data.source import archive,parse_archive,MissingArchive,atomic_bytes
from research.statistics.__main__ import save_frame
from .coverage_audit import classify_missing


def planned_days(gaps):
    days=set()
    for g in gaps:
        a,b=utc(g['start']),utc(g['end_exclusive'])
        if a<utc('2018-01-01') or a>=b or b>RESERVED_FROM:
            raise ValueError('Invalid or reserved recovery range')
        days.update(pd.date_range(a.floor('D'),(b-pd.Timedelta(nanoseconds=1)).floor('D'),freq='D'))
    return sorted(days)


def compare_day(base, daily, missing):
    """Only full valid absent slots can be candidates; never overwrite conflicts."""
    a=base.set_index('open_time');b=daily.set_index('open_time')
    if a.index.duplicated().any() or b.index.duplicated().any():
        raise ValueError('Duplicate candle')
    shared=a.index.intersection(b.index)
    conflicts=[]
    for t in shared:
        fields=[c for c in VALUES if a.loc[t,c]!=b.loc[t,c]]
        if fields:
            values={}
            for field in fields:
                old,new=a.loc[t,field],b.loc[t,field]
                values[field]={'stored':old.item() if hasattr(old,'item') else old,
                               'daily':new.item() if hasattr(new,'item') else new}
            conflicts.append({'open_time':str(t),'fields':fields,'values':values})
    candidates=daily[daily.open_time.isin(missing)].copy()
    return candidates,conflicts,len(shared)


def fetch_day(cache,day):
    period=day.strftime('%Y-%m-%d')
    try:
        path,source=archive(cache,period)
        quarantine=[]
        frame,dropped=parse_archive(path,'5m',day+pd.Timedelta(days=1),quarantine)
        if dropped or (frame.open_time<day).any() or (frame.open_time>=day+pd.Timedelta(days=1)).any():
            raise ValueError('Daily archive contains out-of-day rows')
        source={k:v for k,v in source.items() if k not in ('cached','path')}
        return day,{'status':'verified','source':source,'frame':frame,'quarantine':quarantine}
    except MissingArchive:
        return day,{'status':'archive_unavailable'}
    except Exception as e:
        return day,{'status':'error','error_type':type(e).__name__,'detail':str(e)[:400]}


def run(market='data/research',cache='data/daily_recovery',report_dir='reports/daily_recovery'):
    market,cache,report_dir=map(Path,(market,cache,report_dir))
    if market.resolve()==cache.resolve():
        raise ValueError('Use a separate recovery cache')
    source_bytes=(market/'catalog.json').read_bytes();catalog=json.loads(source_bytes)
    baseline=read_market(market,'5m','2018-01-01',RESERVED_FROM,allow_gaps=True)
    q=quality(baseline,'5m','2018-01-01',RESERVED_FROM)
    missing=pd.date_range(utc('2018-01-01'),RESERVED_FROM,freq='5min',inclusive='left').difference(
        pd.DatetimeIndex(baseline.open_time))
    days=planned_days(q['gaps']);downloads={}
    with ThreadPoolExecutor(max_workers=4) as executor:
        tasks=[executor.submit(fetch_day,cache,day) for day in days]
        for task in as_completed(tasks):
            day,result=task.result();downloads[day]=result
            print(day.strftime('%Y-%m-%d')+' '+result['status'],flush=True)
    records=[];proposals=[];classifications={};conflicts=[]
    for day in days:
        result=downloads[day]
        day_missing=missing[(missing>=day)&(missing<day+pd.Timedelta(days=1))]
        record={'day':str(day.date()),'missing_slots':len(day_missing),'status':result['status']}
        if result['status']=='verified':
            frame=result['frame'];base=baseline[(baseline.open_time>=day)&(baseline.open_time<day+pd.Timedelta(days=1))]
            recovered,clashes,shared=compare_day(base,frame,day_missing)
            proposals.append(recovered)
            conflicts.extend({'day':str(day.date()),**c} for c in clashes)
            evidence=classify_missing(day_missing,frame.open_time,result['quarantine'])
            for t,reason in evidence.items():
                classifications[t]='valid_daily_recovery_candidate' if reason=='valid_archive_row_missing_from_store' else reason
            record.update(source=result['source'],valid_rows=len(frame),quarantined_rows=len(result['quarantine']),
                shared_candles_compared=shared,conflicts=len(clashes),candidate_count=len(recovered),
                candidate_open_times=[str(t) for t in recovered.open_time])
        else:
            for t in day_missing:classifications[t]='unresolved_'+result['status']
            record.update({k:v for k,v in result.items() if k!='status'})
        records.append(record)
    candidates=pd.concat(proposals,ignore_index=True) if proposals else empty()
    candidate_file=save_frame(cache,'candidate_candles',candidates) if len(candidates) else None
    gaps=[]
    for g in q['gaps']:
        times=pd.date_range(utc(g['start']),utc(g['end_exclusive']),freq='5min',inclusive='left')
        gaps.append({**g,'daily_evidence':dict(Counter(classifications[t] for t in times))})
    if len(classifications)!=len(missing):
        raise ValueError('Missing-slot accounting incomplete')
    if source_bytes!=(market/'catalog.json').read_bytes():
        raise ValueError('Market snapshot changed')
    failed=sum(x['status']!='verified' for x in records)
    decision=('incomplete_cross_check' if failed else
              'conflicts_require_review' if conflicts else
              'verified_candidates_require_new_snapshot' if len(candidates) else
              'no_recoverable_candles_in_daily_archives')
    report={'source_snapshot':catalog['snapshot_id'],'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope':['2018-01-01','2026-04-01'],'planned_gap_ranges':len(gaps),'planned_days':len(days),
        'daily_archives_verified':len(days)-failed,'source_errors_or_missing':failed,
        'missing_slots':len(missing),'evidence_counts':dict(Counter(classifications.values())),
        'candidate_count':len(candidates),'candidate_file':candidate_file,'conflicts':conflicts,
        'days':records,'gaps':gaps,'decision':decision,'market_data_changed':False,
        'new_hypothesis_tests':0,'reserved_data_read':False,
        'limits':'Daily and monthly archives can share upstream defects. Archive absence does not prove an exchange outage. No API or trade-level reconstruction is included.'}
    payload=(json.dumps(report,indent=2)+'\n').encode()
    atomic_bytes(report_dir/'results.json',payload)
    lines=['# Official daily-archive recovery cross-check','',
        '**Decision: '+decision+'.**','',
        f"Checked {len(days)} UTC days covering all {len(gaps)} development gaps. {len(days)-failed} daily archives passed checksum and structural checks; {failed} were missing or errored. Existing market data was not changed.",
        '',
        f"Recovery candidates: **{len(candidates)}**. Conflicting overlapping candles: **{len(conflicts)}**. Comparison uses exact normalized numeric values; conflicts are never silently overwritten.",
        '',
        '| Evidence for missing 5m slots | Count |','|---|---:|']
    for reason,n in report['evidence_counts'].items():lines.append(f"| {reason} | {n} |")
    lines+=['',
        'Each downloaded ZIP is checked against its official SHA256 sidecar. Timestamps, OHLCV, candle boundaries and day membership are validated using the existing normalizer. Off-grid or partial source candles remain quarantined; they are not rounded, shifted or filled.',
        '',
        'Daily archives provide an additional representation of official data, but may share their source with monthly archives. Agreement does not prove an exchange outage or prove no other source can recover the interval.',
        '',
        'All daily source URLs, checksums, gap classifications, candidate timestamps and conflicts are recorded in results.json. Downloads and any candidate Parquet file are excluded from Git. The existing market snapshot, strategy reports and 35-test ledger remain unchanged.',
        '',
        '## Next checkpoint','',
        'Source disagreements must be reconciled with bounded public-API evidence before applying corrections. The report records both stored and daily values for every conflicting field. Candidate candles remain staged and have not been promoted.',
        '',
        'If there are no candidates or conflicts, a bounded public-API cross-check of these same development gaps is the remaining recovery option before accepting the documented gaps. If candidates exist, review source agreement and publish only verified additions into a new immutable snapshot, preserving the old one. Missing/error responses are unresolved, never evidence of zero recoverability.',
        '',
        'No strategy outcomes were evaluated. Reserved data from 2026-04-01 onward was not requested. Paper and live trading remain inactive.',
        '',
        'Reproduce: python -m research.diagnostics.daily_recovery. Cached archives are reverified on every read.',
        '',f"Source snapshot: {catalog['snapshot_id']}",'']
    atomic_bytes(report_dir/'RECOVERY.md','\n'.join(lines).encode())
    print(json.dumps({k:report[k] for k in ('planned_days','daily_archives_verified','candidate_count','evidence_counts','decision')}),flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--market',default='data/research');p.add_argument('--cache',default='data/daily_recovery')
    p.add_argument('--report-dir',default='reports/daily_recovery')
    a=p.parse_args();run(a.market,a.cache,a.report_dir)
