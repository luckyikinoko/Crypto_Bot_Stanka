"""Deterministic cost decomposition of fixed historical fills; no new strategy search."""
import json
from pathlib import Path
import pandas as pd


def break_even(fee,slippage,base_fee=False):
    if not 0<=fee<1 or not 0<=slippage<1:
        raise ValueError('Rates must be decimal fractions in [0,1)')
    entry_multiplier=1/(1-fee) if base_fee else 1+fee
    return (1+slippage)*entry_multiplier/((1-slippage)*(1-fee))-1


def decompose(t,slippage=.0002):
    entry_ref=t.entry/(1+slippage)
    exit_ref=t.exit/(1-slippage)
    gross=float((t.q*(exit_ref-entry_ref)).sum())
    fees=float((t.entry_fee+t.exit_fee).sum())
    execution=float((t.q*(t.entry-entry_ref+exit_ref-t.exit)).sum())
    net=float(t.pnl.sum())
    if abs(gross-fees-execution-net)>1e-7:
        raise ValueError('Cashflow reconciliation failed')
    turnover=float((t.q*(t.entry+t.exit)).sum())
    return dict(trades=len(t),gross_reference_pnl=gross,explicit_fees=fees,
                execution_cost=execution,net_pnl=net,
                max_affordable_equal_fee_per_side=(gross-execution)/turnover,
                note='Fixed original quantities and decisions. Negative fee capacity means even zero fees cannot cover modeled execution costs.')


def main():
    out=Path('reports/execution_audit');out.mkdir(parents=True,exist_ok=True)
    paths={'original_v1':'reports/experiment_001/quarterly_baseline_trades.csv',
           'no_60m_exit':'reports/experiment_001/quarterly_no_60m_exit_trades.csv',
           'breakout':'reports/experiment_002/quarterly_breakout_trades.csv'}
    results={name:decompose(pd.read_csv(path)) for name,path in paths.items()}
    scenarios=[]
    for fee in [.001,.00075,.0005,0]:
        scenarios.append(dict(fee_per_side=fee,execution_per_side=.0002,
                              break_even_reference_move=break_even(fee,.0002),
                              base_asset_buy_fee_break_even=break_even(fee,.0002,True)))
    pd.DataFrame(scenarios).to_csv(out/'fee_scenarios.csv',index=False)
    pd.DataFrame(results).T.to_csv(out/'decomposition.csv')
    # Counterfactual costs on the same quantities/reference-price path, NOT a rerun.
    sensitivity=[]
    for name,path in paths.items():
        t=pd.read_csv(path)
        for fee in [.001,.00075,.0005,0]:
            cashflow=(t.q*(t.exit*(1-fee)-t.entry*(1+fee))).sum()
            sensitivity.append(dict(strategy=name,fee_per_side=fee,fixed_trade_net_pnl=float(cashflow)))
    pd.DataFrame(sensitivity).to_csv(out/'fixed_trade_fee_sensitivity.csv',index=False)
    result={'account_fees_verified':False,'fee_scenarios':scenarios,'decomposition':results,'sensitivity':sensitivity,
            'holdout_accessed':False,'new_strategy_backtest':False}
    (out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
