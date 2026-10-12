"""Review five discovery rounds from saved reports; no market data or new tests."""
import hashlib
import json
from pathlib import Path
from market_data.source import atomic_bytes
from research.statistics.metrics import adjust_by

SOURCES=[f'reports/research_revision_v1/round{i}/'+('outcomes.json' if i==3 else 'results.json') for i in range(1,5)] + ['reports/discovery_round5/outcomes.json']


def validate_chain(reports):
    previous=[]
    for i,r in enumerate(reports):
        payload=dict(r);payload.pop('snapshot_id')
        if hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()!=r['snapshot_id']:
            raise ValueError('Invalid report snapshot')
        ledger=r['test_ledger'];pairs=[(x['id'],x['p']) for x in ledger]
        if len(ledger)!=[31,33,34,35,36][i] or len(set(x['id'] for x in ledger))!=len(ledger):
            raise ValueError('Hypothesis count or identity mismatch')
        if pairs[:len(previous)]!=previous:
            raise ValueError('Prior hypothesis changed')
        if [x['by_q'] for x in ledger]!=adjust_by([x['p'] for x in ledger]):
            raise ValueError('Multiplicity mismatch')
        if r['selected_strategy'] is not None:
            raise ValueError('Unexpected strategy activation')
        previous=pairs


def implied_gross(mean_net,cost):
    """Invert fixed proportional execution costs; linearity also holds for means."""
    friction=cost['half_spread']+cost['slippage']
    factor=(1-friction)*(1-cost['fee'])/((1+friction)*(1+cost['fee']))
    return (1+mean_net)/factor-1


