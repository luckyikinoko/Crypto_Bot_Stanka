import unittest
import pandas as pd
from research.discovery_round5.outcomes import join_observations
from research.discovery_round3.outcomes import LABEL_COLUMNS
from research.statistics.outcomes import SCENARIOS


def fixture():
    t=pd.date_range('2020-01-01',periods=3,freq='h',tz='UTC')
    f=pd.DataFrame({'observation_id':['a','b','c'],'available_at':t,'segment_id':[0]*3,
                    'close':[99.,101.,102.],'ema_20':[100.]*3,'ema_50':[105.]*3,'ema_200':[100.]*3})
    rows=[]
    for i in (1,2):
        row={k:0. for k in LABEL_COLUMNS}
        row.update(observation_id=f.observation_id[i],decision_at=t[i],entry_at=t[i]+pd.Timedelta(minutes=5),
            label_end=t[i]+pd.Timedelta(hours=24,minutes=5),status='complete',entry_raw=100.,exit_raw=101.)
        row.update({'net_'+name:cost.net(100.,101.) for name,cost in SCENARIOS.items()})
        rows.append(row)
    return f,pd.DataFrame(rows)


class OutcomeTests(unittest.TestCase):
    def test_baseline_eligibility_and_signal_subset(self):
        f,l=fixture();r=join_observations(f,l)
        self.assertEqual(r.observation_id.tolist(),['b','c'])
        self.assertEqual(r.signal.tolist(),[True,False])

    def test_wrong_identity_and_duplicates_rejected(self):
        f,l=fixture();l.loc[0,'observation_id']='a'
        with self.assertRaises(ValueError):join_observations(f,l)
        f,l=fixture();l.loc[0,'observation_id']='c'
        with self.assertRaises(ValueError):join_observations(f,l)

    def test_delay_and_horizon_enforced(self):
        for column in ('entry_at','label_end','decision_at'):
            f,l=fixture();l.loc[0,column]+=pd.Timedelta(minutes=5)
            with self.assertRaises(ValueError):join_observations(f,l)

    def test_costs_checked_and_incomplete_paths_kept_for_accounting(self):
        f,l=fixture();l.loc[0,'net_standard']=.1
        with self.assertRaises(ValueError):join_observations(f,l)
        l.loc[0,'status']='path_gap'
        self.assertEqual(join_observations(f,l).status.tolist(),['path_gap','complete'])
