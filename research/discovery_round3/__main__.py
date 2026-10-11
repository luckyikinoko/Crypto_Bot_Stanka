"""Count frozen breakout signals using only causal feature columns."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
from market_data.schema import utc
from market_data.store import RESERVED_FROM
from market_data.source import atomic_bytes
from research.discovery.engine import scheduled

FEATURE_COLUMNS = ['observation_id','available_at','breakout']


def signal_mask(features):
    t = features.available_at
    if t.dt.tz is None or str(t.dt.tz) != 'UTC':
        raise ValueError('UTC features required')
    if t.isna().any() or not t.is_monotonic_increasing or t.duplicated().any():
        raise ValueError('Sorted unique timestamps required')
    if (t >= RESERVED_FROM).any():
        raise ValueError('Reserved data blocked')
    if features.observation_id.isna().any() or features.observation_id.duplicated().any():
        raise ValueError('Unique observation IDs required')
    return features.breakout.eq(1).fillna(False).astype(bool)


def count_pool(features, start, end):
    if start >= end or end > RESERVED_FROM:
        raise ValueError('Invalid or reserved pool')
    mask = signal_mask(features)
    in_pool = features.available_at.ge(start) & features.available_at.lt(end)
    decisions = features.loc[mask & in_pool,['observation_id','available_at']].rename(
        columns={'available_at':'decision_at'})
    decisions['entry_at'] = decisions.decision_at + pd.Timedelta(minutes=5)
    decisions['label_end'] = decisions.entry_at + pd.Timedelta(hours=72)
    kept = decisions[decisions.label_end <= end]
    schedule = scheduled(kept,cooldown_minutes=60)
    origin = start.floor('D')
    blocks = ((kept.decision_at-origin).dt.total_seconds()//(28*86400)).astype(int)
    return {
        'raw_events':len(decisions),
        'boundary_purged':len(decisions)-len(kept),
        'timing_eligible':len(kept),
        'scheduled_nonoverlap':len(schedule),
        'active_28day_blocks':int(blocks.nunique()),
        'block_origin':str(origin),
        'counts_by_year':{str(y):len(g) for y,g in kept.groupby(kept.decision_at.dt.year)},
        'execution_paths_checked':False
    }


def feasibility(results, gates):
    train, recent = results['training'], results['reused_recent']
    checks = {
        'training_observations':train['timing_eligible'] >= gates['training_observations'],
        'training_nonoverlap':train['scheduled_nonoverlap'] >= gates['training_nonoverlap'],
        'training_active_28day_blocks':train['active_28day_blocks'] >= gates['training_active_28day_blocks'],
        'recent_observations':recent['timing_eligible'] >= gates['recent_observations']}
    return {'passed':all(checks.values()),'checks':checks}


def run(source='data/research_discovery_round2', destination='reports/discovery_round3'):
    source, destination = Path(source), Path(destination)
    registry_path = Path(__file__).with_name('REGISTRY.json')
    registry_bytes = registry_path.read_bytes()
    registry = json.loads(registry_bytes)
    if registry['candidate']['id'] != 'unfiltered_breakout_4h' or registry['future_execution'] != {
        'fixed_hold_hours':72,'entry_delay_minutes':5,'cooldown_minutes':60,'secondary_exit':None}:
        raise ValueError('Only registered round-three specification supported')
    catalog_bytes = (source/'catalog.json').read_bytes()
    catalog = json.loads(catalog_bytes)
    payload = dict(catalog);payload.pop('snapshot_id')
    if hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()!=catalog['snapshot_id']:
        raise ValueError('Invalid source manifest')
    meta = catalog['provenance']['files']['features']
    feature_path = source/meta['path']
    if hashlib.sha256(feature_path.read_bytes()).hexdigest()!=meta['sha256']:
        raise ValueError('Feature checksum mismatch')
    features = pd.read_parquet(feature_path,columns=FEATURE_COLUMNS)
    if len(features)!=meta['rows']:
        raise ValueError('Feature row count mismatch')
    results = {name:count_pool(features,utc(start),utc(end))
               for name,(start,end) in registry['periods'].items()}
    outcome = feasibility(results,registry['feasibility_gates'])
    report = {
        'source_snapshot':catalog['snapshot_id'],'feature_sha256':meta['sha256'],
        'registry_sha256':hashlib.sha256(registry_bytes).hexdigest(),
        'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'columns_read':FEATURE_COLUMNS,'results':results,'feasibility':outcome,
        'new_return_tests':0,'prior_return_tests':33,'selected_strategy':None,
        'decision':'propose_outcome_screen' if outcome['passed'] else 'insufficient_feature_sample'}
    if catalog_bytes!=(source/'catalog.json').read_bytes() or registry_bytes!=registry_path.read_bytes():
        raise ValueError('Inputs changed')
    atomic_bytes(destination/'feasibility.json',(json.dumps(report,indent=2)+'\n').encode())
    lines = ['# Round 3 — standalone breakout feasibility','',
             'Hypothesis: a completed 4h close above the preceding 20 highs may predict continued buying over a 72-hour hold. Existing causal breakout definitions, gap resets and warm-up are reused. There are no EMA, ADX, RSI or volatility entry filters.','',
             'Registered before this feasibility run in commit 4571eae. Prior candidate returns and raw breakout frequency were already known; this is explicitly adaptive research.','',
             '| Pool | Raw signals | Boundary purged | Timing eligible | Nonoverlap | Active 28-day blocks |',
             '|---|---:|---:|---:|---:|---:|']
    for name,r in results.items():
        lines.append(f"| {name} | {r['raw_events']} | {r['boundary_purged']} | {r['timing_eligible']} | {r['scheduled_nonoverlap']} | {r['active_28day_blocks']} |")
    lines += ['',
              'Feature-count gates: at least 100 training observations, 50 scheduled nonoverlapping observations, 30 active 28-day blocks, and 30 reused-recent observations.',
              '',f"**Feature feasibility: {'PASS' if outcome['passed'] else 'FAIL'}.**",
              '',
              'Counts use a five-minute delayed entry and a planned 72-hour hold; labels crossing a pool boundary are purged. A greedy single-position schedule includes a 60-minute cooldown. These counts do not verify future execution-path completeness. Actual eligible counts may be lower, and the schedule may change when missing paths are removed.',
              '',
              'Blocks start at each pool start. A later outcome screen must use its actual complete unconditional baseline origin and recount active blocks. Passing frequency thresholds is not a power calculation, profitability evidence or a strategy-selection decision.',
              '',
              'Only observation ID, decision availability time and breakout feature columns were read from Parquet. The source manifest was used for integrity metadata; no label file was opened and no returns, win rates, confidence intervals or p-values were calculated.',
              '',
              'Training: 2018–2023. Reused recent: 2024–2026 Q1, not fresh validation. Data from 2026-04-01 onward remains blocked. Existing 33-test ledger and earlier rules/reports remain unchanged.',
              '',
              '## Review checkpoint','',
              'If feasibility passes, the next step is a separately reviewed net-outcome screen under the registered standard, conditional-BNB and stress costs. Retain the previous statistical gates, compare with unconditional 4h decisions, and append the candidate as test 34 in the exploratory BY ledger. No alternate exit or parameter grid is registered. No strategy, paper trading or live trading is activated.',
              '',
              'Reproduce: python -m research.discovery_round3',
              '',f"Source snapshot: {catalog['snapshot_id']}",'']
    atomic_bytes(destination/'FEASIBILITY.md','\n'.join(lines).encode())
    print(json.dumps(report,indent=2))
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default='data/research_discovery_round2')
    parser.add_argument('--destination',default='reports/discovery_round3')
    args=parser.parse_args()
    run(args.source,args.destination)
