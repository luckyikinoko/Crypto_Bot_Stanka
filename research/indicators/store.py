"""Checksum-verified feature access; align using market_data.schema.align_available."""
import hashlib
import json
from pathlib import Path
import pandas as pd
from market_data.schema import utc, MINUTES
from market_data.store import RESERVED_FROM


def read_features(root, interval, start, end):
    start, end = utc(start), utc(end)
    if start >= end or interval not in MINUTES:
        raise ValueError('Invalid range or interval')
    if start >= RESERVED_FROM or end > RESERVED_FROM:
        raise PermissionError('Reserved evaluation pool remains blocked')
    root = Path(root)
    catalog = json.loads((root/'catalog.json').read_text())
    if start < utc(catalog['start']) or end > utc(catalog['end_exclusive']):
        raise ValueError('Outside feature snapshot coverage')
    frames = []
    for part in catalog['partitions']:
        month = utc(part['month']+'-01')
        if part['interval'] != interval or month >= end or month+pd.offsets.MonthBegin(1) <= start:
            continue
        path = root/part['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != part['file_sha256']:
            raise ValueError('Feature partition checksum mismatch')
        a = pd.read_parquet(path)
        frames.append(a[(a.open_time >= start) & (a.open_time < end)])
    if not frames:
        raise ValueError('No feature partitions in requested range')
    return pd.concat(frames, ignore_index=True)
