"""Explicit opt-in QLoRA SFT. No test/holdout rows are read by this trainer."""
import argparse
import importlib.metadata
import json
import random
import math
import time
from pathlib import Path
from audit import rows
from engine import SCHEMA, dumps
from model_io import encode, load_model, load_tokenizer
from prepare import HERE, sha


def training_rows(data):
    manifest=json.loads((data/'manifest.json').read_text(encoding='utf8'))
    if manifest['schema']!=SCHEMA or manifest['engineSha256']!=sha(HERE/'engine.py'):
        raise ValueError('dataset_contract_or_engine_drift')
    splits={}
    for split in ('train','development'):
        file=data/f'{split}.sft.jsonl'
        if sha(file)!=manifest['files'][file.name]['sha256']:
            raise ValueError('training_hash_mismatch')
        splits[split]=list(rows(file))
        if not splits[split]:
            raise ValueError('empty_training_split')
        for r in splits[split]:
            gold=json.loads(r['completion'])
            if r['split']!=split or gold['decision']!=r['decision'] or set(gold)!={'decision','direction','sourceNodeIds','edits'}:
                raise ValueError('training_contract')
    if {r['groupId'] for r in splits['train']} & {r['groupId'] for r in splits['development']}:
        raise ValueError('train_dev_group_leak')
    return splits


def main():
    p=argparse.ArgumentParser(); p.add_argument('--data',type=Path,default=HERE/'data')
    p.add_argument('--out',type=Path,required=True); p.add_argument('--model')
    p.add_argument('--execute-training',action='store_true'); p.add_argument('--preflight-report',type=Path)
    a=p.parse_args(); cfg=json.loads((HERE/'config.json').read_text()); base=a.model or cfg['baseModel']
    if a.out.exists():
        raise ValueError('new_output_directory_required')
    splits=training_rows(a.data)
    if not a.execute_training:
        print(dumps({'status':'DRY_RUN_NO_TRAINING','rows':{s:len(r) for s,r in splits.items()},'base':base})); return
    if not a.preflight_report:
        raise ValueError('preflight_report_required')
    report=json.loads(a.preflight_report.read_text())
    if report.get('status')!='READY' or report.get('manifestSha256')!=sha(a.data/'manifest.json') or report.get('configSha256')!=sha(HERE/'config.json') or report.get('codeHashes')!={f.name:sha(f) for f in sorted(HERE.glob('*.py'))}:
        raise ValueError('stale_or_blocked_preflight')
    from preflight import inspect_environment
    environment=inspect_environment(base)
    if environment['blockers'] or environment['baseFiles']!=report['environment']['baseFiles']:
        raise ValueError('environment_or_base_changed')
    import torch
    from datasets import Dataset
    from transformers import Trainer, TrainingArguments, DataCollatorForSeq2Seq, set_seed
    set_seed(cfg['seed']); tok=load_tokenizer(base)
    encoded={s:[encode(tok,r['prompt'],r['completion'],cfg['maxLength']) for r in rr] for s,rr in splits.items()}
    a.out.mkdir(parents=True,exist_ok=False)
    run={'schema':SCHEMA,'status':'loading','base':base,'config':cfg,'manifestSha256':sha(a.data/'manifest.json'),
         'codeHashes':{f.name:sha(f) for f in sorted(HERE.glob('*.py'))},'testRead':False,'startedAt':time.time(),
         'dataHashes':{s:sha(a.data/f'{s}.sft.jsonl') for s in splits},'environment':environment}
    def save(): (a.out/'run_manifest.json').write_text(json.dumps(run,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    save()
    try:
        net=load_model(base,training=True,config=cfg)
        args=TrainingArguments(output_dir=str(a.out/'checkpoints'),num_train_epochs=cfg['epochs'],
             per_device_train_batch_size=cfg['batchSize'],per_device_eval_batch_size=1,
             gradient_accumulation_steps=cfg['gradientAccumulationSteps'],learning_rate=cfg['learningRate'],
             bf16=True,gradient_checkpointing=True,lr_scheduler_type='cosine',
             warmup_steps=max(1,math.ceil(.03*len(splits['train'])*cfg['epochs']/cfg['gradientAccumulationSteps'])),
             eval_strategy='epoch',save_strategy='epoch',load_best_model_at_end=True,metric_for_best_model='eval_loss',
             greater_is_better=False,save_total_limit=2,logging_steps=10,report_to='none',
             seed=cfg['seed'],data_seed=cfg['seed'],dataloader_num_workers=0)
        trainer=Trainer(model=net,args=args,train_dataset=Dataset.from_list(encoded['train']),
             eval_dataset=Dataset.from_list(encoded['development']),
             data_collator=DataCollatorForSeq2Seq(tok,padding=True,label_pad_token_id=-100,pad_to_multiple_of=8))
        run['status']='training'; save()
        result=trainer.train(); trainer.save_model(str(a.out/'adapter')); tok.save_pretrained(a.out/'adapter')
        trainer.state.save_to_json(str(a.out/'trainer_state.json'))
        run.update(status='trained',metrics=result.metrics,steps=trainer.state.global_step,
                   bestDevelopmentLoss=trainer.state.best_metric,elapsedSeconds=time.time()-run['startedAt'],
                   adapterHashes={f.name:sha(f) for f in (a.out/'adapter').iterdir() if f.is_file()})
        save()
    except BaseException as e:
        run.update(status='failed',error=f'{type(e).__name__}:{e}'); save(); raise


if __name__=='__main__':
    main()
