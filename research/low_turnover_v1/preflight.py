"""Registered daily EMA200 coverage check; no strategy signals or returns."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from market_data.schema import utc
from market_data.store import read_market, RESERVED_FROM
from market_data.source import atomic_bytes
from research.indicators import calculate


def count_coverage(features,start,end,origin):
    if start>=end or end>RESERVED_FROM or start!=start.floor('D') or end!=end.floor('D'):
        raise ValueError('Complete development calendar days required')
    t=features.available_at
    if str(t.dt.tz)!='UTC' or t.isna().any() or t.duplicated().any() or not t.is_monotonic_increasing:
        raise ValueError('Sorted unique UTC decision timestamps required')
    f=features[t.ge(start)&t.lt(end)]
    eligible=f[np.isfinite(f.ema_200)]
    days=int((end-start)/pd.Timedelta(days=1))
    if len(f)>days:raise ValueError('More than one daily decision per calendar day')
    return {'calendar_days':days,'observed_daily_decisions':len(f),'eligible_daily_decisions':len(eligible),
        'calendar_coverage':len(eligible)/days,'unavailable_or_warming_days':days-len(eligible),
        'active_28day_blocks':int(((eligible.available_at-origin).dt.total_seconds()//(28*86400)).nunique()),
        'eligible_by_year':{str(y):len(g) for y,g in eligible.groupby(eligible.available_at.dt.year)}}


def run():
    repo=Path(__file__).resolve().parents[2]
    reg_path=Path(__file__).with_name('REGISTRY.json');raw=reg_path.read_bytes();reg=json.loads(raw)
    protocol=Path(__file__).with_name('PROTOCOL.md')
    if hashlib.sha256(protocol.read_bytes()).hexdigest()!=reg['protocol_sha256']:raise ValueError('Protocol changed')
    market=repo/'data/research_repaired_v1';source=(market/'catalog.json').read_bytes()
    if json.loads(source)['snapshot_id']!=reg['market_snapshot']:raise ValueError('Wrong market snapshot')
    if hashlib.sha256((repo/reg['prior_report']).read_bytes()).hexdigest()!=reg['prior_report_sha256']:raise ValueError('Prior ledger changed')
    candles=read_market(market,'1d','2018-01-01',RESERVED_FROM,allow_gaps=True)
    features=calculate(candles,'1d')[['available_at','ema_200']]
    origin=utc(reg['preflight']['block_origin'])
    counts={p:count_coverage(features,utc(a),utc(b),origin) for p,(a,b) in reg['periods'].items()}
    limits=reg['preflight']
    checks={'training_calendar_coverage':counts['training']['calendar_coverage']>=limits['training_calendar_coverage'],
        'recent_calendar_coverage':counts['reused_recent']['calendar_coverage']>=limits['recent_calendar_coverage'],
        'training_active_28day_blocks':counts['training']['active_28day_blocks']>=limits['training_active_28day_blocks']}
    if raw!=reg_path.read_bytes() or source!=(market/'catalog.json').read_bytes():raise ValueError('Inputs changed')
    report={'candidate':reg['candidate'],'market_snapshot':reg['market_snapshot'],'registry_sha256':hashlib.sha256(raw).hexdigest(),
        'source_manifest_sha256':hashlib.sha256(source).hexdigest(),'code_sha256':{
          p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in ['research/low_turnover_v1/preflight.py','research/indicators/engine.py','market_data/store.py']},
        'counts':counts,'thresholds':limits,'checks':checks,'passed':all(checks.values()),
        'decision':'eligible_for_registered_portfolio_implementation' if all(checks.values()) else 'stop_insufficient_data_coverage',
        'new_strategy_signals':False,'portfolio_implemented':False,'backtest_run':False,'new_return_tests':0,'prior_return_tests':37,
        'selected_strategy':None,'reserved_pool_read':False,
        'note':'Counts use decision availability timestamps in half-open UTC pools; denominator includes every calendar day, including missing data and warm-up. Latest boundary candle is not a decision within the pool.'}
    out=repo/'reports/low_turnover_v1'
    atomic_bytes(out/'preflight.json',(json.dumps(report,indent=2)+'\n').encode())
    lines=['# Daily EMA200 coverage preflight','',
       'Specification registered in d1a56421a01d7154341281927498cdbb7c9042e6. Only indicator availability was counted; no entry rules, trades, portfolio returns or hypothesis tests were evaluated.','',
       '| Pool | Calendar days | Eligible daily decisions | Coverage | Required |','|---|---:|---:|---:|---:|']
    for p,required in [('training',.5),('reused_recent',.8)]:
        c=counts[p];lines.append(f"| {p} | {c['calendar_days']} | {c['eligible_daily_decisions']} | {c['calendar_coverage']:.2%} | {required:.0%} |")
    lines+=['',f"Training active 28-day blocks: {counts['training']['active_28day_blocks']}; required: 30.",'',
        f"Decision: **{report['decision']}**.",'',
        'EMA200 requires 200 complete contiguous daily candles after each reset. Sparse historical gaps can therefore remove substantially more indicator-ready days than the number of missing candles alone. No warm-up was shortened, price filled, period changed or replacement data acquired.','',
        ('The registered coverage check passes. A separate offline portfolio implementation is permitted within the bounded results checkpoint; no profitability conclusion follows.' if report['passed'] else 'The registered stopping rule applies: do not build the portfolio runner or run this backtest. Close this bounded experiment as insufficient data coverage, not as a losing strategy. The prior nine strategy rejections remain unchanged. Further work would require a new scope decision; no automatic replacement candidate.'),'',
        'The return-test ledger remains at 37. No portfolio, paper-trading or live-execution code was added. Reserved data stays sealed.','',
        report['note'],'', 'Reproduce: `python -m research.low_turnover_v1.preflight`.','']
    atomic_bytes(out/'PREFLIGHT.md','\n'.join(lines).encode())
    print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':run()
