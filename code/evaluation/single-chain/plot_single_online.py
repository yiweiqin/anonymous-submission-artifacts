"""Publication exports for completed single-chain online measurements only."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main(root):
    summary=json.loads((root/'summary.json').read_text(encoding='utf-8'))
    assert summary['complete'] and summary['chainVarianceEstimable'] is False
    rows=sorted([x for x in summary['methods'] if x['kind']=='c1-online'],key=lambda x:x['round'])
    assert [x['round'] for x in rows]==[2,3,4]
    assert all(x['sampleStdPP'] is None and 'liftVsFreshVanillaPP' in x for x in rows)
    old=next(x for x in summary['methods'] if x['kind']=='historical-selected-janus')
    vanilla=next(x for x in summary['methods'] if x['kind']=='fresh-matched-vanilla')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.linewidth':1.1,
        'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','pdf.fonttype':42})
    fig,axes=plt.subplots(1,2,figsize=(11.6,4.3))
    x=[r['round'] for r in rows];color='#184F86'
    axes[0].scatter([1],[old['familyMeanPct']],marker='D',s=58,color='#7A7A7A',label='Historical selected R1',zorder=3)
    axes[0].plot(x,[r['familyMeanPct'] for r in rows],marker='o',color=color,lw=1.8,label='c1 online primary')
    axes[0].axhline(vanilla['familyMeanPct'],color='#A77830',ls=':',lw=1.3,label='Fresh matched Vanilla')
    axes[0].axvline(1.5,color='#C8C8C8',ls='--',lw=1)
    axes[0].set(xlabel='Evolution round',ylabel='Equal-family pass rate (%)',xticks=[1,2,3,4],title='Historical R1 and online continuation')
    axes[0].legend(frameon=False,fontsize=8,loc='best')
    lift=[r['liftVsFreshVanillaPP'] for r in rows]
    axes[1].plot(x,lift,marker='o',color=color,lw=1.8)
    axes[1].axhline(0,color='#7A7A7A',ls='--',lw=1)
    for r,y in zip(x,lift):axes[1].annotate(f'{y:.2f}',(r,y),xytext=(0,9),textcoords='offset points',ha='center',fontsize=9)
    axes[1].margins(y=0.3)
    axes[1].set(xlabel='Evolution round',ylabel='Lift vs fresh Vanilla (pp)',xticks=[2,3,4],title='One continuation chain; no variance estimate')
    fig.text(.5,.025,'Development set only. Historical R1 uses adaptive selected scores; R2–R4 are online, not frozen evaluations.',ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.06,1,1),pad=1.7)
    for suffix in ['png','pdf','svg']:fig.savefig(root/('single-online-round-curves.'+suffix),dpi=300,facecolor='white')
    plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('summary',type=Path);a=p.parse_args();main(a.summary)
