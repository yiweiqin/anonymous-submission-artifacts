"""Independent metrics, strict coverage and historical/frozen separation."""
import argparse,csv,json,statistics
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

def load(path):return json.loads(path.read_text(encoding='utf-8'))
def rate(rows):return Fraction(sum(float(x['reward'])>=1 for x in rows),len(rows))
def family_mean(rows,families):
    return sum(rate([x for x in rows if x['family']==f]) for f in families)/len(families)
def csvfile(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def aggregate(root,output,history,strict=False):
    prep=load(root/'preparation-request.json');tasks=defaultdict(list)
    for row in prep['tasks']:tasks[row['family']].append(row['task'])
    expected={(f,t) for f,ts in tasks.items() for t in ts}
    groups=defaultdict(list);ledger=[];attempts=[]
    for p in sorted((root/'executions').glob('*/commit.json')):
        row=load(p);phase=row['phase'];parts=row['logicalId'].split('/')
        if phase=='formal-vanilla':key=('fresh-vanilla-frozen','shared',1)
        elif phase=='formal-online':key=('uniform-online-primary',parts[1],int(parts[2]))
        elif phase=='formal-validation':key=('candidate-validation-adoption-only',parts[1],int(parts[2]))
        elif phase.startswith('formal-r') and phase.endswith('-frozen'):
            r=int(parts[2]);key=('diagnostic-cancelled-r1-frozen' if r==1 else 'terminal-snapshot-frozen',parts[1],r)
        else:continue
        if key[0] not in ['candidate-validation-adoption-only','diagnostic-cancelled-r1-frozen']:groups[key].append(row)
        ledger.append(dict(kind=key[0],chain=key[1],round=key[2],family=row['family'],task=row['task'],
                           reward=row['reward'],passed=int(float(row['reward'])>=1),logicalId=row['logicalId'],
                           inputStateSha256=row['inputStateSha256'],protocolSha256=row['protocolSha256'],
                           artifact=str(p.parent),inputConsumed=row['inputConsumed'],phase=phase,
                           usedForPrimaryMetrics=key[0] not in ['candidate-validation-adoption-only','diagnostic-cancelled-r1-frozen']))
        for a in row['attempts']:attempts.append(dict(logicalId=row['logicalId'],**{k:v for k,v in a.items() if not isinstance(v,dict)},**a.get('usage',{})))
    historical=load(history)
    for arm,source_arm in [('janus','janus_full'),('vanilla','vanilla')]:
        rows=[x for x in historical if x['arm']==source_arm]
        assert len(rows)==66,'historical arm missing: '+source_arm
        groups[('historical-main-table-'+arm,'shared',1)]=rows
        for x in rows:ledger.append(dict(kind='historical-main-table-'+arm,sourceArm=source_arm,chain='shared',round=1,family=x['family'],task=x['task'],reward=x['reward'],passed=int(float(x['reward'])>=1),historicalSelectedLine=x['selectedLine']))
    coverage=[]
    required=[('fresh-vanilla-frozen','shared',1)]+[(kind,c,r) for kind in ['uniform-online-primary','terminal-snapshot-frozen'] for c in ['c1','c2','c3'] for r in [2,3,4]]
    for key in required:
        rows=groups[key];pairs=[(x['family'],x['task']) for x in rows]
        coverage.append(dict(kind=key[0],chain=key[1],round=key[2],count=len(rows),complete=len(pairs)==66 and len(set(pairs))==66 and set(pairs)==expected))
    if strict:assert all(x['complete'] for x in coverage),coverage
    complete={k:v for k,v in groups.items() if len(v)==66 and {(x['family'],x['task']) for x in v}==expected}
    summaries=[];family_rows=[]
    fresh=complete.get(('fresh-vanilla-frozen','shared',1));hjanus=complete[('historical-main-table-janus','shared',1)];hvanilla=complete[('historical-main-table-vanilla','shared',1)]
    for key,rows in complete.items():
        mean=family_mean(rows,tasks)
        summary=dict(kind=key[0],chain=key[1],round=key[2],n=66,passed=sum(float(x['reward'])>=1 for x in rows),passRatePct=float(rate(rows)*100),familyMeanPct=float(mean*100),
                     scoreRule='historical adaptive selected records' if key[0].startswith('historical-') else 'first auditable primary result; validation never replaces primary')
        if key[0]=='historical-main-table-janus':summary['liftVsHistoricalVanillaPP']=float((mean-family_mean(hvanilla,tasks))*100)
        if key[0] in ['terminal-snapshot-frozen','uniform-online-primary']:
            summary['differenceVsHistoricalR1PP']=float((mean-family_mean(hjanus,tasks))*100)
            summary['differenceVsR1Caveat']='descriptive only: historical adaptive selected scores versus new uniform online/frozen measurement'
            if fresh:summary['liftVsFreshVanillaPP']=float((mean-family_mean(fresh,tasks))*100)
        summaries.append(summary)
        for f,ts in tasks.items():
            fr=[x for x in rows if x['family']==f]
            family_rows.append(dict(kind=key[0],chain=key[1],round=key[2],family=f,n=len(ts),passed=sum(float(x['reward'])>=1 for x in fr),passRatePct=float(rate(fr)*100)))
    def summarize_rounds(kind):
        values=[]
        for r in [2,3,4]:
            rs=[x for x in summaries if x['kind']==kind and x['round']==r]
            if len(rs)!=3:continue
            row=dict(kind=kind,round=r,chains=3,meanFamilyRatePct=statistics.mean(x['familyMeanPct'] for x in rs),sampleStdFamilyRatePP=statistics.stdev(x['familyMeanPct'] for x in rs),
                     meanDifferenceVsHistoricalR1PP=statistics.mean(x['differenceVsHistoricalR1PP'] for x in rs),r1Comparison='different measurement rules; not causal evolution gain')
            if fresh:row.update(meanLiftVsFreshVanillaPP=statistics.mean(x['liftVsFreshVanillaPP'] for x in rs),sampleStdLiftPP=statistics.stdev(x['liftVsFreshVanillaPP'] for x in rs))
            values.append(row)
        return values
    round_rows=summarize_rounds('terminal-snapshot-frozen');online_round_rows=summarize_rounds('uniform-online-primary')
    paired=[]
    for a,b in [(2,3),(3,4),(2,4)]:
        ds=[]
        for c in ['c1','c2','c3']:
            x=complete.get(('terminal-snapshot-frozen',c,a));y=complete.get(('terminal-snapshot-frozen',c,b))
            if x and y:
                delta=float((family_mean(y,tasks)-family_mean(x,tasks))*100);ds.append(delta);paired.append(dict(fromRound=a,toRound=b,chain=c,deltaFamilyPP=delta))
        if len(ds)==3:paired.append(dict(fromRound=a,toRound=b,chain='mean',deltaFamilyPP=statistics.mean(ds),sampleStdPP=statistics.stdev(ds)))
    exact_round_means={r:sum(family_mean(complete[('terminal-snapshot-frozen',c,r)],tasks) for c in ['c1','c2','c3'])/3
                       for r in [2,3,4] if all(('terminal-snapshot-frozen',c,r) in complete for c in ['c1','c2','c3'])}
    best=min(exact_round_means,key=lambda r:(-exact_round_means[r],r)) if len(exact_round_means)==3 else None
    exact_online_means={r:sum(family_mean(complete[('uniform-online-primary',c,r)],tasks) for c in ['c1','c2','c3'])/3
                        for r in [2,3,4] if all(('uniform-online-primary',c,r) in complete for c in ['c1','c2','c3'])}
    best_online=min(exact_online_means,key=lambda r:(-exact_online_means[r],r)) if len(exact_online_means)==3 else None
    comparisons=[]
    if best is not None:
        for other in [r for r in [2,3,4] if r!=best]:
            deltas=[float((family_mean(complete[('terminal-snapshot-frozen',c,best)],tasks)-family_mean(complete[('terminal-snapshot-frozen',c,other)],tasks))*100) for c in ['c1','c2','c3']]
            comparisons.append(dict(bestRound=best,otherRound=other,pairedDeltasPP=deltas,meanPP=statistics.mean(deltas),sampleStdPP=statistics.stdev(deltas),chainsStrictlyBetter=sum(x>0 for x in deltas)))
    output.mkdir(parents=True,exist_ok=True)
    report=dict(complete=all(x['complete'] for x in coverage),coverage=coverage,bestFrozenRound=best,historicalR1IndependentStates=1,historicalR1NotFrozen=True,
                bestAmong='R2/R3/R4 uniform frozen measurements; historical R1 cannot enter same-estimand ranking',rounds=round_rows,
                uniformOnlineRounds=online_round_rows,bestUniformOnlineRound=best_online,
                onlineCaveat='Online primary rewards are uniformly collected before candidate validation; historical adaptive rerun selection is not reproduced.',
                bestRoundComparisons=comparisons,bestSupportedInAllChains=bool(comparisons) and all(x['chainsStrictlyBetter']==3 for x in comparisons),
                uncertainty='Three continuation states share one historical starting state and one matched fresh Vanilla execution; baseline execution uncertainty is not estimated.')
    (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    for name,rows in [('task-ledger',ledger),('attempt-ledger',attempts),('method-summary',summaries),('family-summary',family_rows),('round-summary',round_rows),('online-round-summary',online_round_rows),('paired-round-differences',paired),('coverage',coverage)]:csvfile(output/(name+'.csv'),rows)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--history',type=Path,required=True);p.add_argument('--strict',action='store_true');a=p.parse_args()
    print(json.dumps(aggregate(a.root,a.output,a.history,a.strict),ensure_ascii=False))
