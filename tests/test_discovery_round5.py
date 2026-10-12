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
