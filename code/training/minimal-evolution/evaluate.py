"""One evaluator for rule, base, adapter and externally generated general-AI answers.

Models see only task/graphs/observations. Hidden verification and transfer worlds are
used only in scoring. External import requires an exact ID join and arm provenance.
"""
import argparse
import json
import time
from collections import Counter
from pathlib import Path
from audit import rows
from engine import answer, catalog, cost, dumps, prompt, solve, verify_prediction
from prepare import HERE, sha


def parse(text):
    try:
        obj=json.loads(text)
        return obj if isinstance(obj,dict) else None
    except (ValueError,TypeError): return None


def score(case, prediction):
    gold=case['oracle']; pred=prediction
    if not isinstance(pred,dict):
        return {'parseError':True,'decisionCorrect':False,'verifiedSuccess':False,'transferSuccess':False,
                'minimalRepair':False,'unsafeAdoption':False,'abstained':False,'costRegret':None}
    checked=verify_prediction(case,pred)
    transfer=verify_prediction(case,pred,case['transferWorlds'])
    adopt=pred.get('decision')=='adopt'
    success=checked['valid'] and pred.get('decision') in ('adopt','no_change')
    regret=checked.get('cost',0)-gold.get('minimumCost',0) if adopt and checked['valid'] and gold['answer']['decision']=='adopt' else None
    return {'parseError':False,'decisionCorrect':pred.get('decision')==gold['answer']['decision'],
            'verifiedSuccess':success,'transferSuccess':success and transfer['valid'],
            'minimalRepair':adopt and checked['valid'] and regret==0 and transfer['valid'],
            'unsafeAdoption':adopt and not (checked['valid'] and transfer['valid']),
            'abstained':pred.get('decision')=='abstain','costRegret':regret,'verification':checked}


def summarize(scored):
    n=len(scored); adopt_gold=[r for r in scored if r['goldDecision']=='adopt']
    decisions=Counter(r['goldDecision'] for r in scored)
    result={'n':n,'goldDecisions':dict(decisions)}
    for key in ('parseError','decisionCorrect','verifiedSuccess','transferSuccess','unsafeAdoption','abstained'):
        result[key+'Rate']=sum(bool(r['metrics'][key]) for r in scored)/n if n else None
    result['minimalRepairRate']=sum(r['metrics']['minimalRepair'] for r in adopt_gold)/len(adopt_gold) if adopt_gold else None
    result['repairDenominator']=len(adopt_gold)
    regrets=[r['metrics']['costRegret'] for r in scored if r['metrics']['costRegret'] is not None]
    result['meanCostRegretOnValidAdoptions']=sum(regrets)/len(regrets) if regrets else None
    result['byMode']={mode:summarize_flat([r for r in scored if r['mode']==mode]) for mode in sorted({r['mode'] for r in scored})}
    return result


def summarize_flat(rr):
    return {'n':len(rr),'decisionCorrectRate':sum(r['metrics']['decisionCorrect'] for r in rr)/len(rr),
            'unsafeAdoptionRate':sum(r['metrics']['unsafeAdoption'] for r in rr)/len(rr)}


def generate_batches(cases, net, tok, cfg, batch_size):
    """Yield raw outputs in case order; preserve completed batches on interruption."""
    import torch
    tok.padding_side='left'
    for start in range(0,len(cases),batch_size):
        batch=cases[start:start+batch_size]
        started=time.time()
        texts=[tok.apply_chat_template([{'role':'user','content':prompt(c)}],
                                       tokenize=False,add_generation_prompt=True,
                                       enable_thinking=False) for c in batch]
        inputs=tok(texts,return_tensors='pt',padding=True,add_special_tokens=False).to(net.device)
        width=inputs['input_ids'].shape[1]
        if width+cfg['maxNewTokens']>cfg['maxLength']:
            raise ValueError('inference_budget_overflow')
        with torch.inference_mode():
            output=net.generate(**inputs,max_new_tokens=cfg['maxNewTokens'],do_sample=False,
                                pad_token_id=tok.pad_token_id)
        if len(output)!=len(batch): raise ValueError('generation_batch_count_mismatch')
        decoded=[tok.decode(row[width:],skip_special_tokens=True) for row in output]
        seconds=(time.time()-started)/len(batch)
        for raw in decoded:
            yield raw,seconds
        print(dumps({'generated':start+len(batch),'total':len(cases)}),flush=True)


