"""Verify and render the completed, frozen round-three outcome screen."""
import hashlib
import json
from pathlib import Path
import pandas as pd
from market_data.schema import utc
from market_data.source import atomic_bytes
from market_data.store import RESERVED_FROM
from research.discovery.__main__ import summarize
from research.discovery.engine import evaluate_gates
from research.statistics.metrics import adjust_by


def review(root='data/research_discovery_round3', report_dir='reports/discovery_round3'):
    root,report_dir=Path(root),Path(report_dir)
    raw=(root/'catalog.json').read_bytes()
    r=json.loads(raw);payload=dict(r);payload.pop('snapshot_id')
    if hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()!=r['snapshot_id']:
        raise ValueError('Snapshot digest mismatch')
    if raw!=(report_dir/'outcomes.json').read_bytes():
        raise ValueError('Published report mismatch')
    m=r['provenance']['files']['candidate_observations'];p=root/m['path']
    if hashlib.sha256(p.read_bytes()).hexdigest()!=m['sha256']:
        raise ValueError('Observation checksum mismatch')
    f=pd.read_parquet(p)
    if len(f)!=m['rows'] or f.observation_id.duplicated().any():
        raise ValueError('Count or duplicate mismatch')
    if not f.signal.all() or not f.breakout.eq(1).all() or not f.status.eq('complete').all():
        raise ValueError('Invalid candidate')
    if not f.entry_at.eq(f.decision_at+pd.Timedelta(minutes=5)).all():
        raise ValueError('Entry delay mismatch')
    if not f.label_end.eq(f.entry_at+pd.Timedelta(hours=72)).all():
        raise ValueError('Holding period mismatch')
    if (f.decision_at>=RESERVED_FROM).any() or (f.label_end>RESERVED_FROM).any():
        raise ValueError('Reserved boundary violation')
    registry=json.loads(Path(__file__).with_name('REGISTRY.json').read_text())
    if hashlib.sha256(Path(__file__).with_name('REGISTRY.json').read_bytes()).hexdigest()!=r['provenance']['registry_sha256']:
        raise ValueError('Registry mismatch')
    for period,(start,end) in registry['periods'].items():
        part=f[f.pool==period]
        if (part.decision_at<utc(start)).any() or (part.label_end>utc(end)).any():
            raise ValueError('Pool boundary violation')
        if summarize(part)!=r['results'][period]['candidate']:
            raise ValueError('Candidate metrics mismatch')
    ledger=r['test_ledger']
    if len(ledger)!=34 or len({x['id'] for x in ledger})!=34:
        raise ValueError('Hypothesis count mismatch')
    if adjust_by([x['p'] for x in ledger])!=[x['by_q'] for x in ledger]:
        raise ValueError('Multiplicity mismatch')
    expected=evaluate_gates(r['results']['training']['candidate'],r['results']['reused_recent']['candidate'],
        r['comparisons']['28'],ledger[-1]['by_q'],{'gates':registry['outcome_gates_if_later_authorized']})
    if expected!=r['gates'] or r['selected_strategy'] is not None:
        raise ValueError('Gate/activation mismatch')
    validation={'snapshot_id':r['snapshot_id'],'status':'passed','candidate_rows':len(f),
                'test_family':34,'metrics_recomputed':True,'boundary_checks_passed':True}
    atomic_bytes(report_dir/'outcome_verification.json',(json.dumps(validation,indent=2)+'\n').encode())
    pct=lambda x:f'{x*100:+.3f}%'
    lines=['# Round 3 — standalone 4h breakout outcomes','',
           '**Decision: '+r['decision']+'. No strategy selected.**','',
           'The user authorized this outcome screen after the feature-only checkpoint. The rule and future execution were registered in 4571eae; feasibility was saved in c43a33a. The original registry remains unchanged as a record of that earlier scope.',
           '',
           'A completed 4h close above the preceding 20 highs triggers an observation. Entry is delayed five minutes; exit is after a fixed 72 hours. There are no extra indicator filters or alternate exits. This screen reuses checksum-verified 5m path labels from round 2, verifies their timing, and independently recomputes cost-adjusted returns from entry and exit prices.',
           '',
           '## Per-observation returns','',
           '| Pool | Complete signals | Mean net | Stress mean | Unconditional mean net | Nonoverlap n | Nonoverlap mean net |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for name,v in r['results'].items():
        c=v['candidate'];u=v['unconditional']
        lines.append(f"| {name} | {c['standard']['n']} | {pct(c['standard']['mean'])} | {pct(c['stress']['mean'])} | {pct(u['standard']['mean'])} | {c['nonoverlap']['n']} | {pct(c['nonoverlap']['mean'])} |")
    ci=r['comparisons']['28'];sens=r['comparisons']['7']
    lines += ['',
        'Training is 2018–2023; reused recent is 2024–2026 Q1. Observations can overlap. Nonoverlap uses the full 72-hour hold plus 60-minute cooldown. These means are not portfolio returns.',
        '',
        '## Statistical decision','',
        f"- Training mean net 95% interval: {pct(ci['net_ci95'][0])} to {pct(ci['net_ci95'][1])}.",
        f"- Excess over unconditional 4h decisions: {pct(ci['excess_mean'])}; 95% interval {pct(ci['excess_ci95'][0])} to {pct(ci['excess_ci95'][1])}.",
        f"- Primary 28-day bootstrap: {ci['active_blocks']} active blocks, {ci['draws']} draws; approximate one-sided p={ci['p_one_sided']:.4f}; cumulative 34-test BY q={ledger[-1]['by_q']:.3f}.",
        f"- Seven-day sensitivity net interval: {pct(sens['net_ci95'][0])} to {pct(sens['net_ci95'][1])}.",
        f"- Failed registered gates: {', '.join(r['gates']['failed'])}.",
        '',
        'Positive sample averages do not establish a robust edge: both primary intervals include zero and the multiple-testing criterion fails. No threshold, hold duration or exit was changed after observing results. Adaptive reuse remains even after BY correction; none of this is fresh out-of-sample confirmation.',
        '',
        '## Integrity and costs','',
        '17 training breakout observations are excluded for missing 5m path candles, leaving 598. All 265 reused-recent signals have complete paths. Signals crossing split boundaries are excluded. Missing candles are never filled.',
        '',
        'Standard per-side assumptions: 0.10% fee plus 0.005% half-spread and 0.015% slippage. Conditional BNB fee is 0.075%; it is not assumed always available. Stress uses 0.10% fee, 0.01% half-spread and 0.04% slippage. Detailed cost scenarios, yearly summaries, MFE/MAE distributions, win rates, profit factors and quality exclusions are in outcomes.json.',
        '',
        'Buy-and-hold context is preserved from the earlier report. Its period-total return is not comparable directly to a per-observation mean. Closed-trade drawdown is descriptive and omits intratrade portfolio marks; this is not Milestone 6 portfolio validation.',
        '',
        '100 tests pass. Verification checks snapshot/file hashes, recomputes candidate summaries and all gates, confirms 34-test accounting, and checks timing and pool boundaries. A separate replay is recorded in outcome_replay.json.',
        '',
        '## Review checkpoint','',
        'The registered breakout candidate is rejected for promotion. The next useful decision is whether to pause discovery or authorize a materially different, independently motivated hypothesis. Do not tune this candidate to rescue its historical results. Reserved data from 2026-04-01 onward remains sealed; paper and live trading remain inactive.',
        '',
        'Reproduce: python -m research.discovery_round3.outcomes; python -m research.discovery_round3.review',
        '',f"Snapshot: {r['snapshot_id']}",'']
    atomic_bytes(report_dir/'OUTCOMES.md','\n'.join(lines).encode())
    print(json.dumps(validation))
    return validation


if __name__=='__main__':
    review()
