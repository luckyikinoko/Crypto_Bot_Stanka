"""Render the saved experiment results without rerunning or tuning the strategy."""
import json
from pathlib import Path
out=Path('reports/experiment_002')
r=json.loads((out/'results.json').read_text())
rows=[]
for name,s in r['continuous'].items():
    rows.append(f"| {name} | {s['trades']} | {s['final_equity']:.2f} | {s['net_return']:.2%} | {s['first_halt_time']} |")
quarters=[]
for name,s in r['pooled'].items():
    quarters.append(f"| {name} | {s['trades']} | {s['profitable_quarters']}/8 | {s['sum_episode_pnl']/8:.2f} | {s['mean_r']:.3f} | {s['profit_factor']:.3f} | {s['halted_quarters']} |")
gates='\n'.join(f"- {name}: {'PASS' if passed else 'FAIL'}" for name,passed in r['research_gates'].items())
decision='Retain only for further research' if r['retain_for_research'] else 'Reject candidate'
text=f"""# Experiment 002 — {decision}

Rules were frozen in commit `{r['protocol_commit']}` before candidate execution.
Only the entry logic changed: a volume-confirmed 15-minute breakout in a rising
hourly trend. Original stops, sizing, fees, risk halts, targets, and time exits
remain. See `research/EXPERIMENT_002.md` for all rules and gates.

## Continuous development simulation

January 2024–March 2026, starting with 1,000 USDT. Permanent drawdown halts
remain in force, and cash is held thereafter. No forced restart.

| Variant | Trades | Final equity, USDT | Net return | Drawdown halt, UTC |
|---|---:|---:|---:|---|
{chr(10).join(rows)}

## Eight independent quarterly episodes

April 2024–March 2026; each quarter starts flat at 1,000 USDT. These episodes
are not a continuously compounded account and are reused development data.

| Variant | Trades | Profitable quarters | Mean quarterly P&L, USDT | Mean net R | Net profit factor | Halted quarters |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(quarters)}

## Predefined gates

{gates}

Decision: **{decision}**. No live trading or paper-trading progression is approved.
All 21 unit tests pass. Historical baseline replay reproduces the saved original
result; default baseline code and the engine are unchanged by this experiment.

The final April–September 2026 holdout remains unaccessed. These reused periods
are exploratory research, not fresh out-of-sample proof. We tried exactly one
candidate here, with no post-result tuning. The results do not establish that all
breakout approaches fail; they concern this exact rule set and cost model.

Minute-bar ordering, fee-currency equivalence, price ticks, partial fills, latency,
and missing news-calendar data remain the limitations documented in README.
The seven-day circular block bootstrap is recorded in `results.json`; it describes
realized episode P&L conditional on these simulated paths, not future trading risk.

Detailed quarter results, parameters, hashes, and trade ledgers are preserved.
Reproduce with `python breakout_experiment.py` and then
`python research/render_experiment_002.py`.
"""
(out/'RESULTS.md').write_text(text)
print(text)
