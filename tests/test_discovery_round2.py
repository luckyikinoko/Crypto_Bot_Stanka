import unittest
import numpy as np
import pandas as pd
from test_indicators import candles
from research.discovery_round2.engine import entry_masks
from research.discovery_round2.__main__ import pool
from research.statistics.outcomes import label_paths, Costs
from research.regimes import classify
from research.discovery.engine import scheduled


def features():
    return pd.DataFrame({'available_at':pd.date_range('2020',periods=5,freq='4h',tz='UTC'),
        'segment_id':[1,1,1,2,2], 'atr':[1.]*5,'trend':['bullish']*5,
        'volatility':['normal']*5,'rsi':[39.,40.,39.,40.,41.],
        'breakout':[0.,1.,np.nan,1.,0.]})


class RoundTwoTests(unittest.TestCase):
    def test_rules_and_segment_boundary(self):
        m=entry_masks(features())
        self.assertEqual(m.trend_breakout_4h.tolist(),[False,True,False,True,False])
        self.assertEqual(m.trend_rsi_recovery_4h.tolist(),[False,True,False,False,False])

    def test_warmup_volatility_and_order(self):
        f=features();f.loc[1,'volatility']='high';f.loc[3,'atr']=np.nan
        self.assertFalse(entry_masks(f).any().any())
        with self.assertRaises(ValueError):entry_masks(f.iloc[::-1])

    def test_causal_prefix_and_outcome_isolation(self):
        f=features();m=entry_masks(f)
        for n in range(1,6):
            pd.testing.assert_frame_equal(entry_masks(f.iloc[:n]),m.iloc[:n])
        f['net_standard']=100.
        pd.testing.assert_frame_equal(entry_masks(f),m)
        a=candles(600,'4h')
        pd.testing.assert_frame_equal(classify(a.iloc[:400],'4h'),classify(a,'4h').iloc[:400])

    def test_72h_delay_and_primary_independence(self):
        a=candles(900,'5m',close=np.arange(100.,1000.))
        o=pd.DataFrame({'observation_id':['a'],'available_at':[a.open_time.iloc[0]],'atr':[np.nan]})
        r=label_paths(o,a,(72,)).iloc[0]
        self.assertEqual(r.status,'complete')
        self.assertEqual(r.barrier_status,'missing_atr')
        self.assertEqual(r.entry_raw,101.)
        self.assertEqual(r.exit_raw,964.)
        self.assertAlmostEqual(r.net_standard,Costs().net(101.,964.))
        self.assertEqual(r.label_end-r.entry_at,pd.Timedelta(hours=72))
        self.assertEqual(label_paths(o,a.drop(index=800),(72,)).iloc[0].status,'path_gap')
        self.assertEqual(label_paths(o,a.iloc[:864],(72,)).iloc[0].status,'insufficient_future')

    def test_pool_purge_and_full_hold_cooldown(self):
        t=pd.date_range('2023-12-28',periods=30,freq='4h',tz='UTC')
        f=pd.DataFrame({'observation_id':range(30),'decision_at':t,
                        'label_end':t+pd.Timedelta(hours=72,minutes=5)})
        chosen=scheduled(f)
        self.assertEqual(chosen.observation_id.tolist(),[0,19])
        p=pool(f,pd.Timestamp('2023',tz='UTC'),pd.Timestamp('2024',tz='UTC'))
        self.assertTrue((p.label_end<=pd.Timestamp('2024',tz='UTC')).all())
        self.assertEqual(len(p),6)
