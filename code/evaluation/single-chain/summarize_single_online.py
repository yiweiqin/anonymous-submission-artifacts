"""Single-chain online metrics under the explicit 2026-10-23 scope revision."""
import argparse,json
from pathlib import Path
from aggregate_results import load,rate,family_mean,csvfile
from checkpoint_store import digest

def summarize(root,output,strict=False):
    scope=load(root/'single-online-scope.json')
    assert scope['chains']==['c1'] and scope['frozenEvaluation'] is False
    tasks={}
    for x in load(root/'preparation-request.json')['tasks']:tasks.setdefault(x['family'],[]).append(x['task'])
    expected={(f,t) for f,ts in tasks.items() for t in ts}
    groups={r:[] for r in [2,3,4]};vanilla=[];ledger=[];aux=[];attempts=[]
    for p in (root/'executions').glob('*/commit.json'):
        x=load(p);parts=x['logicalId'].split('/');selected=False
        if x['phase']=='formal-online' and parts[1]=='c1' and int(parts[2]) in groups:
            groups[int(parts[2])].append(x);selected=True
        elif x['phase']=='formal-vanilla':vanilla.append(x);selected=True
        row=dict(logicalId=x['logicalId'],phase=x['phase'],family=x['family'],task=x['task'],reward=x['reward'],
            passed=int(float(x['reward'])>=1),inputStateSha256=x['inputStateSha256'],protocolSha256=x['protocolSha256'],
            artifact=str(p.parent),usedForPrimaryMetrics=selected)
        (ledger if selected else aux).append(row)
        for a in x['attempts']:
            attempts.append(dict(logicalId=x['logicalId'],usedForPrimaryMetrics=selected,
                **{k:v for k,v in a.items() if not isinstance(v,dict)},**a.get('usage',{})))
    def complete(rows):
        pairs=[(x['family'],x['task']) for x in rows]
        return len(pairs)==66 and len(set(pairs))==66 and set(pairs)==expected
    coverage=[dict(kind='c1-online',round=r,n=len(xs),complete=complete(xs)) for r,xs in groups.items()]
    coverage.append(dict(kind='fresh-matched-vanilla',round=1,n=len(vanilla),complete=complete(vanilla)))
    if strict:assert all(x['complete'] for x in coverage),coverage
    history=load(root/'historical-result-provenance.json')
    hj=[x for x in history if x['arm']=='janus_full'];hv=[x for x in history if x['arm']=='vanilla']
    assert complete(hj) and complete(hv)
    methods=[('historical-selected-janus',1,hj),('historical-selected-vanilla',1,hv)]
    if complete(vanilla):methods.append(('fresh-matched-vanilla',1,vanilla))
    methods += [('c1-online',r,xs) for r,xs in groups.items() if complete(xs)]
    summary=[];family=[];snapshots=[]
    for kind,r,rows in methods:
        macro=family_mean(rows,tasks)
        row=dict(kind=kind,round=r,n=66,passed=sum(float(x['reward'])>=1 for x in rows),
            passRatePct=float(rate(rows)*100),familyMeanPct=float(macro*100),chains=1,sampleStdPP=None)
        if kind=='c1-online':
            row.update(differenceVsHistoricalR1PP=float((macro-family_mean(hj,tasks))*100),
                r1Caveat='descriptive comparison: historical adaptive selection versus uniform online primary scores')
            if complete(vanilla):row['liftVsFreshVanillaPP']=float((macro-family_mean(vanilla,tasks))*100)
        if kind=='historical-selected-janus':row['liftVsHistoricalVanillaPP']=float((macro-family_mean(hv,tasks))*100)
        summary.append(row)
        for f in tasks:
            xs=[x for x in rows if x['family']==f]
            family.append(dict(kind=kind,round=r,family=f,n=len(xs),passed=sum(float(x['reward'])>=1 for x in xs),passRatePct=float(rate(xs)*100)))
    exact={r:family_mean(xs,tasks) for r,xs in groups.items() if complete(xs)}
    best=min(exact,key=lambda r:(-exact[r],r)) if len(exact)==3 else None
    pairs=[dict(fromRound=a,toRound=b,deltaFamilyPP=float((exact[b]-exact[a])*100)) for a,b in [(2,3),(3,4),(2,4)] if a in exact and b in exact]
    for p in (root/'formal/chains/c1').glob('r*/snapshots/*.json'):
        import hashlib
        x=load(p);snapshots.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),stateSha256=digest(x)))
    output.mkdir(parents=True,exist_ok=True)
    report=dict(complete=all(x['complete'] for x in coverage),scope=scope,coverage=coverage,bestOnlineRound=best,
        ranking='R2/R3/R4 uniform c1 online scores; tie favors fewer rounds; historical R1 shown separately',
        chainVarianceEstimable=False,sampleStdPP=None,methods=summary,
        uncertainty='One continuation chain and one matched baseline; no chain-to-chain uncertainty estimate. Online scores are not terminal frozen evaluations.',
        goalComplete=False)
    (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    for name,rows in [('task-ledger',ledger),('auxiliary-retained-ledger',aux),('attempt-ledger',attempts),('method-summary',summary),('family-summary',family),('paired-round-differences',pairs),('coverage',coverage)]:csvfile(output/(name+'.csv'),rows)
    (output/'snapshot-manifest.json').write_text(json.dumps(snapshots,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--strict',action='store_true');a=p.parse_args()
    print(json.dumps(summarize(a.root,a.root/'single-online-summary',a.strict),ensure_ascii=False))
