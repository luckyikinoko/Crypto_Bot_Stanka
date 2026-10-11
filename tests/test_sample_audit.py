import unittest
import pandas as pd
from test_discovery_round2 import features
from research.diagnostics.sample_audit import audit
from market_data.schema import utc


class SampleAuditTests(unittest.TestCase):
    def sample(self):
        f=features()
        f['observation_id']=range(len(f))
        labels=pd.DataFrame({'observation_id':f.observation_id,'decision_at':f.available_at,
            'entry_at':f.available_at+pd.Timedelta(minutes=5),
            'label_end':f.available_at+pd.Timedelta(hours=72,minutes=5),'status':'complete'})
        return f,labels

    def test_filter_path_and_overlap_reconcile(self):
        f,l=self.sample()
        f['trend']=f.trend.astype('string')
        f['volatility']=f.volatility.astype('string')
        r=audit(f,l,utc('2020-01-01'),utc('2020-02-01'))['candidates']
        b=r['trend_breakout_4h']
        self.assertEqual(b['funnel']['event'],2)
        self.assertEqual(b['usable'],2)
        self.assertEqual(b['nonoverlap'],1)
        self.assertEqual(r['trend_rsi_recovery_4h']['usable'],1)

    def test_gaps_and_boundary_are_disjoint(self):
        f,l=self.sample()
        l.loc[1,'status']='path_gap'
        r=audit(f,l,utc('2020-01-01'),utc('2020-01-04'))['candidates']['trend_breakout_4h']
        self.assertEqual(r['usable'],0)
        self.assertEqual(r['incomplete_by_status'],{'path_gap':1})
        self.assertEqual(r['complete_crossing_pool_boundary'],1)

    def test_returns_cannot_affect_counts(self):
        f,l=self.sample()
        a=audit(f,l,utc('2020'),utc('2021'))
        l['net_standard']=float('inf')
        self.assertEqual(a,audit(f,l,utc('2020'),utc('2021')))

    def test_missing_duplicate_and_reserved_rejected(self):
        f,l=self.sample()
        with self.assertRaises(ValueError):audit(f,l.iloc[:1],utc('2020'),utc('2021'))
        with self.assertRaises(ValueError):audit(f,pd.concat([l,l]),utc('2020'),utc('2021'))
        with self.assertRaises(ValueError):audit(f,l,utc('2020'),utc('2027'))
