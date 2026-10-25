"""Historical-state continuation with explicit pilot, R1, and continuation gates."""
import argparse
import copy
import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor,as_completed
from fractions import Fraction
from pathlib import Path
from checkpoint_store import Checkpoints,digest,immutable
from legacy_executor import Executor,atomic
from legacy_policy import load_policy,next_state
from model_client import ModelClient

HERE=Path(__file__).resolve().parent
LOCK=threading.RLock()


def key(*parts):return hashlib.sha256('/'.join(map(str,parts)).encode()).hexdigest()[:24]


class Campaign:
    def __init__(self,workers):
        self.workers=workers
        self.executor=Executor()
        self.bridge,self.policy=load_policy()
        self.checkpoints=Checkpoints(HERE/'formal')
        self.model=None
        self.records=[]
        self.phase='initializing'
        self.stop=threading.Event()
        self.failure=None
        prep=json.loads((HERE/'preparation-request.json').read_text())
        self.tasks={}
        self.sample={}
        for x in prep['tasks']:self.tasks.setdefault(x['family'],[]).append(x['task'])
        for x in prep['sample']:self.sample.setdefault(x['family'],[]).append(x['task'])
        self.seeds={}
        for p in sorted((HERE/'historical-terminal-state').glob('*.json')):
            state=json.loads(p.read_text());self.seeds[state['family']]=state
        assert len(self.tasks)==len(self.seeds)==8 and sum(map(len,self.tasks.values()))==66
        self.seed_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (HERE/'historical-terminal-state').glob('*.json')}

    def status(self,error=None):
        with LOCK:
            atomic(HERE/'campaign-status.json',dict(phase=self.phase,completedInThisProcess=len(self.records),
                 scoredExecutionsOnDisk=sum(1 for p in (HERE/'executions').glob('*/commit.json')),
                 trainingCommitsOnDisk=sum(1 for p in (HERE/'formal/chains').glob('*/r*/commits/*.json')),
                 error=error or self.failure,updatedAt=time.time(),workers=self.workers,rounds=[1,2,3,4],goalComplete=False))

    def parallel(self,items,function):
        def guarded(item):
            if self.stop.is_set():raise RuntimeError('stopped after a different worker failed')
            try:return function(*item)
            except BaseException as exc:
                with LOCK:
                    if self.failure is None:
                        self.failure=type(exc).__name__+':'+str(exc)
                        import traceback
                        atomic(HERE/'first-worker-failure.json',dict(error=self.failure,phase=self.phase,at=time.time(),traceback=traceback.format_exc()))
                self.stop.set();self.status(self.failure);raise
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures=[pool.submit(guarded,item) for item in items]
            values=[]
            for future in as_completed(futures):values.append(future.result());self.status()
        return values

    def execute(self,logical,phase,arm,family,task,state):
        before=digest(state)
        row=self.executor.run(logical,phase,arm,family,task,state['carry'],before)
        assert digest(state)==before
        with LOCK:self.records.append(row)
        return row

    def frozen_family(self,scope,chain,round_,family,state,tasks,arm='janus'):
        original=digest(state)
        if scope.startswith('formal-r') and round_>=2:
            source=HERE/'formal/chains'/chain/('r%d'%round_)/'snapshots'/('family-'+digest(family)[:12]+'.json')
            assert source.exists() and json.loads(source.read_text())==state
            snapshot_hash=hashlib.sha256(source.read_bytes()).hexdigest()
        else:
            source=HERE/'evaluation-inputs'/(key(scope,chain,round_,family,arm)+'.json')
            snapshot_hash=immutable(source,state)
        rows=[]
        for task in tasks:
            if self.stop.is_set():raise RuntimeError('stopped after a different worker failed')
            # A new logical execution is required even when the state hash has
            # not changed from an earlier checkpoint.
            logical='/'.join([scope,chain,str(round_),arm,family,task])
            frozen=self.checkpoints.read_for_evaluation(source,snapshot_hash)
            rows.append(self.execute(logical,scope,arm,family,task,frozen))
            assert hashlib.sha256(source.read_bytes()).hexdigest()==snapshot_hash
        assert digest(state)==original
        return rows

    def evolve_family(self,scope,chain,round_,family,tasks):
        state=copy.deepcopy(self.seeds[family])
        if scope=='formal':
            self.checkpoints.seed(chain,family,state)
            if round_>2:
                path=HERE/'formal/chains'/chain/('r%d'%(round_-1))/'snapshots'/('family-'+digest(family)[:12]+'.json')
                state=json.loads(path.read_text())
        for task in tasks:
            if self.stop.is_set():raise RuntimeError('stopped after a different worker failed')
            commit_path=HERE/scope/'chains'/chain/('r%d'%round_)/'commits'/(digest([family,task])[:24]+'.json')
            if commit_path.exists():
                committed=json.loads(commit_path.read_text())
                assert committed['inputStateSha256']==digest(state)
                state=committed['stateAfter'];continue
            before=copy.deepcopy(state)
            logical='/'.join([scope,chain,str(round_),'online',family,task])
            official=self.execute(logical,scope+'-online','janus',family,task,state)
            execution=self.bridge.execution_graph(state['plan'],1 if float(official['reward'])>=1 else 0,official['trace'])
            case=self.bridge.detective_case(family+'/'+task,state['plan'],execution)
            response=self.model.ask(case,key(scope,chain,round_,family,task))
            raw=response['result']
            verdict=dict(raw['verdict'],valid=raw['valid'],warnings=raw.get('warnings',[]),raw=raw['raw'])
            verdict=self.bridge.recover_verdict(verdict,[x['id'] for x in state['plan']['nodes']],self.bridge.changed_fields_by_node(state['plan'],execution))
            replacement=''
            if verdict.get('type')=='wrong_agent' and (verdict.get('changedFields') or [None])[0]=='agentId':
                from conditional_probes import ds_score
                current=next(x['agentId'] for x in state['plan']['nodes'] if x['id']==verdict['nodeId'])
                scores=ds_score(self.bridge.replacement_pairs(current,family),'formal-S-'+key(scope,chain,round_,family,task),unscored=scope!='formal')
                replacement=self.bridge.choose_replacement(current,scores)
            candidate=self.bridge.one_update(verdict,official['trace'],family)
            replay=None
            if candidate and candidate!=state['carry'] and float(official['reward'])<1:
                candidate_state=copy.deepcopy(state);candidate_state['carry']=candidate
                replay=self.execute(logical+'/validation',scope+'-validation','janus',family,task,candidate_state)
            after=next_state(self.bridge,state,verdict,official['trace'],official['reward'],None if replay is None else replay['reward'],replacement)
            outcome=dict(officialExecution=official['artifactDirectory'],officialReward=official['reward'],
                         validationExecution=None if replay is None else replay['artifactDirectory'],validationReward=None if replay is None else replay['reward'],
                         verdict=verdict,modelEvidence=str(HERE/'model-calls'/key(scope,chain,round_,family,task)),
                         carryChanged=after['carry']!=before['carry'],staffChanged=after['plan']!=before['plan'],
                         rejectionReason='unchanged or no validated candidate' if after==before else None,
                         protocolSha256=self.executor.protocol_hash,learningMechanism='original terminal campaign policy')
            store=self.checkpoints if scope=='formal' else Checkpoints(HERE/scope)
            store.commit(chain,round_,family,task,before,after,outcome)
            state=after
            self.status()
        store=self.checkpoints if scope=='formal' else Checkpoints(HERE/scope)
        store.snapshot(chain,round_,family,state)
        return state

    def validate_seed_integrity(self):
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in self.seed_hashes.items())

    def pilot_gate(self):
        origin=json.loads((HERE/'historical-state-recovery.json').read_text())
        assert origin['passed'] and origin['verifiablyReconstructedTerminalSnapshot']
        assert json.loads((HERE/'controlled-probes/acceptance.json').read_text())['passed']
        self.phase='pilot-continuation-and-frozen-evaluation';self.status()
        states=self.parallel([('pilot-learning','c1',2,f,ts) for f,ts in self.sample.items()],self.evolve_family)
        by_family={x['family']:x for x in states}
        self.parallel([('pilot-r2-frozen','c1',2,f,by_family[f],ts) for f,ts in self.sample.items()],self.frozen_family)
        self.validate_seed_integrity()
        immutable(HERE/'pilot-continuation-acceptance.json',dict(passed=True,historicalSeedsUnchanged=True,
                  trainingTasks=16,frozenTasks=16,firstStageHistoricalRecoveryVerified=True,conditionalProbesPassed=True,
                  initialStateOrigin='verified historical terminal state',protocolSha256=self.executor.protocol_hash,
                  historicalScoringNotAssumedFrozen=True))

    def r1(self):
        assert json.loads((HERE/'pilot-continuation-acceptance.json').read_text())['passed']
        self.phase='formal-r1-and-matched-vanilla';self.status()
        items=[]
        for f,tasks in self.tasks.items():
            for arm in ['janus','vanilla']:
                state=copy.deepcopy(self.seeds[f])
                if arm=='vanilla':state=dict(family=f,carry='',plan=None,staffSource=None)
                items.append(('formal-r1-frozen' if arm=='janus' else 'formal-vanilla','shared',1,f,state,tasks,arm))
        groups=self.parallel(items,self.frozen_family)
        rows=[r for group in groups for r in group]
        assert len(rows)==132 and sum(r['arm']=='janus' for r in rows)==66
        self.validate_seed_integrity()
        atomic(HERE/'formal-r1-records.json',rows)
        report=self.summarize_r1(rows)
        atomic(HERE/'r1-historical-difference-audit.json',report)
        self.phase='r1-completed-awaiting-difference-review';self.status()

    def summarize_r1(self,rows):
        metrics={}
        for arm in ['janus','vanilla']:
            selected=[r for r in rows if r['arm']==arm]
            families=[]
            for family in self.tasks:
                subset=[r for r in selected if r['family']==family]
                assert len(subset)==len(self.tasks[family])
                families.append(dict(family=family,n=len(subset),passed=sum(float(r['reward'])>=1 for r in subset)))
            metrics[arm]=dict(passed=sum(x['passed'] for x in families),n=66,families=families)
        lift=sum(Fraction(j['passed'],j['n'])-Fraction(v['passed'],v['n']) for j,v in zip(metrics['janus']['families'],metrics['vanilla']['families']))/8
        return dict(completed=True,executionAndStateConsumptionChecksPassed=all(r['inputConsumed'] for r in rows),
                    metrics=metrics,equalFamilyLiftPP=float(lift*100),historicalJanusPassed=39,historicalVanillaPassed=33,
                    historyUsedAdaptiveScores=True,currentMeasurement='frozen shared historical terminal state, unified terminal task contract',
                    stateReplicates=1,executionReplicates=1,vanillaReplicates=1,autoAuthorizeContinuation=False,
                    requiredReview='Inspect input/base/scoring equivalence and explain historical differences; do not demand historical percentages.')

    def vanilla(self):
        self.phase='formal-matched-vanilla';self.status()
        groups=self.parallel([('formal-vanilla','shared',1,f,dict(family=f,carry='',plan=None,staffSource=None),ts,'vanilla')
                              for f,ts in self.tasks.items()],self.frozen_family)
        rows=[r for group in groups for r in group]
        assert len(rows)==66
        atomic(HERE/'formal-vanilla-records.json',rows)
        self.phase='matched-vanilla-completed';self.status()

    def continuation(self):
        gate=json.loads((HERE/'r1-review-acceptance.json').read_text())
        assert gate['passed'] and gate['protocolSha256']==self.executor.protocol_hash
        for chain in ['c1','c2','c3']:
            for family,state in self.seeds.items():
                self.checkpoints.seed(chain,family,copy.deepcopy(state))
                self.checkpoints.snapshot(chain,1,family,copy.deepcopy(state))
        for round_ in [2,3,4]:
            self.phase='formal-r%d-online'%round_;self.status()
            states=self.parallel([('formal',chain,round_,family,tasks) for chain in ['c1','c2','c3'] for family,tasks in self.tasks.items()],self.evolve_family)
            self.phase='formal-r%d-frozen'%round_;self.status()
            jobs=[]
            for chain in ['c1','c2','c3']:
                for family,tasks in self.tasks.items():
                    path=HERE/'formal/chains'/chain/('r%d'%round_)/'snapshots'/('family-'+digest(family)[:12]+'.json')
                    state=json.loads(path.read_text());jobs.append(('formal-r%d-frozen'%round_,chain,round_,family,state,tasks))
            self.parallel(jobs,self.frozen_family)
            self.validate_seed_integrity()
        self.phase='all-rounds-scored-awaiting-independent-audit';self.status()

    def close(self):
        if self.model is not None:self.model.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--through',choices=['pilot','r1','vanilla','continue','all'],required=True)
    parser.add_argument('--workers',type=int,default=6);args=parser.parse_args()
    # One in-flight task per chain and family. Tasks inside one family stay ordered.
    assert 1<=args.workers<=24
    campaign=Campaign(args.workers)
    try:
        if not (HERE/'pilot-continuation-acceptance.json').exists():
            campaign.model=ModelClient();campaign.pilot_gate()
        if args.through in ['r1','all']:campaign.r1()
        if args.through=='vanilla':campaign.vanilla()
        if args.through=='continue':
            campaign.model=ModelClient();campaign.continuation()
        if args.through=='all':
            if campaign.model is None:campaign.model=ModelClient()
            campaign.continuation()
    except BaseException as exc:
        campaign.status(type(exc).__name__+':'+str(exc));raise
    finally:campaign.close()


if __name__=='__main__':main()
