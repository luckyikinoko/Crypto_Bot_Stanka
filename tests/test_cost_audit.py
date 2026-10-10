import unittest
import pandas as pd
from btc_backtest import Config,run
from cost_audit import break_even,decompose

class AuditTests(unittest.TestCase):
    def test_break_even_cashflow(self):
        for f in [0,.0005,.001]:
            for s in [0,.0002,.0004]:
                g=break_even(f,s)
                self.assertAlmostEqual((1+g)*(1-s)*(1-f),(1+s)*(1+f))
                g=break_even(f,s,True)
                self.assertAlmostEqual((1+g)*(1-s)*(1-f)*(1-f),1+s)
    def test_negative_inputs_rejected(self):
        with self.assertRaises(ValueError):break_even(-.1,.001)
    def test_cashflow_decomposition(self):
        t=pd.DataFrame([dict(q=2,entry=100.02,exit=100.9798,entry_fee=.20004,exit_fee=.2019596,pnl=1.5176004)])
        d=decompose(t)
        self.assertAlmostEqual(d['gross_reference_pnl'],2)
        self.assertAlmostEqual(d['net_pnl'],1.5176004)
    def test_drawdown_includes_observed_open_peak(self):
        idx=pd.date_range('2024-01-01',periods=3,freq='min',tz='UTC')
        df=pd.DataFrame(dict(open=[100,105,100],high=[100.05,105,100.05],low=[99.95]*3,close=[100]*3,volume=[1]*3),index=idx)
        sig=pd.DataFrame(dict(signal=[True,False,False],reference=100.,stop=99.2,regime_exit=False),index=idx)
        trades,eq,summary=run(df,Config(warmup_hours=0,reward=100),signals=sig)
        self.assertGreater(eq.peak.max(),1005)
        self.assertGreater(summary['max_drawdown'],.01)
        self.assertAlmostEqual(summary['final_equity'],1000+trades.pnl.sum())

if __name__=='__main__':unittest.main()
