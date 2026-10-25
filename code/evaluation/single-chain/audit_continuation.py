"""Independent end-to-end state and frozen-read audit; never repairs artifacts."""
import json,hashlib
from pathlib import Path
from checkpoint_store import digest

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def audit(root,chains=('c1','c2','c3'),frozen_enabled=True):
    tasks={}
    for row in load(root/'preparation-request.json')['tasks']:tasks.setdefault(row['family'],[]).append(row['task'])
    seeds={x['family']:x for x in map(load,sorted((root/'historical-terminal-state').glob('*.json')))}
    errors=[];learning=[];snapshots=[];frozen=[];indexes={}
    for p in (root/'executions').glob('*/commit.json'):
        row=load(p);assert row['logicalId'] not in indexes,'duplicate logical execution'
        indexes[row['logicalId']]=(p,row)
    protocols=set();adoptions=0;model_proofs=0;bundles={};native_bundles={}
    for chain in chains:
        for family,ts in tasks.items():
            state=seeds[family]
            initial=root/'formal/chains'/chain/'initial'/('family-'+digest(family)[:12]+'.json')
            if not initial.exists() or load(initial)!=state:errors.append('missing/mismatched seed '+str(initial))
            for r in [2,3,4]:
                for task in ts:
                    p=root/'formal/chains'/chain/('r%d'%r)/'commits'/(digest([family,task])[:24]+'.json')
                    if not p.exists():errors.append('missing learning '+str(p));continue
                    row=load(p);assert row['inputStateSha256']==digest(state),str(p)
                    assert row['outputStateSha256']==digest(row['stateAfter']) and row['stateAfter']['family']==family
                    outcome=row['outcome'];protocols.add(outcome['protocolSha256'])
                    logical='/'.join(['formal',chain,str(r),'online',family,task])
                    ep,execution=indexes[logical]
                    assert execution['inputStateSha256']==digest(state) and execution['carry']==state['carry']
                    assert execution['reward']==outcome['officialReward'] and execution['inputConsumed']
                    assert not execution['planningCapabilitiesConsumed'] and not execution['staffCapabilitiesConsumed']
                    request=Path(outcome['modelEvidence'])/'request.json';result=Path(outcome['modelEvidence'])/'result.json'
                    # Relocate evidence after downloading the unchanged remote tree.
                    if not request.exists():
                        directory=root/'model-calls'/Path(outcome['modelEvidence']).name;request=directory/'request.json';result=directory/'result.json'
                    assert request.exists() and result.exists(),outcome['modelEvidence']
                    assert load(request)['requestId']==load(result)['requestId']
                    model_proofs+=1
                    changed=row['inputStateSha256']!=row['outputStateSha256'];adoptions+=changed
                    learning.append(dict(chain=chain,round=r,family=family,task=task,changed=changed,carryChanged=state['carry']!=row['stateAfter']['carry'],inputStateSha256=row['inputStateSha256'],outputStateSha256=row['outputStateSha256'],rejectionReason=outcome.get('rejectionReason')))
                    state=row['stateAfter']
                snap=root/'formal/chains'/chain/('r%d'%r)/'snapshots'/('family-'+digest(family)[:12]+'.json')
                if not snap.exists():errors.append('missing snapshot '+str(snap));continue
                assert load(snap)==state,str(snap)
                bundles.setdefault((chain,r),{})[family]=digest(state)
                native_bundles.setdefault((chain,r),{})[family]=state['carry']
                snapshots.append(dict(chain=chain,round=r,family=family,path=str(snap),sha256=hashlib.sha256(snap.read_bytes()).hexdigest(),stateSha256=digest(state)))
                for task in (ts if frozen_enabled else []):
                    logical='/'.join(['formal-r%d-frozen'%r,chain,str(r),'janus',family,task])
                    if logical not in indexes:errors.append('missing frozen '+logical);continue
                    ep,row=indexes[logical]
                    assert row['inputStateSha256']==digest(state) and row['carry']==state['carry'] and row['inputConsumed'],logical
                    # Frozen evaluations have no detective request with their logical request identifier.
                    frozen_key=hashlib.sha256(logical.encode()).hexdigest()[:24]
                    assert not (root/'model-calls'/frozen_key/'request.json').exists(),logical
                    frozen.append(logical)
    assert len(protocols)<=1,'mixed formal protocols'
    probes=load(root/'controlled-probes/acceptance.json');assert probes['passed']
    bundle_hashes={str(r):{c:digest(bundles[(c,r)]) for c in chains if len(bundles.get((c,r),{}))==8} for r in [2,3,4]}
    initial_bundle=digest({family:digest(state) for family,state in seeds.items()})
    initial_native=digest({family:state['carry'] for family,state in seeds.items()})
    native_hashes={str(r):{c:digest(native_bundles[(c,r)]) for c in chains if len(native_bundles.get((c,r),{}))==8} for r in [2,3,4]}
    report=dict(passed=not errors and len(learning)==198*len(chains) and len(frozen)==(198*len(chains) if frozen_enabled else 0) and len(snapshots)==24*len(chains),
                chains=list(chains),frozenEvaluation=frozen_enabled,chainVarianceEstimable=len(chains)>1,
                errors=errors,learningTasks=len(learning),frozenTasks=len(frozen),snapshots=len(snapshots),
                adoptions=adoptions,realDetectiveEvidence=model_proofs,protocolHashes=sorted(protocols),
                historicalRound1States=1,conditionalProbesPassed=True,fullNativePersonnelConsumption=False,
                initialStateBundleSha256=initial_bundle,roundStateBundleHashes=bundle_hashes,
                uniqueStateBundlesByRound={r:len(set(x.values())) for r,x in bundle_hashes.items()},
                checkpointBundlesEqualHistorical={r:{c:h==initial_bundle for c,h in x.items()} for r,x in bundle_hashes.items()},
                initialNativeCarryBundleSha256=initial_native,roundNativeCarryBundleHashes=native_hashes,
                frozenNativeCarryEqualsHistorical={r:{c:h==initial_native for c,h in x.items()} for r,x in native_hashes.items()},
                nativeCarryAdoptions=sum(x['carryChanged'] for x in learning),
                noAdoptedChanges=adoptions==0,
                noChangeInterpretation='If frozen native carry inputs stay identical, score variation cannot establish a native execution benefit, even if internal unconsumed personnel or planning fields change.',
                historicalCapabilityBoundary='Only legacy carry enters native actor; internal plans and personnel are not directly consumed.',
                scope='state continuity, task order, chain/family separation, real native carry consumption, frozen reads and real detective evidence')
    return report,learning,snapshots

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    report,learning,snapshots=audit(a.root)
    out=a.root/'summary';out.mkdir(exist_ok=True)
    for name,value in [('independent-state-audit',report),('learning-audit',learning),('snapshot-manifest',snapshots)]:
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False));assert report['passed']
