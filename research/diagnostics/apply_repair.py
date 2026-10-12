"""Publish the corroborated 247-row repair as a separate market snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from market_data.schema import COLUMNS,VALUES,MINUTES,utc,validate,aggregate,quality
from market_data.source import atomic_bytes
from market_data.store import read_market,publish,writer_lock,RESERVED_FROM
from .coverage_audit import coverage


def diff_rows(before,after):
    a=before.set_index('open_time');b=after.set_index('open_time')
    common=a.index.intersection(b.index)
    changed=common[a.loc[common].ne(b.loc[common]).any(axis=1)]
    return {'added':[str(t) for t in b.index.difference(a.index)],
            'removed':[str(t) for t in a.index.difference(b.index)],
            'changed':[str(t) for t in changed]}


def apply_rows(base,additions,corrections):
    validate(base,'5m');validate(additions,'5m')
    if (additions.open_time<utc('2018-01-01')).any() or (additions.available_at>RESERVED_FROM).any():
        raise ValueError('Addition outside development range')
    if additions.open_time.isin(base.open_time).any():
        raise ValueError('Addition overwrites existing row')
    patched=base.set_index('open_time').copy()
    times=[utc(x['open_time']) for x in corrections]
    if len(set(times))!=len(times):raise ValueError('Duplicate correction')
    for t,row in zip(times,corrections):
        if t not in patched.index or t>=RESERVED_FROM:raise ValueError('Invalid correction target')
        if set(row['old_monthly_values'])!=set(VALUES) or set(row['new_daily_api_values'])!=set(VALUES):
            raise ValueError('Incomplete correction fields')
        for c in VALUES:
            old=float(row['old_monthly_values'][c])
            # Parent file hashes pin the exact preimage; tolerate only float representation
            # differences between raw CSV decimal text and its stored float64 value.
            if not np.isclose(float(patched.loc[t,c]),old,rtol=1e-14,atol=0):
                raise ValueError('Correction preimage mismatch')
            value=row['new_daily_api_values'][c]
            if c=='trades':
                if float(value)!=int(value):raise ValueError('Noninteger trades')
                patched.loc[t,c]=int(value)
            else:patched.loc[t,c]=float(value)
    patched=patched.reset_index()[COLUMNS]
    result=pd.concat([patched,additions],ignore_index=True).sort_values('open_time').reset_index(drop=True)
    result['trades']=result.trades.astype('int64');validate(result,'5m')
    delta=diff_rows(base,result)
    if delta['removed'] or set(delta['added'])!=set(map(str,additions.open_time)) or set(delta['changed'])!=set(map(str,times)):
        raise ValueError('Unplanned row change')
    return result,delta


def run(source='data/research',destination='data/research_repaired_v1',
        daily_cache='data/daily_recovery',api_cache='data/api_reconciliation',
        report_dir='reports/repair_v1'):
    source,destination,daily_cache,api_cache,report_dir=map(Path,(source,destination,daily_cache,api_cache,report_dir))
    if destination.resolve() in (source.resolve(),daily_cache.resolve(),api_cache.resolve()):
        raise ValueError('Separate repair destination required')
    if (destination/'catalog.json').exists():
        raise ValueError('Refusing to replace an existing repaired snapshot; use a fresh destination')
    repo=Path(__file__).resolve().parents[2]
    plan_bytes=(repo/'reports/api_reconciliation/REPAIR_PLAN.json').read_bytes();plan=json.loads(plan_bytes)
    api_bytes=(repo/'reports/api_reconciliation/results.json').read_bytes();api=json.loads(api_bytes)
    parent_bytes=(source/'catalog.json').read_bytes();parent=json.loads(parent_bytes)
    identity=dict(parent);identity.pop('snapshot_id')
    if hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()!=parent['snapshot_id']:
        raise ValueError('Parent manifest digest mismatch')
    daily_bytes=(repo/'reports/daily_recovery/results.json').read_bytes()
    if hashlib.sha256(daily_bytes).hexdigest()!=api['daily_report_sha256']:
        raise ValueError('Daily evidence report changed')
    if parent['snapshot_id']!=plan['base_market_snapshot'] or api['source_snapshot']!=parent['snapshot_id']:
        raise ValueError('Parent identity mismatch')
    if hashlib.sha256(api_bytes).hexdigest()!=plan['api_report_sha256']:
        raise ValueError('API evidence changed')
    if api['verdict_counts']!={'api_confirms_daily_addition':240,'api_supports_daily':7}:
        raise ValueError('Expected fully corroborated repair')
    for response in api['responses']:
        p=api_cache/'responses'/(response['day']+'.json')
        if response['status']!='verified' or hashlib.sha256(p.read_bytes()).hexdigest()!=response['sha256']:
            raise ValueError('API response integrity failure')
    from .api_reconcile import canonical_map
    api_values={}
    for response in api['responses']:
        rows=json.loads((api_cache/'responses'/(response['day']+'.json')).read_bytes())
        values,_=canonical_map(rows,utc(response['day'])+pd.Timedelta(days=1))
        api_values.update(values)
    for row in plan['corrections']:
        t=utc(row['open_time'])
        if {k:str(v) for k,v in api_values[t].items()}!=row['new_daily_api_values']:
            raise ValueError('Correction differs from exact API decimal evidence')
    meta=plan['additions']['source_file'];path=daily_cache/meta['path']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:
        raise ValueError('Candidate file changed')
    additions=pd.read_parquet(path)
    if len(additions)!=240 or len(plan['corrections'])!=7 or set(map(str,additions.open_time))!=set(plan['additions']['open_times']):
        raise ValueError('Repair scope mismatch')
    # Recheck all addition fields against API evidence, allowing only float64 parsing noise.
    for row in additions.itertuples():
        for c in VALUES:
            if not np.isclose(getattr(row,c),float(api_values[row.open_time][c]),rtol=1e-14,atol=0):
                raise ValueError('Addition differs from API evidence')
    daily_report=json.loads(daily_bytes)
    repair_days={str(t.date()) for t in additions.open_time}|{str(utc(x['open_time']).date()) for x in plan['corrections']}
    for day in daily_report['days']:
        if day['day'] in repair_days:
            archive=daily_cache/'raw'/'daily'/'5m'/('BTCUSDT-5m-'+day['day']+'.zip')
            if hashlib.sha256(archive.read_bytes()).hexdigest()!=day['source']['sha256']:
                raise ValueError('Daily archive changed')
    original={i:read_market(source,i,'2018-01-01',RESERVED_FROM,allow_gaps=True) for i in MINUTES}
    repaired,delta=apply_rows(original['5m'],additions,plan['corrections'])
    frames={i:aggregate(repaired,i) for i in MINUTES}
    changes={};before_quality={};after_quality={}
    for i,f in frames.items():
        changes[i]=diff_rows(original[i],f)
        allowed_add={str(t.floor(str(MINUTES[i])+'min')) for t in additions.open_time}
        allowed_change={str(utc(x['open_time']).floor(str(MINUTES[i])+'min')) for x in plan['corrections']}
        if changes[i]['removed'] or not set(changes[i]['added'])<=allowed_add or not set(changes[i]['changed'])<=allowed_change:
            raise ValueError('Unplanned derived candle change')
        before_quality[i]=quality(original[i],i,'2018-01-01',RESERVED_FROM)
        after_quality[i]=quality(f,i,'2018-01-01',RESERVED_FROM)
    warmup={}
    old_coverage=json.loads((repo/'reports/coverage_audit/results.json').read_text())
    if old_coverage['source_snapshot']!=parent['snapshot_id']:raise ValueError('Coverage baseline mismatch')
    for i in ('15m','1h','4h'):
        warmup[i]={'before':old_coverage['warmup'][i],'after':coverage(frames[i],i)}
    repair_meta={'parent_snapshot':parent['snapshot_id'],'repair_plan_sha256':hashlib.sha256(plan_bytes).hexdigest(),
        'api_report_sha256':hashlib.sha256(api_bytes).hexdigest(),'added_5m':240,'corrected_5m':7,
        'source_policy':'Daily archive values corroborated by public API; original snapshot preserved',
        'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    q={'start':str(utc('2018-01-01')),'cutoff':str(RESERVED_FROM),'primary_research_interval':'15m',
       'reserved_from':str(RESERVED_FROM),'intervals':after_quality,'repair':repair_meta,
       'quarantined_timestamp_rows':parent['quality']['quarantined_timestamp_rows'],
       'quarantine_note':'Historical parent evidence retained; repaired rows are identified by repair plan'}
    sources=parent['sources']+[{'kind':'api_repair_evidence',**x} for x in api['responses']]
    daily_report=json.loads((repo/'reports/daily_recovery/results.json').read_text())
    repair_days={str(t.date()) for t in additions.open_time}|{str(utc(x['open_time']).date()) for x in plan['corrections']}
    sources += [{'kind':'daily_repair_evidence',**x['source']} for x in daily_report['days'] if x['day'] in repair_days]
    if parent_bytes!=(source/'catalog.json').read_bytes():raise ValueError('Parent changed during repair')
    with writer_lock(destination):
        catalog,_=publish(destination,frames,q,sources)
    # Verify the public reader and all resulting partition checksums.
    for i in MINUTES:
        pd.testing.assert_frame_equal(read_market(destination,i,'2018-01-01',RESERVED_FROM,allow_gaps=True),frames[i],check_exact=True)
    if parent_bytes!=(source/'catalog.json').read_bytes():raise ValueError('Original catalog changed')
    report={'parent_snapshot':parent['snapshot_id'],'repaired_snapshot':catalog['snapshot_id'],
        'repair':repair_meta,'row_changes':changes,'quality_before':before_quality,'quality_after':after_quality,
        'warmup':warmup,'original_snapshot_unchanged':True,'all_partitions_readback_verified':True,
        'research_results_recomputed':False,'default_market_root_changed':False,
        'reserved_data_read':False,'new_hypothesis_tests':0}
    atomic_bytes(report_dir/'results.json',(json.dumps(report,indent=2)+'\n').encode())
    atomic_bytes(report_dir/'manifest.json',(destination/'catalog.json').read_bytes())
    lines=['# Repaired development market snapshot v1','',
        '**240 additions and seven corrections applied to a separate snapshot. Original market data and all original research results are preserved.**','',
        '| Interval | Added candles | Corrected candles | Missing before | Missing after |',
        '|---|---:|---:|---:|---:|']
    for i,c in changes.items():
        lines.append(f"| {i} | {len(c['added'])} | {len(c['changed'])} | {before_quality[i]['missing_candles']} | {after_quality[i]['missing_candles']} |")
    lines+=['','## Warm-up coverage impact','',
        '| Interval / pool | Unknown volatility before | Unknown volatility after | Decisions before | Decisions after |',
        '|---|---:|---:|---:|---:|']
    for i,w in warmup.items():
        for pool in ('training','reused_recent'):
            b=[x for x in w['before']['annual'] if x['pool']==pool]
            a=[x for x in w['after']['annual'] if x['pool']==pool]
            lines.append(f"| {i} / {pool} | {sum(x['unknown_volatility'] for x in b)} | {sum(x['unknown_volatility'] for x in a)} | {sum(x['decisions'] for x in b)} | {sum(x['decisions'] for x in a)} |")
    lines+=['',
        'More candles do not necessarily reduce unknown-indicator counts: newly recovered short segments can add observations that still lack warm-up. No indicator definition or warm-up requirement was relaxed. Residual gaps remain documented and are not filled.',
        '',
        '## Validation and provenance','',
        'API response hashes, the staged addition-file hash, exact correction decimal values, parent snapshot identity and repair-plan digest are checked before publication. Float64 comparisons permit only representation noise (relative tolerance 1e-14); parent file hashes pin the exact stored preimage. No row outside the approved additions/corrections or their higher-timeframe buckets may change.',
        '',
        'Every timeframe is rebuilt from repaired 5m candles, written as UTC Parquet partitions, and read back through the checksum-verifying research reader. The original catalog bytes remain identical. Provenance includes the parent, daily/API evidence, repair plan and changed-row timestamps.',
        '',
        '## Research checkpoint','',
        'This is a data revision, not a new strategy result. Existing reported returns, uncertainty and rejected-candidate decisions refer to the original snapshot until affected experiments are replayed with their registered rules unchanged. Preserve those original reports and label revised reports explicitly.',
        '',
        'The default research input is not switched automatically. The next step is a controlled replay of affected feature, pattern and outcome calculations on this repaired snapshot, followed by a delta report. No parameter search, reserved evaluation, paper trading or live execution is part of this repair.',
        '',
        'Reproduce into a fresh destination: python -m research.diagnostics.apply_repair --destination data/research_repaired_replay --report-dir data/repair_replay_report',
        '',f"Parent: {parent['snapshot_id']}",'',f"Repaired: {catalog['snapshot_id']}",'']
    atomic_bytes(report_dir/'REPAIR.md','\n'.join(lines).encode())
    print(json.dumps({'snapshot':catalog['snapshot_id'],'changes':{i:{k:len(v) for k,v in x.items()} for i,x in changes.items()},
        'missing_after':{i:q['missing_candles'] for i,q in after_quality.items()}}),flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',default='data/research');p.add_argument('--destination',default='data/research_repaired_v1')
    p.add_argument('--daily-cache',default='data/daily_recovery');p.add_argument('--api-cache',default='data/api_reconciliation')
    p.add_argument('--report-dir',default='reports/repair_v1')
    a=p.parse_args();run(a.source,a.destination,a.daily_cache,a.api_cache,a.report_dir)
