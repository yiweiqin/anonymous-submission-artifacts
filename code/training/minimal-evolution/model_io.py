"""Single prompt/encoding definition shared by training and both inference arms."""
import json
from collections.abc import Mapping


def token_ids(value):
    if isinstance(value, Mapping):
        value=value['input_ids']
    if hasattr(value,'tolist'):
        value=value.tolist()
    if value and isinstance(value[0],list):
        if len(value)!=1: raise ValueError('single_conversation_required')
        value=value[0]
    return list(value)


def encode(tokenizer, prompt, completion, limit):
    if not isinstance(json.loads(completion), dict):
        raise ValueError('completion_not_object')
    messages=[{'role':'user','content':prompt}]
    prefix=token_ids(tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, enable_thinking=False))
    full=token_ids(tokenizer.apply_chat_template(messages+[{'role':'assistant','content':completion}], tokenize=True,
                                       add_generation_prompt=False, enable_thinking=False))
    if full[:len(prefix)] != prefix or len(full)<=len(prefix):
        raise ValueError('template_prefix_or_empty_answer')
    if len(full)>limit:
        raise ValueError(f'truncation_forbidden:{len(full)}>{limit}')
    return {'input_ids':full,'attention_mask':[1]*len(full),'labels':[-100]*len(prefix)+full[len(prefix):]}


def load_tokenizer(model):
    from transformers import AutoTokenizer
    tok=AutoTokenizer.from_pretrained(model,local_files_only=True,trust_remote_code=False)
    if tok.pad_token_id is None:
        tok.pad_token=tok.eos_token
    tok.padding_side='right'
    return tok


def load_model(model, adapter=None, training=False, config=None):
    import torch
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig
    from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
    if not torch.cuda.is_available():
        raise RuntimeError('gpu_allocation_required')
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError('bf16_gpu_required')
    quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',
                            bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16)
    net=AutoModelForCausalLM.from_pretrained(model,quantization_config=quant,dtype=torch.bfloat16,
                                            device_map={'':0},local_files_only=True,trust_remote_code=False)
    if training:
        net=prepare_model_for_kbit_training(net)
        net=get_peft_model(net,LoraConfig(r=config['loraRank'],lora_alpha=config['loraAlpha'],
                             lora_dropout=config['loraDropout'],target_modules=config['targetModules'],task_type='CAUSAL_LM'))
        net.config.use_cache=False
    elif adapter:
        net=PeftModel.from_pretrained(net,adapter,local_files_only=True)
    return net
