"""Static research plots and readable tables; no dashboard or execution controls."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def render(report_dir='reports/statistics',root='data/research_statistics'):
    out=Path(report_dir);root=Path(root)
    data=json.loads((out/'results.json').read_text());rows=[r for r in data['summaries'] if r['hours']==24]
    plt.rcParams.update({'font.size':10,'svg.hashsalt':'stanka-m4-v1'})
    fig,axes=plt.subplots(1,2,figsize=(14,5),layout='constrained')
    names=[r['signal'].replace('_',' ') for r in rows]
    for i,r in enumerate(rows):
        mean=r['costs']['standard'].get('mean')
        if mean is not None:
            ci=r.get('inference28',{}).get('net_ci95')
            axes[0].scatter(mean*100,i,color='#167c80')
            if ci:axes[0].plot(np.array(ci)*100,[i,i],color='#167c80')
        for j,name in enumerate(('bnb_conditional','standard','stress')):
            value=r['costs'][name].get('mean')
            if value is not None:axes[1].scatter(value*100,i+(j-1)*.15,label=name if i==0 else None,s=22,color=['#167c80','#5275bb','#c45745'][j])
    for ax in axes:
        ax.axvline(0,color='gray',lw=1);ax.set_yticks(range(len(rows)),names);ax.invert_yaxis();ax.grid(axis='x',alpha=.2)
        ax.set_xlabel('Average 24h net return (%)')
    axes[0].set_title('28-day block intervals where eligible\nNo interval means insufficient blocks or baseline')
    axes[1].set_title('Cost assumptions, not fee guarantees');axes[1].legend()
    fig.suptitle('Development data only • overlapping observations • no OOS claim')
    fig.savefig(out/'expectancy.svg',metadata={'Date':None});fig.savefig(root/'expectancy_preview.png',dpi=100);plt.close(fig)
    diag=pd.read_parquet(root/data['snapshot']['diagnostics']['path'])
    fig,axes=plt.subplots(2,1,figsize=(12,8),sharex=True,layout='constrained')
    for signal,g in diag.groupby('signal',sort=False):
        if len(g)<2:continue
        g=g.sort_values('label_end');eq=np.r_[1.,np.cumprod(1+g.net_standard.to_numpy())]
        dates=[g.decision_at.iloc[0],*g.label_end]
        axes[0].plot(dates,eq,label=signal.replace('_',' '),lw=1)
        axes[1].plot(dates,(eq/np.maximum.accumulate(eq)-1)*100,lw=1)
    axes[0].set_yscale('log');axes[0].set_ylabel('Compounded equity (log scale)');axes[0].legend(fontsize=8,ncol=2)
    axes[1].set_ylabel('Closed-trade drawdown (%)')
    axes[0].set_title('24h non-overlap diagnostics • fully invested per accepted observation\nNot a strategy backtest; intratrade drawdowns are omitted')
    fig.savefig(out/'diagnostics.svg',metadata={'Date':None});fig.savefig(root/'diagnostics_preview.png',dpi=90);plt.close(fig)
    labels=pd.read_parquet(root/data['snapshot']['labels']['24']['path'])
    f=pd.read_parquet(root/data['snapshot']['features']['path'])
    joined=labels[labels.status=='complete'].merge(f[['observation_id','bullish_engulfing','resistance_retest']],on='observation_id')
    fig,ax=plt.subplots(figsize=(9,5),layout='constrained')
    bins=np.linspace(-10,10,81)
    for name in ('bullish_engulfing','resistance_retest'):
        values=joined.loc[joined[name],'net_standard']*100
        ax.hist(values,bins=bins,density=True,histtype='step',label=name.replace('_',' '))
    ax.set_xlabel('24h net return (%)');ax.set_ylabel('Density within displayed range');ax.legend()
    ax.set_title('Development return distributions • display clipped to ±10%\nFull tails remain in the numerical summaries')
    fig.savefig(out/'distributions.svg',metadata={'Date':None});fig.savefig(root/'distributions_preview.png',dpi=90);plt.close(fig)
    print('Rendered three research figures')

if __name__=='__main__':render()
