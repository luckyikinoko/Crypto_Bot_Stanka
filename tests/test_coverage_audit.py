import unittest
import pandas as pd
from test_indicators import candles
from market_data.schema import utc,aggregate
from research.diagnostics.coverage_audit import classify_missing,missing_members,coverage


class CoverageAuditTests(unittest.TestCase):
    def test_evidence_priority_and_off_grid_overlap(self):
        t=pd.date_range('2020',periods=5,freq='5min',tz='UTC')
        def reject(open_time,close_time,reason):
            return {'open_time_utc':str(open_time),'open_time_raw':int(open_time.timestamp()*1000),
                    'close_time_raw':int(close_time.timestamp()*1000),'reason':reason}
        q=[reject(t[1],t[1]+pd.Timedelta(seconds=2),'nonstandard_close_boundary'),
           reject(t[2]+pd.Timedelta(minutes=1),t[3]+pd.Timedelta(minutes=1),'off_grid_open')]
        r=classify_missing(t,[t[0]],q)
        self.assertEqual(list(r.values()),['valid_archive_row_missing_from_store','quarantined_exact_open',
            'overlaps_quarantined_off_grid_row','overlaps_quarantined_off_grid_row','absent_from_cached_archive'])

    def test_higher_timeframe_omission_traced(self):
        f=candles(24,'5m').drop(index=3).reset_index(drop=True)
        high=aggregate(f,'1h')
        r=missing_members(f,high,'1h',f.open_time.iloc[0],f.available_at.iloc[-1])
        self.assertEqual(len(r),1)
        self.assertEqual(r[0]['missing_5m_members'],1)

    def test_warmup_reset_lengths(self):
        f=candles(600,'4h')
        f.loc[300:,'open_time']+=pd.Timedelta(hours=4)
        f.loc[300:,'available_at']+=pd.Timedelta(hours=4)
        r=coverage(f,'4h')
        self.assertEqual(len(r['segments']),2)
        self.assertEqual([x['unknown_trend'] for x in r['segments']],[199,199])
        self.assertEqual([x['unknown_volatility'] for x in r['segments']],[265,265])
        self.assertEqual(r['segments'][1]['gap_before_minutes'],240)
