"""User-approved c1 only, online primary scores, with original evolution methods."""
import copy,json,time
from campaign import Campaign,HERE
from model_client import ModelClient
from legacy_executor import atomic

def main():
    scope=json.loads((HERE/'single-online-scope.json').read_text())
    assert scope['chains']==['c1'] and scope['frozenEvaluation'] is False
    c=Campaign(8)
    assert json.loads((HERE/'pilot-continuation-acceptance.json').read_text())['passed']
    gate=json.loads((HERE/'r1-review-acceptance.json').read_text())
    assert gate['passed'] and gate['protocolSha256']==c.executor.protocol_hash
    try:
        c.model=ModelClient()
        for f,state in c.seeds.items():
            c.checkpoints.seed('c1',f,copy.deepcopy(state))
            c.checkpoints.snapshot('c1',1,f,copy.deepcopy(state))
        for r in [2,3,4]:
            c.phase='single-c1-r%d-online'%r;c.status()
            c.parallel([('formal','c1',r,f,ts) for f,ts in c.tasks.items()],c.evolve_family)
            c.validate_seed_integrity()
        c.phase='single-online-rounds-scored';c.status()
    except BaseException as e:
        c.status(type(e).__name__+':'+str(e));raise
    finally:c.close()
    # Complete the single matched baseline, reusing its existing logical commits.
    v=Campaign(8)
    try:v.vanilla()
    finally:v.close()
    from summarize_single_online import summarize
    summary=summarize(HERE,HERE/'single-online-summary',strict=True)
    from audit_continuation import audit
    audited,learning,snapshots=audit(HERE,chains=('c1',),frozen_enabled=False)
    for name,value in [('independent-state-audit',audited),('learning-audit',learning),('snapshot-manifest',snapshots)]:
        atomic(HERE/'single-online-summary'/(name+'.json'),value)
    assert audited['passed'],audited
    from audit_committed_prefix import audit as audit_prefix
    prefix,evidence=audit_prefix(HERE)
    atomic(HERE/'single-online-summary'/'original-policy-audit.json',prefix)
    atomic(HERE/'single-online-summary'/'original-policy-evidence.json',evidence)
    assert prefix['passed'],prefix
    atomic(HERE/'single-online-completion.json',dict(at=time.time(),onlineRounds=[2,3,4],chain='c1',
        historicalRound1=True,matchedVanillaComplete=True,frozenEvaluation=False,
        stateAuditPassed=audited['passed'],originalPolicyAuditPassed=prefix['passed'],
        goalComplete=False,status='scores-and-state-audited-awaiting-costs-figure-and-delivery'))
    v.phase='single-online-scored-and-audited-awaiting-delivery';v.status()

if __name__=='__main__':main()
