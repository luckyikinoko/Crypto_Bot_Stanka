import unittest
import numpy as np
import pandas as pd
from btc_backtest import Config, bars, indicators, run, size_trade, validate, wilder

class BacktestTests(unittest.TestCase):
    def frame(self,n=10):
        idx=pd.date_range('2024-01-01',periods=n,freq='min',tz='UTC')
        return pd.DataFrame(dict(open=100.,high=100.05,low=99.95,close=100.,volume=1.),index=idx)
    def signals(self,df):
        s=pd.DataFrame(dict(signal=False,stop=99.2,reference=100.,regime_exit=False),index=df.index)
        s.loc[df.index[0],'signal']=True
        return s
    def test_fee_adjusted_sizing_and_target(self):
        c=Config(); p=size_trade(100.,99.2,1000,1000,c)
        self.assertLessEqual(p['risk'],2.5)
        self.assertLessEqual(p['q']*p['entry'],350)
        proceeds=p['q']*p['target']*(1-c.slippage)*(1-c.fee)
        self.assertAlmostEqual(proceeds-p['cost'],1.5*p['risk'])
    def test_both_touched_stop_first(self):
        df=self.frame(); df.loc[df.index[0],['high','low']]=[103,98]
        t,e,s=run(df,Config(warmup_hours=0),signals=self.signals(df))
        self.assertEqual(t.iloc[0].reason,'stop')
        self.assertAlmostEqual(t.iloc[0].r,-1)
        self.assertAlmostEqual(s['final_equity'],1000+t.pnl.sum())
    def test_gap_stop_fills_at_open(self):
        df=self.frame(); df.loc[df.index[1],['open','high','low','close']]=[98,98.1,97.9,98]
        t,_,_=run(df,Config(warmup_hours=0),signals=self.signals(df))
        self.assertEqual(t.iloc[0].reason,'stop_gap')
        self.assertLess(t.iloc[0].r,-1)
    def test_target_net_reward(self):
        df=self.frame(); df.loc[df.index[1],'high']=103
        t,_,_=run(df,Config(warmup_hours=0),signals=self.signals(df))
        self.assertAlmostEqual(t.iloc[0].r,1.5)
    def test_time_exit(self):
        df=self.frame(200)
        t,_,_=run(df,Config(warmup_hours=0),signals=self.signals(df))
        self.assertEqual(t.iloc[0].reason,'time')
        self.assertEqual((t.iloc[0].exit_time-t.iloc[0].entry_time).total_seconds(),3600)
    def test_daily_limit(self):
        df=self.frame();df.loc[df.index[0],'low']=90
        t,_,s=run(df,Config(warmup_hours=0,daily_loss=.001),signals=self.signals(df))
        self.assertEqual(t.iloc[0].reason,'daily_loss')
        self.assertAlmostEqual(s['final_equity'],999.)
    def test_drawdown_limit(self):
        df=self.frame();df.loc[df.index[0],'low']=90
        t,_,s=run(df,Config(warmup_hours=0,drawdown=.001),signals=self.signals(df))
        self.assertEqual(t.iloc[0].reason,'drawdown')
        self.assertTrue(s['halted'])
    def test_cash_and_no_signals(self):
        df=self.frame();sig=self.signals(df);sig.signal=False
        t,_,s=run(df,Config(warmup_hours=0),signals=sig)
        self.assertEqual(len(t),0);self.assertEqual(s['final_equity'],1000)
    def test_future_data_cannot_change_past_signals(self):
        df=self.frame(72000)
        rng=np.random.default_rng(42)
        df['close']=100*np.exp(np.cumsum(rng.normal(0,.0003,len(df))))
        df['open']=df.close.shift().fillna(100)
        df['high']=df[['open','close']].max(axis=1)*1.001
        df['low']=df[['open','close']].min(axis=1)*.999
        cut=df.index[65000]
        before=indicators(df.loc[df.index<cut])
        df.loc[df.index>=cut,['open','high','low','close']]*=2
        after=indicators(df).reindex(before.index)
        pd.testing.assert_frame_equal(before,after)
    def test_candle_completion(self):
        df=self.frame(7); b=bars(df,5)
        self.assertEqual(len(b),1)
        self.assertEqual(b.index[0],df.index[5])
    def test_reject_gaps_and_duplicate(self):
        df=self.frame()
        with self.assertRaises(ValueError):validate(df.drop(df.index[2]))
        with self.assertRaises(ValueError):validate(pd.concat([df,df.iloc[-1:]]))
    def test_wilder_seed(self):
        s=wilder(pd.Series(range(1,17),dtype=float))
        self.assertAlmostEqual(s.iloc[13],7.5)
        self.assertAlmostEqual(s.iloc[14],(7.5*13+15)/14)
    def test_news_window(self):
        df=self.frame()
        t,_,_=run(df,Config(warmup_hours=0),signals=self.signals(df),events=[df.index[0]])
        self.assertEqual(len(t),0)
    def test_rounding_and_minimum(self):
        self.assertIsNone(size_trade(100,99.2,1,1,Config()))
        p=size_trade(100,99.2,1000,1000,Config(step=.1))
        self.assertAlmostEqual(p['q']/.1,round(p['q']/.1))

    def test_disabled_early_exit_keeps_three_hour_maximum(self):
        df=self.frame(200)
        t,_,_=run(df,Config(warmup_hours=0,early_time_exit=False),signals=self.signals(df))
        self.assertEqual(t.iloc[0].reason,'time')
        self.assertEqual((t.iloc[0].exit_time-t.iloc[0].entry_time).total_seconds(),10800)
    def test_disabled_early_exit_still_honors_stop(self):
        df=self.frame(200);df.loc[df.index[70],'low']=98
        t,_,_=run(df,Config(warmup_hours=0,early_time_exit=False),signals=self.signals(df))
        self.assertEqual(t.iloc[0].reason,'stop')
        self.assertAlmostEqual(t.iloc[0].r,-1)
    def test_disabled_early_exit_still_honors_regime(self):
        df=self.frame(200);sig=self.signals(df);sig.loc[df.index[70],'regime_exit']=True
        t,_,_=run(df,Config(warmup_hours=0,early_time_exit=False),signals=sig)
        self.assertEqual(t.iloc[0].reason,'regime')
    def test_bootstrap_preserves_zero_and_constant_daily_pnl(self):
        from research_experiment import bootstrap
        self.assertEqual(bootstrap([np.zeros(90)])['summed_episode_pnl_95pct_interval'],[0.,0.])
        self.assertEqual(bootstrap([np.ones(90),np.ones(91)])['summed_episode_pnl_95pct_interval'],[181.,181.])

if __name__=='__main__':unittest.main()
