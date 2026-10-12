import unittest
import numpy as np
import pandas as pd
from research.low_turnover_v1.preflight import count_coverage


class CoverageTests(unittest.TestCase):
    def test_denominator_includes_missing_and_warmup_and_excludes_end(self):
        start=pd.Timestamp('2020-01-01',tz='UTC');end=start+pd.Timedelta(days=10)
        f=pd.DataFrame({'available_at':[start,start+pd.Timedelta(days=2),end],'ema_200':[np.nan,100.,100.]})
        r=count_coverage(f,start,end,start)
        self.assertEqual(r['calendar_days'],10)
        self.assertEqual(r['observed_daily_decisions'],2)
        self.assertEqual(r['eligible_daily_decisions'],1)
        self.assertEqual(r['calendar_coverage'],.1)
        self.assertEqual(r['active_28day_blocks'],1)

    def test_block_count_and_reserved_guard(self):
        start=pd.Timestamp('2020-01-01',tz='UTC')
        f=pd.DataFrame({'available_at':[start,start+pd.Timedelta(days=28)],'ema_200':[100.,101.]})
        self.assertEqual(count_coverage(f,start,start+pd.Timedelta(days=29),start)['active_28day_blocks'],2)
        with self.assertRaises(ValueError):count_coverage(f,start,pd.Timestamp('2026-04-02',tz='UTC'),start)
