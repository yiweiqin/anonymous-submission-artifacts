"""Original Harbor execution with task-unique requests and complete attempt retention."""
import hashlib
import json
import stat
import time
from pathlib import Path
from pilot_controller_v2 import connect,read_json,resource_wait,ACTOR_SHA
from checkpoint_store import encoded

HERE=Path(__file__).resolve().parent
BASE='sha256:796d89c5bf93e24493b4aa2ae5b4079f861e56c95274fc1b0f97c5597d4501b8'


def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_bytes(encoded(value));tmp.replace(path)


def execution_identity(logical_id,family,task,carry,protocol_hash):
    value=dict(logicalId=logical_id,family=family,task=task,carry=carry,protocolSha256=protocol_hash)
    return hashlib.sha256(encoded(value)).hexdigest()


class Executor:
    def __init__(self):
        self.env=json.loads((HERE/'.control-env.json').read_text())
        self.protocol=json.loads((HERE/'execution-protocol.json').read_text())
        self.protocol_hash=hashlib.sha256((HERE/'execution-protocol.json').read_bytes()).hexdigest()
        self.native=self.protocol['nativeRoot']
        assert self.native.endswith('/legacy-continuation-20261022/v3')
        manifest=json.loads((HERE/'native-task-manifest.json').read_text())
        self.packages={(x['family'],x['task']):x for x in manifest['packages']}

    def run(self,logical_id,phase,arm,family,task,carry,state_hash=None):
        identity=execution_identity(logical_id,family,task,carry,self.protocol_hash)
        outdir=HERE/'executions'/identity
        outdir.mkdir(parents=True,exist_ok=True)
        final=outdir/'commit.json'
        if final.exists():
            value=json.loads(final.read_text())
            assert value['logicalId']==logical_id and value['carry']==carry and value['protocolSha256']==self.protocol_hash
            return value
        attempts=[]
        for attempt in range(1,4):
            job='legacy-'+identity[:28]+'-a'+str(attempt)
            request=dict(jobName=job,family=family,task=task,carry=carry,actorSha256=ACTOR_SHA,
                         protocol='historical-single-session-40',logicalId=logical_id,phase=phase,
                         expectedBaseImage=BASE,expectedTaskDigest=self.packages[(family,task)]['executionDigest'])
            atomic(outdir/('request-a%d.json'%attempt),request)
            c=None
            last=None
            for _ in range(5):
                try:
                    c=connect(self.env)
                    break
                except Exception as exc:
                    last=exc
                    time.sleep(2)
            if c is None:
                raise RuntimeError('native ssh unavailable') from last
            try:
                pressure=resource_wait(c)
                s=c.open_sftp();s.get_channel().settimeout(40)
                remote=self.native+'/requests/'+job+'.json'
                try:s.mkdir(self.native+'/requests')
                except OSError:pass
                try:assert read_json(s,remote)==request
                except FileNotFoundError:
                    with s.open(remote,'w') as f:f.write(json.dumps(request))
                result_path=self.native+'/jobs/'+job+'.json'
                try:payload=read_json(s,result_path)
                except FileNotFoundError:
                    command='/benchmark/skillflow-main-20261008/SkillFlow/.venv/bin/python '+self.native+'/native_attempt.py '+remote
                    waited=0
                    while True:
                        _,stdout,stderr=c.exec_command(command,timeout=10900)
                        out=stdout.read().decode();error=stderr.read().decode();code=stdout.channel.recv_exit_status()
                        (outdir/('transport-a%d.log'%attempt)).write_text(out+'\n'+error)
                        if code and 'existing_attempt_requires_reconciliation' in out+error:
                            waited+=1
                            if waited>24:raise RuntimeError('existing attempt stayed locked; not resampling')
                            time.sleep(5)
                            continue
                        break
                    if code:
                        try:
                            payload=read_json(s,result_path)
                        except FileNotFoundError:
                            if attempt<3:
                                continue
                            raise RuntimeError('Uncertain native execution requires reconciliation; do not resample: '+str(code))
                    else:
                        payload=read_json(s,result_path)
                receipt=read_json(s,self.native+'/jobs/'+job+'.receipt.json')
                assert receipt.get('baseImage')==BASE
                atomic(outdir/('result-a%d.json'%attempt),payload)
                atomic(outdir/('receipt-a%d.json'%attempt),receipt)
                valid=payload.get('reward') is not None and not payload.get('error')
                usage={k:payload.get(k) for k in ['modelCalls','promptTokens','completionTokens','wallSeconds']}
                attempts.append(dict(attempt=attempt,jobName=job,reward=payload.get('reward'),error=payload.get('error'),
                                     usage=usage,usageCompleteness='reported native usage' if valid else 'failure usage may be incomplete; raw zero is not asserted as zero actual cost',
                                     resourceBefore=pressure))
                atomic(outdir/'attempts.json',attempts)
                if not valid:
                    if attempt<3:continue
                    raise RuntimeError('native infrastructure attempts exhausted')
                config=read_json(s,self.native+'/jobs/'+job+'/config.json')
                lock=read_json(s,self.native+'/jobs/'+job+'/lock.json')
                agent=config['agents'][0]
                assert agent['model_name']=='openai/deepseek-flash' and agent['kwargs']['temperature']==0 and agent['kwargs']['max_turns']==40
                assert config['environment']['force_build'] is True
                assert config.get('extra_instructions',[])==([carry] if carry else [])
                assert lock['harbor']['version']=='0.24.0'
                assert lock['trials'][0]['task']['digest']==self.packages[(family,task)]['executionDigest']
                dirs=[x.filename for x in s.listdir_attr(self.native+'/jobs/'+job) if stat.S_ISDIR(x.st_mode)]
                assert len(dirs)==1
                trajectory_path=self.native+'/jobs/'+job+'/'+dirs[0]+'/agent/trajectory.json'
                try:
                    trajectory=read_json(s,trajectory_path)
                except (json.JSONDecodeError,FileNotFoundError) as exc:
                    # Apply the same evidence requirement to every reward,
                    # including passing attempts. Never adopt before this gate.
                    attempts[-1].update(auditFailure='missing or corrupt real execution trajectory',
                                        scoreRetainedButNotAdmissible=True,originalReward=payload['reward'],
                                        error=type(exc).__name__,trajectoryPath=trajectory_path)
                    atomic(outdir/'attempts.json',attempts)
                    if attempt<3:continue
                    raise RuntimeError('native trajectory evidence exhausted; no update adopted') from exc
                first=next(x['message'] for x in trajectory['steps'] if x.get('source')=='user')
                assert (not carry or carry in first) and any(x.get('source')=='agent' for x in trajectory['steps'])
                assert hashlib.sha256(first.split('Task Description:',1)[0].encode()).hexdigest()==self.protocol['historicalExecutorPromptPrefixSha256']
                atomic(outdir/'native-config.json',config);atomic(outdir/'native-lock.json',lock);atomic(outdir/'native-trajectory.json',trajectory)
                value=dict(logicalId=logical_id,phase=phase,arm=arm,family=family,task=task,carry=carry,reward=payload['reward'],
                           protocolSha256=self.protocol_hash,inputStateSha256=state_hash,inputCarrySha256=hashlib.sha256(carry.encode()).hexdigest(),
                           attempts=attempts,sourceTaskDigest=lock['trials'][0]['task']['digest'],baseImage=BASE,
                           nativeResultPath=result_path,nativeEvidenceDirectory=self.native+'/jobs/'+job,
                           inputConsumed=True,planningCapabilitiesConsumed=False,staffCapabilitiesConsumed=False,
                           trace=payload.get('trace',''),artifactDirectory=str(outdir),finishedAt=time.time())
                atomic(final,value)
                return value
            finally:c.close()
        raise AssertionError('unreachable')
