import unittest
import pandas as pd
from research.discovery_round3.outcomes import join_observations,select_pool,LABEL_COLUMNS
from market_data.schema import utc


class RoundThreeOutcomeTests(unittest.TestCase):
    def frames(self):
        t=pd.date_range('2023-12-27',periods=4,freq='1d',tz='UTC')
        f=pd.DataFrame({'observation_id':range(4),'available_at':t,'breakout':[1.,0.,1.,1.]})
        labels=pd.DataFrame({c:[0.]*4 for c in LABEL_COLUMNS})
        labels['observation_id']=range(4);labels['decision_at']=t
        labels['entry_at']=t+pd.Timedelta(minutes=5)
        labels['label_end']=t+pd.Timedelta(hours=72,minutes=5)
        labels['status']=['complete','complete','path_gap','complete']
        return f,labels

    def test_purge_gap_and_signal_join(self):
        f,l=self.frames();j=join_observations(f,l)
        pool,q=select_pool(j[j.signal],utc('2023'),utc('2024'))
        self.assertEqual(pool.observation_id.tolist(),[0])
        self.assertEqual(q,{'decisions':3,'incomplete_by_status':{'path_gap':1},
                            'complete_boundary_purged':1,'usable':1})

    def test_id_timing_and_horizon_mismatch_rejected(self):
        f,l=self.frames()
        with self.assertRaises(ValueError):join_observations(f,l.iloc[:3])
        l.loc[0,'entry_at']+=pd.Timedelta(minutes=5)
        with self.assertRaises(ValueError):join_observations(f,l)
        f,l=self.frames();l.loc[0,'label_end']+=pd.Timedelta(hours=1)
        with self.assertRaises(ValueError):join_observations(f,l)

    def test_future_values_cannot_change_signals(self):
        f,l=self.frames();a=join_observations(f,l)
        l['net_standard']=-100.;l['mae']=float('nan')
        pd.testing.assert_series_equal(a.signal,join_observations(f,l).signal)
        with self.assertRaises(ValueError):select_pool(a,utc('2023'),utc('2027'))
