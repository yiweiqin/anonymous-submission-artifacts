"""QLoRA SFT for CPDB 0-100 scores. Same JSON task as the Astra teacher.

Does not train a 101-class head or the 92-d MLP. Without Astra labels the
trainer exits `cpdb_qlora_labels_missing` and does not fall back to hybrid/v3.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "qlora_config.json"
DEFAULT_SFT = ROOT / "artifacts" / "cpdb-scorer-v5-100" / "sft"
DEFAULT_LABELS = ROOT / "artifacts" / "cpdb-scorer-v5-100" / "labels.jsonl"
LABELS_MISSING = "cpdb_qlora_labels_missing"

from tdb_completion import encode_completion


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def parse_score_100(value) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        value = int(value.strip())
    if isinstance(value, float) and not value.is_integer():
        return None
    if isinstance(value, (int, float)):
        number = int(value)
        if number == value and 0 <= number <= 100:
            return number
    return None


def assert_sft_contract(train: list[dict], development: list[dict]) -> None:
    if not train or not development:
        raise ValueError("train_and_development_required")
    for split, rows in (("train", train), ("development", development)):
        for row in rows:
            prompt = row.get("prompt") or ""
            completion = row.get("completion") or ""
            if "dependency" not in prompt or "similarity" not in prompt:
                raise ValueError(f"prompt_missing_axes:{row.get('id')}")
            if "0.75" in completion:
                raise ValueError(f"five_bin_completion_forbidden:{row.get('id')}")
            gold = json.loads(completion)
            if "combined" in gold:
                raise ValueError(f"combined_score_forbidden:{row.get('id')}")
            if set(gold) != {"dependency", "similarity", "rationale"}:
                raise ValueError(f"completion_schema:{row.get('id')}")
            if parse_score_100(gold["dependency"]) is None or parse_score_100(gold["similarity"]) is None:
                raise ValueError(f"completion_not_score100:{split}:{row.get('id')}")
            if completion and completion in prompt:
                raise ValueError(f"prompt_contains_completion:{row.get('id')}")


def _transformers_available() -> bool:
    import importlib.util
    return importlib.util.find_spec("transformers") is not None


def _gpu_info(torch_mod) -> dict:
    if not torch_mod.cuda.is_available():
        return {"available": False}
    return {
        "available": True,
        "index": 0,
        "name": torch_mod.cuda.get_device_name(0),
        "totalBytes": torch_mod.cuda.get_device_properties(0).total_memory,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(DEFAULT_SFT))
    parser.add_argument("--labels", default=str(DEFAULT_LABELS))
    parser.add_argument("--model", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--epochs", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-length", type=int, default=0)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--skip-tokenize", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    labels_path = Path(args.labels)
    if not args.smoke and not labels_path.is_file():
        raise SystemExit(LABELS_MISSING)

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
    head = str(cfg.get("head") or "").lower()
    if head in {"mlp", "101-class", "101_class", "92d"}:
        raise SystemExit("cpdb_qlora_mlp_head_forbidden")

    data = Path(args.data) / "smoke" if args.smoke else Path(args.data)
    train_path = data / "train.jsonl"
    dev_path = data / "development.jsonl"
    if not train_path.is_file() or not dev_path.is_file():
        raise SystemExit(LABELS_MISSING)

    train = read_jsonl(train_path)
    development = read_jsonl(dev_path)
    assert_sft_contract(train, development)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=args.force)
    epochs = args.epochs or int(cfg.get("epochs", 2))
    seed = args.seed or int(cfg.get("seed", 20260920))
    max_length = args.max_length or int(cfg.get("maxLength", 4096))
    model_id = args.model or cfg.get("baseModel") or "Qwen/Qwen3-8B"
    local_only = Path(model_id).is_dir()
    sft_manifest = data / "manifest.json"
    sft_meta = json.loads(sft_manifest.read_text(encoding="utf-8-sig")) if sft_manifest.is_file() else {}

    manifest = {
        "schemaVersion": "cpdb-qlora-run-v1",
        "task": "cpdb_score100_sft",
        "kind": "llm_sft",
        "head": "generative_json",
        "dataKind": sft_meta.get("schemaVersion") or "cpdb-sft-v1",
        "model": model_id,
        "seed": seed,
        "epochs": epochs,
        "smoke": bool(args.smoke),
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "outputDir": str(out.resolve()),
        "rows": {"train": len(train), "development": len(development)},
        "dataSha256": {"train": digest(train_path), "development": digest(dev_path)},
        "labelsSha256": digest(labels_path) if labels_path.is_file() else "",
        "config": cfg,
        "maxLength": max_length,
        "status": "prepared",
        "note": "Do not load tokenizer into Electron. scored* divides 0-100 by 100.",
    }

    if args.skip_tokenize or (args.prepare_only and not _transformers_available()):
        manifest["tokenization"] = "skipped"
        write_json(out / "run_manifest.json", manifest)
        print(json.dumps({"status": "prepared", "tokenization": "skipped", "rows": manifest["rows"]}, ensure_ascii=False))
        return

    import torch
    from transformers import AutoTokenizer, set_seed

    set_seed(seed)
    torch.set_num_threads(4)
    tok = AutoTokenizer.from_pretrained(model_id, local_files_only=local_only, trust_remote_code=True)
    if not isinstance(getattr(tok, "chat_template", None), str) or not str(tok.chat_template).strip():
        raise ValueError("explicit_chat_template_required")
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token

    encoded = {}
    supervised = []
    max_len = 0
    for split, rows in (("train", train), ("development", development)):
        encoded[split] = []
        for index, row in enumerate(rows):
            if index % 200 == 0:
                print(f"encode {split} {index}/{len(rows)}", flush=True)
            item = encode_completion(tok, row["prompt"], row["completion"], max_length)
            length = int(sum(item["attention_mask"]))
            max_len = max(max_len, length)
            supervised.append(sum(label != -100 for label in item["labels"]))
            encoded[split].append({key: value[:length] for key, value in item.items()})
    manifest.update(
        maxTokens=max_len,
        minimumSupervisedTokens=min(supervised) if supervised else 0,
        tokenization="encoded",
        gpu=_gpu_info(torch),
        assistantOnlyLoss=True,
    )
    write_json(out / "run_manifest.json", manifest)
    if args.prepare_only:
        print(json.dumps({"status": "prepared", "maxTokens": max_len, "rows": manifest["rows"]}, ensure_ascii=False))
        return

    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig, DataCollatorForSeq2Seq, Trainer, TrainingArguments

    lora = cfg.get("lora") or {}
    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=quant,
        dtype=torch.bfloat16,
        device_map={"": 0},
        local_files_only=local_only,
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    model = get_peft_model(
        model,
        LoraConfig(
            r=int(lora.get("r", 16)),
            lora_alpha=int(lora.get("alpha", 32)),
            lora_dropout=float(lora.get("dropout", 0.05)),
            target_modules=list(lora.get("targetModules") or ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]),
            task_type="CAUSAL_LM",
        ),
    )
    model.config.use_cache = False
    effective = max(1, int(cfg.get("perDeviceTrainBatchSize", 1)) * int(cfg.get("gradientAccumulationSteps", 16)))
    warmup = max(1, math.ceil(0.03 * len(train) / effective * epochs))
    training = TrainingArguments(
        output_dir=str(out / "checkpoints"),
        num_train_epochs=epochs,
        per_device_train_batch_size=int(cfg.get("perDeviceTrainBatchSize", 1)),
        per_device_eval_batch_size=int(cfg.get("perDeviceEvalBatchSize", 1)),
        gradient_accumulation_steps=int(cfg.get("gradientAccumulationSteps", 16)),
        learning_rate=float(cfg.get("learningRate", 1e-4)),
        bf16=True,
        gradient_checkpointing=True,
        lr_scheduler_type="cosine",
        warmup_steps=warmup,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to=[],
    )

    def to_dataset(encoded_rows):
        return Dataset.from_list([
            {
                "input_ids": item["input_ids"],
                "attention_mask": item["attention_mask"],
                "labels": item["labels"],
            }
            for item in encoded_rows
        ])

    trainer = Trainer(
        model=model,
        args=training,
        train_dataset=to_dataset(encoded["train"]),
        eval_dataset=to_dataset(encoded["development"]),
        data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100),
    )
    trainer.train()
    adapter_dir = out / "adapter"
    trainer.save_model(str(adapter_dir))
    tok.save_pretrained(str(adapter_dir))
    manifest["status"] = "trained"
    manifest["adapterDir"] = str(adapter_dir)
    write_json(out / "run_manifest.json", manifest)
    print(json.dumps({"status": "trained", "adapterDir": str(adapter_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