def main():
    p=argparse.ArgumentParser(); p.add_argument('--data',type=Path,default=HERE/'data')
    p.add_argument('--split',choices=['development','test','holdout'],default='holdout')
    p.add_argument('--arm',choices=['no_change','copy_exec','rule_search','H3_base','trained','external','oracle_selftest'],required=True)
    p.add_argument('--out',type=Path,required=True); p.add_argument('--model'); p.add_argument('--adapter',type=Path)
    p.add_argument('--external',type=Path); p.add_argument('--external-provenance',type=Path)
    p.add_argument('--export-requests',action='store_true'); p.add_argument('--batch-size',type=int,default=8); a=p.parse_args()
    if a.batch_size < 1: raise ValueError('batch_size_must_be_positive')
    cfg=json.loads((HERE/'config.json').read_text()); model=a.model or cfg['baseModel']
    file=a.data/f'{a.split}.cases.jsonl'
    manifest=json.loads((a.data/'manifest.json').read_text())
    if sha(file)!=manifest['files'][file.name]['sha256']: raise ValueError('case_hash_mismatch')
    cases=list(rows(file)); ids={c['id'] for c in cases}
    if len(ids)!=len(cases): raise ValueError('duplicate_case_id')
    a.out.mkdir(parents=True,exist_ok=False)
    request_path=a.out/'requests.jsonl'
    request_path.write_text(''.join(dumps({'id':c['id'],'messages':[{'role':'user','content':prompt(c)}],
                                        'temperature':0,'max_tokens':cfg['maxNewTokens'],'n':1})+'\n' for c in cases),encoding='utf8')
    if a.export_requests:
        print(dumps({'requests':str(request_path),'rows':len(cases),'sha256':sha(request_path)})); return
    provenance={'arm':a.arm,'model':model if a.arm in ('H3_base','trained') else None,'split':a.split,
                'caseSha256':sha(file),'engineSha256':sha(HERE/'engine.py'),'evaluatorSha256':sha(__file__),
                'requestSha256':sha(request_path),'maxNewTokens':cfg['maxNewTokens'],'temperature':0,'n':1,
                'visibleVerifierBudget':64 if a.arm=='rule_search' else 0,'trained':a.arm=='trained',
                'oracleSelftest':a.arm=='oracle_selftest'}
    imported={}; net=tok=None
    if a.arm=='external':
        if not a.external or not a.external_provenance: raise ValueError('external_files_required')
        entries=list(rows(a.external)); imported={r['id']:r['prediction'] for r in entries}
        if len(imported)!=len(entries) or set(imported)!=ids: raise ValueError('external_join_mismatch')
        ep=json.loads(a.external_provenance.read_text())
        if ep.get('requestSha256')!=sha(request_path) or not ep.get('model') or ep.get('n')!=1 or ep.get('temperature')!=0 or ep.get('maxNewTokens')!=cfg['maxNewTokens']:
            raise ValueError('external_provenance_or_budget_mismatch')
        provenance['external']=ep; provenance['externalPredictionsSha256']=sha(a.external)
    if a.arm in ('H3_base','trained'):
        from model_io import load_model,load_tokenizer
        from transformers import set_seed
        set_seed(cfg['seed'])
        if a.arm=='trained' and not a.adapter: raise ValueError('adapter_required')
        if a.arm=='H3_base' and a.adapter: raise ValueError('base_arm_cannot_load_adapter')
        tok=load_tokenizer(model); net=load_model(model,str(a.adapter) if a.adapter else None); net.eval()
        provenance['adapterHashes']={f.name:sha(f) for f in a.adapter.iterdir() if f.is_file()} if a.adapter else None
        provenance['baseHashes']={f.name:sha(f) for f in Path(model).glob('*.safetensors')}
    generated=None
    if a.arm in ('H3_base','trained'):
        generated=generate_batches(cases,net,tok,cfg,a.batch_size)
        provenance['batchSize']=a.batch_size
        provenance['rowSecondsMeaning']='amortized_batch_generation_seconds'
    (a.out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf8')
    scored=[]; started=time.time()
    with (a.out/'predictions.jsonl').open('w',encoding='utf8',newline='\n') as sink:
        for c in cases:
            t=time.time(); raw=''; generation_seconds=None
            if a.arm=='no_change': pred=answer(c,decision='no_change')
            elif a.arm=='copy_exec': pred=answer(c,catalog(c['G_plan'],c['G_exec']))
            elif a.arm=='rule_search': pred=solve(c,worlds=c['observedWorlds'],budget=64)['answer']
            elif a.arm=='oracle_selftest': pred=c['oracle']['answer']
            elif a.arm=='external':
                raw=imported[c['id']]; pred=parse(raw) if isinstance(raw,str) else raw
            else:
                raw,generation_seconds=next(generated); pred=parse(raw)
            row={'id':c['id'],'groupId':c['groupId'],'mode':c['generation']['mode'],
                 'goldDecision':c['oracle']['answer']['decision'],'prediction':pred,'raw':raw,
                 'seconds':generation_seconds if generation_seconds is not None else time.time()-t,'metrics':score(c,pred)}
            sink.write(dumps(row)+'\n'); sink.flush(); scored.append(row)
    summary={**summarize(scored),'arm':a.arm,'elapsedSeconds':time.time()-started,'provenance':provenance}
    (a.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(dumps(summary))


if __name__=='__main__': main()
