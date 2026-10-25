"""A resident original detector; immutable requests are never shared across tasks."""
import json
import subprocess
import threading
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
PYTHON='/data/modelstore/rdmd-env/bin/python'


class ModelClient:
    def __init__(self):
        self.lock=threading.Lock()
        self.stderr=(HERE/'model-worker.stderr.log').open('a')
        self.process=subprocess.Popen([PYTHON,str(HERE/'model_worker.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                      stderr=self.stderr,text=True,bufsize=1)
        self.ready=self._read()
        assert self.ready['type']=='ready',self.ready
        (HERE/'model-worker-ready.json').write_text(json.dumps(self.ready,indent=2))

    def _read(self):
        while True:
            line=self.process.stdout.readline()
            if not line:raise RuntimeError('model_worker_exited')
            try:return json.loads(line)
            except ValueError:
                with (HERE/'model-worker-extra-output.log').open('a') as f:f.write(line)

    def ask(self,case,request_id):
        directory=HERE/'model-calls'/request_id
        directory.mkdir(parents=True,exist_ok=True)
        request=dict(op='detective',requestId=request_id,case=case)
        src=directory/'request.json';out=directory/'result.json'
        if src.exists():assert json.loads(src.read_text())==request
        else:src.write_text(json.dumps(request,ensure_ascii=False,indent=2))
        if out.exists():return json.loads(out.read_text())
        attempt=directory/('attempt-%d.json'%time.time_ns())
        started=time.monotonic()
        attempt.write_text(json.dumps(dict(status='started',startedAt=time.time(),workerPid=self.process.pid,
                         modelCallsAttempted=1,tokenUsage=None,requestId=request_id)))
        with self.lock:
            self.process.stdin.write(json.dumps(request,ensure_ascii=False)+'\n');self.process.stdin.flush()
            result=self._read()
        assert result['type']=='result',result
        assert result['requestId']==request_id
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2))
        attempt.write_text(json.dumps(dict(status='completed',modelCallsAttempted=1,requestId=request_id,
                         workerPid=self.process.pid,wallSeconds=time.monotonic()-started,usage=result['usage'])))
        return result

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.write('{"op":"shutdown"}\n');self.process.stdin.flush()
            try:self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=10)
        self.stderr.close()
