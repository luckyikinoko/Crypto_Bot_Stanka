"""Evaluate only the frozen second discovery family."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import numpy as np
import pandas as pd
from market_data.schema import utc
from market_data.store import read_market, writer_lock, RESERVED_FROM
from market_data.source import atomic_bytes
from research.regimes import classify
from research.statistics.outcomes import label_paths, SCENARIOS
from research.statistics.metrics import describe, block_compare, adjust_by
from research.statistics.__main__ import save_frame
from research.discovery.engine import evaluate_gates
from research.discovery.__main__ import summarize
from .engine import CANDIDATES, entry_masks


def pool(frame, start, end):
    return frame[(frame.decision_at >= start) & (frame.label_end <= end)]


def run(market_root='data/research', out='data/research_discovery_round2',
        report_dir='reports/discovery_round2', prior_report=None):
    market_root, out, report_dir = map(Path, (market_root, out, report_dir))
    if out.resolve() == market_root.resolve():
        raise ValueError('Separate destination required')
    repo = Path(__file__).resolve().parents[2]
    registry_path = Path(__file__).with_name('REGISTRY.json')
    registry_bytes = registry_path.read_bytes()
    registry = json.loads(registry_bytes)
    if registry['primary_exit'] != {'fixed_hold_hours':72, 'entry_delay_minutes':5}:
        raise ValueError('Only registered 72h implementation supported')
    source_bytes = (market_root/'catalog.json').read_bytes()
    source = json.loads(source_bytes)
    prior_path = Path(prior_report) if prior_report is not None else repo/'reports/discovery/results.json'
    prior_bytes = prior_path.read_bytes()
    prior = json.loads(prior_bytes)
    if prior_report is not None and prior['provenance']['market_snapshot'] != source['snapshot_id']:
        raise ValueError('Prior report/market snapshot mismatch')
    if len(prior['test_ledger']) != 31:
        raise ValueError('Incomplete prior test family')
    with writer_lock(out):
        candles = read_market(market_root, '4h', '2018-01-01', RESERVED_FROM, allow_gaps=True)
        features = classify(candles, '4h')
        features = features[features.available_at < RESERVED_FROM].reset_index(drop=True)
        features['observation_id'] = features.available_at.astype(str)
        entries = features[['observation_id','available_at']].join(entry_masks(features))
        execution = read_market(market_root, '5m', '2018-01-01', RESERVED_FROM, allow_gaps=True)
        labels = label_paths(features[['observation_id','available_at','atr']], execution,
                             horizons=(72,), stop_atr=2., take_atr=3., entry_delay_minutes=5)
        for column in ('stop_hit','take_hit','ambiguous_same_bar'):
            labels[column] = labels[column].astype('boolean')
        for column in ('status','barrier_status','barrier_exit'):
            labels[column] = labels[column].astype('string')
        # Primary fixed-hold eligibility does not depend on a hypothetical stop.
        joined = labels[labels.status.eq('complete')].merge(
            entries.drop(columns='available_at'), on='observation_id', validate='one_to_one')
        periods = {'training':(utc('2018-01-01'), utc('2024-01-01')),
                   'reused_recent':(utc('2024-01-01'), RESERVED_FROM)}
        results = {c:{} for c in ('unconditional', *CANDIDATES)}
        comparisons, quality, selected = {}, {}, []
        for period, (start,end) in periods.items():
            baseline = pool(joined, start, end)
            for c in results:
                group = baseline if c == 'unconditional' else baseline[baseline[c]]
                results[c][period] = summarize(group)
                secondary = group[group.barrier_status.eq('complete')]
                results[c][period]['secondary_barrier_standard'] = describe(secondary, 'barrier_net_standard')
                decisions = entries[(entries.available_at >= start) & (entries.available_at < end)]
                count = len(decisions) if c == 'unconditional' else int(decisions[c].sum())
                quality[c+'/'+period] = {'signal_decisions':count, 'complete_primary_labels':len(group),
                                         'excluded_or_boundary_purged':count-len(group)}
                if c in CANDIDATES:
                    selected.append(group.assign(candidate=c,pool=period))
                    if period == 'training':
                        comparisons[c] = {str(days):block_compare(group, baseline, days,
                            registry['bootstrap']['draws'], registry['bootstrap']['seed']) for days in (28,7)}
        ledger = [{'id':t['id'],'p':t['p']} for t in prior['test_ledger']]
        ledger += [{'id':'M5R2/'+c,'p':comparisons[c]['28'].get('p_one_sided',1.)} for c in CANDIDATES]
        for test,q in zip(ledger,adjust_by([t['p'] for t in ledger])):
            test['by_q'] = q
        gates = {c:evaluate_gates(results[c]['training'],results[c]['reused_recent'],
                 comparisons[c]['28'],ledger[31+i]['by_q'],registry) for i,c in enumerate(CANDIDATES)}
        files = {name:save_frame(out,name,f) for name,f in {
            'features':features,'entries':entries,'labels':labels,
            'candidate_observations':pd.concat(selected,ignore_index=True)}.items()}
        if source_bytes != (market_root/'catalog.json').read_bytes():
            raise RuntimeError('Market snapshot changed')
        if registry_bytes != registry_path.read_bytes() or prior_bytes != prior_path.read_bytes():
            raise RuntimeError('Protocol or prior ledger changed')
        paths = [*repo.glob('market_data/*.py'), *repo.glob('research/indicators/*.py'),
                 *repo.glob('research/regimes/*.py'), *repo.glob('research/statistics/*.py'),
                 *repo.glob('research/discovery/*.py'), *repo.glob('research/discovery_round2/*.py')]
        provenance = {'market_snapshot':source['snapshot_id'],
            'registry_sha256':hashlib.sha256(registry_bytes).hexdigest(),
            'prior_ledger_sha256':hashlib.sha256(prior_bytes).hexdigest(),
            'code_sha256':{str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)},
            'runtime':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__},
            'files':files}
        eligible = [c for c in CANDIDATES if gates[c]['passed']]
        report = {'provenance':provenance,'registry':registry,'quality':quality,
            'label_status_counts':labels.status.value_counts().to_dict(),
            'costs':{k:vars(v) for k,v in SCENARIOS.items()},
            'results':results,'comparisons':comparisons,'test_ledger':ledger,'gates':gates,
            'buy_and_hold_context':prior['buy_and_hold_context'],
            'eligible_for_later_validation':eligible,'selected_strategy':None,
            'decision':'no_candidate_passes' if not eligible else 'candidates_require_separate_validation'}
        report['snapshot_id'] = hashlib.sha256(json.dumps(report,sort_keys=True,allow_nan=False).encode()).hexdigest()
        payload = (json.dumps(report,indent=2,allow_nan=False)+'\n').encode()
        atomic_bytes(out/'manifests'/(report['snapshot_id']+'.json'),payload)
        atomic_bytes(out/'catalog.json',payload)
        atomic_bytes(report_dir/'results.json',payload)
        print(json.dumps({'snapshot_id':report['snapshot_id'],'gates':gates}),flush=True)
        return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--market',default='data/research')
    p.add_argument('--destination',default='data/research_discovery_round2')
    p.add_argument('--report-dir',default='reports/discovery_round2')
    a = p.parse_args()
    run(a.market,a.destination,a.report_dir)
