"""Protected access with independent feature and label interfaces."""
import hashlib
import json
from pathlib import Path
import pandas as pd
from market_data.schema import utc
from market_data.store import RESERVED_FROM


def read(root,start,end,hours=None):
    """hours=None returns causal features; hours specified returns outcome labels.

    Label reads require the full label horizon to end by requested end, so a
    training slice cannot silently import outcomes from the next chronological pool.
    """
    start,end=utc(start),utc(end)
    if start>=end:raise ValueError('Invalid range')
    if start>=RESERVED_FROM or end>RESERVED_FROM:raise PermissionError('Reserved evaluation pool blocked')
    root=Path(root);catalog=json.loads((root/'catalog.json').read_text())
    if start<utc(catalog['start']) or end>utc(catalog['end_exclusive']):raise ValueError('Outside snapshot range')
    meta=catalog['features'] if hours is None else catalog['labels'][str(hours)]
    path=root/meta['path']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('Research file checksum mismatch')
    f=pd.read_parquet(path)
    time=f.available_at if hours is None else f.decision_at
    mask=(time>=start)&(time<end)
    if hours is not None:mask &= f.label_end<=end
    return f[mask].reset_index(drop=True)
