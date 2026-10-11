import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from market_data.schema import empty, MINUTES
from market_data.store import publish
from research.patterns import Config, detect
from research.patterns.__main__ import build
from test_indicators import candles


def setup_breakout():
    a = candles(close=[100.]*40)
    a.loc[25, ['open','high','low','close']] = [100,104,100,103]
    a.loc[26, ['open','high','low','close']] = [103,103,100.9,102]
    return a


def setup_flag():
    c = [100.]*20 + list(np.arange(102.,118.,2)) + [115.8,115.6,115.4,115.2,115.,114.8] + [118.]
    a = candles(close=c)
    a['volume'] = 100.
    a.loc[28:33, 'volume'] = 50.
    return a


class Patterns(unittest.TestCase):
    def test_breakout_and_retest_reference(self):
        a = setup_breakout()
        f = detect(a,'15m')
        b = f[f.pattern == 'resistance_breakout'].iloc[0]
        r = f[f.pattern == 'resistance_retest'].iloc[0]
        self.assertEqual(b.available_at, a.available_at.iloc[25])
        self.assertEqual(r.available_at, a.available_at.iloc[26])
        self.assertEqual(json.loads(b.metrics)['level'],101)
        self.assertEqual(r.parent_event_id,b.event_id)
        self.assertEqual(len(f[f.pattern == 'resistance_retest']),1)

    def test_retest_invalidated_expired_and_gap(self):
        a = setup_breakout()
        a.loc[26,['open','high','low','close']] = [103,103,99,99.5]
        self.assertFalse((detect(a,'15m').pattern == 'resistance_retest').any())
        a = setup_breakout()
        a.loc[26:28,['open','high','low','close']] = [103,104,102,103]
        a.loc[29,['open','high','low','close']] = [103,103,100.9,102]
        f = detect(a,'15m',Config(retest_bars=2))
        self.assertFalse((f.pattern == 'resistance_retest').any())
        a = setup_breakout().drop(index=26).reset_index(drop=True)
        self.assertFalse((detect(a,'15m').pattern == 'resistance_retest').any())

    def test_flag_reference_and_rejection(self):
        a = setup_flag()
        f = detect(a,'15m')
        flag = f[f.pattern == 'bull_flag'].iloc[0]
        self.assertEqual(flag.available_at,a.available_at.iloc[34])
        m = json.loads(flag.metrics)
        self.assertAlmostEqual(m['pole_height_atr'],8)
        self.assertAlmostEqual(m['flag_to_pole_volume'],.5)
        self.assertAlmostEqual(m['retracement_fraction'],3.2/16)
        a.loc[28:33,'volume'] = 200.
        self.assertFalse((detect(a,'15m').pattern == 'bull_flag').any())
        a = setup_flag(); a.loc[34,['open','high','low','close']] = [115,116,114,115]
        self.assertFalse((detect(a,'15m').pattern == 'bull_flag').any())

    def test_engulfing_both_directions(self):
        a = candles(close=[100.]*25)
        a.loc[20,['open','high','low','close']] = [101,102,99,100]
        a.loc[21,['open','high','low','close']] = [99.5,103,99,102]
        a.loc[22,['open','high','low','close']] = [102.5,103,98,99]
        f = detect(a,'15m')
        self.assertEqual(len(f[f.pattern == 'bullish_engulfing']),1)
        self.assertEqual(len(f[f.pattern == 'bearish_engulfing']),1)
        self.assertEqual(f[f.pattern == 'bullish_engulfing'].iloc[0].available_at,a.available_at.iloc[21])

    def test_prefix_nonrepainting_and_identity(self):
        for a in (setup_flag(), setup_breakout()):
            full = detect(a,'15m')
            for n in range(1,len(a)+1):
                expected = full[full.available_at <= a.available_at.iloc[n-1]].reset_index(drop=True)
                pd.testing.assert_frame_equal(detect(a.iloc[:n],'15m'), expected)

    def test_timeframe_confirmation_and_no_same_bar_retest(self):
        from market_data.schema import duration
        for interval in MINUTES:
            a = setup_breakout().iloc[:26].copy()
            a['open_time'] = pd.date_range('2020-01-01', periods=len(a), freq=duration(interval), tz='UTC')
            a['available_at'] = a.open_time + duration(interval)
            f = detect(a,interval)
            self.assertEqual(len(f[f.pattern == 'resistance_breakout']),1)
            self.assertFalse((f.pattern == 'resistance_retest').any())
            self.assertEqual(f.iloc[-1].available_at,a.available_at.iloc[-1])

    def test_gap_is_independent_segment(self):
        a = pd.concat([candles(40),setup_flag()],ignore_index=True)
        a.loc[40:,'open_time'] += pd.Timedelta('2D')
        a.loc[40:,'available_at'] += pd.Timedelta('2D')
        full = detect(a,'15m')
        expected = detect(a.iloc[40:].reset_index(drop=True),'15m')
        pd.testing.assert_frame_equal(full[full.available_at >= a.available_at.iloc[40]].reset_index(drop=True),expected)

    def test_empty_flat_and_config(self):
        self.assertTrue(detect(empty(),'15m').empty)
        self.assertTrue(detect(candles(close=[100.]*40),'15m').empty)
        for kwargs in ({'pole':1},{'flag':2.5},{'retracement':2},{'pole_atr':float('nan')}):
            with self.assertRaises(ValueError): Config(**kwargs)

    def test_snapshot_repeat_and_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, dest = Path(tmp)/'market',Path(tmp)/'patterns'
            frames={i:candles(int(2*1440/m),i) for i,m in MINUTES.items()}
            publish(source,frames,{'start':'2020-01-01','cutoff':'2020-01-03'},[])
            first, counts = build(source,dest,'2020-01-01','2020-01-03')
            second, replay = build(source,dest,'2020-01-01','2020-01-03')
            self.assertEqual(first,second)
            self.assertEqual(counts,{'written':5,'reused':0})
            self.assertEqual(replay,{'written':0,'reused':5})
            with self.assertRaises(PermissionError): build(source,dest,end='2026-04-02')
            from research.patterns.store import read_events
            saved = read_events(dest,'15m','2020-01-01','2020-01-03')
            self.assertEqual(len(saved),first['partitions'][1]['rows'])
            with self.assertRaises(PermissionError):
                read_events(dest,'15m','2026-04-01','2026-04-02')
            file = dest/first['partitions'][1]['path']
            file.write_bytes(b'bad')
            with self.assertRaises(ValueError): read_events(dest,'15m','2020-01-01','2020-01-03')
