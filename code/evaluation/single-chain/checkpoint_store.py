"""Immutable content-verified scientific checkpoints and idempotent task commits."""
import hashlib
import json
import os
from pathlib import Path


def encoded(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def immutable(path,value):
    path=Path(path)
    data=encoded(value)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        assert path.read_bytes()==data,'immutable artifact mismatch: '+str(path)
        return hashlib.sha256(data).hexdigest()
    temporary=path.with_name(path.name+'.pending-'+str(os.getpid()))
    with temporary.open('xb') as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    # A logical task has one owner. Existing finished paths are never replaced.
    if path.exists():
        assert path.read_bytes()==data
        temporary.unlink()
    else:temporary.rename(path)
    return hashlib.sha256(data).hexdigest()


class Checkpoints:
    def __init__(self,root):self.root=Path(root)

    def seed(self,chain,family,state):
        assert chain in ['c1','c2','c3'] and state['family']==family
        return immutable(self.root/'chains'/chain/'initial'/('family-'+digest(family)[:12]+'.json'),state)

    def commit(self,chain,round_,family,task,before,after,outcome):
        assert chain in ['c1','c2','c3'] and round_ in [2,3,4]
        assert before['family']==after['family']==family
        path=self.root/'chains'/chain/('r%d'%round_)/'commits'/(digest([family,task])[:24]+'.json')
        return immutable(path,dict(chain=chain,round=round_,family=family,task=task,
                              inputStateSha256=digest(before),outputStateSha256=digest(after),stateAfter=after,outcome=outcome))

    def snapshot(self,chain,round_,family,state):
        assert chain in ['c1','c2','c3'] and round_ in [1,2,3,4]
        assert state['family']==family
        path=self.root/'chains'/chain/('r%d'%round_)/'snapshots'/('family-'+digest(family)[:12]+'.json')
        return path,immutable(path,state)

    def read_for_evaluation(self,path,expected):
        data=Path(path).read_bytes()
        assert hashlib.sha256(data).hexdigest()==expected
        # JSON deserialization creates an independent object; evaluators receive
        # no mutable writer or current-state handle.
        return json.loads(data)
