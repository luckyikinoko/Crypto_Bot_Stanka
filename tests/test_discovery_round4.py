import unittest
import pandas as pd
from research.discovery_round4.engine import signal_mask,frequency
from market_data.schema import utc


class RoundFourTests(unittest.TestCase):
    def frame(self):
        return pd.DataFrame({'available_at':pd.date_range('2020',periods=6,freq='1h',tz='UTC'),
            'observation_id':range(6),'segment_id':[1,1,1,1,2,2],
            'close':[98.,99.,101.,98.,101.,101.],'bb_lower':[99.,99.,99.,99.,99.,99.]})

    def test_exact_cross_and_segment_reset(self):
        self.assertEqual(signal_mask(self.frame()).tolist(),[False,True,False,False,False,False])

    def test_prefix_and_future_outcomes(self):
        f=self.frame();a=signal_mask(f)
        for n in range(1,7):pd.testing.assert_series_equal(a.iloc[:n],signal_mask(f.iloc[:n]))
        f['net_standard']=100.
        pd.testing.assert_series_equal(a,signal_mask(f))

    def test_gap_warmup_and_invalid_order(self):
        f=self.frame();f.loc[1,'bb_lower']=float('nan')
        self.assertFalse(signal_mask(f).any())
        with self.assertRaises(ValueError):signal_mask(self.frame().iloc[::-1])
        f=self.frame();f['available_at']=f.available_at+pd.to_timedelta([0,1,1,1,1,1],unit='h')
        self.assertFalse(signal_mask(f).any())

    def test_boundary_and_future_pool(self):
        f=self.frame()
        self.assertEqual(frequency(f,utc('2020'),utc('2020-01-02'))['timing_eligible'],0)
        self.assertEqual(frequency(f,utc('2020'),utc('2020-01-03'))['timing_eligible'],1)
        with self.assertRaises(ValueError):frequency(f,utc('2020'),utc('2027'))
