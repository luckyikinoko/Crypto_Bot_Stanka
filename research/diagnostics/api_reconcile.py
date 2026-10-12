"""Bounded public-API reconciliation of staged additions and archive conflicts."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import urllib.parse
import zipfile
import pandas as pd
from market_data.schema import normalize,utc,VALUES
from market_data.store import RESERVED_FROM
from market_data.source import get,PUBLIC,atomic_bytes

POSITIONS=[1,2,3,4,5,7,8,9,10]


def request_url(day):
    day=utc(day)
    if day!=day.floor('D') or day<utc('2018-01-01') or day+pd.Timedelta(days=1)>RESERVED_FROM:
        raise ValueError('Only complete development days allowed')
    params={'symbol':'BTCUSDT','interval':'5m','startTime':int(day.timestamp()*1000),
            'endTime':int((day+pd.Timedelta(days=1)).timestamp()*1000)-1,'limit':1000}
    return PUBLIC+'/api/v3/klines?'+urllib.parse.urlencode(params)


def canonical_map(rows,cutoff):
    """Validate through the candle contract; compare original decimal strings."""
    quarantine=[]
    frame,dropped=normalize(rows,'5m',cutoff,quarantine)
    if dropped:
        raise ValueError('Incomplete/out-of-range source rows')
    accepted=set(frame.open_time)
    result={}
    for row in rows:
        value=int(row[0]);t=pd.to_datetime(value,unit='us' if value>10**14 else 'ms',utc=True)
        if t in accepted:
            if t in result:raise ValueError('Duplicate canonical candle')
            result[t]={name:Decimal(str(row[i])) for name,i in zip(VALUES,POSITIONS)}
    return result,quarantine


def zip_rows(path,expected):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        raise ValueError('Archive differs from recorded evidence')
    with zipfile.ZipFile(path) as z:
        names=[n for n in z.namelist() if n.endswith('.csv')]
        if len(names)!=1:raise ValueError('Expected one CSV')
        return pd.read_csv(z.open(names[0]),header=None,dtype=str).values.tolist()


def verdict(api,daily,monthly,kind):
    if api is None:return 'api_candle_absent_or_quarantined'
    if kind=='addition':
        return 'api_confirms_daily_addition' if api==daily else 'api_disagrees_with_daily_addition'
    if api==daily and api==monthly:return 'all_sources_agree'
    if api==daily:return 'api_supports_daily'
    if api==monthly:return 'api_supports_monthly'
    return 'api_matches_neither_archive'


def fetch_api_day(cache,day):
    url=request_url(day);key=day.strftime('%Y-%m-%d')
    path=cache/'responses'/(key+'.json');meta_path=cache/'responses'/(key+'.meta.json')
    if path.exists() and meta_path.exists():
        raw=path.read_bytes();meta=json.loads(meta_path.read_text())
        if meta['url']!=url or hashlib.sha256(raw).hexdigest()!=meta['sha256']:
            raise ValueError('API response cache mismatch')
    else:
        raw=get(url)
        meta={'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),
              'retrieved_at':str(pd.Timestamp.now(tz='UTC'))}
        atomic_bytes(path,raw);atomic_bytes(meta_path,(json.dumps(meta,indent=2)+'\n').encode())
    rows=json.loads(raw)
    if not isinstance(rows,list) or len(rows)>=1000:raise ValueError('Unexpected or possibly truncated API response')
    for row in rows:
        v=int(row[0]);t=pd.to_datetime(v,unit='us' if v>10**14 else 'ms',utc=True)
        if not day<=t<day+pd.Timedelta(days=1):raise ValueError('API returned outside requested day')
    mapped,quarantine=canonical_map(rows,day+pd.Timedelta(days=1))
    return mapped,{**meta,'valid_candles':len(mapped),'quarantined_rows':len(quarantine)}


def run(market='data/research',daily_cache='data/daily_recovery',cache='data/api_reconciliation',
        report_dir='reports/api_reconciliation'):
    market,daily_cache,cache,report_dir=map(Path,(market,daily_cache,cache,report_dir))
    if cache.resolve() in (market.resolve(),daily_cache.resolve()):
        raise ValueError('Separate API evidence cache required')
    repo=Path(__file__).resolve().parents[2]
    prior_path=repo/'reports/daily_recovery/results.json'
    prior_bytes=prior_path.read_bytes();prior=json.loads(prior_bytes)
    catalog_bytes=(market/'catalog.json').read_bytes();catalog=json.loads(catalog_bytes)
    if catalog['snapshot_id']!=prior['source_snapshot']:raise ValueError('Market snapshot changed')
    candidate_meta=prior['candidate_file'];p=daily_cache/candidate_meta['path']
    if hashlib.sha256(p.read_bytes()).hexdigest()!=candidate_meta['sha256']:
        raise ValueError('Staged candidate hash mismatch')
    candidates=pd.read_parquet(p)
    if len(candidates)!=prior['candidate_count']:raise ValueError('Candidate count mismatch')
    targets=[{'open_time':str(t),'kind':'addition'} for t in candidates.open_time]
    targets += [{'open_time':x['open_time'],'kind':'conflict'} for x in prior['conflicts']]
    if len({x['open_time'] for x in targets})!=len(targets):raise ValueError('Duplicate targets')
    days=sorted({utc(x['open_time']).floor('D') for x in targets})
    # Validate all planned requests before any network access.
    for day in days:request_url(day)
    daily_meta={x['day']:x['source'] for x in prior['days'] if x['status']=='verified'}
    monthly_meta={Path(x['path']).name:x for x in catalog['sources'] if '/monthly/' in x['url']}
    records=[];responses=[]
    for day in days:
        key=day.strftime('%Y-%m-%d')
        daily_path=daily_cache/'raw'/'daily'/'5m'/('BTCUSDT-5m-'+key+'.zip')
        daily,_=canonical_map(zip_rows(daily_path,daily_meta[key]['sha256']),day+pd.Timedelta(days=1))
        month=day.strftime('%Y-%m');name='BTCUSDT-5m-'+month+'.zip'
        monthly_path=market/'raw'/'monthly'/'5m'/name
        monthly,_=canonical_map(zip_rows(monthly_path,monthly_meta[name]['sha256']),RESERVED_FROM)
        error=None
        try:
            api,meta=fetch_api_day(cache,day)
            responses.append({'day':key,'status':'verified',**meta})
        except Exception as e:
            api={};error={'error_type':type(e).__name__,'detail':str(e)[:400]}
            responses.append({'day':key,'status':'error',**error})
        for target in targets:
            t=utc(target['open_time'])
            if t.floor('D')!=day:continue
            a,d,m=api.get(t),daily.get(t),monthly.get(t)
            if d is None:raise ValueError('Daily target missing from validated source')
            status='unresolved_api_error' if error else verdict(a,d,m,target['kind'])
            record={**target,'status':status}
            if target['kind']=='conflict' or status!='api_confirms_daily_addition':
                record['values']={name:{'api':str(a[name]) if a else None,
                    'daily':str(d[name]),'monthly':str(m[name]) if m else None} for name in VALUES}
            records.append(record)
        print(key+' '+('error' if error else 'verified'),flush=True)
    if prior_bytes!=prior_path.read_bytes() or catalog_bytes!=(market/'catalog.json').read_bytes():
        raise ValueError('Inputs changed')
    counts=dict(Counter(x['status'] for x in records))
    report={'source_snapshot':catalog['snapshot_id'],'daily_report_sha256':hashlib.sha256(prior_bytes).hexdigest(),
        'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'target_count':len(targets),'planned_days':len(days),'responses':responses,
        'verdict_counts':counts,'targets':records,'market_data_changed':False,
        'new_strategy_tests':0,'reserved_data_read':False,
        'decision':'api_errors_require_followup' if any(x['status']=='error' for x in responses) else 'reconciliation_complete_review_evidence',
        'comparison':'Exact decimal equality on all nine OHLCV/trade fields after timestamp and candle validation.',
        'limits':'API and archives share exchange infrastructure; agreement is corroboration, not independent truth. Only the 240 staged candidates and seven existing conflicts are adjudicated; other gaps remain outside this request.'}
    atomic_bytes(report_dir/'results.json',(json.dumps(report,indent=2)+'\n').encode())
    lines=['# Public API reconciliation','',
        '**Decision: '+report['decision']+'.**','',
        f"Requested {len(days)} complete UTC development days to adjudicate {len(targets)} target candles. Both startTime and endTime are bounded; no reserved dates or account/order endpoints are used.",
        '',
        '| Verdict | Candles |','|---|---:|']
    for status,n in counts.items():lines.append(f"| {status} | {n} |")
    lines+=['',
        'Comparisons use exact Decimal values from original archive/API strings for all nine price, volume and trade-count fields. The existing timestamp/OHLCV validator first excludes malformed or incomplete rows. This avoids treating floating-point parsing differences as source conflicts.',
        '',
        'The API response bytes, retrieval times and SHA256 digests are cached separately. A digest establishes local integrity, not an exchange-signed authenticity guarantee. Every archive must still match its previously recorded checksum.',
        '',
        '## Review checkpoint','',
        'The market database and all strategy results remain unchanged. Only API-confirmed additions or explicitly corroborated corrections may be proposed for a new immutable snapshot. Retain unresolved contradictions. A response error is not evidence that a candle is absent.',
        '',
        'A confirmed repair requires rebuilding affected timeframes and features and repeating affected registered analyses under their unchanged rules. Preserve the old data snapshot and negative results. This comparison has not assessed effects on strategy outcomes.',
        '',
        'API and archive agreement may reflect common upstream data. The remaining missing slots were not evaluated by this bounded request and must not be described as recovered.',
        '',
        'Endpoint reference: https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints',
        '',
        'Reproduce: python -m research.diagnostics.api_reconcile (reuses hash-verified responses).',
        '',f"Source snapshot: {catalog['snapshot_id']}",'']
    atomic_bytes(report_dir/'RECONCILIATION.md','\n'.join(lines).encode())
    print(json.dumps({'verdict_counts':counts,'decision':report['decision']}),flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--market',default='data/research');p.add_argument('--daily-cache',default='data/daily_recovery')
    p.add_argument('--cache',default='data/api_reconciliation');p.add_argument('--report-dir',default='reports/api_reconciliation')
    a=p.parse_args();run(a.market,a.daily_cache,a.cache,a.report_dir)
