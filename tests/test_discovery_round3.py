import unittest
from unittest.mock import patch
import pandas as pd
from research.discovery_round3.__main__ import signal_mask, count_pool, feasibility
from market_data.schema import utc


class RoundThreeTests(unittest.TestCase):
    def frame(self):
        t=pd.date_range('2023-01-01',periods=40,freq='4h',tz='UTC')
        return pd.DataFrame({'observation_id':range(40),'available_at':t,'breakout':1.})

    def test_exact_signal_and_no_extra_filters(self):
        f=self.frame();f.loc[0,'breakout']=float('nan');f.loc[1,'breakout']=0.
        f['trend']='bearish';f['net_standard']=-100
        self.assertEqual(signal_mask(f).sum(),38)
        for n in (1,5,20):
            pd.testing.assert_series_equal(signal_mask(f.iloc[:n]),signal_mask(f).iloc[:n])

    def test_boundary_delay_and_cooldown(self):
        f=self.frame()
        r=count_pool(f,utc('2023-01-01'),utc('2023-01-05'))
        self.assertEqual(r['raw_events'],24)
        self.assertEqual(r['timing_eligible'],6)
        self.assertEqual(r['boundary_purged'],18)
        self.assertEqual(r['scheduled_nonoverlap'],1)
        r=count_pool(f,utc('2023-01-01'),utc('2023-02-01'))
        self.assertEqual(r['scheduled_nonoverlap'],3)  # indexes 0, 19, 38

    def test_blocks_empty_and_thresholds(self):
        f=self.frame();f['breakout']=0
        r=count_pool(f,utc('2023'),utc('2024'))
        self.assertEqual(r['active_28day_blocks'],0)
        g={'training_observations':100,'training_nonoverlap':50,
           'training_active_28day_blocks':30,'recent_observations':30}
        t={'timing_eligible':100,'scheduled_nonoverlap':50,'active_28day_blocks':30}
        self.assertTrue(feasibility({'training':t,'reused_recent':{'timing_eligible':30}},g)['passed'])
        t['active_28day_blocks']=29
        self.assertFalse(feasibility({'training':t,'reused_recent':{'timing_eligible':30}},g)['passed'])

    def test_reserved_duplicate_and_non_utc_rejected(self):
        f=self.frame()
        with self.assertRaises(ValueError):signal_mask(f.iloc[::-1])
        with self.assertRaises(ValueError):signal_mask(pd.concat([f,f]))
        with self.assertRaises(ValueError):count_pool(f,utc('2023'),utc('2027'))
        f.available_at=f.available_at.dt.tz_localize(None)
        with self.assertRaises(ValueError):signal_mask(f)
