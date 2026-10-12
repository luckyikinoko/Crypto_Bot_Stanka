import unittest
import pandas as pd
from test_indicators import candles
from market_data.schema import utc
from research.diagnostics.daily_recovery import planned_days,compare_day


class DailyRecoveryTests(unittest.TestCase):
    def test_day_planning_midnight_and_multiday(self):
        gaps=[{'start':'2018-01-01 23:55','end_exclusive':'2018-01-02'},
              {'start':'2018-01-02 23:55','end_exclusive':'2018-01-04 00:05'}]
        self.assertEqual([str(x.date()) for x in planned_days(gaps)],
                         ['2018-01-01','2018-01-02','2018-01-03','2018-01-04'])
        with self.assertRaises(ValueError):planned_days([{'start':'2026-04-01','end_exclusive':'2026-04-02'}])

    def test_exact_overlap_conflict_and_candidate(self):
        daily=candles(4,'5m');base=daily.drop(index=1).copy()
        missing=pd.DatetimeIndex([daily.open_time.iloc[1]])
        candidates,conflicts,n=compare_day(base,daily,missing)
        self.assertEqual(n,3);self.assertEqual(len(candidates),1);self.assertFalse(conflicts)
        daily.loc[0,'volume']+=1
        _,conflicts,_=compare_day(base,daily,missing)
        self.assertEqual(conflicts[0]['fields'],['volume'])

    def test_duplicates_rejected_and_no_candidate_invention(self):
        daily=candles(4,'5m')
        missing=pd.DatetimeIndex([daily.open_time.iloc[0]-pd.Timedelta(minutes=5)])
        self.assertTrue(compare_day(daily,daily,missing)[0].empty)
        with self.assertRaises(ValueError):compare_day(daily,pd.concat([daily,daily]),missing)
