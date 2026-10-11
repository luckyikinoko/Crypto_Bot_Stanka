"""Read confirmed events by their availability time, with file integrity checks."""
import hashlib
import json
from pathlib import Path
import pandas as pd
from market_data.schema import utc, MINUTES
from market_data.store import RESERVED_FROM


def read_events(root, interval, start, end):
    start, end = utc(start), utc(end)
    if start >= end or interval not in MINUTES:
        raise ValueError('Invalid interval or range')
    if start >= RESERVED_FROM or end > RESERVED_FROM:
        raise PermissionError('Reserved evaluation pool remains blocked')
    root = Path(root)
    catalog = json.loads((root/'catalog.json').read_text())
    if start < utc(catalog['start']) or end > utc(catalog['end_exclusive']):
        raise ValueError('Outside pattern snapshot coverage')
    part = next(p for p in catalog['partitions'] if p['interval'] == interval)
    path = root/part['path']
    if hashlib.sha256(path.read_bytes()).hexdigest() != part['file_sha256']:
        raise ValueError('Pattern file checksum mismatch')
    events = pd.read_parquet(path)
    # Half-open availability interval, unlike candle readers' open-time filters.
    return events[(events.available_at >= start) & (events.available_at < end)].reset_index(drop=True)
