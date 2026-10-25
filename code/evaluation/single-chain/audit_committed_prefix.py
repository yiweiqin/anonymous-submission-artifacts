"""Audit a captured immutable commit prefix while other families keep running."""
import hashlib,json
from collections import Counter
from pathlib import Path
from checkpoint_store import digest
from legacy_policy import load_policy,next_state

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def audit(root):
    tasks={}
    for x in load(root/'preparation-request.json')['tasks']:tasks.setdefault(x['family'],[]).append(x['task'])
    seeds={x['family']:x for x in map(load,(root/'historical-terminal-state').glob('*.json'))}
    bridge,_=load_policy();protocol=load(root/'execution-protocol.json');manifest=load(root/'native-task-manifest.json')
    packages={(x['family'],x['task']):x for x in manifest['packages']}
    captured={str(p.relative_to(root)):load(p) for p in (root/'formal/chains').glob('c*/r*/commits/*.json')}
    executions={x['logicalId']:(p.parent,x) for p in (root/'executions').glob('*/commit.json') for x in [load(p)]}
    rows=[];adopted=0;s_calls=0;snapshots=0
    for chain in ['c1','c2','c3']:
        for family,ts in tasks.items():
            state=seeds[family]
            initial=root/'formal/chains'/chain/'initial'/('family-'+digest(family)[:12]+'.json')
            assert load(initial)==state
            for r in [2,3,4]:
                missing=False;count=0
                for task in ts:
                    relative='formal/chains/'+chain+'/r'+str(r)+'/commits/'+digest([family,task])[:24]+'.json'
                    if relative not in captured:missing=True;continue
                    assert not missing,'gap in captured family prefix: '+relative
                    row=captured[relative]
                    assert (row['chain'],row['round'],row['family'],row['task'])==(chain,r,family,task)
                    assert row['inputStateSha256']==digest(state) and row['outputStateSha256']==digest(row['stateAfter'])
                    logical='/'.join(['formal',chain,str(r),'online',family,task]);directory,execution=executions[logical]
                    assert execution['carry']==state['carry'] and execution['inputStateSha256']==digest(state)
                    cfg=load(directory/'native-config.json');lock=load(directory/'native-lock.json');trajectory=load(directory/'native-trajectory.json')
                    assert cfg.get('extra_instructions',[])==([state['carry']] if state['carry'] else [])
                    assert cfg['agents'][0]['kwargs']['max_turns']==40 and cfg['agents'][0]['kwargs']['temperature']==0
                    assert lock['trials'][0]['task']['digest']==packages[(family,task)]['executionDigest']
                    first=next(x['message'] for x in trajectory['steps'] if x.get('source')=='user')
                    assert not state['carry'] or state['carry'] in first
                    assert hashlib.sha256(first.split('Task Description:',1)[0].encode()).hexdigest()==protocol['historicalExecutorPromptPrefixSha256']
                    assert any(x.get('source')=='agent' for x in trajectory['steps'])
                    outcome=row['outcome'];assert outcome['officialReward']==execution['reward']
                    graph=bridge.execution_graph(state['plan'],int(float(execution['reward'])>=1),execution['trace'])
                    expected_case=bridge.detective_case(family+'/'+task,state['plan'],graph)
                    key=hashlib.sha256('/'.join(map(str,['formal',chain,r,family,task])).encode()).hexdigest()[:24]
                    request=load(root/'model-calls'/key/'request.json');response=load(root/'model-calls'/key/'result.json')
                    assert request['case']==expected_case and response['requestId']==request['requestId'] and response['parametersUnchanged']
                    raw=response['result'];verdict=dict(raw['verdict'],valid=raw['valid'],warnings=raw.get('warnings',[]),raw=raw['raw'])
                    verdict=bridge.recover_verdict(verdict,[x['id'] for x in state['plan']['nodes']],bridge.changed_fields_by_node(state['plan'],graph))
                    assert verdict==outcome['verdict']
                    replacement=''
                    if verdict.get('type')=='wrong_agent' and (verdict.get('changedFields') or [None])[0]=='agentId':
                        current=next(x['agentId'] for x in state['plan']['nodes'] if x['id']==verdict['nodeId'])
                        pairs=bridge.replacement_pairs(current,family);ds=root/'controlled-probes'/('formal-S-'+key)
                        inputs=[json.loads(x) for x in (ds/'pairs.jsonl').read_text().splitlines()]
                        assert inputs==[dict(id=x['id'],prompt=x['prompt']) for x in pairs]
                        scores={x['id']:x for x in map(json.loads,(ds/'scores.jsonl').read_text().splitlines())}
                        values=[dict(left=x['left'],right=x['right'],dependency=scores[x['id']]['dependency'],similarity=scores[x['id']]['similarity']) for x in pairs]
                        replacement=bridge.choose_replacement(current,values);s_calls+=1
                    replay_reward=outcome['validationReward']
                    if outcome['validationExecution']:
                        _,replay=executions[logical+'/validation'];assert replay['reward']==replay_reward
                        candidate=bridge.one_update(verdict,execution['trace'],family)
                        assert replay['carry']==candidate
                    expected=next_state(bridge,state,verdict,execution['trace'],execution['reward'],replay_reward,replacement)
                    assert expected==row['stateAfter'],'adoption differs from original policy: '+relative
                    changed=digest(state)!=digest(expected);adopted+=changed
                    proposal=bridge.one_update(verdict,execution['trace'],family)
                    if changed:reason='adopted_state_change'
                    elif float(execution['reward'])>=1:reason='primary_already_passed_no_change'
                    elif not verdict.get('valid'):reason='invalid_detective_verdict'
                    elif verdict.get('status')!='drift':reason='no_drift_reported'
                    elif not proposal:reason='no_permitted_candidate'
                    elif proposal==state['carry']:reason='candidate_equals_current'
                    elif replay_reward is None:reason='no_candidate_validation_result'
                    elif float(replay_reward)<1:reason='candidate_failed_validation'
                    else:reason='retained_by_original_protection'
                    rows.append(dict(chain=chain,round=r,family=family,task=task,adopted=changed,derivedDecisionReason=reason,
                                     primaryReward=execution['reward'],validationReward=replay_reward,
                                     verdictValid=verdict.get('valid'),verdictStatus=verdict.get('status'),verdictType=verdict.get('type'),
                                     inputStateSha256=digest(state),outputStateSha256=digest(expected)))
                    state=expected;count+=1
                if count==len(ts):
                    snapshot=root/'formal/chains'/chain/('r%d'%r)/'snapshots'/('family-'+digest(family)[:12]+'.json')
                    if snapshot.exists():assert load(snapshot)==state;snapshots+=1
                else:break
    return dict(passed=True,capturedLearningCommits=len(captured),auditedLearningCommits=len(rows),adoptions=adopted,completeFamilySnapshots=snapshots,
                decisionReasons=dict(Counter(x['derivedDecisionReason'] for x in rows)),
                formalSConditionsTriggered=s_calls,realNativeInputAndResponseVerified=True,detectiveInputsAndCallsVerified=True,
                originalAdoptionPolicyRecomputed=True,allLearningRoundsComplete=len(rows)==594 and snapshots==72,
                limitation='Learning prefix audit; frozen evaluations are audited separately.'),rows

if __name__=='__main__':
    import argparse,time
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);args=p.parse_args()
    report,rows=audit(args.root);assert report['capturedLearningCommits']==report['auditedLearningCommits']
    out=args.root/'summary';out.mkdir(exist_ok=True)
    for name,value in [('committed-prefix-audit',dict(at=time.time(),**report)),('committed-prefix-evidence',rows)]:
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
