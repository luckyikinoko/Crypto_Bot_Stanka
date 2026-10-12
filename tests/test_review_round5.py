import copy
import hashlib
import json
from pathlib import Path
import unittest
from research.diagnostics.review_round5 import SOURCES, validate_chain, implied_gross
from research.statistics.outcomes import SCENARIOS
from research.statistics.metrics import adjust_by


class ReviewTests(unittest.TestCase):
    def test_cost_inverse_for_means(self):
        for cost in SCENARIOS.values():
            returns=[-.02,.01,.05]
            net=sum(cost.net(100,100*(1+x)) for x in returns)/len(returns)
            self.assertAlmostEqual(implied_gross(net,vars(cost)),sum(returns)/len(returns),places=14)

    def test_reviewed_chain(self):
        repo=Path(__file__).resolve().parents[1]
        reports=[json.loads((repo/p).read_text()) for p in SOURCES]
        validate_chain(reports)
        self.assertEqual(len(reports[-1]['test_ledger']),36)

    def test_changed_prior_pvalue_rejected_even_with_valid_hash(self):
        repo=Path(__file__).resolve().parents[1]
        reports=[json.loads((repo/p).read_text()) for p in SOURCES]
        r=copy.deepcopy(reports[-1]);r['test_ledger'][0]['p']=.1234567
        for row,q in zip(r['test_ledger'],adjust_by([x['p'] for x in r['test_ledger']])):
            row['by_q']=q
        payload=dict(r);payload.pop('snapshot_id')
        r['snapshot_id']=hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()
        with self.assertRaisesRegex(ValueError,'Prior hypothesis changed'):
            validate_chain(reports[:-1]+[r])
