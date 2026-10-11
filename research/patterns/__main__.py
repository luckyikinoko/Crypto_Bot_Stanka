"""Build development-only pattern event snapshots: python -m research.patterns."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import numpy as np
import pandas as pd
import pyarrow
from market_data.schema import MINUTES, utc
from market_data.store import read_market, writer_lock, RESERVED_FROM
from market_data.source import atomic_bytes
from research.indicators import Config as IndicatorConfig
from .engine import Config, detect


def build(source, destination, start='2018-01-01', end='2026-04-01', config=None):
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError('Use a separate pattern destination')
    if utc(start) >= utc(end):
        raise ValueError('start must precede end')
    if utc(end) > RESERVED_FROM or utc(start) >= RESERVED_FROM:
        raise PermissionError('Reserved evaluation pool remains blocked')
    cfg = config or Config()
    before = (source/'catalog.json').read_bytes()
    source_catalog = json.loads(before)
    code_paths = ['research/patterns/engine.py', 'research/indicators/engine.py', 'market_data/schema.py']
    repo = Path(__file__).resolve().parents[2]
    hashes = {p: hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in code_paths}
    parts, summary = [], {}
    written = reused = 0
    with writer_lock(destination):
        for interval in MINUTES:
            a = read_market(source, interval, start, end, allow_gaps=True)
            events = detect(a, interval, cfg)
            payload = events.to_parquet(index=False, compression='zstd')
            digest = hashlib.sha256(payload).hexdigest()
            relative = interval+'/'+digest+'.parquet'
            path = destination/relative
            if path.exists():
                if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    raise ValueError('Corrupt pattern partition')
                reused += 1
            else:
                atomic_bytes(path, payload)
                written += 1
            pd.testing.assert_frame_equal(events, pd.read_parquet(path))
            parts.append({'interval': interval, 'path': relative, 'file_sha256': digest, 'rows': len(events)})
            summary[interval] = {'candles': len(a), 'events': len(events),
                                 'by_pattern': {str(k): int(v) for k,v in events.pattern.value_counts().items()},
                                 'by_year': {str(k): int(v) for k,v in events.available_at.dt.year.value_counts().sort_index().items()}}
            print(interval, summary[interval]['by_pattern'], flush=True)
        if (source/'catalog.json').read_bytes() != before:
            raise RuntimeError('Source changed during build')
        catalog = {'schema_version': 1, 'source_snapshot': source_catalog['snapshot_id'],
                   'start': str(utc(start)), 'end_exclusive': str(utc(end)), 'reserved_from': str(RESERVED_FROM),
                   'config': asdict(cfg), 'indicator_config': asdict(IndicatorConfig()), 'code_sha256': hashes,
                   'runtime': {'python': platform.python_version(), 'pandas': pd.__version__,
                               'numpy': np.__version__, 'pyarrow': pyarrow.__version__},
                   'partitions': parts, 'summary': summary}
        catalog['snapshot_id'] = hashlib.sha256(json.dumps(catalog, sort_keys=True).encode()).hexdigest()
        payload = (json.dumps(catalog, indent=2)+'\n').encode()
        atomic_bytes(destination/'manifests'/(catalog['snapshot_id']+'.json'), payload)
        atomic_bytes(destination/'catalog.json', payload)
    return catalog, {'written': written, 'reused': reused}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='data/research')
    parser.add_argument('--destination', default='data/research_patterns')
    parser.add_argument('--start', default='2018-01-01')
    parser.add_argument('--end', default='2026-04-01')
    parser.add_argument('--config')
    parser.add_argument('--report', default='reports/patterns/quality.json')
    args = parser.parse_args()
    cfg = Config(**json.loads(Path(args.config).read_text())) if args.config else Config()
    catalog, counts = build(args.source, args.destination, args.start, args.end, cfg)
    atomic_bytes(Path(args.report), (json.dumps({**catalog, 'publication': counts}, indent=2)+'\n').encode())
    print(json.dumps({'snapshot_id': catalog['snapshot_id'], **counts}))


if __name__ == '__main__':
    main()
