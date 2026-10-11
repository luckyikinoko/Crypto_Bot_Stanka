"""Verify event integrity and historical prefix invariance without outcome analysis."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
from market_data.schema import utc
from market_data.store import read_market
from market_data.source import atomic_bytes
from .engine import Config, detect


def verify(source, root):
    source, root = Path(source), Path(root)
    catalog = json.loads((root/'catalog.json').read_text())
    current = json.loads((source/'catalog.json').read_text())
    if catalog['source_snapshot'] != current['snapshot_id']:
        raise ValueError('Verification requires the original source snapshot')
    results = {}
    for part in catalog['partitions']:
        path = root/part['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != part['file_sha256']:
            raise ValueError('Pattern checksum mismatch')
        f = pd.read_parquet(path)
        if len(f) != part['rows'] or f.event_id.duplicated().any():
            raise ValueError('Duplicate IDs or wrong row count')
        if not f.available_at.is_monotonic_increasing:
            raise ValueError('Unordered events')
        if not ((f.formation_start < f.formation_end) & (f.formation_end <= f.available_at)).all():
            raise ValueError('Invalid event timing')
        if not ((f.formation_start >= utc(catalog['start'])) & (f.available_at <= utc(catalog['end_exclusive']))).all():
            raise ValueError('Event outside source coverage')
        if not (f.status == 'confirmed').all():
            raise ValueError('Unexpected status')
        by_id = f.set_index('event_id')
        for row in f[f.parent_event_id != ''].itertuples():
            parent = by_id.loc[row.parent_event_id]
            if parent.pattern != 'resistance_breakout' or parent.available_at >= row.available_at:
                raise ValueError('Invalid retest parent/timing')
        for value in [*f.metrics, *f.context]:
            json.loads(value, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
        a = read_market(source, part['interval'], catalog['start'], catalog['end_exclusive'], allow_gaps=True)
        prefix = a.iloc[:min(1000,len(a))]
        expected = f[f.available_at <= prefix.available_at.iloc[-1]].reset_index(drop=True)
        pd.testing.assert_frame_equal(detect(prefix,part['interval'],Config(**catalog['config'])),expected)
        results[part['interval']] = {'events':len(f),'prefix_candles':len(prefix),'prefix_events':len(expected),'status':'passed'}
    return {'snapshot_id':catalog['snapshot_id'],'verified_partitions':len(results),'timeframes':results}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default='data/research')
    parser.add_argument('--root',default='data/research_patterns')
    parser.add_argument('--report',default='reports/patterns/verification.json')
    args=parser.parse_args()
    report=verify(args.source,args.root)
    atomic_bytes(Path(args.report),(json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps(report))


if __name__ == '__main__': main()
