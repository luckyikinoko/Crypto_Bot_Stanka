import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from market_data.schema import COLUMNS, duration, empty, align_available
from market_data.store import publish
from research.indicators import Config, calculate
from research.indicators.engine import smooth
from research.indicators.__main__ import build


def candles(n=300, interval='15m', close=None):
    c = np.asarray(close if close is not None else 100+np.arange(n)*.1+np.sin(np.arange(n)), dtype=float)
    n = len(c)
    a = pd.DataFrame({'open_time': pd.date_range('2020-01-01', periods=n, freq=duration(interval), tz='UTC')})
    a['available_at'] = a.open_time+duration(interval)
    for key in ('open', 'close'): a[key] = c
    a['high'], a['low'] = c+1, c-1
    for key in ('volume', 'quote_volume'): a[key] = np.arange(n)+10.0
    a['trades'] = 1
    a['taker_base'] = a['taker_quote'] = 0.0
    return a[COLUMNS]


class Indicators(unittest.TestCase):
    def test_seed_reference(self):
        s = smooth(pd.Series([1., 2., 3., 7., 9.]), 3, .5)
        np.testing.assert_allclose(s, [np.nan, np.nan, 2, 4.5, 6.75], equal_nan=True)

    def test_linear_reference(self):
        f = calculate(candles(close=np.arange(1., 301)+100), '15m')
        self.assertEqual(f.ema_20.first_valid_index(), 19)
        self.assertAlmostEqual(f.ema_20.iloc[19], 110.5)
        self.assertAlmostEqual(f.ema_20.iloc[20], 111.5)
        self.assertEqual(f.rsi.first_valid_index(), 14)
        self.assertEqual(f.atr.first_valid_index(), 13)
        self.assertEqual(f.adx.first_valid_index(), 26)
        self.assertEqual(f.macd_signal.first_valid_index(), 33)
        self.assertEqual(f.historical_volatility.first_valid_index(), 20)
        self.assertAlmostEqual(f.rsi.iloc[-1], 100)
        self.assertAlmostEqual(f.atr.iloc[-1], 2)
        self.assertAlmostEqual(f.adx.iloc[-1], 100)
        self.assertAlmostEqual(f.macd.iloc[-1], 7)
        self.assertAlmostEqual(f.macd_signal.iloc[-1], 7)
        self.assertAlmostEqual(f.bb_middle.iloc[19], 110.5)
        self.assertAlmostEqual(f.bb_upper.iloc[19], 110.5+2*np.std(np.arange(20)))
        self.assertAlmostEqual(f.roc.iloc[12], 113/101-1)
        self.assertAlmostEqual(f.relative_volume.iloc[20], 30/19.5)
        self.assertAlmostEqual(f.obv.iloc[3], 11+12+13)
        self.assertAlmostEqual(f.resistance.iloc[20], 121)
        self.assertAlmostEqual(f.support.iloc[20], 100)

    def test_rsi_mixed_reference(self):
        cfg = Config(wilder=3)
        f = calculate(candles(close=[100, 102, 101, 104, 102]), '15m', cfg)
        self.assertAlmostEqual(f.rsi.iloc[3], 100*5/6)
        self.assertAlmostEqual(f.rsi.iloc[4], 100*(10/9)/(10/9+8/9))

    def test_prefix_invariance(self):
        a = candles()
        full = calculate(a, '15m')
        for n in (1, 10, 50, 199, 250):
            pd.testing.assert_frame_equal(calculate(a.iloc[:n], '15m'), full.iloc[:n].reset_index(drop=True))

    def test_gap_reset(self):
        a = candles(600).drop(index=300).reset_index(drop=True)
        full = calculate(a, '15m')
        separate = calculate(a.iloc[300:], '15m')
        pd.testing.assert_frame_equal(full.iloc[300:].drop(columns='segment_id').reset_index(drop=True), separate.drop(columns='segment_id'))
        self.assertTrue(np.isnan(full.ema_200.iloc[300]))

    def test_flat_zero_volume(self):
        a = candles(close=[100]*250)
        a['high'] = a['low'] = 100.
        a['volume'] = 0.
        f = calculate(a, '15m')
        for name, value in [('rsi', 50), ('adx', 0), ('atr', 0), ('bb_width', 0), ('obv', 0)]:
            self.assertEqual(f[name].iloc[-1], value)
        self.assertTrue(f.relative_volume.isna().all())
        self.assertFalse(np.isinf(f.select_dtypes('number')).any().any())

    def test_pivot_confirmation(self):
        f = calculate(candles(close=[100, 101, 105, 101, 100, 101]), '15m')
        self.assertTrue(f.swing_high.iloc[:4].isna().all())
        self.assertEqual(f.swing_high.iloc[4], 106)
        self.assertEqual(f.last_swing_high.iloc[5], 106)
        ties = calculate(candles(close=[100, 105, 105, 100, 100]), '15m')
        self.assertTrue(ties.swing_high.isna().all())

    def test_higher_timeframe_availability(self):
        f = calculate(candles(25, '1h'), '1h')
        t = f.available_at.iloc[19]
        result = align_available([t-pd.Timedelta('1ns'), t, t+pd.Timedelta('1h')], f.iloc[:20], ['ema_20'], '1h')
        self.assertTrue(np.isnan(result.ema_20.iloc[0]))
        self.assertEqual(result.ema_20.iloc[1], f.ema_20.iloc[19])
        self.assertTrue(np.isnan(result.ema_20.iloc[2]))

    def test_all_timeframes_and_volatility_reference(self):
        from market_data.schema import MINUTES
        for interval, minutes in MINUTES.items():
            a = candles(60, interval)
            f = calculate(a, interval)
            returns = np.diff(np.log(a.close.to_numpy()[:21]))
            expected = np.std(returns, ddof=1)*np.sqrt(365*1440/minutes)
            self.assertAlmostEqual(f.historical_volatility.iloc[20], expected)
            pd.testing.assert_frame_equal(calculate(a.iloc[:40], interval), f.iloc[:40])

    def test_empty_and_config(self):
        self.assertEqual(len(calculate(empty(), '5m')), 0)
        for kwargs in ({'wilder': 0}, {'window': 1}, {'bands': float('nan')}, {'macd_fast': 40}):
            with self.assertRaises(ValueError): Config(**kwargs)

    def test_store_roundtrip_and_reserved_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, dest = Path(tmp)/'source', Path(tmp)/'features'
            from market_data.schema import MINUTES
            frames = {i: candles(int(2*1440/m), i) for i, m in MINUTES.items()}
            publish(source, frames, {'start': '2020-01-01', 'cutoff': '2020-01-03'}, [])
            first, counts = build(source, dest, '2020-01-01', '2020-01-03')
            second, replay = build(source, dest, '2020-01-01', '2020-01-03')
            self.assertEqual(first, second)
            self.assertEqual(counts['written'], 5)
            self.assertEqual(replay, {'written': 0, 'reused': 5})
            with self.assertRaises(PermissionError): build(source, dest, end='2026-04-02')
            from research.indicators.store import read_features
            saved = read_features(dest, '5m', '2020-01-01', '2020-01-03')
            pd.testing.assert_frame_equal(saved, calculate(frames['5m'], '5m'))
            with self.assertRaises(PermissionError):
                read_features(dest, '5m', '2026-04-01', '2026-04-02')
            p = dest/first['partitions'][0]['path']
            p.write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                read_features(dest, '5m', '2020-01-01', '2020-01-03')
            with self.assertRaises(Exception): build(source, dest, '2020-01-01', '2020-01-03')


if __name__ == '__main__': unittest.main()
