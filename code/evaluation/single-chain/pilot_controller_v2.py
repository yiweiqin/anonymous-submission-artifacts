"""Frozen R1 historical-state handoff pilot only. Never starts a full campaign."""
import argparse
import hashlib
import json
import os
import shlex
import threading
import time
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import paramiko

HERE=Path(__file__).resolve().parent
NATIVE='/benchmark/skillflow-main-20261008/legacy-continuation-20261022/v2'
ACTOR_SHA='972e67ccca571702abc09b7371da96cc7aa0ee7f5363b3787b8fc8c20381b2f9'
LOCK=threading.Lock()
STOP=threading.Event()


def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2));tmp.replace(path)


def connect(env):
    c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(env['host'],username=env['user'],password=env['password'],timeout=15,banner_timeout=15,auth_timeout=15)
    c.get_transport().set_keepalive(15)
    return c


def read_json(s,path):
    for attempt in range(5):
        try:
            with s.open(path,'rb') as f:return json.loads(f.read().decode())
        except json.JSONDecodeError:
            if attempt==4:raise
            time.sleep(1)


def resource_wait(client):
    source='import json,pathlib,shutil; m={x.split(":",1)[0]:int(x.split()[1])*1024 for x in pathlib.Path("/proc/meminfo").read_text().splitlines() if x.split()[1].isdigit()};print(json.dumps({"available":m["MemAvailable"],"swapFree":m["SwapFree"],"diskFree":shutil.disk_usage("/").free}))'
    # Waiting for free resources happens before any task execution. Keep the
    # original thresholds; do not abort healthy in-flight work after 15 minutes.
    deadline=time.monotonic()+7200
    while time.monotonic()<deadline:
        _,out,err=client.exec_command('python3 -c '+shlex.quote(source),timeout=20)
        r=json.loads(out.read().decode());assert out.channel.recv_exit_status()==0
        if r['available']>512*1024**2 and r['swapFree']>1024**3 and r['diskFree']>6*1024**3:return r
        time.sleep(10)
    raise RuntimeError('native_resource_pressure')