def build(repo=None):
    repo=Path(repo) if repo else Path(__file__).resolve().parents[2]
    raw=[(repo/p).read_bytes() for p in SOURCES];reports=[json.loads(x) for x in raw]
    validate_chain(reports)
    market=reports[-1]['market_snapshot']
    for i,r in enumerate(reports):
        source=r['provenance']['market_snapshot'] if i<3 else r['market_snapshot']
        if source!=market:raise ValueError('Mixed market snapshots')
    rows=[]
    for number,r in enumerate(reports,1):
        names=list(r['gates']) if number<=2 else [r['candidate']]
        for name in names:
            if number<=2:
                t=r['results'][name]['training'];v=r['results'][name]['reused_recent']
                inf=r['comparisons'][name]['28'];gate=r['gates'][name]
            else:
                t=r['results']['training']['candidate'];v=r['results']['reused_recent']['candidate']
                inf=r['comparisons']['28'];gate=r['gates']
            cost=r.get('costs',reports[-1]['costs'])['standard']
            rows.append({'round':number,'candidate':name,'training':t,'reused_recent':v,
                'inference28':inf,'gates':gate,
                'implied_gross_mean':{p:implied_gross(s['standard']['mean'],cost) for p,s in [('training',t),('reused_recent',v)]},
                'limitations':{
                    'insufficient_sample':any(x in gate['failed'] for x in ('training_count','training_nonoverlap_count','active_blocks','recent_count')),
                    'negative_training_net':t['standard']['mean']<0,
                    'negative_recent_net':v['standard']['mean']<0,
                    'uncertainty_or_multiplicity':any(x in gate['failed'] for x in ('positive_net_ci','positive_excess_ci','multiplicity'))},
                'source':SOURCES[number-1]})
    if len(rows)!=8 or any(x['gates']['passed'] for x in rows):
        raise ValueError('Expected eight rejected candidates; review narrative needs revision')
    latest=reports[-1]['test_ledger']
    stats_path=repo/'reports/research_revision_v1/statistics/results.json'
    stats_raw=stats_path.read_bytes();stats=json.loads(stats_raw)
    significant=[]
    for test in latest:
        if test['by_q']<.05:
            entry=dict(test)
            if test['id'].startswith('M4/'):
                _,signal,horizon=test['id'].split('/')
                s=next(x for x in stats['summaries'] if x['signal']==signal and x['hours']==int(horizon[:-1]))
                entry['standard_mean_net']=s['costs']['standard']['mean']
                entry['interpretation']='Relative excess over baseline; not proof of positive net expectancy'
            significant.append(entry)
    evidence={'scope':'Saved-report reconciliation and algebraic cost decomposition only; no new hypothesis, market scan, outcome or p-value.',
        'market_snapshot':market,'sources':[{'path':p,'sha256':hashlib.sha256(b).hexdigest(),'snapshot_id':r['snapshot_id']} for p,b,r in zip(SOURCES,raw,reports)],
        'statistics_report_sha256':hashlib.sha256(stats_raw).hexdigest(),'candidates':rows,'tracked_test_ledger':latest,
        'tracked_tests':36,'new_tests':0,'candidate_count':8,'passed_candidates':0,'selected_strategy':None,
        'significant_relative_comparisons':significant,
        'recommendation':'Close this eight-candidate set without tuning. Further discovery requires a separately registered, distinct hypothesis; a bounded causal chart-pattern definition and feature-only feasibility checkpoint may be proposed after review. No automatic new experiment or reserved-pool access.'}
    out=repo/'reports/research_review_round5'
    atomic_bytes(out/'evidence.json',(json.dumps(evidence,indent=2,allow_nan=False)+'\n').encode())
    pct=lambda x:f'{x*100:+.3f}%'
    lines=['# Five-round evidence review','',
        '**All eight candidates remain rejected. No robust profitable edge has been established and no strategy is promoted.**','',
        'This review uses the repaired-data replay for rounds 1–4 and the registered round-5 result. It preserves the earlier original-data review and every negative result. No new market scan or hypothesis test is performed.','',
        '| Candidate | Train n | Standard net mean | Conditional BNB mean | Stress mean | Recent standard mean |',
        '|---|---:|---:|---:|---:|---:|']
    for x in rows:
        t=x['training'];v=x['reused_recent'];lines.append(f"| {x['candidate']} | {t['standard']['n']} | {pct(t['standard']['mean'])} | {pct(t['bnb_conditional']['mean'])} | {pct(t['stress']['mean'])} | {pct(v['standard']['mean'])} |")
    lines+=['','Means describe potentially overlapping events, not portfolio performance. Round 1 uses 15m signals with 2ATR/3ATR barriers and a 24h limit; rounds 2–3 use 4h signals and 72h holds; rounds 4–5 use 1h signals and 24h holds. Different exposures prevent ranking strategies by these means alone.','',
        '## Sample size versus uncertainty','',
        '| Candidate | Train nonoverlap n | Active 28-day blocks | Training net mean 95% interval | Sample gate failed? |',
        '|---|---:|---:|---|---|']
    for x in rows:
        ci=x['inference28'].get('net_ci95');ci='Unavailable: insufficient blocks' if ci is None else pct(ci[0])+' to '+pct(ci[1])
        lines.append(f"| {x['candidate']} | {x['training']['nonoverlap']['n']} | {x['inference28'].get('active_blocks',0)} | {ci} | {x['limitations']['insufficient_sample']} |")
    lines+=['',
        'Three candidates fail at least one registered sample requirement: range RSI recovery, filtered 4h breakout and filtered 4h RSI recovery. Their positive training averages cannot override sparse evidence. The unfiltered 4h breakout has a positive mean but its net/excess intervals cross zero and its multiplicity criterion fails. The two 1h recovery candidates have substantial samples, yet negative training net averages. More occurrences alone would not establish an edge.',
        '', '## Transaction-cost attribution','',
        'The existing proportional cost formula can be inverted algebraically to recover mean gross return from mean net return. This adds no return test. It does not simulate a fee-free strategy, maker fills or market impact.','',
        '| 1h candidate / pool | Implied gross mean | Standard net mean | Conditional BNB net mean |','|---|---:|---:|---:|']
    for x in rows[-2:]:
        for pool in ('training','reused_recent'):
            s=x[pool];lines.append(f"| {x['candidate']} / {pool} | {pct(x['implied_gross_mean'][pool])} | {pct(s['standard']['mean'])} | {pct(s['bnb_conditional']['mean'])} |")
    lines+=['',
        'Round 5 has small positive gross averages but negative net averages in both periods, including the conditional BNB scenario. That suggests cost drag exceeds its observed average move; it does not prove the gross relationship is statistically reliable. Reducing fees in a spreadsheet is not evidence that better execution is attainable. Do not waive standard/stress gates to rescue a rule.',
        '', '## Statistical accounting','',
        'The ledger contains 28 descriptive signal/horizon comparisons and eight discovery candidates: 36 tests. Earlier IDs and p-values survive unchanged along the revised-report chain; BY q-values are recalculated as the family grows. Data revisions remain explicitly separate from original results. Earlier legacy experiments fall outside this family. Adaptive rule choice and repeated data reuse are not cured by the correction.','',
        'One descriptive comparison still has q < 0.05: bearish engulfing at 1h versus its unconditional baseline. Its net average is negative. Relative outperformance of a losing baseline is not a profitable long strategy. None of the eight candidates passes its full gate set.','',
        'Training is 2018–2023. Recent 2024–2026 Q1 has been reused repeatedly and is not fresh validation. Data from 2026-04-01 onward stays sealed.','',
        '## Data and execution limits','',
        'The verified repair added 240 5m candles and corrected seven, leaving 1,620 missing 5m candles. It did not increase fully warmed trend/volatility decision coverage. Replaying the first seven candidates preserved their mean returns and rejection decisions. Round 5 excluded nine training signals because of incomplete 5m paths. Excluding missing paths can create selection bias; none of these screens models managing an open position through an outage.','',
        'Nonoverlap schedules reduce repeated exposure but do not guarantee independent observations. Bootstrap intervals are approximate in changing markets. Closed-trade drawdowns omit intratrade portfolio risk. Conditional BNB fees depend on eligibility and inventory; actual historical fees, depth, market impact and maker fills are not established. Buy-and-hold is retained as exposure context, not comparable to event-average returns.','',
        '## Decision and next checkpoint','',
        'Close this eight-candidate set without parameter tuning or trading promotion. This result does not show that all BTC opportunities are absent; it shows these specified rules have not met the evidence requirements.','',
        'If research continues, the next bounded proposal is to expand the objective chart-pattern catalog with one causal definition, such as a confirmed double bottom, and test its recognition on synthetic examples before scanning history. First register confirmation timing, tolerances, warm-up, outcome horizon, costs and stopping rules. Do not choose parameters from favorable historical examples. Sparse feasibility should stop that candidate; sufficient frequency would only justify a separate outcome review. This review does not register or implement that next hypothesis.','',
        'No live/paper trading, holdout opening, automatic search or strategy selection is part of this checkpoint.','',
        'Machine-readable evidence: [evidence.json](evidence.json). Reproduce: `python -m research.diagnostics.review_round5`.','']
    atomic_bytes(out/'REVIEW.md','\n'.join(lines).encode())
    print(json.dumps({'candidates':8,'tracked_tests':36,'new_tests':0,'passed':0,'ledger_continuity':'passed'}))
    return evidence


if __name__=='__main__':build()
