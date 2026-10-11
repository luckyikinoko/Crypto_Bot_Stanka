import json
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from research.discovery.engine import entry_masks, scheduled, evaluate_gates, proposed_allocation
from research.discovery.__main__ import primary, summarize


def features():
    return pd.DataFrame({'available_at':pd.date_range('2020-01-01',periods=4,freq='15min',tz='UTC'),
                         'segment_id':[1]*4,'atr':[1.]*4,'trend':['ranging']*4,
                         'trend_1h':['bullish','bullish','ranging','ranging'],
                         'trend_4h':['bullish','bullish','ranging','ranging'],
                         'volatility':['normal']*4,'rsi':[50.,29.,30.,40.],
                         'resistance_breakout':[True,False,False,False],
                         'resistance_retest':[False,True,False,False]})


class DiscoveryTests(unittest.TestCase):
    def test_exact_entry_rules(self):
        m=entry_masks(features())
        self.assertEqual(list(m.trend_breakout),[True,False,False,False])
        self.assertEqual(list(m.trend_retest),[False,True,False,False])
        self.assertEqual(list(m.range_rsi_recovery),[False,False,True,False])

    def test_unknown_high_volatility_and_gap(self):
        f=features();f.loc[0,'trend_4h']='unknown';f.loc[1,'volatility']='high';f.loc[2:,'segment_id']=2
        m=entry_masks(f)
        self.assertFalse(m[['trend_breakout','trend_retest','range_rsi_recovery']].any().any())
        f=features();f.loc[0,'atr']=np.nan
        self.assertFalse(entry_masks(f).trend_breakout.iloc[0])

    def test_prefix_and_labels_cannot_affect_signals(self):
        f=features();m=entry_masks(f)
        for n in range(1,5):pd.testing.assert_frame_equal(entry_masks(f.iloc[:n]),m.iloc[:n])
        f['net_standard']=[100,-100,100,-100]
        pd.testing.assert_frame_equal(entry_masks(f),m)

    def test_bad_timestamps_rejected(self):
        with self.assertRaises(ValueError):entry_masks(features().iloc[::-1])
        f=features();f.loc[1,'available_at']=f.available_at.iloc[0]
        with self.assertRaises(ValueError):entry_masks(f)

    def test_full_horizon_cooldown(self):
        t=pd.date_range('2020-01-01',periods=3,freq='1h',tz='UTC')
        f=pd.DataFrame({'observation_id':['a','b','c'],'decision_at':t,'label_end':t+pd.Timedelta('1h'),'barrier_minutes':[5,5,5]})
        self.assertEqual(list(scheduled(f).observation_id),['a','c'])

    def gate_inputs(self):
        registry=json.loads(Path('research/discovery/REGISTRY.json').read_text())
        train={'standard':{'n':100},'stress':{'mean':.01},'nonoverlap':{'n':50,'mean':.01},'positive_years':4}
        recent={'standard':{'n':30,'mean':.01},'stress':{'mean':.001}}
        inference={'active_blocks':30,'net_ci95':[.001,.02],'excess_ci95':[.001,.02]}
        return train,recent,inference,.01,registry

    def test_every_gate_must_pass(self):
        args=self.gate_inputs();self.assertTrue(evaluate_gates(*args)['passed'])
        args[0]['standard']['n']=99
        r=evaluate_gates(*args);self.assertFalse(r['passed']);self.assertIn('training_count',r['failed'])
        args=self.gate_inputs();args[1]['stress']['mean']=-.001
        self.assertIn('recent_stress',evaluate_gates(*args)['failed'])
        args=self.gate_inputs();args[2]['net_ci95']=[0,.01]
        self.assertIn('positive_net_ci',evaluate_gates(*args)['failed'])

    def test_ineligible_and_empty_cannot_pass(self):
        args=list(self.gate_inputs());args[2]={}
        r=evaluate_gates(*args)
        self.assertFalse(r['passed']);self.assertIn('active_blocks',r['failed'])
        self.assertIn('positive_net_ci',r['failed'])

    def test_primary_uses_barrier_not_better_exit(self):
        f=pd.DataFrame({'net_standard':[.5],'net_bnb_conditional':[.6],'net_stress':[.4],
                        'barrier_net_standard':[-.01],'barrier_net_bnb_conditional':[-.005],'barrier_net_stress':[-.02]})
        self.assertEqual(primary(f).net_standard.iloc[0],-.01)
        self.assertEqual(f.net_standard.iloc[0],.5)

    def test_empty_summary(self):
        f=pd.DataFrame({'decision_at':pd.Series(dtype='datetime64[ns, UTC]'),
                        'label_end':pd.Series(dtype='datetime64[ns, UTC]'),
                        'observation_id':pd.Series(dtype='string'),
                        **{k:pd.Series(dtype='float') for k in ['net_standard','net_bnb_conditional','net_stress']}})
        s=summarize(f)
        self.assertEqual(s['standard']['n'],0);self.assertEqual(s['positive_years'],0)
        self.assertIsNone(s['return_std'])

    def test_cost_adjusted_budget_and_caps(self):
        from research.statistics.outcomes import Costs
        cost=Costs(fee=.001,half_spread=.0001,slippage=.0004)
        p=proposed_allocation(1000,1000,100,5,cost)
        self.assertAlmostEqual(p['planned_loss_quote'],5)
        self.assertLess(p['quote_budget'],250)
        self.assertEqual(proposed_allocation(1000,1000,100,.01,cost)['quote_budget'],250)
        self.assertEqual(proposed_allocation(1000,10,100,5,cost)['quote_budget'],10)
        with self.assertRaises(ValueError):proposed_allocation(1000,1000,100,60,cost)
