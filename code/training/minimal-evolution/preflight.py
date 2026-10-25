"""Full pre-training preflight; tokenizes corpus but NEVER loads model weights or trains."""
import argparse
import importlib.metadata as metadata
import inspect
import json
import shutil
import time
from pathlib import Path
from audit import audit
from prepare import HERE, sha


def inspect_environment(model):
    import torch
    from transformers import Trainer, TrainingArguments, BitsAndBytesConfig
    from peft import LoraConfig, prepare_model_for_kbit_training
    from datasets import Dataset
    from safetensors import safe_open
    from model_io import load_tokenizer
    model=Path(model)
    versions={n:metadata.version(n) for n in ('torch','transformers','peft','datasets','bitsandbytes','accelerate','safetensors')}
    index=json.loads((model/'model.safetensors.index.json').read_text())
    config=json.loads((model/'config.json').read_text())
    if config.get('model_type')!='qwen3':
        raise ValueError('unexpected_base_architecture')
    base_files={}
    for filename in sorted(set(index['weight_map'].values())):
        file=model/filename
        if file.parent!=model or not file.is_file():
            raise ValueError('weight_shard_missing')
        with safe_open(str(file),framework='pt',device='cpu') as f:
            actual=set(f.keys())
            expected={k for k,v in index['weight_map'].items() if v==filename}
            if actual!=expected:
                raise ValueError('weight_index_mismatch')
        base_files[filename]={'bytes':file.stat().st_size,'sha256':sha(file)}
    for filename in ('config.json','tokenizer.json','tokenizer_config.json','model.safetensors.index.json'):
        base_files[filename]={'bytes':(model/filename).stat().st_size,'sha256':sha(model/filename)}
    required={'eval_strategy','save_strategy','bf16','warmup_steps','gradient_checkpointing','load_best_model_at_end'}
    if not required<=set(inspect.signature(TrainingArguments).parameters):
        raise ValueError('training_api_incompatible')
    cfg=json.loads((HERE/'config.json').read_text())
    # Instantiate the same API on CPU without creating Trainer or any model.
    TrainingArguments(output_dir='/tmp/rdmd-preflight-no-training',use_cpu=True,
                      eval_strategy='epoch',save_strategy='epoch',load_best_model_at_end=True,
                      warmup_steps=1,gradient_checkpointing=True,report_to='none')
    LoraConfig(r=cfg['loraRank'],lora_alpha=cfg['loraAlpha'],target_modules=cfg['targetModules'],task_type='CAUSAL_LM')
    BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16)
    free=shutil.disk_usage(HERE).free/2**30
    gpu=torch.cuda.is_available(); blockers=[]
    if not gpu: blockers.append('gpu_not_allocated')
    elif not torch.cuda.is_bf16_supported(): blockers.append('bf16_unsupported')
    if free<8: blockers.append('disk_free_below_8GiB')
    gpu_info=[]
    for i in range(torch.cuda.device_count()):
        p=torch.cuda.get_device_properties(i)
        gpu_info.append({'name':p.name,'totalGiB':p.total_memory/2**30})
    if gpu and gpu_info[0]['totalGiB']<22: blockers.append('gpu_memory_below_22GiB')
    return {'packages':versions,'cuda':gpu,'gpus':gpu_info,'diskFreeGiB':free,'baseFiles':base_files,'blockers':blockers,
            'weightsLoaded':False,'optimizerSteps':0,'gpuMemoryFitMeasured':False}


def main():
    p=argparse.ArgumentParser(); p.add_argument('--data',type=Path,default=HERE/'data')
    p.add_argument('--model',default=json.loads((HERE/'config.json').read_text())['baseModel'])
    p.add_argument('--out',type=Path,required=True); a=p.parse_args()
    checked=audit(a.data,a.model,full_oracle=True)
    env=inspect_environment(a.model)
    report={'status':'READY' if not env['blockers'] else 'BLOCKED','preparedWithoutGpu':checked['status']=='PASS',
            'timestamp':time.time(),'dataset':checked,'environment':env,
            'manifestSha256':sha(a.data/'manifest.json'),'configSha256':sha(HERE/'config.json'),
            'codeHashes':{f.name:sha(f) for f in sorted(HERE.glob('*.py'))},'trainingStarted':False}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(json.dumps({'status':report['status'],'preparedWithoutGpu':report['preparedWithoutGpu'],
                       'blockers':env['blockers'],'maxTokens':checked['maxTokens'],'trainingStarted':False}))
    if env['blockers']: raise SystemExit(3)


if __name__=='__main__': main()
