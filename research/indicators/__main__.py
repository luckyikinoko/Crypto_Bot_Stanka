"""Build reproducible development-only feature snapshots."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import pandas as pd
import numpy as np
import pyarrow
from market_data.schema import MINUTES, utc
from market_data.store import read_market, writer_lock, frame_hash, RESERVED_FROM
from market_data.source import atomic_bytes
from .engine import Config, calculate


def build(source, destination, start='2018-01-01', end='2026-04-01', config=None):
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError('Feature destination must differ from market database')
    if utc(start) >= utc(end):
        raise ValueError('start must precede end')
    if utc(end) > RESERVED_FROM or utc(start) >= RESERVED_FROM:
        raise PermissionError('Reserved evaluation data remains blocked')
    cfg = config or Config()
    source_bytes = (source/'catalog.json').read_bytes()
    catalog = json.loads(source_bytes)
    code_hash = hashlib.sha256(Path(__file__).with_name('engine.py').read_bytes()).hexdigest()
    parts, summary = [], {}
    written = reused = 0
    with writer_lock(destination):
        for interval in MINUTES:
            candles = read_market(source, interval, start, end, allow_gaps=True)
            features = calculate(candles, interval, cfg)
            columns = [c for c in features if c not in ('open_time', 'available_at', 'segment_id', 'bars_since_gap')]
            summary[interval] = {'rows': len(features), 'segments': int(features.segment_id.nunique()),
                                 'non_null_counts': {c: int(features[c].notna().sum()) for c in columns}}
            for month, part in features.groupby(features.open_time.dt.strftime('%Y-%m')):
                part = part.reset_index(drop=True)
                digest = frame_hash(part)
                relative = Path(interval)/(month+'-'+digest[:20]+'.parquet')
                path = destination/relative
                if path.exists():
                    if frame_hash(pd.read_parquet(path)) != digest:
                        raise ValueError('Corrupt feature partition: '+str(path))
                    reused += 1
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = path.with_suffix('.tmp')
                    try:
                        part.to_parquet(tmp, index=False, compression='zstd')
                        pd.testing.assert_frame_equal(part, pd.read_parquet(tmp))
                        tmp.replace(path)
                    finally:
                        tmp.unlink(missing_ok=True)
                    written += 1
                parts.append({'interval': interval, 'month': month, 'path': str(relative),
                              'rows': len(part), 'logical_sha256': digest,
                              'file_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        if (source/'catalog.json').read_bytes() != source_bytes:
            raise RuntimeError('Source snapshot changed during build; retry')
        result = {'schema_version': 1, 'source_snapshot': catalog['snapshot_id'],
                  'engine_sha256': code_hash, 'config': asdict(cfg), 'start': str(utc(start)),
                  'end_exclusive': str(utc(end)), 'reserved_from': str(RESERVED_FROM),
                  'runtime': {'python': platform.python_version(), 'pandas': pd.__version__,
                              'numpy': np.__version__, 'pyarrow': pyarrow.__version__},
                  'summary': summary, 'partitions': parts}
        result['snapshot_id'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
        payload = (json.dumps(result, indent=2, allow_nan=False)+'\n').encode()
        atomic_bytes(destination/'manifests'/(result['snapshot_id']+'.json'), payload)
        atomic_bytes(destination/'catalog.json', payload)
    return result, {'written': written, 'reused': reused}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='data/research')
    parser.add_argument('--destination', default='data/research_features')
    parser.add_argument('--start', default='2018-01-01')
    parser.add_argument('--end', default='2026-04-01')
    parser.add_argument('--config', help='JSON object overriding Config defaults')
    parser.add_argument('--report', default='reports/indicators/quality.json')
    args = parser.parse_args()
    overrides = json.loads(Path(args.config).read_text()) if args.config else {}
    if 'ema_periods' in overrides:
        overrides['ema_periods'] = tuple(overrides['ema_periods'])
    catalog, counts = build(args.source, args.destination, args.start, args.end, Config(**overrides))
    report = {k: v for k, v in catalog.items() if k != 'partitions'}
    report['partitions'] = len(catalog['partitions'])
    report['publication'] = counts
    atomic_bytes(Path(args.report), (json.dumps(report, indent=2)+'\n').encode())
    print(json.dumps({'snapshot_id': catalog['snapshot_id'], **counts}))


if __name__ == '__main__':
    main()
