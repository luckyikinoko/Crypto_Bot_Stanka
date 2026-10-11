"""Audit development candle gaps, source evidence and causal warm-up losses."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import pandas as pd
from market_data.schema import utc,quality,aggregate,duration
from market_data.store import read_market,RESERVED_FROM
from market_data.source import parse_archive,atomic_bytes
from research.regimes import classify


def classify_missing(missing, accepted, rejected):
    """Classify evidence, not economic outage causes; never repair timestamps."""
    accepted=set(accepted)
    exact={utc(x['open_time_utc']) for x in rejected}
    offgrid=[]
    for row in rejected:
        if row['reason']=='off_grid_open':
            unit='us' if row['open_time_raw']>10**14 else 'ms'
            a=utc(row['open_time_utc'])
            b=pd.to_datetime(row['close_time_raw'],unit=unit,utc=True)+pd.Timedelta(microseconds=1 if unit=='us' else 1000)
            offgrid.append((a,b))
    result={}
    for t in missing:
        if t in accepted:reason='valid_archive_row_missing_from_store'
        elif t in exact:reason='quarantined_exact_open'
        elif any(a<t+duration('5m') and b>t for a,b in offgrid):reason='overlaps_quarantined_off_grid_row'
        else:reason='absent_from_cached_archive'
        result[t]=reason
    return result


def missing_members(base, higher, interval, start, end):
    expected=pd.date_range(start,end,freq=duration(interval),inclusive='left')
    missing=expected.difference(pd.DatetimeIndex(higher.open_time))
    have=pd.DatetimeIndex(base.open_time)
    rows=[]
    for t in missing:
        absent=pd.date_range(t,t+duration(interval),freq='5min',inclusive='left').difference(have)
        rows.append({'open_time':str(t),'missing_5m_members':len(absent),
                     'first_missing_5m':str(absent[0]) if len(absent) else None})
    return rows


def coverage(candles, interval):
    f=classify(candles,interval)
    f=f[f.available_at<RESERVED_FROM]
    annual=[]
    for (year,pool),g in f.groupby([f.available_at.dt.year,
            f.available_at.ge(utc('2024-01-01')).map({False:'training',True:'reused_recent'})]):
        annual.append({'year':int(year),'pool':pool,'decisions':len(g),
                       'unknown_trend':int(g.trend.eq('unknown').sum()),
                       'unknown_volatility':int(g.volatility.eq('unknown').sum()),
                       'both_ready':int((g.trend.ne('unknown')&g.volatility.ne('unknown')).sum())})
    segments=[]
    previous=None
    for sid,g in f.groupby('segment_id',sort=True):
        segments.append({'segment_id':int(sid),'first_open':str(g.open_time.iloc[0]),
            'last_decision':str(g.available_at.iloc[-1]),'decisions':len(g),
            'gap_before_minutes':None if previous is None else (g.open_time.iloc[0]-previous).total_seconds()/60,
            'unknown_trend':int(g.trend.eq('unknown').sum()),
            'unknown_volatility':int(g.volatility.eq('unknown').sum()),
            'reason':'initial_warmup' if previous is None else 'post_gap_warmup'})
        previous=g.available_at.iloc[-1]
    return {'annual':annual,'segments':segments}


def run(root='data/research',destination='reports/coverage_audit'):
    root,destination=Path(root),Path(destination)
    raw=(root/'catalog.json').read_bytes();catalog=json.loads(raw)
    identity=dict(catalog);identity.pop('snapshot_id')
    if hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()!=catalog['snapshot_id']:
        raise ValueError('Market manifest digest mismatch')
    start=utc('2018-01-01');end=RESERVED_FROM
    frames={i:read_market(root,i,start,end,allow_gaps=True) for i in ('5m','15m','1h','4h','1d')}
    inventory={i:quality(f,i,start,end) for i,f in frames.items()}
    monthly={}
    skipped=[]
    for source in catalog['sources']:
        match=re.search(r'BTCUSDT-5m-(\d{4}-\d{2})\.zip$',source['url'])
        if not match:
            skipped.append(source['url']);continue
        month=match.group(1)
        if utc(month+'-01')>=end:
            skipped.append(source['url']);continue
        path=root/'raw'/'monthly'/'5m'/Path(source['path']).name
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        side=path.with_suffix('.zip.CHECKSUM').read_text().split()[0]
        if digest!=source['sha256'] or digest!=side:
            raise ValueError('Archive checksum mismatch: '+month)
        monthly[month]=(path,source)
    expected_months=pd.date_range(start,end,freq='MS',inclusive='left').strftime('%Y-%m')
    if set(monthly)!=set(expected_months):
        raise ValueError('Monthly archive coverage incomplete')
    base=frames['5m']
    missing=pd.date_range(start,end,freq='5min',inclusive='left').difference(pd.DatetimeIndex(base.open_time))
    evidence={};rejections=[];raw_months=[]
    for month in sorted(set(missing.strftime('%Y-%m'))):
        path,source=monthly[month];quarantine=[]
        accepted,_=parse_archive(path,'5m',end,quarantine)
        month_missing=missing[missing.strftime('%Y-%m')==month]
        evidence.update(classify_missing(month_missing,accepted.open_time,quarantine))
        for q in quarantine:rejections.append({**q,'source':source['url']})
        raw_months.append({'month':month,'source':source['url'],'sha256':source['sha256'],
                           'rejected_rows':len(quarantine),'missing_slots':len(month_missing)})
    key=lambda q:(q['open_time_raw'],q['close_time_raw'],q['reason'],q['source'])
    old=catalog['quality']['quarantined_timestamp_rows']
    if sorted(map(key,rejections))!=sorted(map(key,old)):
        raise ValueError('Quarantine evidence differs from recorded snapshot')
    gap_evidence=[]
    for gap in inventory['5m']['gaps']:
        times=pd.date_range(utc(gap['start']),utc(gap['end_exclusive']),freq='5min',inclusive='left')
        gap_evidence.append({**gap,'evidence_counts':dict(Counter(evidence[t] for t in times)),
            'exchange_outage_confirmed':False})
    derived={}
    for interval in ('15m','1h','4h','1d'):
        regenerated=aggregate(base,interval)
        pd.testing.assert_frame_equal(regenerated,frames[interval],check_exact=True)
        members=missing_members(base,frames[interval],interval,start,end)
        if any(x['missing_5m_members']==0 for x in members):
            raise ValueError('Unexplained aggregation omission')
        derived[interval]={'exact_reaggregation_match':True,'missing_candles':members}
    warmup={i:coverage(frames[i],i) for i in ('15m','1h','4h')}
    if raw!=(root/'catalog.json').read_bytes():
        raise ValueError('Source changed')
    report={'source_snapshot':catalog['snapshot_id'],'scope':['2018-01-01','2026-04-01'],
        'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'monthly_archives_checksum_verified':len(monthly),'skipped_sources_not_opened':skipped,
        'gap_months_reparsed':raw_months,'quarantined_rows_reproduced':len(rejections),
        'inventory':inventory,'missing_5m_evidence':dict(Counter(evidence.values())),
        'gap_evidence':gap_evidence,'derived':derived,'warmup':warmup,
        'market_data_changed':False,'new_hypothesis_tests':0,'outcome_labels_read':False,
        'limits':'Absence from a cached official archive does not prove an exchange outage. Off-grid overlaps do not establish a valid replacement candle. Independent daily/API recovery has not been attempted by this command.'}
    atomic_bytes(destination/'results.json',(json.dumps(report,indent=2)+'\n').encode())
    lines=['# Development data coverage and warm-up audit','',
        'Market data and strategy results are unchanged. No outcome labels or reserved observations were read. Scope: 2018-01-01 through 2026-03-31 UTC.',
        '',
        '## Candle integrity','',
        '| Interval | Stored candles | Missing candles | Gap ranges |',
        '|---|---:|---:|---:|']
    for i,q in inventory.items():
        lines.append(f"| {i} | {q['rows']} | {q['missing_candles']} | {len(q['gaps'])} |")
    lines+=['',
        f"All {len(monthly)} development monthly archive files match their recorded hashes and checksum sidecars. Stored partitions pass checksum/schema validation. Reaggregation of every 15m/1h/4h/1d candle from 5m inputs matches stored values exactly. Every higher-timeframe omission contains missing 5m members.",
        '',
        '## Source evidence for missing 5m slots','',
        '| Classification | Missing slots |',
        '|---|---:|']
    for reason,n in report['missing_5m_evidence'].items():lines.append(f"| {reason} | {n} |")
    lines+=['',
        'Classifications are mutually exclusive: a valid archived row takes priority, then a quarantined exact open, then temporal overlap with an off-grid rejected row, then absence. An overlapping off-grid candle cannot be shifted or rounded onto the UTC grid without inventing a price path.',
        '',
        f"Reparsing affected monthly archives reproduces {len(rejections)} quarantined timestamp rows. The per-gap evidence, source URLs, yearly coverage and all segment resets are in results.json. Exchange outage causes remain unconfirmed. The reserved 2026-04-01 daily source listed in historical metadata was explicitly skipped.",
        '',
        '## Decision coverage after warm-up','',
        '| Interval / pool | Decisions | Unknown trend | Unknown volatility | Both ready |',
        '|---|---:|---:|---:|---:|']
    for interval,w in warmup.items():
        for pool in ('training','reused_recent'):
            a=[x for x in w['annual'] if x['pool']==pool]
            sums={k:sum(x[k] for x in a) for k in ('decisions','unknown_trend','unknown_volatility','both_ready')}
            lines.append(f"| {interval} / {pool} | {sums['decisions']} | {sums['unknown_trend']} | {sums['unknown_volatility']} | {sums['both_ready']} |")
    lines+=['',
        'The current definitions reset all indicator state after a missing bar. EMA200 requires 200 contiguous bars; trend is unavailable on the first 199. ATR14 plus 252 preceding ATR/close values makes volatility unavailable on the first 265 bars of each segment. At 4h that is over 44 days per fully warmable segment. Gaps close together can prevent readiness entirely. Unknown trend and volatility counts overlap and must not be added.',
        '',
        'The audit does not treat reset-related loss as a software bug or recommend bypassing it. Indicators carried across gaps would be a different definition needing separate justification. Recent history has better continuity, so coverage is not uniform across research periods.',
        '',
        '## Next recovery checkpoint','',
        'Use official daily archives or the public API only for the 30 documented development gap ranges. Compare exact timestamps, boundaries and OHLCV with the frozen monthly evidence; require valid complete candles and record provenance/conflicts. If sources agree the data is absent or malformed, retain the gap. Do not label the entire gap an exchange outage without supporting evidence.',
        '',
        'Any verified additions must create a new market snapshot. Re-run affected feature calculations and registered experiments without changing their rules; keep original results. A recovery investigation may find no usable additions. This audit itself makes no repairs.',
        '',
        'Official source format/checksum reference: https://github.com/binance/binance-public-data (checked 2026-10-11). Millisecond and microsecond source timestamps remain supported; the timestamp unit transition is not treated as a gap.',
        '',
        'Reproduce: python -m research.diagnostics.coverage_audit',
        '',f"Source snapshot: {catalog['snapshot_id']}",'']
    atomic_bytes(destination/'COVERAGE.md','\n'.join(lines).encode())
    print(json.dumps({'missing':{i:q['missing_candles'] for i,q in inventory.items()},
        'source_evidence':report['missing_5m_evidence'],'archives_verified':len(monthly),
        'quarantined_rows_reproduced':len(rejections),'market_data_changed':False}),flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',default='data/research');p.add_argument('--destination',default='reports/coverage_audit')
    a=p.parse_args();run(a.source,a.destination)
