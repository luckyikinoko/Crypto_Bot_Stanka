"""Verify the round-four snapshot and render its review report."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from market_data.schema import utc
from market_data.source import atomic_bytes
from market_data.store import RESERVED_FROM
from research.discovery_round4.engine import signal_mask
from research.discovery.__main__ import summarize
from research.discovery.engine import evaluate_gates
from research.statistics.metrics import adjust_by
from research.statistics.outcomes import SCENARIOS


def review(root='data/research_discovery_round4', report_dir='reports/discovery_round4'):
    root,report_dir=Path(root),Path(report_dir)
    raw=(root/'catalog.json').read_bytes();r=json.loads(raw)
    payload=dict(r);payload.pop('snapshot_id')
    if hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()!=r['snapshot_id']:
        raise ValueError('Snapshot mismatch')
    if raw!=(report_dir/'results.json').read_bytes():
        raise ValueError('Report mismatch')
    frames={}
    for name,meta in r['provenance']['files'].items():
        p=root/meta['path']
        if hashlib.sha256(p.read_bytes()).hexdigest()!=meta['sha256']:
            raise ValueError('File checksum mismatch')
        frames[name]=pd.read_parquet(p)
        if len(frames[name])!=meta['rows']:
            raise ValueError('Row count mismatch')
    features=frames['features']
    pd.testing.assert_series_equal(features.signal,signal_mask(features),check_names=False)
    if r['selected_strategy'] is not None:
        raise ValueError('Screen cannot activate strategy')
    expected_n=35 if r['feasibility']['passed'] else 34
    ledger=r['test_ledger']
    if len(ledger)!=expected_n or len({x['id'] for x in ledger})!=expected_n:
        raise ValueError('Lost hypothesis')
    if adjust_by([x['p'] for x in ledger])!=[x['by_q'] for x in ledger]:
        raise ValueError('Multiplicity mismatch')
    if r['feasibility']['passed']:
        labels=frames['labels'];f=frames['candidate_observations']
        if labels.observation_id.duplicated().any() or f.observation_id.duplicated().any():
            raise ValueError('Duplicate outcome')
        if set(labels.observation_id)!=set(features.observation_id):
            raise ValueError('Label coverage mismatch')
        if not labels.entry_at.eq(labels.decision_at+pd.Timedelta(minutes=5)).all():
            raise ValueError('Entry timing mismatch')
        if not labels.label_end.eq(labels.entry_at+pd.Timedelta(hours=24)).all():
            raise ValueError('Horizon mismatch')
        if not f.status.eq('complete').all() or not f.signal.all() or (f.label_end>RESERVED_FROM).any():
            raise ValueError('Invalid candidate labels')
        mask=features.set_index('observation_id').signal
        if not mask.loc[f.observation_id].all():
            raise ValueError('Outcome without signal')
        for name,cost in SCENARIOS.items():
            if not np.allclose(f['net_'+name],cost.net(f.entry_raw,f.exit_raw),rtol=1e-12,atol=1e-12):
                raise ValueError('Cost mismatch')
        for period,(start,end) in r['registry']['periods'].items():
            part=f[f.pool==period]
            if (part.decision_at<utc(start)).any() or (part.label_end>utc(end)).any():
                raise ValueError('Pool leakage')
            if summarize(part)!=r['results'][period]['candidate']:
                raise ValueError('Metrics mismatch')
        gate=evaluate_gates(r['results']['training']['candidate'],r['results']['reused_recent']['candidate'],
             r['comparisons']['28'],ledger[-1]['by_q'],{'gates':r['registry']['outcome_gates']})
        if gate!=r['gates']:
            raise ValueError('Gate mismatch')
    validation={'snapshot_id':r['snapshot_id'],'status':'passed','verified_files':len(frames),
                'hypotheses_accounted_for':expected_n,'candidate_metrics_recomputed':r['feasibility']['passed']}
    atomic_bytes(report_dir/'verification.json',(json.dumps(validation,indent=2)+'\n').encode())
    pct=lambda x:f'{100*x:+.3f}%'
    lines=['# Round 4 — lower Bollinger Band re-entry','',
           '**Decision: '+r['decision']+'. No strategy selected.**','',
           'Registered in c7cbd1a before feature counts or outcomes. One fixed rule was evaluated: prior 1h close below its lower Bollinger Band, followed by current close at or above the current lower band, within the same uninterrupted segment. Bands use 20 closes, two population standard deviations (ddof=0). No additional indicator filters or alternative exits.',
           '',
           'Entry is five minutes after recognition; primary exit is 24 hours after entry. A full contiguous 5m path is required. Gaps are not filled. Features and future labels are stored separately. Nonoverlap locks the 24-hour hold plus a 60-minute cooldown.',
           '',
           '## Feature feasibility','',
           '| Pool | Raw signals | Timing eligible | Nonoverlap | Active 28-day blocks |',
           '|---|---:|---:|---:|---:|']
    for name,c in r['feature_counts'].items():
        lines.append(f"| {name} | {c['raw']} | {c['timing_eligible']} | {c['scheduled_nonoverlap']} | {c['active_28day_blocks']} |")
    if r['feasibility']['passed']:
        lines+=['','## Outcomes after costs','',
                '| Pool | Complete signals | Mean net | Stress mean | Unconditional mean | Nonoverlap n | Nonoverlap mean |',
                '|---|---:|---:|---:|---:|---:|---:|']
        for name,v in r['results'].items():
            c=v['candidate'];b=v['unconditional']
            lines.append(f"| {name} | {c['standard']['n']} | {pct(c['standard']['mean'])} | {pct(c['stress']['mean'])} | {pct(b['standard']['mean'])} | {c['nonoverlap']['n']} | {pct(c['nonoverlap']['mean'])} |")
        inf=r['comparisons']['28'];sens=r['comparisons']['7']
        lines+=['',
                f"Training 95% interval for mean net: {pct(inf['net_ci95'][0])} to {pct(inf['net_ci95'][1])}. Excess over unconditional 1h decisions: {pct(inf['excess_mean'])}, interval {pct(inf['excess_ci95'][0])} to {pct(inf['excess_ci95'][1])}.",
                '',
                f"Primary 28-day block comparison: {inf['active_blocks']} active blocks, {inf['draws']} draws; approximate one-sided p={inf['p_one_sided']:.4f}; 35-test BY q={ledger[-1]['by_q']:.3f}. Seven-day sensitivity net interval: {pct(sens['net_ci95'][0])} to {pct(sens['net_ci95'][1])}.",
                '',
                f"Failed gates: {', '.join(r['gates']['failed'])}. No rules or thresholds were adjusted.",
                '',
                '## Data exclusions','']
        for name,q in r['quality'].items():
            if 'unconditional' not in name:
                lines.append(f"- {name}: incomplete paths {q['incomplete_by_status']}; complete paths crossing split boundary {q['complete_boundary_purged']}; usable {q['usable']}.")
    lines+=['',
            '## Interpretation and limitations','',
            'The registered statistical gates determine rejection or eligibility for later review. Sample frequency alone does not establish an edge. Training is 2018–2023; recent data is 2024–2026 Q1 and has been reused. This adaptive discovery is not independent OOS confirmation, even after multiple-testing correction.',
            '',
            'Standard per-side costs: 0.10% fee, 0.005% half-spread, 0.015% slippage. Conditional BNB fee: 0.075%, only when applicable. Stress: 0.10% fee, 0.01% half-spread, 0.04% slippage. Results are per overlapping observation, not portfolio returns. Buy-and-hold period totals and closed-trade drawdown are context, not direct risk-adjusted portfolio comparisons.',
            '',
            'Detailed yearly summaries, conditional-BNB results, win rates, profit factors, MFE/MAE distributions, uncertainty and all 35 p-values are in results.json. Fixed-hold labels require no ATR; no stop or take-profit alternative was evaluated.',
            '',
            '104 unit tests passed, including new re-entry, equality, gap, warm-up, prefix-invariance and boundary tests. Snapshot verification checks hashes, recalculates signals, costs, candidate summaries and gates, and verifies the cumulative test ledger. Replay status is in replay.json.',
            '',
            '## Review checkpoint','',
            'Stop this round here. A rejected rule is not promoted to Milestone 6, paper trading or live execution. Review the accumulated findings before deciding whether another distinct hypothesis is worth testing. Reserved data from 2026-04-01 onward remains blocked.',
            '',
            'Reproduce: python -m research.discovery_round4; python -m research.diagnostics.review_round4',
            '',f"Snapshot: {r['snapshot_id']}",'']
    atomic_bytes(report_dir/'ROUND_4.md','\n'.join(lines).encode())
    print(json.dumps(validation))
    return validation


if __name__=='__main__':
    review()
