"""Evaluate the single registered round-six outcome on development data only."""
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
from research.statistics.outcomes import label_paths, SCENARIOS
from research.statistics.metrics import block_compare, adjust_by
from research.statistics.__main__ import save_frame
from research.discovery.__main__ import summarize
from research.discovery.engine import evaluate_gates
from research.discovery_round3.outcomes import LABEL_COLUMNS, select_pool
CANDIDATE = 'confirmed_double_bottom_1h'


def eligibility_mask(features):
    t=features.available_at
    if str(t.dt.tz)!='UTC' or t.isna().any() or t.duplicated().any() or not t.is_monotonic_increasing or (t>=RESERVED_FROM).any():
        raise ValueError('Sorted unique development UTC decisions required')
    if features.observation_id.isna().any() or features.observation_id.duplicated().any():
        raise ValueError('Unique feature identities required')
    expected=np.isfinite(features.prior_atr)&features.prior_atr.gt(0)&features.bars_since_gap.ge(16)
    if not features.eligible.equals(expected) or (features.signal & ~expected).any():
        raise ValueError('Eligible baseline mismatch')
    return expected


def verify_events(features, events):
    eligibility_mask(features)
    if events.event_id.duplicated().any() or events.available_at.duplicated().any():
        raise ValueError('Duplicate pattern events')
    if not events.available_at.isin(features.available_at).all():
        raise ValueError('Event outside feature coverage')
    if not features.signal.equals(features.available_at.isin(events.available_at)):
        raise ValueError('Signals differ from frozen events')
    if not ((events.formation_start<events.formation_end)&(events.formation_end<=events.available_at)).all():
        raise ValueError('Pattern timing mismatch')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def join_observations(features, labels):
    entries=features.loc[eligibility_mask(features),['observation_id','available_at']].copy()
    entries['signal']=features.signal.loc[entries.index]
    if labels.observation_id.duplicated().any() or set(labels.observation_id)!=set(entries.observation_id):
        raise ValueError('Eligible feature/label identities differ')
    joined=entries.merge(labels[LABEL_COLUMNS],on='observation_id',validate='one_to_one')
    if not joined.available_at.equals(joined.decision_at):
        raise ValueError('Decision timing mismatch')
    if not joined.entry_at.eq(joined.decision_at+pd.Timedelta(minutes=5)).all():
        raise ValueError('Entry timing mismatch')
    if not joined.label_end.eq(joined.entry_at+pd.Timedelta(hours=24)).all():
        raise ValueError('Exit timing mismatch')
    complete=joined[joined.status.eq('complete')]
    if (complete.label_end>RESERVED_FROM).any():
        raise ValueError('Reserved outcome blocked')
    for name,cost in SCENARIOS.items():
        if not np.allclose(complete['net_'+name],cost.net(complete.entry_raw,complete.exit_raw),rtol=1e-12,atol=1e-12):
            raise ValueError('Return/cost mismatch')
    return joined


