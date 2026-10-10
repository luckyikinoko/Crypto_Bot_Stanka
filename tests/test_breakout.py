import unittest
import numpy as np
import pandas as pd
from breakout_strategy import breakout_signals, breakout_conditions
from btc_backtest import indicators

class BreakoutTests(unittest.TestCase):
    def frame(self):
        idx=pd.date_range('2024-01-01',periods=72000,freq='min',tz='UTC')
        rng=np.random.default_rng(12)
        close=100*np.exp(np.cumsum(rng.normal(.000005,.0003,len(idx))))
        df=pd.DataFrame({'close':close,'volume':rng.uniform(1,5,len(idx))},index=idx)
        df['open']=df.close.shift().fillna(df.close.iloc[0])
        df['high']=df[['open','close']].max(axis=1)*1.0001
        df['low']=df[['open','close']].min(axis=1)*.9999
        return df[['open','high','low','close','volume']]
    def test_no_future_leakage(self):
        df=self.frame();cut=df.index[65000]
        before=breakout_signals(df.loc[df.index<cut])
        df.loc[df.index>=cut,['open','high','low','close']]*=2
        after=breakout_signals(df).reindex(before.index)
        pd.testing.assert_frame_equal(before,after)
    def test_signal_clock_and_unchanged_risk(self):
        df=self.frame();s=breakout_signals(df)
        self.assertTrue((s.index[s.signal].minute%15==0).all())
        self.assertGreater(s.signal.sum(),0)
        pd.testing.assert_frame_equal(s.drop(columns='signal'),indicators(df).drop(columns='signal'))
    def test_excludes_current_bar_from_range_and_volume(self):
        hi=pd.date_range('2024-01-01',periods=100,freq='h',tz='UTC')
        h=pd.DataFrame({'close':np.arange(100.,200.)},index=hi)
        mi=pd.date_range(hi[-1],periods=21,freq='15min')
        m=pd.DataFrame({'high':200.,'close':199.,'volume':100.},index=mi)
        m.loc[mi[-1],['high','close','volume']]=[205,201,120]
        self.assertTrue(breakout_conditions(m,h).iloc[-1])
        m.loc[mi[-1],'volume']=119.9
        self.assertFalse(breakout_conditions(m,h).iloc[-1])
        m.loc[mi[-1],['close','volume']]=[200,120]
        self.assertFalse(breakout_conditions(m,h).iloc[-1])

if __name__=='__main__':unittest.main()
