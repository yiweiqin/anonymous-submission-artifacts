"""Score dependency and similarity with the CPDB LoRA.

The tokenizer is loaded from the base model. The adapter directory has weights only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def parse_scores(text):
    raw = str(text or "").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return None
    try:
        dependency = int(data["dependency"])
        similarity = int(data["similarity"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (0 <= dependency <= 100 and 0 <= similarity <= 100):
        return None
    return {
        "dependency": dependency,
        "similarity": similarity,
        "rationale": str(data.get("rationale") or "")[:240],
    }


def main():
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model = sys.argv[1]
    adapter = sys.argv[2]
    src = Path(sys.argv[3])
    dest = Path(sys.argv[4])
    rows = [json.loads(line) for line in src.read_text(encoding="utf-8").splitlines() if line.strip()]
    tokenizer = AutoTokenizer.from_pretrained(model, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    base = AutoModelForCausalLM.from_pretrained(
        model, dtype=torch.bfloat16, device_map={"": "cuda:0"}, trust_remote_code=True,
    )
    scored = PeftModel.from_pretrained(base, adapter)
    scored.eval()
    out = []
    for row in rows:
        encoded = tokenizer.apply_chat_template(
            [{"role": "user", "content": row["prompt"]}],
            tokenize=True, add_generation_prompt=True, enable_thinking=False, return_tensors="pt",
        )
        if hasattr(encoded, "keys"):
            prompt_ids = encoded["input_ids"]
            attention = encoded.get("attention_mask")
        else:
            prompt_ids = encoded
            attention = None
        prompt_ids = prompt_ids.to(scored.device)
        kwargs = {"max_new_tokens": 120, "do_sample": False}
        if attention is not None:
            kwargs["attention_mask"] = attention.to(scored.device)
        with torch.no_grad():
            generated = scored.generate(prompt_ids, **kwargs)
        text = tokenizer.decode(generated[0][prompt_ids.shape[-1]:], skip_special_tokens=True)
        parsed = parse_scores(text) or {"dependency": None, "similarity": None, "rationale": "", "error": "unparsed"}
        parsed["id"] = row["id"]
        out.append(parsed)
    dest.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in out), encoding="utf-8")


if __name__ == "__main__":
    main()