def run(source='data/research_discovery_round6',market='data/research_repaired_v1',
        destination='data/research_round6_outcomes',report_dir='reports/discovery_round6'):
    source,market,destination,report_dir=map(Path,(source,market,destination,report_dir))
    if destination.resolve() in (source.resolve(),market.resolve()):
        raise ValueError('Separate destination required')
    if (destination/'catalog.json').exists() or (report_dir/'outcomes.json').exists():
        raise ValueError('Preserve prior outcomes; use fresh destinations')
    repo=Path(__file__).resolve().parents[2]
    reg_path=Path(__file__).with_name('REGISTRY.json');reg_bytes=reg_path.read_bytes();reg=json.loads(reg_bytes)
    raw=(source/'catalog.json').read_bytes();feas=json.loads(raw)
    if raw!=(repo/'reports/discovery_round6/feasibility.json').read_bytes():
        raise ValueError('Feature source differs from reviewed feasibility')
    if not feas['feasibility']['passed'] or feas['registry_sha256']!=digest(reg_bytes):
        raise ValueError('Failed feasibility or altered registry')
    if reg['candidate']!=CANDIDATE or reg['execution']!={'hold_hours':24,'delay_minutes':5,'cooldown_minutes':60,'secondary_exit':None}:
        raise ValueError('Only registered execution supported')
    if reg['costs']!={k:vars(v) for k,v in SCENARIOS.items()}:
        raise ValueError('Registered costs changed')
    market_bytes=(market/'catalog.json').read_bytes()
    if json.loads(market_bytes)['snapshot_id']!=reg['market_snapshot'] or feas['market_snapshot']!=reg['market_snapshot']:
        raise ValueError('Market snapshot mismatch')
    prior_path=repo/reg['prior_report'];prior_bytes=prior_path.read_bytes();prior=json.loads(prior_bytes)
    if digest(prior_bytes)!=reg['prior_report_sha256'] or prior['snapshot_id']!=reg['prior_snapshot'] or len(prior['test_ledger'])!=36:
        raise ValueError('Prior ledger mismatch')
    for name,sha in feas['code_sha256'].items():
        if digest((repo/name).read_bytes())!=sha:
            raise ValueError('Feature implementation changed')
    meta=feas['files']['features'];path=source/meta['path']
    if digest(path.read_bytes())!=meta['sha256']:
        raise ValueError('Feature checksum mismatch')
    features=pd.read_parquet(path)
    if len(features)!=meta['rows']:
        raise ValueError('Feature count mismatch')
    event_meta=feas['files']['events'];event_path=source/event_meta['path']
    if digest(event_path.read_bytes())!=event_meta['sha256']:
        raise ValueError('Event checksum mismatch')
    events=pd.read_parquet(event_path)
    if len(events)!=event_meta['rows']:raise ValueError('Event count mismatch')
    verify_events(features,events)
    with writer_lock(destination):
        execution=read_market(market,'5m','2018-01-01',RESERVED_FROM,allow_gaps=True)
        obs=features.loc[eligibility_mask(features),['observation_id','available_at']].assign(atr=np.nan)
        labels=label_paths(obs,execution,horizons=(24,),entry_delay_minutes=5)[LABEL_COLUMNS]
        labels['status']=labels.status.astype('string')
        joined=join_observations(features,labels)
        results={};quality={};comparisons={};selected=[]
        for period,(start,end) in reg['periods'].items():
            start,end=utc(start),utc(end)
            base,quality[period+'/unconditional']=select_pool(joined,start,end)
            group,quality[period+'/'+CANDIDATE]=select_pool(joined[joined.signal],start,end)
            results[period]={'candidate':summarize(group),'unconditional':summarize(base)}
            selected.append(group.assign(pool=period))
            if period=='training':
                # Require the registered feature-baseline origin to survive path exclusions.
                origin=str(base.decision_at.min().floor('D')) if len(base) else None
                if origin!=feas['counts'][period]['block_origin']:
                    raise ValueError('Path exclusions changed registered block origin')
                b=reg['bootstrap']
                comparisons={str(d):block_compare(group,base,d,b['draws'],b['seed']) for d in (28,7)}
        ledger=[{'id':x['id'],'p':x['p']} for x in prior['test_ledger']]
        ledger.append({'id':'M5R6/'+CANDIDATE,'p':comparisons['28'].get('p_one_sided',1.)})
        for row,q in zip(ledger,adjust_by([x['p'] for x in ledger])):
            row['by_q']=q
        gates=evaluate_gates(results['training']['candidate'],results['reused_recent']['candidate'],comparisons['28'],ledger[-1]['by_q'],{'gates':reg['outcome_gates']})
        files={'labels':save_frame(destination,'labels',labels),
               'candidate_observations':save_frame(destination,'candidate_observations',pd.concat(selected,ignore_index=True))}
        protected={reg_path:reg_bytes,source/'catalog.json':raw,market/'catalog.json':market_bytes,prior_path:prior_bytes}
        if any(p.read_bytes()!=value for p,value in protected.items()):
            raise ValueError('Inputs changed')
        code=['research/discovery_round6/outcomes.py','research/patterns/double_bottom.py',
              'research/discovery_round3/outcomes.py','research/statistics/outcomes.py','research/statistics/metrics.py',
              'research/discovery/__main__.py','research/discovery/engine.py','market_data/store.py']
        report={'candidate':CANDIDATE,'market_snapshot':reg['market_snapshot'],'feature_snapshot':feas['snapshot_id'],
            'registry':reg,'provenance':{'registry_sha256':digest(reg_bytes),'feature_report_sha256':digest(raw),
                'prior_report_sha256':digest(prior_bytes),'files':files,
                'code_sha256':{p:digest((repo/p).read_bytes()) for p in code},
                'runtime':{'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,'pyarrow':pyarrow.__version__}},
            'costs':reg['costs'],'results':results,'quality':quality,'comparisons':comparisons,'test_ledger':ledger,
            'gates':gates,'buy_and_hold_context':prior['buy_and_hold_context'],'selected_strategy':None,
            'decision':'requires_separate_validation' if gates['passed'] else 'candidate_rejected',
            'limits':'Adaptive exploratory research; recent data reused. Event means are not portfolio returns. Missing paths excluded. Reserved data remains sealed. No strategy or trading activated.'}
        report['snapshot_id']=digest(json.dumps(report,sort_keys=True,allow_nan=False).encode())
        encoded=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode()
        atomic_bytes(destination/'manifests'/(report['snapshot_id']+'.json'),encoded)
        atomic_bytes(destination/'catalog.json',encoded);atomic_bytes(report_dir/'outcomes.json',encoded)
        lines=['# Round 6 — registered outcome screen','',report['limits'],'',
            'Entry: confirmed 1h double bottom with the frozen causal pivot and neckline definition. Entry delayed five minutes; fixed 24h exit; no alternative horizons or parameters tested. Standard costs are primary; BNB is conditional and stress costs are retained.','',
            '| Pool | Complete signals | Standard mean net | Stress mean net | Nonoverlap n | Nonoverlap mean net |','|---|---:|---:|---:|---:|---:|']
        for period,r in results.items():
            c=r['candidate'];lines.append(f"| {period} | {c['standard']['n']} | {c['standard'].get('mean',float('nan')):.4%} | {c['stress'].get('mean',float('nan')):.4%} | {c['nonoverlap']['n']} | {c['nonoverlap'].get('mean',float('nan')):.4%} |")
        inf=comparisons['28']
        lines+=['',f"Decision: **{report['decision']}**.",'',f"Failed criteria: {', '.join(gates['failed']) or 'none'}.",'',
            f"Training standard net mean 95% block interval: {inf.get('net_ci95')}. Training excess-over-baseline 95% interval: {inf.get('excess_ci95')}. These JSON values are return fractions (multiply by 100 for percent).",
            f"Primary p-value: {ledger[-1]['p']}; BY-adjusted q across 37 tests: {ledger[-1]['by_q']}.",'',
            'The prior 36 revised-ledger IDs and p-values are preserved. This adds one primary hypothesis test. Seven-day blocks are a sensitivity check, not an alternate selection test. Earlier legacy experiments remain outside this ledger. No claim of independent confirmation follows from multiple-testing correction.','',
            'Full-path exclusions and boundary purges, annual performance, MFE/MAE summaries, cost scenarios and the unconditional matched baseline are in outcomes.json. Buy-and-hold is an exposure context, not directly comparable with signal-average returns. Scheduled closed-trade drawdown omits intratrade portfolio risk.','',
            'Stop for review. A failed screen does not authorize parameter tuning or use of the reserved pool. A pass only proposes separate portfolio and walk-forward validation.','',
            'Reproduce with `python -m research.discovery_round6.outcomes --destination <fresh-data-directory> --report-dir <fresh-report-directory>`.','']
        atomic_bytes(report_dir/'OUTCOMES.md','\n'.join(lines).encode())
        print(json.dumps({'snapshot_id':report['snapshot_id'],'decision':report['decision'],'gates':gates,'quality':quality}),flush=True)
        return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',default='data/research_discovery_round6')
    p.add_argument('--market',default='data/research_repaired_v1')
    p.add_argument('--destination',default='data/research_round6_outcomes')
    p.add_argument('--report-dir',default='reports/discovery_round6')
    a=p.parse_args();run(a.source,a.market,a.destination,a.report_dir)
