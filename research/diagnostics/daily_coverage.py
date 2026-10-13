"""Explain frozen EMA200 coverage using existing data only; no return tests."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from market_data.schema import aggregate, utc
from market_data.store import read_market, RESERVED_FROM
from research.indicators import calculate


def run():
    repo = Path(__file__).resolve().parents[2]
    root = repo / 'data/research_repaired_v1'
    prior = json.loads((repo / 'reports/low_turnover_v1/preflight.json').read_text())
    catalog = (root / 'catalog.json').read_bytes()
    assert hashlib.sha256(catalog).hexdigest() == prior['source_manifest_sha256']
    daily = read_market(root, '1d', '2018-01-01', RESERVED_FROM, allow_gaps=True)
    base = read_market(root, '5m', '2018-01-01', RESERVED_FROM, allow_gaps=True)
    rebuilt = aggregate(base, '1d')
    pd.testing.assert_frame_equal(daily.reset_index(drop=True), rebuilt.reset_index(drop=True))
    features = calculate(daily, '1d')
    groups = daily.open_time.diff().ne(pd.Timedelta(days=1)).cumsum()
    # Independent timestamp-only reconstruction of EMA warm-up eligibility.
    ready = daily.groupby(groups).cumcount().ge(199)
    assert np.array_equal(ready.to_numpy(), np.isfinite(features.ema_200).to_numpy())
    grid = pd.date_range(utc('2018-01-01'), RESERVED_FROM, freq='D', inclusive='left')
    missing = grid.difference(pd.DatetimeIndex(daily.open_time))
    counts = base.groupby(base.open_time.dt.floor('D')).size()
    assert set(missing) == set(grid[counts.reindex(grid, fill_value=0).lt(288)])
    segments = []
    for _, part in daily.groupby(groups):
        segments.append({'first_open': str(part.open_time.iloc[0]),
                         'last_open': str(part.open_time.iloc[-1]), 'days': len(part)})
    pools = {}
    for name, start, end in [('training', '2018-01-01', '2024-01-01'),
                             ('reused_recent', '2024-01-01', '2026-04-01')]:
        mask = features.available_at.ge(utc(start)) & features.available_at.lt(utc(end))
        expected = prior['counts'][name]
        absent = expected['calendar_days'] - int(mask.sum())
        initial = int((mask & ~ready & groups.eq(1)).sum())
        restart = int((mask & ~ready & groups.ne(1)).sum())
        eligible = int((mask & ready).sum())
        assert eligible == expected['eligible_daily_decisions']
        assert absent + initial + restart + eligible == expected['calendar_days']
        pools[name] = dict(absent_decisions=absent, initial_warmup=initial,
                           post_gap_warmup=restart, eligible=eligible)
    report = {'market_snapshot': prior['market_snapshot'], 'source_manifest_sha256':
              prior['source_manifest_sha256'], 'pools': pools, 'segments': segments,
              'missing_daily_opens': [str(x) for x in missing],
              'missing_5m_per_affected_day': {str(x): int(288-counts.get(x, 0)) for x in missing},
              'validation': ['daily aggregation exactly reproduced',
                             'EMA eligibility independently reproduced from timestamps',
                             'all absent daily candles explained by incomplete 5m buckets',
                             'pool totals and eligibility match frozen preflight'],
              'return_tests_added': 0, 'reserved_pool_read': False,
              'conclusion': 'Strict complete-bucket aggregation plus gap-reset warm-up explains coverage. Native exchange daily candles have not been audited; remaining intraday gaps are not proven recoverable.'}
    out = repo / 'reports/low_turnover_v1/coverage_diagnosis.json'
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'pools': pools, 'missing_daily_candles': len(missing),
                      'contiguous_segments': len(segments), 'validation': report['validation']}, indent=2))
    return report


if __name__ == '__main__':
    run()
