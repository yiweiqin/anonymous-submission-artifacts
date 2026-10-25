"""Fail-closed dataset audit. Optional exact tokenizer audit uses no model/GPU."""
import argparse
import json
from collections import Counter
from pathlib import Path
from engine import SCHEMA, digest, dumps, prompt, solve, verify_prediction
from prepare import HERE, sha


def rows(path):
    with Path(path).open(encoding='utf8') as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def audit(data, model=None, full_oracle=False):
    manifest=json.loads((data/'manifest.json').read_text(encoding='utf8'))
    if manifest['schema'] != SCHEMA or manifest['status'] != 'PREPARED_NOT_TRAINED':
        raise ValueError('manifest_contract')
    for filename, info in manifest['files'].items():
        file=data/filename
        if not file.is_file() or sha(file)!=info['sha256'] or file.stat().st_size!=info['bytes']:
            raise ValueError(f'data_hash_mismatch:{filename}')
    if manifest['engineSha256']!=sha(HERE/'engine.py') or manifest['generatorSha256']!=sha(HERE/'prepare.py'):
        raise ValueError('generator_drift_regenerate_data')
    config=json.loads((HERE/'config.json').read_text())
    if manifest['configSha256']!=sha(HERE/'config.json'):
        raise ValueError('config_drift')
    tokenizer=None
    if model:
        from model_io import load_tokenizer
        tokenizer=load_tokenizer(model)
    result={'schema':SCHEMA,'model':str(model) if model else None,'manifestSha256':sha(data/'manifest.json'),
            'splits':{},'fullOracleRecomputed':full_oracle,'trainingStarted':False}
    groups_seen=set(); ids_seen=set(); prompts_seen=set(); max_tokens=0
    for split in ('train','development','test','holdout'):
        raw=list(rows(data/f'{split}.cases.jsonl')); sft=list(rows(data/f'{split}.sft.jsonl'))
        if not raw or len(raw)!=len(sft):
            raise ValueError(f'empty_or_mismatched_split:{split}')
        groups={c['groupId'] for c in raw}
        if groups & groups_seen:
            raise ValueError('group_split_leak')
        groups_seen |= groups
        lengths=[]; decisions=Counter(); ids={c['id'] for c in raw}
        if len(ids)!=len(raw) or ids & ids_seen:
            raise ValueError('duplicate_id')
        ids_seen |= ids
        for c,r in zip(raw,sft):
            if c['id']!=r['id'] or c['split']!=split or r['split']!=split or r['groupId']!=c['groupId']:
                raise ValueError('case_sft_join')
            if r['prompt']!=prompt(c) or r['completion']!=dumps(c['oracle']['answer']):
                raise ValueError('prompt_or_gold_drift')
            ph=digest(r['prompt'])
            if ph in prompts_seen:
                raise ValueError('duplicate_prompt')
            prompts_seen.add(ph)
            if not c['oracle']['certified'] or not verify_prediction(c,c['oracle']['answer'])['valid']:
                raise ValueError('invalid_gold')
            if full_oracle and solve(c)!=c['oracle']:
                raise ValueError('oracle_not_reproducible')
            if tokenizer:
                from model_io import encode
                encoded=encode(tokenizer,r['prompt'],r['completion'],config['maxLength'])
                lengths.append(len(encoded['input_ids']))
                if sum(x==-100 for x in encoded['labels'])+config['maxNewTokens']>config['maxLength']:
                    raise ValueError('prompt_exceeds_inference_budget')
                if sum(x!=-100 for x in encoded['labels'])>config['maxNewTokens']:
                    raise ValueError('gold_exceeds_generation_budget')
            decisions[r['decision']]+=1
        if set(decisions)!={'adopt','no_change','abstain'}:
            raise ValueError('missing_decision_class')
        preferences=list(rows(data/f'{split}.preferences.jsonl'))
        cases={c['id']:c for c in raw}
        for p in preferences:
            if p['id'] not in cases or p['groupId']!=cases[p['id']]['groupId']:
                raise ValueError('preference_join')
            c=cases[p['id']]; chk=verify_prediction(c,p['rejected'])
            if p['chosen']!=c['oracle']['answer'] or (chk['valid'] and chk.get('cost',0)<=c['oracle'].get('minimumCost',0)):
                raise ValueError('invalid_preference')
        result['splits'][split]={'rows':len(raw),'groups':len(groups),'decisions':dict(decisions),
                                'preferencePairs':len(preferences),'maxTokens':max(lengths,default=None)}
        if lengths:
            max_tokens=max(max_tokens,max(lengths))
        print(dumps({'audited':split,**result['splits'][split]}),flush=True)
    result.update(status='PASS',tokenizerChecked=tokenizer is not None,maxTokens=max_tokens or None)
    return result


def main():
    p=argparse.ArgumentParser(); p.add_argument('--data',type=Path,default=HERE/'data')
    p.add_argument('--model'); p.add_argument('--full-oracle',action='store_true'); p.add_argument('--out',type=Path)
    a=p.parse_args(); result=audit(a.data,a.model,a.full_oracle)
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(dumps(result))


if __name__=='__main__':
    main()
