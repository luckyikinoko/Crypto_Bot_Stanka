import json
from pathlib import Path
import tempfile
import unittest
from research.diagnostics.replay_repair import validate_destinations, compare
from research.discovery_round2.__main__ import run as round2
from research.discovery_round4.__main__ import run as round4


class ReplayTests(unittest.TestCase):
    def test_destinations_reject_overlap_and_existing_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaises(ValueError):
                validate_destinations(root/'market',root/'market'/'output',root/'reports')
            (root/'out').mkdir();(root/'out'/'evidence').write_text('preserve')
            with self.assertRaises(ValueError):
                validate_destinations(root/'market',root/'out',root/'reports')
            validate_destinations(root/'market',root/'fresh',root/'reports')

    def test_explicit_prior_rejects_other_market_before_research(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);market=root/'market';market.mkdir()
            (market/'catalog.json').write_text(json.dumps({'snapshot_id':'new'}))
            prior=root/'prior.json'
            prior.write_text(json.dumps({'provenance':{'market_snapshot':'old'}}))
            for runner in (round2,round4):
                with self.assertRaisesRegex(ValueError,'market snapshot mismatch'):
                    runner(market,root/'out',root/'reports',prior_report=prior)
                self.assertFalse((root/'out').exists())

    def test_comparison_matches_frozen_report_identity(self):
        repo=Path(__file__).resolve().parents[1]
        paths={'round1':'discovery/results.json','round2':'discovery_round2/results.json',
               'round3':'discovery_round3/outcomes.json','round4':'discovery_round4/results.json'}
        reports={k:json.loads((repo/'reports'/p).read_text()) for k,p in paths.items()}
        rows=compare(reports,reports)
        self.assertEqual(len(rows),7)
        for row in rows:
            self.assertEqual(row['passed_before'],row['passed_after'])
            for period in row['periods'].values():
                self.assertEqual(period['n_delta'],0)
                self.assertEqual(period['mean_delta'],0)
