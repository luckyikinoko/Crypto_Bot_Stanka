import unittest
import pandas as pd
from test_indicators import candles
from market_data.schema import VALUES
from research.diagnostics.apply_repair import apply_rows,diff_rows


class RepairTests(unittest.TestCase):
    def setup_data(self):
        allrows=candles(4,'5m')
        base=allrows.drop(index=1).reset_index(drop=True)
        add=allrows.iloc[[1]].reset_index(drop=True)
        old={c:str(base.iloc[0][c]) for c in VALUES}
        new=dict(old);new['high']=str(float(new['high'])+1)
        correction={'open_time':str(base.open_time.iloc[0]),'old_monthly_values':old,'new_daily_api_values':new}
        return base,add,correction

    def test_exact_addition_correction_no_other_changes(self):
        base,add,c=self.setup_data();before=base.copy(deep=True)
        result,delta=apply_rows(base,add,[c])
        pd.testing.assert_frame_equal(base,before)
        self.assertEqual(len(result),4)
        self.assertEqual(len(delta['added']),1);self.assertEqual(len(delta['changed']),1)
        self.assertFalse(delta['removed'])

    def test_preimage_duplicate_and_existing_addition_rejected(self):
        base,add,c=self.setup_data()
        with self.assertRaises(ValueError):apply_rows(base,base.iloc[[0]],[c])
        with self.assertRaises(ValueError):apply_rows(base,add,[c,c])
        c['old_monthly_values']['close']='1'
        with self.assertRaises(ValueError):apply_rows(base,add,[c])

    def test_bad_corrected_ohlc_rejected(self):
        base,add,c=self.setup_data();c['new_daily_api_values']['high']='1'
        with self.assertRaises(ValueError):apply_rows(base,add,[c])
