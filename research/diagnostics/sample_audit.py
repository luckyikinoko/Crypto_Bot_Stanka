"""Explain sample attrition for frozen round-two rules, without return analysis."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from market_data.schema import utc
from market_data.store import RESERVED_FROM
from market_data.source import atomic_bytes
from research.discovery.engine import scheduled
from research.discovery_round2.engine import CANDIDATES, entry_masks

# Deliberately exclude returns, excursion values and alternate exit outcomes.
LABEL_COLUMNS = ['observation_id','decision_at','entry_at','label_end','status']


def audit(features, labels, start, end):
    if end > RESERVED_FROM:
        raise ValueError('Reserved data blocked')
    if features.observation_id.duplicated().any() or labels.observation_id.duplicated().any():
        raise ValueError('Duplicate observations')
    if (features.available_at >= RESERVED_FROM).any():
        raise ValueError('Reserved features blocked')
    masks = entry_masks(features)
    previous = features.groupby('segment_id', sort=False).rsi.shift()
    events = {CANDIDATES[0]:features.breakout.eq(1),
              CANDIDATES[1]:previous.lt(40) & features.rsi.ge(40)}
    period = features.available_at.ge(start) & features.available_at.lt(end)
    valid = np.isfinite(features.atr) & features.atr.gt(0)
    selected = features.loc[period]
    counts = {
        'decisions':len(selected),
        'segments':int(selected.segment_id.nunique()),
        'unknown_trend':int(selected.trend.eq('unknown').sum()),
        'unknown_volatility':int(selected.volatility.eq('unknown').sum()),
        'candidates':{}
    }
    for c in CANDIDATES:
        steps = {}
        mask = period.copy()
        for name, condition in [
            ('event',events[c]), ('positive_atr',valid),
            ('bullish_trend',features.trend.eq('bullish')),
            ('normal_volatility',features.volatility.eq('normal'))]:
            mask &= condition.fillna(False)
            steps[name] = int(mask.sum())
        if not np.array_equal(mask.to_numpy(dtype=bool), (period & masks[c]).to_numpy(dtype=bool)):
            raise ValueError('Funnel differs from registered rule')
        signals = features.loc[mask,['observation_id','available_at']]
        joined = signals.merge(labels[LABEL_COLUMNS],on='observation_id',
                               how='left',validate='one_to_one',indicator=True)
        if not joined['_merge'].eq('both').all():
            raise ValueError('Missing outcome metadata')
        if not joined.available_at.equals(joined.decision_at):
            raise ValueError('Decision timestamp mismatch')
        complete = joined.status.eq('complete')
        boundary = complete & joined.label_end.gt(end)
        usable = joined[complete & ~boundary]
        nonoverlap = scheduled(usable)
        excluded = joined.loc[~complete,'status'].value_counts().to_dict()
        if len(usable)+int(boundary.sum())+sum(excluded.values()) != len(signals):
            raise ValueError('Attrition does not reconcile')
        counts['candidates'][c] = {
            'funnel':steps,
            'trend_at_raw_event':features.loc[period & events[c].fillna(False),'trend'].value_counts().to_dict(),
            'volatility_after_bullish_event':features.loc[
                period & events[c].fillna(False) & valid & features.trend.eq('bullish'),
                'volatility'].value_counts().to_dict(),
            'incomplete_by_status':excluded,
            'complete_crossing_pool_boundary':int(boundary.sum()),
            'usable':len(usable), 'nonoverlap':len(nonoverlap),
            'overlap_or_cooldown_removed':len(usable)-len(nonoverlap),
            'usable_by_year':{str(y):len(g) for y,g in usable.groupby(usable.decision_at.dt.year)},
            'usable_by_quarter':{str(q):len(g) for q,g in usable.groupby(
                usable.decision_at.dt.tz_localize(None).dt.to_period('Q'))}}
    return counts


def run(source='data/research_discovery_round2', destination='reports/sample_audit'):
    source, destination = Path(source), Path(destination)
    raw = (source/'catalog.json').read_bytes()
    catalog = json.loads(raw)
    payload = dict(catalog); payload.pop('snapshot_id')
    if hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()!=catalog['snapshot_id']:
        raise ValueError('Snapshot hash mismatch')
    frames = {}
    for key,columns in [('features',None),('labels',LABEL_COLUMNS)]:
        meta = catalog['provenance']['files'][key]
        path = source/meta['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:
            raise ValueError('Input checksum mismatch')
        frames[key] = pd.read_parquet(path,columns=columns)
        if len(frames[key])!=meta['rows']:
            raise ValueError('Input row count mismatch')
    results = {name:audit(frames['features'],frames['labels'],start,end)
               for name,start,end in [
                   ('training',utc('2018-01-01'),utc('2024-01-01')),
                   ('reused_recent',utc('2024-01-01'),RESERVED_FROM)]}
    for name,result in results.items():
        for c,detail in result['candidates'].items():
            old = catalog['results'][c][name]
            if detail['usable']!=old['standard']['n'] or detail['nonoverlap']!=old['nonoverlap']['n']:
                raise ValueError('Does not reconcile with frozen discovery report')
    if raw != (source/'catalog.json').read_bytes():
        raise ValueError('Source changed during audit')
    report = {'source_snapshot':catalog['snapshot_id'],
              'audit_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope':'Descriptive sample counts only; no new return tests or parameter selection',
              'results':results}
    atomic_bytes(destination/'results.json',(json.dumps(report,indent=2)+'\n').encode())
    lines = ['# Discovery sample-size audit','',
             'This audit preserves the two registered round-two rules. It counts filter, data-quality and overlap losses without comparing returns under alternative rules. No new hypothesis test is added.','',
             '| Pool / signal | Raw events | ATR valid | Bullish | Normal volatility | Complete in pool | Nonoverlap |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for name,result in results.items():
        for c,d in result['candidates'].items():
            f=d['funnel']
            lines.append(f"| {name} / {c} | {f['event']} | {f['positive_atr']} | {f['bullish_trend']} | {f['normal_volatility']} | {d['usable']} | {d['nonoverlap']} |")
    lines += ['','Counts are sequential and order-dependent: a loss at a filter is not evidence that removing that filter improves trading performance. Nonoverlap uses the registered 72-hour hold plus 60-minute cooldown.','',
              '## Regime availability at events','',
              'Trend counts at raw events separate unavailable warm-up from observed bearish/ranging conditions. Volatility counts apply after the bullish filter.','']
    for name,result in results.items():
        for c,d in result['candidates'].items():
            lines.append(f"- {name} / {c}: trend {d['trend_at_raw_event']}; volatility after bullish {d['volatility_after_bullish_event']}.")
    lines += ['','## Data exclusions','']
    for name,result in results.items():
        lines.append(f"- {name}: {result['decisions']} decisions; {result['segments']} contiguous segments; unknown trend on {result['unknown_trend']} decisions and unknown volatility on {result['unknown_volatility']} (these can overlap).")
        for c,d in result['candidates'].items():
            lines.append(f"  - {c}: incomplete {d['incomplete_by_status']}; complete labels crossing pool boundary {d['complete_crossing_pool_boundary']}; overlap/cooldown removes {d['overlap_or_cooldown_removed']}.")
    lines += ['','## Interpretation and next step','',
              'The sequential counts distinguish restrictive rules, unavailable regime labels, missing execution paths and overlap. A low number of missing execution paths does not imply full historical coverage: indicator warm-up after gaps can also exclude many decisions. Neither existing candidate is promoted. Filling missing candles, counting overlapping signals as independent trades, or relaxing gates would not supply independent evidence.',
              '',
              'Before another outcome screen, preregister a small, simpler family with an explicit economic hypothesis and check feature-only occurrence counts. Sample size is a feasibility check, not proof of an edge. Keep a record of every frequency check and candidate considered, because feature-driven selection is still adaptive. Retain the cumulative test ledger and keep the reserved pool sealed.',
              '',
              '## Reproduce','',
              'Run python -m research.diagnostics.sample_audit. The command checks input hashes, reconciles all usable/nonoverlap counts against the frozen discovery report, and reads only timing/status columns from future labels. results.json includes yearly and quarterly counts.',
              '',f"Source snapshot: {catalog['snapshot_id']}",'']
    atomic_bytes(destination/'SAMPLE_AUDIT.md','\n'.join(lines).encode())
    print(json.dumps(results,indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',default='data/research_discovery_round2')
    p.add_argument('--destination',default='reports/sample_audit')
    a=p.parse_args()
    run(a.source,a.destination)
