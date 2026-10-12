import unittest
import pandas as pd
from test_round5_outcomes import fixture as prior_fixture
from research.discovery_round6.outcomes import join_observations, eligibility_mask, verify_events


def fixture():
    f,l=prior_fixture()
    f=f[['observation_id','available_at','segment_id']].assign(prior_atr=2.,bars_since_gap=[15,16,17],eligible=[False,True,True],signal=[False,True,False])
    return f,l


class Round6OutcomeTests(unittest.TestCase):
    def test_frozen_baseline_and_pattern_subset(self):
        f,l=fixture();r=join_observations(f,l)
        self.assertEqual(r.observation_id.tolist(),['b','c'])
        self.assertEqual(r.signal.tolist(),[True,False])
        f.loc[0,'eligible']=True
        with self.assertRaises(ValueError):eligibility_mask(f)

    def test_pattern_identity_and_recognition_time_checked(self):
        f,l=fixture();t=f.available_at.iloc[1]
        e=pd.DataFrame({'event_id':['pattern1'],'formation_start':[t-pd.Timedelta(hours=10)],'formation_end':[t-pd.Timedelta(hours=1)],'available_at':[t]})
        verify_events(f,e)
        f.loc[2,'signal']=True
        with self.assertRaises(ValueError):verify_events(f,e)
        f.loc[2,'signal']=False;e.loc[0,'formation_end']=t+pd.Timedelta(hours=1)
        with self.assertRaises(ValueError):verify_events(f,e)

    def test_labels_require_correct_delay_cost_and_identity(self):
        for column in ('entry_at','decision_at','label_end'):
            f,l=fixture();l.loc[0,column]+=pd.Timedelta(minutes=5)
            with self.assertRaises(ValueError):join_observations(f,l)
        f,l=fixture();l.loc[0,'net_standard']=.5
        with self.assertRaises(ValueError):join_observations(f,l)
        f,l=fixture();l.loc[0,'observation_id']='a'
        with self.assertRaises(ValueError):join_observations(f,l)
