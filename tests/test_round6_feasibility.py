import unittest
import pandas as pd
from research.discovery_round6.__main__ import count_pool


def features():
    return pd.DataFrame({'available_at':pd.date_range('2020-01-02',periods=5,freq='h',tz='UTC'),
        'observation_id':list('abcde'),'eligible':[True]*5,'signal':[False,True,False,False,True]})


class FeasibilityTests(unittest.TestCase):
    def test_boundary_purge_and_baseline_origin(self):
        f=features();start=pd.Timestamp('2020-01-01',tz='UTC');end=f.available_at.iloc[0]+pd.Timedelta(hours=26)
        c=count_pool(f,start,end)
        self.assertEqual(c['raw_events'],2);self.assertEqual(c['timing_eligible'],1)
        self.assertEqual(c['scheduled_nonoverlap'],1);self.assertEqual(c['boundary_purged'],1)
        self.assertEqual(c['block_origin'],'2020-01-02 00:00:00+00:00')
        self.assertFalse(c['execution_paths_checked'])

    def test_invalid_event_baseline_and_reserved_rejected(self):
        f=features();f.loc[1,'eligible']=False
        start=pd.Timestamp('2020-01-01',tz='UTC');end=pd.Timestamp('2021-01-01',tz='UTC')
        with self.assertRaises(ValueError):count_pool(f,start,end)
        with self.assertRaises(ValueError):count_pool(features(),start,pd.Timestamp('2026-04-02',tz='UTC'))
        f=features();f.loc[1,'available_at']=f.available_at.iloc[0]
        with self.assertRaises(ValueError):count_pool(f,start,end)

    def test_empty_pool(self):
        f=features();f['eligible']=False;f['signal']=False
        c=count_pool(f,pd.Timestamp('2020-01-01',tz='UTC'),pd.Timestamp('2021-01-01',tz='UTC'))
        self.assertEqual(c['active_28day_blocks'],0);self.assertEqual(c['raw_events'],0)
        self.assertEqual(c['scheduled_nonoverlap'],0);self.assertIsNone(c['block_origin'])
