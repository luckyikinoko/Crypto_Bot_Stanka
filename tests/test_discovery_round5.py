import hashlib
import json
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
from research.discovery_round5.engine import signal_mask, eligibility_mask


def features():
    return pd.DataFrame({'observation_id':list('abcde'),
        'available_at':pd.date_range('2020-01-01',periods=5,freq='h',tz='UTC'),
        'segment_id':[0]*5,'close':[99.,101.,102.,100.,101.],
        'ema_20':[100.]*5,'ema_50':[105.]*5,'ema_200':[100.]*5})


class Round5Tests(unittest.TestCase):
    def test_event_and_equalities(self):
        f=features()
        self.assertEqual(signal_mask(f).tolist(),[False,True,False,False,True])
        f.loc[1,'ema_50']=100.
        self.assertFalse(signal_mask(f).iloc[1])
        f.loc[4,'close']=100.
        self.assertFalse(signal_mask(f).iloc[4])

    def test_gap_and_segment_reset(self):
        f=features();f.loc[1:,'available_at']+=pd.Timedelta(hours=1)
        self.assertFalse(signal_mask(f).iloc[1])
        f=features();f.loc[1:,'segment_id']=1
        self.assertFalse(signal_mask(f).iloc[1])

    def test_warmup_and_invalid_feature_are_ineligible(self):
        for column,value in [('ema_200',np.nan),('ema_50',np.inf),('ema_20',np.nan)]:
            f=features();f.loc[1,column]=value
            self.assertFalse(eligibility_mask(f).iloc[1])
            self.assertFalse(signal_mask(f).iloc[1])
        f=features();f.loc[0,'ema_20']=np.nan
        self.assertFalse(signal_mask(f).iloc[1])

    def test_prefix_invariance(self):
        f=features();expected=signal_mask(f)
        for n in range(1,len(f)+1):
            pd.testing.assert_series_equal(signal_mask(f.iloc[:n]),expected.iloc[:n])

    def test_timestamp_and_identity_guards(self):
        f=features();f.loc[1,'observation_id']=f.loc[0,'observation_id']
        with self.assertRaises(ValueError):signal_mask(f)
        f=features();f['available_at']=pd.date_range('2026-04-01',periods=5,freq='h',tz='UTC')
        with self.assertRaises(ValueError):signal_mask(f)
        f=features();f['available_at']=f.available_at.dt.tz_localize(None)
        with self.assertRaises(ValueError):signal_mask(f)
        f=features();f.loc[1,'segment_id']=np.nan
        with self.assertRaises(ValueError):signal_mask(f)

    def test_registry_uses_reviewed_lineage_and_existing_gates(self):
        repo=Path(__file__).resolve().parents[1]
        r=json.loads((repo/'research/discovery_round5/REGISTRY.json').read_text())
        raw=(repo/r['prior_report']).read_bytes();prior=json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),r['prior_report_sha256'])
        self.assertEqual(prior['snapshot_id'],r['prior_snapshot'])
        self.assertEqual(prior['market_snapshot'],r['market_snapshot'])
        self.assertEqual(len(prior['test_ledger']),r['prior_tests'])
        old=json.loads((repo/'research/discovery_round4/REGISTRY.json').read_text())
        for key in ('execution','feasibility_gates','outcome_gates','bootstrap','periods'):
            self.assertEqual(r[key],old[key])
        self.assertEqual(r['costs'],prior['costs'])
        self.assertEqual(r['status'],'registered_not_evaluated')


class Round5FeasibilityTests(unittest.TestCase):
    def test_boundary_purge_and_baseline_origin(self):
        from research.discovery_round5.__main__ import count_pool
        f=features()
        start=pd.Timestamp('2020-01-01',tz='UTC')
        end=start+pd.Timedelta(hours=26)
        c=count_pool(f,start,end)
        self.assertEqual(c['raw_events'],2)
        self.assertEqual(c['timing_eligible'],1)
        self.assertEqual(c['boundary_purged'],1)
        self.assertEqual(c['scheduled_nonoverlap'],1)
        self.assertEqual(c['block_origin'],str(start))
        self.assertEqual(c['eligible_baseline_decisions'],4)
        self.assertFalse(c['execution_paths_checked'])

    def test_empty_signal_pool_and_reserved_boundary(self):
        from research.discovery_round5.__main__ import count_pool
        f=features();f['ema_200']=np.nan
        c=count_pool(f,pd.Timestamp('2020-01-01',tz='UTC'),pd.Timestamp('2021-01-01',tz='UTC'))
        self.assertEqual(c['timing_eligible'],0)
        self.assertEqual(c['active_28day_blocks'],0)
        self.assertIsNone(c['block_origin'])
        with self.assertRaises(ValueError):
            count_pool(f,pd.Timestamp('2020-01-01',tz='UTC'),pd.Timestamp('2026-04-02',tz='UTC'))

    def test_each_gate_is_required(self):
        from research.discovery_round5.__main__ import feasibility
        gates={'training_observations':100,'training_nonoverlap':50,'training_active_28day_blocks':30,'recent_observations':30}
        counts={'training':{'timing_eligible':100,'scheduled_nonoverlap':50,'active_28day_blocks':30},'reused_recent':{'timing_eligible':30}}
        self.assertTrue(feasibility(counts,gates)['passed'])
        for pool,key in [('training','timing_eligible'),('training','scheduled_nonoverlap'),('training','active_28day_blocks'),('reused_recent','timing_eligible')]:
            counts[pool][key]-=1
            self.assertFalse(feasibility(counts,gates)['passed'])
            counts[pool][key]+=1