def native_trial(env,family,task,carry,arm):
    key=hashlib.sha256((family+'/'+task).encode()).hexdigest()[:14]
    logical='pilot-v2-r1-'+arm+'-'+key
    outdir=HERE/'pilot-v2-r1'/logical
    outdir.mkdir(parents=True,exist_ok=True)
    final=outdir/'commit.json'
    state_sha=hashlib.sha256(carry.encode()).hexdigest()
    if final.exists():
        data=json.loads(final.read_text());assert data['inputCarrySha256']==state_sha
        return data
    attempts=[]
    for attempt in range(1,4):
        job='legacy-'+logical+'-a'+str(attempt)
        request=dict(jobName=job,family=family,task=task,carry=carry,actorSha256=ACTOR_SHA,
                     protocol='historical-single-session-40',learningEnabled=False)
        atomic(outdir/('request-a%d.json'%attempt),request)
        c=connect(env)
        try:
            pressure=resource_wait(c)
            s=c.open_sftp();s.get_channel().settimeout(30)
            remote_request=NATIVE+'/requests/'+job+'.json'
            try:s.mkdir(NATIVE+'/requests')
            except OSError:pass
            try:
                old=read_json(s,remote_request);assert old==request
            except FileNotFoundError:
                with s.open(remote_request,'w') as f:f.write(json.dumps(request))
            result_path=NATIVE+'/jobs/'+job+'.json'
            try:payload=read_json(s,result_path)
            except FileNotFoundError:
                cmd='/benchmark/skillflow-main-20261008/SkillFlow/.venv/bin/python '+shlex.quote(NATIVE+'/native_attempt.py')+' '+shlex.quote(remote_request)
                _,out,err=c.exec_command(cmd,timeout=10900)
                # The native helper writes full logs to its owned job directory.
                output=out.read().decode();error=err.read().decode();code=out.channel.recv_exit_status()
                (outdir/('transport-a%d.log'%attempt)).write_text(output+'\n'+error)
                if code:raise RuntimeError('native_attempt_nonzero:'+str(code))
                payload=read_json(s,result_path)
            receipt=read_json(s,NATIVE+'/jobs/'+job+'.receipt.json')
            assert receipt['baseImage']=='sha256:44397015d80d7bed516cfe355743720748f3950e1f02f5f887274348e033a955'
            atomic(outdir/('result-a%d.json'%attempt),payload)
            atomic(outdir/('receipt-a%d.json'%attempt),receipt)
            valid=payload.get('reward') is not None and not payload.get('error')
            attempts.append(dict(attempt=attempt,jobName=job,reward=payload.get('reward'),error=payload.get('error'),
                                 modelCalls=payload.get('modelCalls'),promptTokens=payload.get('promptTokens'),
                                 completionTokens=payload.get('completionTokens'),wallSeconds=payload.get('wallSeconds'),resourceBefore=pressure))
            if not valid:
                if attempt<3:continue
                raise RuntimeError('native_infrastructure_attempts_exhausted')
            config=read_json(s,NATIVE+'/jobs/'+job+'/config.json')
            agent=config['agents'][0]
            assert agent['kwargs']['max_turns']==40 and agent['kwargs']['temperature']==0
            assert agent['model_name']=='openai/deepseek-flash'
            assert config.get('extra_instructions',[])==([carry] if carry else [])
            trial_dirs=[x for x in s.listdir_attr(NATIVE+'/jobs/'+job) if __import__('stat').S_ISDIR(x.st_mode)]
            assert len(trial_dirs)==1
            trajectory=read_json(s,NATIVE+'/jobs/'+job+'/'+trial_dirs[0].filename+'/agent/trajectory.json')
            messages=[x.get('message','') for x in trajectory['steps'] if x.get('source')=='user']
            assert messages and (not carry or carry in messages[0])
            expected_prefix=json.loads((HERE/'execution-protocol.json').read_text())['historicalExecutorPromptPrefixSha256']
            assert hashlib.sha256(messages[0].split('Task Description:',1)[0].encode()).hexdigest()==expected_prefix, 'executor prompt changed'
            assert any(x.get('source')=='agent' for x in trajectory['steps']), 'no real execution response'
            atomic(outdir/'native-config.json',config)
            atomic(outdir/'native-trajectory.json',trajectory)
            row=dict(logicalId=logical,phase='pilot-v2-r1-frozen',arm=arm,family=family,task=task,reward=payload['reward'],
                     inputCarrySha256=state_sha,carryCharacters=len(carry),stateConsumedInRealFirstRequest=True,
                     planningReportConsumed=False,staffCapabilitiesConsumed=False,learningEnabled=False,
                     protocol='historical-single-session-40',attempts=attempts,finishedAt=time.time(),
                     sourceState='shared historical terminal state' if arm=='janus' else 'empty Vanilla context')
            atomic(final,row);return row
        finally:c.close()
    raise AssertionError('unreachable')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=6);args=parser.parse_args()
    assert 1<=args.workers<=8
    env=json.loads((HERE/'.control-env.json').read_text())
    prep=json.loads((HERE/'preparation-request.json').read_text())
    family_tasks={}
    for x in prep['sample']:family_tasks.setdefault(x['family'],[]).append(x['task'])
    states={}
    for p in (HERE/'historical-terminal-state').glob('*.json'):
        d=json.loads(p.read_text());states[d['family']]=d
    original_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (HERE/'historical-terminal-state').glob('*.json')}
    done=[]
    def status(phase,error=None):
        with LOCK:
            atomic(HERE/'pilot-status.json',dict(phase=phase,completed=len(done),expected=32,workers=args.workers,
                    fullScaleStarted=False,learningEnabled=False,error=error,updatedAt=time.time(),
                    passed=sum(float(x['reward'])>=1 for x in done)))
    def family_worker(family,tasks,arm):
        try:
            for task in tasks:
                if STOP.is_set():return False
                row=native_trial(env,family,task,states[family]['carry'] if arm=='janus' else '',arm)
                with LOCK:done.append(row)
                status('halting-after-failure' if STOP.is_set() else 'running')
        except BaseException:
            STOP.set();raise
        return True
    from conditional_probes import run_probes
    status('controlled-probes')
    try:
        run_probes()
    except BaseException as exc:
        status('failed',type(exc).__name__+':'+str(exc))
        raise
    status('starting')
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            jobs=[pool.submit(family_worker,f,ts,arm) for f,ts in family_tasks.items() for arm in ['janus','vanilla']]
            for f in as_completed(jobs):f.result()
        assert len(done)==32 and all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in original_hashes.items())
        atomic(HERE/'pilot-v2-r1-summary.json',dict(completed=True,records=done,sourceSnapshotsUnchanged=True,
                evaluatorLearningCalls=0,fullScaleStarted=False,requiredNextStep='Audit handoff and historical differences before any full-scale execution.'))
        status('completed-awaiting-handoff-audit')
    except BaseException as exc:
        status('failed',type(exc).__name__+':'+str(exc));raise


if __name__=='__main__':main()
