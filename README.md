# Model weights

Two QLoRA adapters for `Qwen/Qwen3-8B`, revision `b968826d9c46dd6066d109eabc6255188de91218`. The base model is Apache-2.0; see `NOTICE`. This archive keeps the adapter settings and the weight checksums. The weight files are available at these links:

- Detective adapter: https://anonymous-hf.com/a/fdrwqsbu2et2/
- Dependency-similarity adapter: https://anonymous-hf.com/a/um2iuefn3n8f/

`MANIFEST.json` gives the byte size and SHA256 of every file in this archive. A `sourceSha256` field means a text file had a local path rewritten before publication. `python reassemble.py` checks the archive against that manifest.

## minimal-evolution

The detective adapter loaded by the recorded SkillFlow runs is https://anonymous-hf.com/a/fdrwqsbu2et2/. `adapter_model.safetensors` SHA256: `8755e26df3f370a8396e7acdae6670f2a45c6cdcdbca4ea3d0ce911a059afebc`. `minimal-evolution/adapter/adapter_config.json` records the PEFT settings.

The caller is `code/evaluation/detective-deploy/`. Its prompt is `prompt.txt`. The parsed object has `status`, `nodeId`, `edgeId`, `type`, `changedFields`, and `evidenceNodeIds`.

## dependency-similarity

The dependency and similarity adapter loaded by those runs is https://anonymous-hf.com/a/um2iuefn3n8f/. `adapter_model.safetensors` SHA256: `86974ad6106845a5e4b6e7d80486414058c4955e30cbe4d7e24698e1a31c8fb9`. `dependency-similarity/adapter/adapter_config.json` records the PEFT settings.

Its JSON object contains integer fields `dependency` and `similarity` from 0 to 100, plus `rationale`. `code/evaluation/skillflow/ds_remote.py` parses that object.

## Load an exported adapter

Download one adapter from the link above, then load that directory:

```python
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

revision = "b968826d9c46dd6066d109eabc6255188de91218"
base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3-8B", revision=revision, torch_dtype=torch.bfloat16, device_map="auto")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-8B", revision=revision)
model = PeftModel.from_pretrained(base, "path/to/downloaded/adapter")
```

Both adapter configs use LoRA `r=16`, `lora_alpha=32`, dropout `0.05`, and the Qwen attention and MLP projections. PEFT 0.20.0 wrote the configs. This archive does not record a completed local load of the weights.

## Code, data, and results

Training code and data for the two adapters are under `code/training/`. SkillFlow evaluation code is under `code/evaluation/skillflow/`. The 66 SkillFlow task definitions are under `benchmarks/skillflow/`. SQL, Bash, and tau-bench runners, prompts, and the selected 2026-10-25 receipts are under `code/evaluation/sql-bash-tau/`.

`code/evaluation/single-chain/` is the continuation used for the round figure. Host name, GPU name, Python, and model directories come from `config/runtime.example.json`.

Offline checks, with no model call:

```bash
python scripts/check_layout.py
python scripts/rebuild_paper_numbers.py
python reassemble.py
```

`scripts/check_layout.py` imports the parsers and does not load weights. A completed adapter load is not recorded.

`benchmarks/skillflow/` holds the 66 SkillFlow tasks. `benchmarks/intercode/` is InterCode revision `c3e46d827cfc9d4c704ec078f7abf9f41e3191d8`. SQL uses `data/sql/spider`. Bash uses `data/nl2bash`. `benchmarks/tau-bench/` is tau-bench revision `59a200c6d575d595120f1cb70fea53cef0632f6b`. `benchmarks/terminal-bench/` is Terminal-Bench 2.1 revision `7131e4375048a0e408a8fb404b5f499d726b695b`.

`results/case-20261024/trajectory.json` is the case-study trajectory. Its SHA256 is `edbb5b87f4b5721a9afe7ac7ef767dd8d430f5045c45741e1fc5ea10af51a29c`. `results/case-20261024/evidence.json` records the workbook excerpts from that file. `results/october19-tables/03A_主表成本.csv` is the recorded SkillFlow execution cost.

Result tables are under `results/`. `results/main-table-20261025/` is the eight-method table.
