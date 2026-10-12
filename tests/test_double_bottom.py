import json
import unittest
import pandas as pd
from test_indicators import candles
from research.patterns.double_bottom import detect


def example():
    return candles(interval='1h',close=[110.]*20+[107.,104.,101.,103.,105.,106.,105.,104.,103.,101.2,103.,104.,108.,109.,110.])


class DoubleBottomTests(unittest.TestCase):
    def test_reference_and_confirmation_delay(self):
        a=example();events=detect(a)
        self.assertEqual(len(events),1)
        e=events.iloc[0];m=json.loads(e.metrics)
        self.assertEqual(e.available_at,a.available_at.iloc[32])
        self.assertEqual(m['second_pivot_known_at'],str(a.available_at.iloc[31]))
        self.assertEqual(m['separation_bars'],7)
        self.assertEqual(m['neckline'],107.)
        self.assertEqual(m['second_low'],100.2)
        self.assertTrue(detect(a.iloc[:32]).empty)

    def test_every_prefix_matches_full_detection(self):
        a=example();full=detect(a)
        for n in range(1,len(a)+1):
            expected=full[full.available_at<=a.available_at.iloc[n-1]].reset_index(drop=True)
            pd.testing.assert_frame_equal(detect(a.iloc[:n]),expected)

    def test_gap_cancels_pair(self):
        a=example().drop(index=27).reset_index(drop=True)
        self.assertTrue(detect(a).empty)

    def test_dissimilar_lows_and_tied_pivot_rejected(self):
        a=example();a.loc[29,['open','high','low','close']]=[98.,99.,97.,98.]
        self.assertTrue(detect(a).empty)
        a=example();a.loc[28,'low']=a.low.iloc[29]
        self.assertTrue(detect(a).empty)

    def test_invalidation_wins_over_same_bar_breakout(self):
        a=example();a.loc[32,'low']=95.
        self.assertTrue(detect(a).empty)

    def test_no_breakout_and_no_repeated_event(self):
        a=example();a.loc[32:,['open','high','low','close']]=[104.,105.,103.,104.]
        self.assertTrue(detect(a).empty)
        a=example();self.assertEqual(len(detect(a)),1)

    def test_expiry(self):
        a=candles(interval='1h',close=example().close.iloc[:32].tolist()+[104.]*13+[109.])
        self.assertTrue(detect(a).empty)

    def test_warmup_and_reserved_guards(self):
        a=example().iloc[18:].reset_index(drop=True)
        self.assertTrue(detect(a).empty)
        with self.assertRaises(ValueError):detect(example(),'15m')
        a=example();a['open_time']=pd.date_range('2026-04-01',periods=len(a),freq='h',tz='UTC');a['available_at']=a.open_time+pd.Timedelta(hours=1)
        with self.assertRaises(ValueError):detect(a)

    def test_premature_breakout_rejected(self):
        a=example();a.loc[30,['open','high','low','close']]=[108.,109.,102.,108.]
        self.assertTrue(detect(a).empty)

    def test_prior_drop_requirement(self):
        a=example();a.loc[:21,['open','high','low','close']]=[102.,103.,101.,102.]
        self.assertTrue(detect(a).empty)

    def test_exact_breakout_threshold_does_not_confirm(self):
        a=example();m=json.loads(detect(a).iloc[0].metrics)
        a.loc[32,'close']=m['neckline']+.1*m['frozen_atr']
        self.assertTrue(detect(a.iloc[:33]).empty)

    def test_registry_matches_detector_and_prior_checkpoint(self):
        import hashlib
        from pathlib import Path
        from research.patterns.double_bottom import PARAMETERS
        repo=Path(__file__).resolve().parents[1]
        r=json.loads((repo/'research/discovery_round6/REGISTRY.json').read_text())
        self.assertEqual(r['parameters'],PARAMETERS)
        raw=(repo/r['prior_report']).read_bytes();prior=json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),r['prior_report_sha256'])
        self.assertEqual(prior['snapshot_id'],r['prior_snapshot'])
        self.assertEqual(len(prior['test_ledger']),36)
        self.assertEqual(r['market_snapshot'],prior['market_snapshot'])
        self.assertEqual(r['costs'],prior['costs'])
        self.assertIsNone(r['selected_strategy'])
