import unittest
from decimal import Decimal
from research.diagnostics.api_reconcile import request_url,canonical_map,verdict
from market_data.schema import utc


class ApiReconcileTests(unittest.TestCase):
    def test_request_bounds_and_reserved_rejection(self):
        u=request_url('2018-02-09')
        self.assertIn('startTime=1518134400000',u)
        self.assertIn('endTime=1518220799999',u)
        with self.assertRaises(ValueError):request_url('2026-04-01')
        with self.assertRaises(ValueError):request_url('2018-02-09 01:00')

    def test_decimal_equality_and_verdicts(self):
        a={'close':Decimal('0.10000000')}
        self.assertEqual(verdict(a,{'close':Decimal('.1')},None,'addition'),'api_confirms_daily_addition')
        b={'close':Decimal('.10000001')}
        self.assertEqual(verdict(a,b,a,'conflict'),'api_supports_monthly')
        self.assertEqual(verdict(a,a,b,'conflict'),'api_supports_daily')
        self.assertEqual(verdict(None,a,b,'conflict'),'api_candle_absent_or_quarantined')

    def test_quarantine_and_exact_decimal_precision(self):
        t=int(utc('2020').timestamp()*1000)
        row=[t,'100.00000001','101','99','100','1',t+299999,'100',1,'.5','50',0]
        bad=list(row);bad[0]+=300000;bad[6]=bad[0]+1
        m,q=canonical_map([row,bad],utc('2020-01-02'))
        self.assertEqual(len(m),1);self.assertEqual(len(q),1)
        self.assertEqual(m[utc('2020')]['open'],Decimal('100.00000001'))
