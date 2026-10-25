"""Recover the terminal campaign's original update functions, not new learning."""
import ast
import hashlib
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
SOURCE=HERE/'legacy-source'
_LOADED=None


def load_policy():
    global _LOADED
    if _LOADED is not None:return _LOADED
    root=SOURCE/'experiments/skillflow_main_table'
    sys.path.insert(0,str(root))
    import harbor_bridge
    wrapper=SOURCE/'skillflow_focus_remote.py'
    text=wrapper.read_text(encoding='utf-8')
    tree=ast.parse(text)
    wanted_assign={'WEIGHTED_ORIGINAL','WEIGHTED_CACHE','WEIGHTED_CACHE_AUTHORIZED'}
    wanted_funcs={'protected_update','protected_carry'}
    keep=[]
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in wanted_assign for t in node.targets):keep.append(node)
        elif isinstance(node,ast.FunctionDef) and node.name in wanted_funcs:keep.append(node)
    assert sum(isinstance(x,ast.FunctionDef) for x in keep)==2
    scope=dict(harbor_bridge=harbor_bridge,original_one_update=harbor_bridge.one_update,original_next_carry=harbor_bridge.next_carry)
    extracted=ast.Module(body=keep,type_ignores=[])
    exec(compile(extracted,str(wrapper),'exec'),scope)
    # The final retained weighted cache state was measured by cacheformal-2345
    # with this historical flag enabled; retain its recorded conditional rule.
    scope['WEIGHTED_CACHE_AUTHORIZED']=True
    harbor_bridge.one_update=scope['protected_update']
    harbor_bridge.next_carry=scope['protected_carry']
    evidence=dict(coreSourceSha256=hashlib.sha256((root/'harbor_bridge.py').read_bytes()).hexdigest(),
                  historicalWrapperSha256=hashlib.sha256(wrapper.read_bytes()).hexdigest(),
                  extractedOriginalFunctions=sorted(wanted_funcs),weightedCacheAuthorized=True,
                  historicalRerunAllowlistRetained=False,historicalSkipPassedRetained=False,
                  uniformNewRoundScheduling=True,newLearningMechanisms=0)
    _LOADED=(harbor_bridge,evidence)
    return _LOADED


def candidate(bridge,state,verdict,trace):
    return bridge.one_update(verdict,trace,state['family'])


def next_state(bridge,state,verdict,trace,reward,replay_reward,replacement=''):
    result=json.loads(json.dumps(state))
    result['plan']=bridge.apply_replacement(state['plan'],verdict,replacement)
    result['carry']=bridge.next_carry(state['carry'],verdict,family=state['family'],reward=reward,replay_reward=replay_reward,trace=trace)
    return result
