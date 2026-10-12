"""Feature-only feasibility for the registered round-five hypothesis."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import pandas as pd
import numpy as np
import pyarrow
from market_data.schema import utc
from market_data.store import read_market, RESERVED_FROM, writer_lock
from market_data.source import atomic_bytes
from research.indicators import calculate
from research.discovery.engine import scheduled
from .engine import FEATURE_COLUMNS, eligibility_mask, signal_mask


def count_pool(features, start, end):
    if start >= end or end > RESERVED_FROM:
        raise ValueError('Invalid or reserved pool')
    eligible = eligibility_mask(features)
    signals = signal_mask(features)
    in_pool = features.available_at.ge(start) & features.available_at.lt(end)
    baseline = features.loc[eligible & in_pool, 'available_at']
    origin = baseline.min().floor('D') if len(baseline) else None
    decisions = features.loc[signals & in_pool, ['observation_id','available_at']].rename(columns={'available_at':'decision_at'})
    # Prospective scheduling timestamps only; no future prices or path checks.
    decisions['label_end'] = decisions.decision_at + pd.Timedelta(hours=24, minutes=5)
    kept = decisions[decisions.label_end.le(end)]
    blocks = ((kept.decision_at-origin).dt.total_seconds()//(28*86400)) if origin is not None else pd.Series(dtype=float)
    return {'raw_events':len(decisions),'boundary_purged':len(decisions)-len(kept),
        'timing_eligible':len(kept),'scheduled_nonoverlap':len(scheduled(kept,60)),
        'active_28day_blocks':int(blocks.nunique()),'block_origin':str(origin) if origin is not None else None,
        'eligible_baseline_decisions':len(baseline),
        'counts_by_year':{str(y):len(g) for y,g in kept.groupby(kept.decision_at.dt.year)},
        'execution_paths_checked':False}


def feasibility(counts, gates):
    train,recent=counts['training'],counts['reused_recent']
    checks={'training_observations':train['timing_eligible']>=gates['training_observations'],
        'training_nonoverlap':train['scheduled_nonoverlap']>=gates['training_nonoverlap'],
        'training_active_28day_blocks':train['active_28day_blocks']>=gates['training_active_28day_blocks'],
        'recent_observations':recent['timing_eligible']>=gates['recent_observations']}
    return {'passed':all(checks.values()),'checks':checks}


def run(source='data/research_repaired_v1',destination='data/research_discovery_round5',report_dir='reports/discovery_round5'):
    source,destination,report_dir=map(Path,(source,destination,report_dir))
    if source.resolve()==destination.resolve() or source.resolve() in destination.resolve().parents:
        raise ValueError('Separate destination required')
    if (destination/'catalog.json').exists() or (report_dir/'feasibility.json').exists():
        raise ValueError('Preserve prior results; use fresh destinations')
    repo=Path(__file__).resolve().parents[2]
    registry_path=Path(__file__).with_name('REGISTRY.json');raw=registry_path.read_bytes();reg=json.loads(raw)
    registered=json.loads((repo/'reports/discovery_round5/registration.json').read_text())
    for name in ('research/discovery_round5/REGISTRY.json','research/discovery_round5/engine.py'):
        if hashlib.sha256((repo/name).read_bytes()).hexdigest()!=registered['files_sha256'][name]:
            raise ValueError('Registered definition changed')
    source_bytes=(source/'catalog.json').read_bytes();market=json.loads(source_bytes)
    if market['snapshot_id']!=reg['market_snapshot']:
        raise ValueError('Wrong market snapshot')
    prior_bytes=(repo/reg['prior_report']).read_bytes()
    if hashlib.sha256(prior_bytes).hexdigest()!=reg['prior_report_sha256']:
        raise ValueError('Prior ledger report changed')
    with writer_lock(destination):
        candles=read_market(source,'1h','2018-01-01',RESERVED_FROM,allow_gaps=True)
        f=calculate(candles,'1h')[['available_at','segment_id','ema_20','ema_50','ema_200']]
        f['close']=candles.reset_index(drop=True).close
        f=f[f.available_at<RESERVED_FROM].reset_index(drop=True)
        f['observation_id']=f.available_at.astype(str)
        f=f[FEATURE_COLUMNS]
        counts={p:count_pool(f,utc(a),utc(b)) for p,(a,b) in reg['periods'].items()}
        decision=feasibility(counts,reg['feasibility_gates'])
        prefix=candles.iloc[:1000]
        check=calculate(prefix,'1h')[['available_at','segment_id','ema_20','ema_50','ema_200']]
        check['close']=prefix.reset_index(drop=True).close
        check['observation_id']=check.available_at.astype(str)
        pd.testing.assert_frame_equal(check[FEATURE_COLUMNS],f.iloc[:len(check)])
        pd.testing.assert_series_equal(signal_mask(check),signal_mask(f).iloc[:len(check)])
        payload=f.to_parquet(index=False,compression='zstd');sha=hashlib.sha256(payload).hexdigest()
        path='features/'+sha+'.parquet';atomic_bytes(destination/path,payload)
        pd.testing.assert_frame_equal(f,pd.read_parquet(destination/path))
        if hashlib.sha256((destination/path).read_bytes()).hexdigest()!=sha:
            raise ValueError('Feature checksum mismatch')
        if raw!=registry_path.read_bytes() or source_bytes!=(source/'catalog.json').read_bytes() or prior_bytes!=(repo/reg['prior_report']).read_bytes():
            raise ValueError('Input changed during feasibility')
        codepaths=['research/discovery_round5/__main__.py','research/discovery_round5/engine.py',
                   'research/indicators/engine.py','research/discovery/engine.py','market_data/store.py','market_data/schema.py']
        report={'candidate':reg['candidate'],'market_snapshot':market['snapshot_id'],
            'registry_sha256':hashlib.sha256(raw).hexdigest(),'prior_report_sha256':reg['prior_report_sha256'],
            'features':{'path':path,'sha256':sha,'rows':len(f),'columns':FEATURE_COLUMNS},
            'code_sha256':{p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in codepaths},
            'runtime':{'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,'pyarrow':pyarrow.__version__},
            'counts':counts,'feasibility':decision,'prefix_verification_candles':len(prefix),
            'new_return_tests':0,'prior_return_tests':reg['prior_tests'],'selected_strategy':None,
            'execution_paths_checked':False,'decision':'propose_outcome_screen' if decision['passed'] else 'insufficient_feature_sample'}
        report['snapshot_id']=hashlib.sha256(json.dumps(report,sort_keys=True,allow_nan=False).encode()).hexdigest()
        encoded=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode()
        atomic_bytes(destination/'manifests'/(report['snapshot_id']+'.json'),encoded)
        atomic_bytes(destination/'catalog.json',encoded);atomic_bytes(report_dir/'feasibility.json',encoded)
        lines=['# Round 5 — feature-only feasibility','',
          'Registered in commit 86fa4489e823f13e13a1c0125309ab7c2c1df9cd. Uses the pinned repaired market snapshot and unchanged EMA-reclaim rule. No historical outcome labels were loaded or calculated. The prior report was checked only by byte hash.','',
          '| Pool | Raw signals | Boundary purged | Timing eligible | Scheduled nonoverlap | Active 28-day blocks |',
          '|---|---:|---:|---:|---:|---:|']
        for p,c in counts.items():
            lines.append(f"| {p} | {c['raw_events']} | {c['boundary_purged']} | {c['timing_eligible']} | {c['scheduled_nonoverlap']} | {c['active_28day_blocks']} |")
        lines+=['',f"Feasibility passed: **{decision['passed']}**.",'',
          'These timing counts are not independent sample sizes or power estimates. Full 5m execution paths have not been checked; usable counts can fall after that check. Feature warm-up and gap resets remain enforced. Annual counts, baseline coverage and block origins are in feasibility.json.','',
          'Training is 2018–2023. Recent 2024–2026 Q1 history is reused, not fresh validation. Reserved data from 2026-04-01 remains blocked. No return, win rate, expectancy, confidence interval or profitability conclusion is produced. The return-test ledger remains at 35.','',
          ('Next checkpoint: review these counts, then evaluate only the registered 24h outcome under the unchanged costs and acceptance gates. Append test 36 only if outcomes are evaluated.' if decision['passed'] else 'Stop this round without outcomes or parameter changes because the registered feasibility requirements failed.'),'',
          'Reproduce with `python -m research.discovery_round5 --destination <fresh-data-directory> --report-dir <fresh-report-directory>`. The output includes only causal features and feasibility metadata. No strategy is selected and no trading is activated.','']
        atomic_bytes(report_dir/'FEASIBILITY.md','\n'.join(lines).encode())
    print(json.dumps({'counts':counts,'feasibility':decision,'snapshot_id':report['snapshot_id']}),flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',default='data/research_repaired_v1')
    p.add_argument('--destination',default='data/research_discovery_round5')
    p.add_argument('--report-dir',default='reports/discovery_round5')
    a=p.parse_args();run(a.source,a.destination,a.report_dir)
