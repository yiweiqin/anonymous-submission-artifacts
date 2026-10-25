"""Paired task-family bootstrap. Never declares necessity of a specialized model."""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from audit import rows
from engine import dumps


def compare(trained, baseline, draws=2000):
    arms=[]
    for folder in (trained,baseline):
        meta=json.loads((folder/'provenance.json').read_text())
        rr=list(rows(folder/'predictions.jsonl'))
        by_id={r['id']:r for r in rr}
        if len(by_id)!=len(rr): raise ValueError('duplicate_predictions')
        arms.append((meta,by_id))
    a,b=arms
    if set(a[1])!=set(b[1]): raise ValueError('prediction_join')
    for k in ('caseSha256','requestSha256','maxNewTokens','temperature','n','engineSha256','evaluatorSha256'):
        if a[0][k]!=b[0][k]: raise ValueError(f'unfair_or_incompatible_comparison:{k}')
    if a[0]['arm']!='trained' or b[0]['arm'] not in ('H3_base','external'):
        raise ValueError('model_arms_required')
    groups=defaultdict(list)
    for key,x in a[1].items():
        y=b[1][key]
        if x['groupId']!=y['groupId'] or x['goldDecision']!=y['goldDecision']: raise ValueError('group_or_gold_mismatch')
        if x['goldDecision']=='adopt':
            groups[x['groupId']].append(int(x['metrics']['minimalRepair'])-int(y['metrics']['minimalRepair']))
    names=sorted(groups)
    if len(names)<50: return {'verdict':'INSUFFICIENT_GROUPS','groups':len(names)}
    flat=[x for rr in groups.values() for x in rr]; delta=sum(flat)/len(flat)
    rng=random.Random(20260923); boot=[]
    for _ in range(draws):
        picked=[x for name in rng.choices(names,k=len(names)) for x in groups[name]]
        boot.append(sum(picked)/len(picked))
    boot.sort(); ci=[boot[int(draws*.025)],boot[int(draws*.975)]]
    unsafe=sum(r['metrics']['unsafeAdoption'] for r in a[1].values())/len(a[1])
    verdict='ADVANTAGE_ON_THIS_BENCHMARK' if delta>.05 and ci[0]>0 and unsafe<=.01 else 'NO_DEMONSTRATED_ADVANTAGE'
    return {'verdict':verdict,'deltaMinimalRepair':delta,'groupBootstrap95CI':ci,'groups':len(names),
            'unsafeAdoptionRate':unsafe,'scope':'declared_synthetic_workflows_only','provesGeneralAINecessity':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--trained',type=Path,required=True); p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True); a=p.parse_args(); result=compare(a.trained,a.baseline)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8'); print(dumps(result))
