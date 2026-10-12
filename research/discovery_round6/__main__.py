"""Feature-only historical feasibility for the frozen double-bottom definition."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import numpy as np
import pandas as pd
import pyarrow
from market_data.schema import utc
from market_data.source import atomic_bytes
from market_data.store import read_market, RESERVED_FROM, writer_lock
from research.indicators import calculate
from research.patterns.double_bottom import detect, PARAMETERS
from research.discovery.engine import scheduled
from research.discovery_round5.__main__ import feasibility


def count_pool(features,start,end):
    if start>=end or end>RESERVED_FROM:raise ValueError('Invalid pool')
    t=features.available_at
    if str(t.dt.tz)!='UTC' or t.isna().any() or t.duplicated().any() or not t.is_monotonic_increasing or (t>=RESERVED_FROM).any():
        raise ValueError('Sorted unique development UTC decisions required')
    if (features.signal & ~features.eligible).any():raise ValueError('Signal outside eligible baseline')
    pool=features[t.ge(start)&t.lt(end)]
    baseline=pool.loc[pool.eligible,'available_at']
    origin=baseline.min().floor('D') if len(baseline) else None
    signals=pool.loc[pool.signal,['observation_id','available_at']].rename(columns={'available_at':'decision_at'})
    signals['label_end']=signals.decision_at+pd.Timedelta(hours=24,minutes=5)
    kept=signals[signals.label_end.le(end)]
    active=0 if origin is None else int(((kept.decision_at-origin).dt.total_seconds()//(28*86400)).nunique())
    return {'raw_events':len(signals),'boundary_purged':len(signals)-len(kept),'timing_eligible':len(kept),
        'scheduled_nonoverlap':len(scheduled(kept,60)),'active_28day_blocks':active,
        'block_origin':str(origin) if origin is not None else None,'eligible_baseline_decisions':len(baseline),
        'counts_by_year':{str(y):len(g) for y,g in kept.groupby(kept.decision_at.dt.year)},'execution_paths_checked':False}


def save_frame(root,name,frame):
    payload=frame.to_parquet(index=False,compression='zstd');sha=hashlib.sha256(payload).hexdigest()
    path=f'{name}/{sha}.parquet';atomic_bytes(root/path,payload)
    if hashlib.sha256((root/path).read_bytes()).hexdigest()!=sha:raise ValueError('Checksum mismatch')
    pd.testing.assert_frame_equal(frame,pd.read_parquet(root/path))
    return {'path':path,'sha256':sha,'rows':len(frame),'columns':list(frame)}


def run(source='data/research_repaired_v1',destination='data/research_discovery_round6',report_dir='reports/discovery_round6'):
    source,destination,report_dir=map(Path,(source,destination,report_dir))
    if source.resolve()==destination.resolve() or source.resolve() in destination.resolve().parents:
        raise ValueError('Separate destination required')
    if (destination/'catalog.json').exists() or (report_dir/'feasibility.json').exists():
        raise ValueError('Preserve previous results; use fresh destinations')
    repo=Path(__file__).resolve().parents[2]
    reg_path=Path(__file__).with_name('REGISTRY.json');raw=reg_path.read_bytes();reg=json.loads(raw)
    registration=json.loads((repo/'reports/discovery_round6/registration.json').read_text())
    for p in ('research/discovery_round6/REGISTRY.json','research/patterns/double_bottom.py'):
        if hashlib.sha256((repo/p).read_bytes()).hexdigest()!=registration['files_sha256'][p]:
            raise ValueError('Registered definition changed')
    if reg['parameters']!=PARAMETERS:raise ValueError('Detector parameters changed')
    source_raw=(source/'catalog.json').read_bytes()
    if json.loads(source_raw)['snapshot_id']!=reg['market_snapshot']:raise ValueError('Wrong market snapshot')
    prior_raw=(repo/reg['prior_report']).read_bytes()
    if hashlib.sha256(prior_raw).hexdigest()!=reg['prior_report_sha256']:raise ValueError('Prior ledger changed')
    with writer_lock(destination):
        candles=read_market(source,'1h','2018-01-01',RESERVED_FROM,allow_gaps=True)
        candles=candles[candles.available_at<RESERVED_FROM].reset_index(drop=True)
        indicators=calculate(candles,'1h')
        features=indicators[['available_at','segment_id','bars_since_gap']].copy()
        features['prior_atr']=indicators.groupby('segment_id',sort=False).atr.shift()
        features['eligible']=np.isfinite(features.prior_atr)&features.prior_atr.gt(0)&features.bars_since_gap.ge(16)
        features['observation_id']=features.available_at.astype(str)
        events=detect(candles)
        if events.event_id.duplicated().any() or events.available_at.duplicated().any():raise ValueError('Duplicate events')
        if not events.available_at.isin(features.available_at).all():raise ValueError('Event outside features')
        features['signal']=features.available_at.isin(events.available_at)
        counts={p:count_pool(features,utc(a),utc(b)) for p,(a,b) in reg['periods'].items()}
        gates=feasibility(counts,reg['feasibility_gates'])
        for n in (1000,10000):
            prefix=candles.iloc[:min(n,len(candles))]
            expected=events[events.available_at<=prefix.available_at.iloc[-1]].reset_index(drop=True)
            pd.testing.assert_frame_equal(detect(prefix),expected)
        if not ((events.formation_start<events.formation_end)&(events.formation_end<=events.available_at)).all():
            raise ValueError('Invalid event recognition timing')
        missing_context={k:sum(json.loads(v)[k] is None for v in events.context) for k in ('atr','rsi','ema_50','ema_200')}
        files={'features':save_frame(destination,'features',features),'events':save_frame(destination,'events',events)}
        if raw!=reg_path.read_bytes() or source_raw!=(source/'catalog.json').read_bytes() or prior_raw!=(repo/reg['prior_report']).read_bytes():
            raise ValueError('Inputs changed during scan')
        paths=['research/discovery_round6/__main__.py','research/patterns/double_bottom.py','research/patterns/engine.py',
               'research/indicators/engine.py','research/discovery/engine.py','research/discovery_round5/__main__.py','market_data/store.py']
        report={'candidate':reg['candidate'],'market_snapshot':reg['market_snapshot'],
            'registry_sha256':hashlib.sha256(raw).hexdigest(),'prior_report_sha256':reg['prior_report_sha256'],
            'files':files,'counts':counts,'feasibility':gates,'missing_context_at_events':missing_context,
            'code_sha256':{p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in paths},
            'runtime':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'pyarrow':pyarrow.__version__},
            'prefix_checks':[1000,10000],'prior_return_tests':36,'new_return_tests':0,'execution_paths_checked':False,
            'selected_strategy':None,'decision':'propose_outcome_screen' if gates['passed'] else 'insufficient_feature_sample'}
        report['snapshot_id']=hashlib.sha256(json.dumps(report,sort_keys=True,allow_nan=False).encode()).hexdigest()
        encoded=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode()
        atomic_bytes(destination/'manifests'/(report['snapshot_id']+'.json'),encoded)
        atomic_bytes(destination/'catalog.json',encoded);atomic_bytes(report_dir/'feasibility.json',encoded)
        lines=['# Round 6 — double-bottom feature feasibility','',
          'Registered in commit 4ee7f663dd8107f758bc8d2c4ef1018b91c7267b. Uses the pinned repaired market snapshot, frozen detector and unchanged sample requirements. Only causal features and confirmed events are calculated; no future labels or return statistics.','',
          '| Pool | Raw events | Boundary purged | Timing eligible | Scheduled nonoverlap | Active 28-day blocks |',
          '|---|---:|---:|---:|---:|---:|']
        for p,c in counts.items():lines.append(f"| {p} | {c['raw_events']} | {c['boundary_purged']} | {c['timing_eligible']} | {c['scheduled_nonoverlap']} | {c['active_28day_blocks']} |")
        lines+=['',f"Decision: **{report['decision']}**.",'',
          'Requirements: training ≥100 timing-eligible events, ≥50 scheduled nonoverlapping events, ≥30 active 28-day blocks; reused recent ≥30 events. Frequency is not statistical power or proof of profitability. Complete 5m execution paths remain unchecked.','',
          'Annual counts, baseline coverage, missing context and block origins are in feasibility.json. Context availability is descriptive and was not used to select new filters. Historical prefixes of 1,000 and 10,000 candles reproduce the same earlier events. Stored tables pass checksum and read-back equality checks.','',
          'Training is 2018–2023; 2024–2026 Q1 is reused recent history. Reserved data from 2026-04-01 remains blocked. The prior ledger was verified by byte hash, without loading prior labels. The return-test ledger remains at 36.','',
          ('Next: review feasibility, then consider only the registered 24h outcome. Append one test only if outcomes are evaluated.' if gates['passed'] else 'Stop this candidate without outcomes or parameter changes because the registered sample requirements failed.'),'',
          'Reproduce using `python -m research.discovery_round6 --destination <fresh-data-directory> --report-dir <fresh-report-directory>`. No strategy is selected and trading remains inactive.','']
        atomic_bytes(report_dir/'FEASIBILITY.md','\n'.join(lines).encode())
        print(json.dumps({'snapshot_id':report['snapshot_id'],'counts':counts,'feasibility':gates}),flush=True)
        return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',default='data/research_repaired_v1');p.add_argument('--destination',default='data/research_discovery_round6')
    p.add_argument('--report-dir',default='reports/discovery_round6');a=p.parse_args();run(a.source,a.destination,a.report_dir)
