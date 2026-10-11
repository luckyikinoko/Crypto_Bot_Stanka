import unittest
import numpy as np
import pandas as pd
from test_indicators import candles
from research.regimes import classify
from research.statistics.outcomes import label_paths, Costs
from research.statistics.metrics import describe, nonoverlapping, drawdown, block_compare, adjust_by


def observations(a, index=0, atr=1.):
    return pd.DataFrame({'observation_id':['a'],'available_at':[a.open_time.iloc[index]],'atr':[atr]})


class OutcomeTests(unittest.TestCase):
    def test_delay_horizon_and_costs(self):
        a=candles(20,'5m',close=np.arange(100.,120))
        r=label_paths(observations(a),a,(1,)).iloc[0]
        self.assertEqual(r.entry_at,a.open_time.iloc[1])
        self.assertEqual(r.entry_raw,101)
        self.assertEqual(r.exit_raw,112)
        self.assertAlmostEqual(r.gross_return,112/101-1)
        self.assertAlmostEqual(r.net_standard,112*.9998*.999/(101*1.0002*1.001)-1)
        self.assertGreater(r.net_bnb_conditional,r.net_standard)
        self.assertLess(r.net_stress,r.net_standard)
        self.assertAlmostEqual(r.mfe,113/101-1)
        self.assertAlmostEqual(r.mae,100/101-1)
        self.assertEqual(r.time_to_mfe_minutes,60)
        self.assertEqual(r.time_to_mae_minutes,5)

    def test_ambiguous_stop_first_and_open_gap(self):
        a=candles(20,'5m',close=[100.]*20)
        a.loc[2,['high','low']]=[104,97]
        r=label_paths(observations(a),a,(1,)).iloc[0]
        self.assertEqual(r.barrier_exit,'stop')
        self.assertTrue(r.ambiguous_same_bar)
        self.assertEqual(r.barrier_exit_raw,98)
        a.loc[2,['open','high','low','close']]=[95,96,94,95]
        r=label_paths(observations(a),a,(1,)).iloc[0]
        self.assertEqual(r.barrier_exit_raw,95)

    def test_take_and_time_exit(self):
        a=candles(20,'5m',close=[100.]*20)
        r=label_paths(observations(a),a,(1,)).iloc[0]
        self.assertEqual(r.barrier_exit,'time_exit')
        a.loc[2,'high']=104
        r=label_paths(observations(a),a,(1,)).iloc[0]
        self.assertEqual(r.barrier_exit,'take')
        self.assertEqual(r.barrier_exit_raw,103)

    def test_missing_paths_and_truncation(self):
        a=candles(20,'5m')
        for remove,status in [(1,'missing_entry'),(0,'execution_gap'),(4,'path_gap')]:
            self.assertEqual(label_paths(observations(a),a.drop(index=remove),(1,)).iloc[0].status,status)
        self.assertEqual(label_paths(observations(a),a,(4,)).iloc[0].status,'insufficient_future')
        r=label_paths(observations(a,atr=np.nan),a,(1,)).iloc[0]
        self.assertEqual(r.barrier_status,'missing_atr')
        with self.assertRaises(ValueError):Costs(fee=-.1)
        with self.assertRaises(ValueError):label_paths(observations(a),a,entry_delay_minutes=1)

    def test_future_after_horizon_irrelevant(self):
        a=candles(40,'5m');b=a.copy();b.loc[14:,'close']*=2;b.loc[14:,'high']*=2
        pd.testing.assert_frame_equal(label_paths(observations(a),a,(1,)),label_paths(observations(b),b,(1,)))


class ResearchTests(unittest.TestCase):
    def test_regime_warmup_and_causality(self):
        a=candles(close=[100.]*600)
        f=classify(a,'15m')
        self.assertTrue((f.trend.iloc[:199]=='unknown').all())
        self.assertEqual(f.trend.iloc[199],'ranging')
        self.assertEqual(f.volatility.iloc[264],'unknown')
        self.assertEqual(f.volatility.iloc[265],'normal')
        pd.testing.assert_frame_equal(classify(a.iloc[:400],'15m'),f.iloc[:400])
        g=classify(a.drop(index=300).reset_index(drop=True),'15m')
        self.assertEqual(g.trend.iloc[300],'unknown')
        self.assertEqual(g.volatility.iloc[300],'unknown')

    def test_descriptive_and_nonoverlap(self):
        t=pd.date_range('2020-01-01',periods=4,freq='1h',tz='UTC')
        f=pd.DataFrame({'observation_id':list('abcd'),'decision_at':t,'label_end':t+pd.Timedelta('2h'),'net_standard':[.1,-.1,.2,-.2]})
        d=describe(f)
        self.assertAlmostEqual(d['mean'],0)
        self.assertAlmostEqual(d['profit_factor'],1)
        self.assertEqual(d['win_rate'],.5)
        self.assertEqual(list(nonoverlapping(f).observation_id),['a','c'])
        self.assertAlmostEqual(drawdown([.1,-.1]),-.1)

    def test_bootstrap_reference_and_small_sample(self):
        t=pd.date_range('2018-01-01',periods=1000,freq='D',tz='UTC')
        b=pd.DataFrame({'decision_at':t,'net_standard':np.zeros(1000)})
        s=b.copy();s['net_standard']=.01
        r=block_compare(s,b,draws=99)
        self.assertTrue(r['eligible'])
        np.testing.assert_allclose(r['excess_ci95'],[.01,.01])
        self.assertEqual(r['p_one_sided'],.01)
        self.assertFalse(block_compare(s.iloc[:3],b)['eligible'])
        self.assertEqual(r,block_compare(s,b,draws=99))

    def test_multiple_testing_reference(self):
        np.testing.assert_allclose(adjust_by([.01,.03,.2]),[.055,.0825,11/30])


class StorageTests(unittest.TestCase):
    def test_split_purge_and_reserved_guard(self):
        import tempfile,json,hashlib
        from pathlib import Path
        from research.statistics.store import read
        from research.statistics.__main__ import save_frame
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            t=pd.date_range('2023-12-31 23:00',periods=3,freq='30min',tz='UTC')
            f=pd.DataFrame({'decision_at':t,'label_end':t+pd.Timedelta('1h')})
            meta=save_frame(root,'labels',f)
            (root/'catalog.json').write_text(json.dumps({'start':'2023-12-31','end_exclusive':'2024-01-02','labels':{'1':meta}}))
            result=read(root,'2023-12-31','2024-01-01',1)
            self.assertEqual(len(result),1)
            with self.assertRaises(PermissionError):read(root,'2026-04-01','2026-04-02',1)
            (root/meta['path']).write_bytes(b'bad')
            with self.assertRaises(ValueError):read(root,'2023-12-31','2024-01-01',1)
