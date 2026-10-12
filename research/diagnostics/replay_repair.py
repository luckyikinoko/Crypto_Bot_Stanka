"""Replay the existing 35 hypotheses on the separately repaired development snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
from market_data.source import atomic_bytes
from research.patterns.__main__ import build
from research.statistics.__main__ import run as statistics
from research.discovery.__main__ import run as round1
from research.discovery_round2.__main__ import run as round2
from research.discovery_round3.outcomes import run as round3
from research.discovery_round4.__main__ import run as round4

REPO = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_destinations(market, destination, report_dir):
    paths = [Path(p).resolve() for p in (market, destination, report_dir)]
    for i, a in enumerate(paths):
        for b in paths[i+1:]:
            if a == b or a in b.parents or b in a.parents:
                raise ValueError('Separate non-nested input and output directories required')
    for p in paths[1:]:
        if p.exists() and any(p.iterdir()):
            raise ValueError('Replay requires fresh output directories')


def compare(old, new):
    """Summarize seven registered candidates; no new hypothesis or parameter search."""
    rows=[]
    for stage in ('round1','round2','round3','round4'):
        a,b=old[stage],new[stage]
        candidates = list(a['gates']) if stage in ('round1','round2') else [a['candidate']]
        for candidate in candidates:
            ga=a['gates'][candidate] if stage in ('round1','round2') else a['gates']
            gb=b['gates'][candidate] if stage in ('round1','round2') else b['gates']
            row={'stage':stage,'candidate':candidate,'passed_before':ga['passed'],
                 'passed_after':gb['passed'],'failed_before':ga['failed'],'failed_after':gb['failed'],'periods':{}}
            for period in ('training','reused_recent'):
                x=a['results'][candidate][period] if stage in ('round1','round2') else a['results'][period]['candidate']
                y=b['results'][candidate][period] if stage in ('round1','round2') else b['results'][period]['candidate']
                row['periods'][period]={'before':x,'after':y,
                    'n_delta':y['standard']['n']-x['standard']['n'],
                    'mean_delta':y['standard']['mean']-x['standard']['mean']}
            rows.append(row)
    return rows


def run(market='data/research_repaired_v1', destination='data/research_revision_v1',
        report_dir='reports/research_revision_v1'):
    market,destination,report_dir=map(Path,(market,destination,report_dir))
    validate_destinations(market,destination,report_dir)
    repair=json.loads((REPO/'reports/repair_v1/results.json').read_text())
    expected=json.loads((REPO/'reports/repair_v1/manifest.json').read_text())['snapshot_id']
    if json.loads((market/'catalog.json').read_text())['snapshot_id']!=expected:
        raise ValueError('Expected the reviewed repair snapshot')
    originals={'statistics':REPO/'reports/statistics/results.json',
        'round1':REPO/'reports/discovery/results.json','round2':REPO/'reports/discovery_round2/results.json',
        'round3':REPO/'reports/discovery_round3/outcomes.json','round4':REPO/'reports/discovery_round4/results.json'}
    protected=[*originals.values(),market/'catalog.json',REPO/'data/research/catalog.json',
               *REPO.glob('research/discovery*/REGISTRY.json')]
    hashes={str(p.relative_to(REPO)) if p.is_absolute() else str(p):digest(p) for p in protected}
    old={k:json.loads(p.read_text()) for k,p in originals.items()}
    patterns,_=build(market,destination/'patterns')
    atomic_bytes(report_dir/'patterns.json',(json.dumps(patterns,indent=2)+'\n').encode())
    revised={}
    revised['statistics']=statistics(market,destination/'patterns',destination/'statistics',report_dir/'statistics')
    revised['round1']=round1(destination/'statistics',market,destination/'round1',report_dir/'round1',
                             prior_report=report_dir/'statistics/results.json')
    revised['round2']=round2(market,destination/'round2',report_dir/'round2',prior_report=report_dir/'round1/results.json')
    revised['round3']=round3(destination/'round2',destination/'round3',report_dir/'round3',prior_report=report_dir/'round2/results.json')
    revised['round4']=round4(market,destination/'round4',report_dir/'round4',prior_report=report_dir/'round3/outcomes.json')
    if any(digest(REPO/p)!=value for p,value in hashes.items()):
        raise ValueError('Protected input changed during replay')
    old_ids=[x['id'] for x in old['round4']['test_ledger']]
    new_ids=[x['id'] for x in revised['round4']['test_ledger']]
    if old_ids!=new_ids or len(new_ids)!=35:
        raise ValueError('Hypothesis family changed')
    if any(revised[k]['costs']!=old[k]['costs'] for k in ('round2','round3','round4')):
        raise ValueError('Costs changed')
    rows=compare(old,revised)
    report={'market_snapshot':expected,'protected_sha256':hashes,
        'revised_snapshots':{k:(v['snapshot']['snapshot_id'] if k=='statistics' else v['snapshot_id']) for k,v in revised.items()},
        'candidates':rows,'test_ledger':revised['round4']['test_ledger'],
        'hypothesis_count':35,'new_hypotheses':0,'selected_strategy':None,
        'note':'Data revision sensitivity analysis, not independent replication or fresh out-of-sample evidence. 2024-2026Q1 is reused. Reserved data from 2026-04-01 remains blocked.',
        'code_sha256':{str(p.relative_to(REPO)):digest(p) for p in sorted(REPO.glob('research/**/*.py'))}}
    atomic_bytes(report_dir/'comparison.json',(json.dumps(report,indent=2,allow_nan=False)+'\n').encode())
    lines=['# Repaired-data research replay','',report['note'],'',
           'All existing rules, execution costs, bootstrap settings and acceptance criteria were retained. Original reports and data are preserved. This replay adds no hypotheses; the existing ledger still contains 35 tests. Earlier project experiments remain outside this ledger, as previously disclosed.','',
           '| Candidate | Training n before → after | Training mean net before → after | Recent mean net before → after | Pass after |',
           '|---|---:|---:|---:|---|']
    for r in rows:
        t=r['periods']['training'];v=r['periods']['reused_recent']
        lines.append(f"| {r['candidate']} | {t['before']['standard']['n']} → {t['after']['standard']['n']} | {t['before']['standard']['mean']:.6%} → {t['after']['standard']['mean']:.6%} | {v['before']['standard']['mean']:.6%} → {v['after']['standard']['mean']:.6%} | {r['passed_after']} |")
    lines += ['', 'No strategy is selected. These are overlapping signal outcome statistics, not portfolio returns. Detailed uncertainty, costs, non-overlap diagnostics and failed criteria are in comparison.json and each stage report.', '',
              'Reproduce from the repository root with `python -m research.diagnostics.replay_repair`. Existing output directories are rejected; use `--destination` and `--report-dir` with fresh paths for another run. Reconstruct the parent and repaired market snapshots first if local ignored datasets are absent.','']
    atomic_bytes(report_dir/'REPLAY.md','\n'.join(lines).encode())
    print(json.dumps({'candidates':len(rows),'passed':sum(x['passed_after'] for x in rows),'report':str(report_dir)}),flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--market',default='data/research_repaired_v1')
    p.add_argument('--destination',default='data/research_revision_v1')
    p.add_argument('--report-dir',default='reports/research_revision_v1')
    a=p.parse_args();run(a.market,a.destination,a.report_dir)
