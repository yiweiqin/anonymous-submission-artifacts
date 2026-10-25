"""Read-only resident instance of the original historical Detective implementation.

Caching avoids loading identical frozen weights for every task. Prompts, parser,
dtype, decoding and minimal update policy remain in the original source files.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
SOURCE=HERE/'legacy-source/experiments/rdmd_detective_dataset/deploy'
sys.path.insert(0,str(SOURCE))
from rdmd_detective import Detective,build_case_prompt,check_case_contract


def emit(value):
    print(json.dumps(value,ensure_ascii=False),flush=True)


def tensor_sha(tensor):
    return hashlib.sha256(tensor.detach().cpu().numpy().tobytes()).hexdigest()


def main():
    sys.path.insert(0,str(HERE/'legacy-source/experiments/skillflow_main_table'))
    from harbor_bridge import model_roles
    roles=model_roles()
    started=time.monotonic()
    detective=Detective(roles['baseModel'],roles['detective']['adapter'],device='cuda:0',max_new_tokens=160)
    load_wall=time.monotonic()-started
    versions={name:parameter._version for name,parameter in detective.model.named_parameters()}
    generate=detective.model.generate
    meters=[]
    def metered(*args,**kwargs):
        ids=args[0] if args else kwargs['input_ids']
        started=time.monotonic()
        generated=generate(*args,**kwargs)
        meters.append(dict(inputTokens=int(ids.shape[-1]),outputTokens=int(generated.shape[-1]-ids.shape[-1]),
                           inputIdsSha256=tensor_sha(ids),outputIdsSha256=tensor_sha(generated),
                           maxNewTokens=kwargs.get('max_new_tokens'),doSample=kwargs.get('do_sample'),
                           inferenceWallSeconds=time.monotonic()-started))
        return generated
    detective.model.generate=metered
    emit(dict(type='ready',loadWallSeconds=load_wall,residentFrozenWeights=True,originalSourceSha256=hashlib.sha256((SOURCE/'rdmd_detective.py').read_bytes()).hexdigest(),
              dtype='original bfloat16',maxNewTokens=160,doSample=False,training=False))
    for line in sys.stdin:
        try:
            req=json.loads(line)
            if req['op']=='shutdown':break
            case=req['case']
            problems=check_case_contract(case)
            assert not problems, 'original case contract: '+str(problems)
            meters.clear();started=time.monotonic()
            result=detective.predict(case)
            assert versions=={name:p._version for name,p in detective.model.named_parameters()},'frozen weights changed'
            prompt=build_case_prompt(case)
            emit(dict(type='result',requestId=req['requestId'],result=result,usage=meters[:],
                      prompt=prompt,promptSha256=hashlib.sha256(prompt.encode()).hexdigest(),
                      wallSeconds=time.monotonic()-started,parametersUnchanged=True))
        except BaseException as exc:
            emit(dict(type='error',error=type(exc).__name__+': '+str(exc)))


if __name__=='__main__':main()
