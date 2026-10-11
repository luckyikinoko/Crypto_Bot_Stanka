"""Reconcile existing discovery reports without evaluating new hypotheses."""
import hashlib
import json
from pathlib import Path
from research.statistics.metrics import adjust_by
from market_data.source import atomic_bytes

SOURCES=['reports/discovery/results.json','reports/discovery_round2/results.json',
         'reports/discovery_round3/outcomes.json','reports/discovery_round4/results.json']


def build(repo=None):
    repo=Path(repo) if repo else Path(__file__).resolve().parents[2]
    rows=[];sources=[];previous=[];latest=None
    for number,path in enumerate(SOURCES,1):
        raw=(repo/path).read_bytes();r=json.loads(raw);payload=dict(r);payload.pop('snapshot_id')
        if hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()!=r['snapshot_id']:
            raise ValueError('Invalid snapshot: '+path)
        ledger=[{'id':t['id'],'p':t['p']} for t in r['test_ledger']]
        if ledger[:len(previous)]!=previous:
            raise ValueError('Historical hypothesis lost or changed')
        if len({t['id'] for t in ledger})!=len(ledger):
            raise ValueError('Duplicate hypothesis')
        if adjust_by([t['p'] for t in ledger])!=[t['by_q'] for t in r['test_ledger']]:
            raise ValueError('BY accounting mismatch')
        if r['selected_strategy'] is not None:
            raise ValueError('Unexpected strategy selection')
        previous=ledger;latest=r['test_ledger']
        sources.append({'path':path,'sha256':hashlib.sha256(raw).hexdigest(),'snapshot_id':r['snapshot_id']})
        candidates=list(r['gates']) if number<=2 else [r['candidate']]
        for c in candidates:
            if number<=2:
                train=r['results'][c]['training'];recent=r['results'][c]['reused_recent']
                inference=r['comparisons'][c]['28'];gate=r['gates'][c]
            else:
                train=r['results']['training']['candidate'];recent=r['results']['reused_recent']['candidate']
                inference=r['comparisons']['28'];gate=r['gates']
            if gate['passed']:
                raise ValueError('Review needs updating for a passing candidate')
            rows.append({'round':number,'candidate':c,
                'execution':['15m; 2ATR stop/3ATR take; max24h','4h; fixed72h','4h; fixed72h','1h; fixed24h'][number-1],
                'training_n':train['standard']['n'],'training_mean_net':train['standard']['mean'],
                'training_mean_stress':train['stress']['mean'],
                'training_nonoverlap_n':train['nonoverlap']['n'],
                'training_nonoverlap_mean':train['nonoverlap']['mean'],
                'recent_n':recent['standard']['n'],'recent_mean_net':recent['standard']['mean'],
                'recent_mean_stress':recent['stress']['mean'],
                'active_blocks':inference.get('active_blocks',0),'net_ci95':inference.get('net_ci95'),
                'failed_gates':gate['failed'],'source':path})
    if len(rows)!=7 or len(latest)!=35:
        raise ValueError('Expected four rounds, seven candidates and 35 tests')
    report={'scope':'Reconciliation only; no new data scan, hypothesis, p-value or strategy selection',
            'sources':sources,'candidates':rows,'tracked_test_ledger':latest,
            'tracked_tests':35,'discovery_candidates':7,'passed_candidates':0,
            'legacy_experiments_not_in_35_test_family':[
                'reports/experiment_001/RESULTS.md','reports/experiment_002/RESULTS.md',
                'reports/bnb_fee_v1/RESULTS.md'],
            'selected_strategy':None,'recommended_next_step':'Development-only data coverage and warm-up audit'}
    out=repo/'reports/research_review'
    atomic_bytes(out/'evidence.json',(json.dumps(report,indent=2)+'\n').encode())
    pct=lambda x:f'{100*x:+.3f}%'
    lines=['# BTC Research Engine — consolidated discovery review','',
        '**No statistically robust trading edge has been established. All seven registered discovery candidates failed their screening criteria. No strategy advances to portfolio validation, paper trading or live execution.**',
        '',
        'This review reconciles four completed discovery rounds. It adds no hypothesis tests, changes no rules, and reads no market or reserved outcome data.',
        '',
        '## Evidence at a glance','',
        '| Candidate | Decision / exit | Train n | Train net mean | Stress mean | Recent n | Recent net mean |',
        '|---|---|---:|---:|---:|---:|---:|']
    for row in rows:
        lines.append(f"| {row['candidate']} | {row['execution']} | {row['training_n']} | {pct(row['training_mean_net'])} | {pct(row['training_mean_stress'])} | {row['recent_n']} | {pct(row['recent_mean_net'])} |")
    lines+=['',
        'Means are per potentially overlapping observation after costs. Different holding periods and exits prevent a direct ranking by these means. They are not annual returns, portfolio equity growth, or risk-adjusted performance.',
        '',
        '## Why candidates failed','',
        '| Candidate | Training nonoverlap n | Active 28-day blocks | Training mean net 95% interval | Main limitation |',
        '|---|---:|---:|---|---|']
    reasons=['Negative net expectancy in both pools','Negative net expectancy in both pools',
             'Sparse training and negative recent result','Too few independent episodes',
             'Sparse; negative recent and nonoverlap training result',
             'Net/excess intervals cross zero; multiple-testing gate fails',
             'Negative training expectancy; recent result fails stressed costs']
    for row,reason in zip(rows,reasons):
        ci=row['net_ci95'];interval='Unavailable: insufficient active blocks' if ci is None else pct(ci[0])+' to '+pct(ci[1])
        lines.append(f"| {row['candidate']} | {row['training_nonoverlap_n']} | {row['active_blocks']} | {interval} | {reason} |")
    lines+=['',
        'The positive 4h breakout average is an uncertain exploratory result. It is not a selected strategy or evidence that its parameters should be optimized. The lower-band re-entry test had ample occurrences and still failed after costs. These results reject the specified rules under the stated assumptions; they do not establish that all momentum or mean-reversion approaches are unprofitable.',
        '',
        '## Research accounting','',
        '- 28 Milestone 4 signal/horizon tests plus seven discovery candidates make the current 35-test exploratory family.',
        '- The reconciliation verifies that every earlier ID and p-value survives unchanged in later ledgers; q-values are recalculated as the family grows.',
        '- Earlier baseline, Experiment 001, Experiment 002 and BNB scenario work predates this family. The 35-test correction is not a claim to cover all historical project experimentation.',
        '- Adaptive choice of new rules after seeing old results is not undone by BY correction. It cannot manufacture independent confirmation.',
        '',
        'Training is 2018–2023. The 2024–2026 Q1 period has been repeatedly reused and must not be called fresh validation. Data from 2026-04-01 onward remains sealed. No final holdout should be opened to rescue a failed candidate.',
        '',
        '## Data and execution limitations','',
        'The sample audit found 5,595 of 13,078 training 4h decisions (42.8%) without a volatility classification, with 31 contiguous segments. Repeated gap resets and warm-up materially reduce usable feature history. That is a coverage limitation, not evidence to waive warm-up. The simple breakout avoids this volatility filter but still fails the statistical screen.',
        '',
        'All screens require complete 5m execution paths. Missing paths are excluded, creating potential selection bias if outages coincide with unusual conditions. A future portfolio simulator must define what an already-open position does through an outage; these event screens do not solve that execution problem.',
        '',
        'Standard per-side costs are 0.10% fee, 0.005% half-spread and 0.015% slippage. The BNB scenario uses 0.075% fees conditionally; stress adds wider spread/slippage. Account-specific and historical fee eligibility are not proven. BNB inventory/depletion and realistic market impact are not modeled.',
        '',
        'Nonoverlap scheduling reduces duplicated exposure but does not guarantee independent observations. Calendar-block intervals are approximate, particularly in changing regimes. Closed-trade drawdown omits intratrade portfolio marks. Buy-and-hold period totals cannot be compared directly with event-average returns.',
        '',
        '## Recommended next checkpoint: coverage audit','',
        'Pause new strategy hypotheses for one development-only data-quality checkpoint:',
        '',
        '1. Inventory missing 5m, 1h and 4h intervals and every segment reset from 2018 through 2026 Q1. Reconcile higher-timeframe omissions with missing or rejected 5m members.',
        '2. Classify documented causes: source/archive absence, quarantined rows, aggregation requirements or confirmed exchange gaps. Leave unresolved causes explicitly unknown.',
        '3. Recover only candles verifiable from official sources. Never synthesize prices, forward-fill gaps, bridge unverified missing periods or shorten warm-up to improve results.',
        '4. Report decision coverage before/after warm-up by year and timeframe without calculating new strategy returns. Preserve old snapshots; version any verified repair.',
        '5. If data changes, reproduce affected experiments under their unchanged rules and label those runs as data revisions. Preserve the original negative results and disclose the extra analysis.',
        '',
        'After that audit, decide whether to stop discovery or register a bounded new family with an economic rationale, minimum sample plan and explicit stopping rule. Further parameter search on the current candidates is not the recommended next action. The audit recommendation is not authorization for live trading or opening reserved data.',
        '',
        '## Implementation status','',
        '| Area | Current status |',
        '|---|---|',
        '| Historical database / indicators | Implemented; development coverage audit recommended |',
        '| Pattern engine | Initial subset implemented; not the full requested pattern catalog |',
        '| Outcomes and statistical screening | Implemented with costs, path checks and cumulative ledger |',
        '| Strategy discovery | Four rounds completed; no candidate selected |',
        '| Milestone 6 formal candidate validation | No candidate promoted; earlier legacy backtests remain reference work |',
        '| Paper / live trading | Inactive |',
        '',
        'The latest implementation checkpoint passed 104 unit tests and byte-identical round-four replay. This consolidation additionally verifies report digests, counts, ledger continuity and corrected q-values; it does not rerun market calculations.',
        '',
        '## Source reports','']
    for s in sources:
        label=s['path'];relative='../'+str(Path(label).relative_to('reports'))
        lines.append(f"- [{label}]({relative}) — snapshot {s['snapshot_id']}.")
    lines+=['','Machine-readable evidence: [evidence.json](evidence.json). Reproduce: python -m research.diagnostics.consolidate.','']
    atomic_bytes(out/'REVIEW.md','\n'.join(lines).encode())
    print(json.dumps({'candidates':7,'tracked_tests':35,'passed':0,'source_digests_verified':4,'ledger_continuity':'passed'}))
    return report


if __name__=='__main__':
    build()
