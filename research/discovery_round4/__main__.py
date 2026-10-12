"""Run the registered feature-feasibility and conditional outcome screen."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import numpy as np
import pandas as pd
import pyarrow
from market_data.schema import utc
from market_data.store import read_market,writer_lock,RESERVED_FROM
from market_data.source import atomic_bytes
from research.indicators import calculate
from research.statistics.outcomes import label_paths,SCENARIOS
from research.statistics.metrics import block_compare,adjust_by
from research.statistics.__main__ import save_frame
from research.discovery.__main__ import summarize
from research.discovery.engine import evaluate_gates
from research.discovery_round3.__main__ import feasibility
from research.discovery_round3.outcomes import select_pool,LABEL_COLUMNS
from .engine import signal_mask,frequency

CANDIDATE='lower_band_reentry_1h'


def run(market='data/research',out='data/research_discovery_round4',report_dir='reports/discovery_round4',prior_report=None):
    market,out,report_dir=map(Path,(market,out,report_dir))
    if market.resolve()==out.resolve():
        raise ValueError('Separate destination required')
    repo=Path(__file__).resolve().parents[2]
    reg_path=Path(__file__).with_name('REGISTRY.json');reg_bytes=reg_path.read_bytes();reg=json.loads(reg_bytes)
    if reg['candidate']!=CANDIDATE or reg['execution']!={'hold_hours':24,'delay_minutes':5,'cooldown_minutes':60,'secondary_exit':None}:
        raise ValueError('Only registered round-four implementation supported')
    source_bytes=(market/'catalog.json').read_bytes();source=json.loads(source_bytes)
    prior_path=Path(prior_report) if prior_report is not None else repo/'reports/discovery_round3/outcomes.json'
    prior_bytes=prior_path.read_bytes();prior=json.loads(prior_bytes)
    if prior_report is not None and prior['provenance']['market_snapshot']!=source['snapshot_id']:
        raise ValueError('Prior report/market snapshot mismatch')
    if len(prior['test_ledger'])!=34:
        raise ValueError('Incomplete previous tests')
    if prior['costs']!={k:vars(v) for k,v in SCENARIOS.items()}:
        raise ValueError('Cost assumptions changed')
    periods={k:(utc(a),utc(b)) for k,(a,b) in reg['periods'].items()}
    with writer_lock(out):
        candles=read_market(market,'1h','2018-01-01',RESERVED_FROM,allow_gaps=True)
        features=calculate(candles,'1h')[['available_at','segment_id','bb_lower']]
        features['close']=candles.reset_index(drop=True).close
        features=features[features.available_at<RESERVED_FROM].reset_index(drop=True)
        features['observation_id']=features.available_at.astype(str)
        features['signal']=signal_mask(features)
        counts={p:frequency(features,a,b) for p,(a,b) in periods.items()}
        feasible=feasibility(counts,reg['feasibility_gates'])
        atomic_bytes(report_dir/'feasibility.json',(json.dumps({'counts':counts,'gates':feasible},indent=2)+'\n').encode())
        print(json.dumps({'feature_feasibility':feasible,'counts':counts}),flush=True)
        files={'features':save_frame(out,'features',features)}
        results={};quality={};comparisons={};gate=None
        ledger=[{'id':x['id'],'p':x['p']} for x in prior['test_ledger']]
        if feasible['passed']:
            execution=read_market(market,'5m','2018-01-01',RESERVED_FROM,allow_gaps=True)
            # A missing ATR prevents unused barrier calculations; fixed-hold labels require no ATR.
            obs=features[['observation_id','available_at']].assign(atr=np.nan)
            labels=label_paths(obs,execution,horizons=(24,),entry_delay_minutes=5)[LABEL_COLUMNS]
            labels['status']=labels.status.astype('string')
            joined=labels.merge(features[['observation_id','signal']],on='observation_id',validate='one_to_one')
            selected=[]
            for p,(start,end) in periods.items():
                base,quality[p+'/unconditional']=select_pool(joined,start,end)
                group,quality[p+'/'+CANDIDATE]=select_pool(joined[joined.signal],start,end)
                results[p]={'candidate':summarize(group),'unconditional':summarize(base)}
                selected.append(group.assign(pool=p))
                if p=='training':
                    b=reg['bootstrap']
                    comparisons={str(d):block_compare(group,base,d,b['draws'],b['seed']) for d in (28,7)}
            ledger.append({'id':'M5R4/'+CANDIDATE,'p':comparisons['28'].get('p_one_sided',1.)})
            for row,q in zip(ledger,adjust_by([x['p'] for x in ledger])):
                row['by_q']=q
            gate=evaluate_gates(results['training']['candidate'],results['reused_recent']['candidate'],
                 comparisons['28'],ledger[-1]['by_q'],{'gates':reg['outcome_gates']})
            files['labels']=save_frame(out,'labels',labels)
            files['candidate_observations']=save_frame(out,'candidate_observations',pd.concat(selected,ignore_index=True))
        else:
            for row,q in zip(ledger,adjust_by([x['p'] for x in ledger])):
                row['by_q']=q
        if prior_bytes!=prior_path.read_bytes() or source_bytes!=(market/'catalog.json').read_bytes() or reg_bytes!=reg_path.read_bytes():
            raise ValueError('Inputs changed')
        paths=[*repo.glob('research/discovery_round4/*.py'),repo/'research/indicators/engine.py',
               repo/'research/statistics/outcomes.py',repo/'research/statistics/metrics.py',
               repo/'research/discovery/__main__.py',repo/'research/discovery/engine.py',
               repo/'research/discovery_round3/__main__.py',repo/'research/discovery_round3/outcomes.py']
        report={'candidate':CANDIDATE,'registry':reg,'market_snapshot':source['snapshot_id'],
            'provenance':{'registry_sha256':hashlib.sha256(reg_bytes).hexdigest(),
                'prior_report_sha256':hashlib.sha256(prior_bytes).hexdigest(),
                'code_sha256':{str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)},
                'runtime':{'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,'pyarrow':pyarrow.__version__},
                'files':files},
            'feature_counts':counts,'feasibility':feasible,'results':results,'quality':quality,
            'comparisons':comparisons,'gates':gate,'test_ledger':ledger,'costs':prior['costs'],
            'buy_and_hold_context':prior['buy_and_hold_context'],'selected_strategy':None,
            'decision':'insufficient_feature_sample' if not feasible['passed'] else
                       ('requires_separate_validation' if gate['passed'] else 'candidate_rejected')}
        report['snapshot_id']=hashlib.sha256(json.dumps(report,sort_keys=True,allow_nan=False).encode()).hexdigest()
        encoded=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode()
        atomic_bytes(out/'manifests'/(report['snapshot_id']+'.json'),encoded)
        atomic_bytes(out/'catalog.json',encoded);atomic_bytes(report_dir/'results.json',encoded)
        print(json.dumps({'snapshot_id':report['snapshot_id'],'gates':gate,'decision':report['decision']}),flush=True)
        return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--market',default='data/research');p.add_argument('--destination',default='data/research_discovery_round4')
    p.add_argument('--report-dir',default='reports/discovery_round4')
    a=p.parse_args();run(a.market,a.destination,a.report_dir)
