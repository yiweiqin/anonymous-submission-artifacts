"""Evaluate CPDB 0-100 QLoRA against Astra teacher scores.

Success metric is facet-fold MAE / Spearman on integers 0-100.
Five-bin exact match is not a success metric.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SFT = ROOT / "experiments" / "cpdb_org_world" / "artifacts" / "cpdb-scorer-v5-100" / "sft"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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


def parse_completion(text: str) -> dict:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = raw.split("```", 1)[0].strip()
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return {"dependency": None, "similarity": None, "parseError": True}
    try:
        value = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"dependency": None, "similarity": None, "parseError": True}
    if not isinstance(value, dict) or "combined" in value:
        return {"dependency": None, "similarity": None, "parseError": True}
    dependency = parse_score_100(value.get("dependency"))
    similarity = parse_score_100(value.get("similarity"))
    if dependency is None or similarity is None:
        return {"dependency": None, "similarity": None, "parseError": True}
    return {
        "dependency": dependency,
        "similarity": similarity,
        "rationale": str(value.get("rationale") or ""),
        "parseError": False,
    }


def pearson(left: list[float], right: list[float]) -> float | None:
    n = len(left)
    if n < 2:
        return None
    mean_l = sum(left) / n
    mean_r = sum(right) / n
    num = sum((a - mean_l) * (b - mean_r) for a, b in zip(left, right))
    den_l = math.sqrt(sum((a - mean_l) ** 2 for a in left))
    den_r = math.sqrt(sum((b - mean_r) ** 2 for b in right))
    if den_l == 0 or den_r == 0:
        return None
    return num / (den_l * den_r)


def rankdata(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda at: values[at])
    out = [0.0] * len(values)
    at = 0
    while at < len(order):
        end = at
        while end + 1 < len(order) and values[order[end + 1]] == values[order[at]]:
            end += 1
        average = (at + end) / 2 + 1
        for cursor in range(at, end + 1):
            out[order[cursor]] = average
        at = end + 1
    return out


def spearman(left: list[float], right: list[float]) -> float | None:
    return pearson(rankdata(left), rankdata(right))


def axis_report(pred: list[float], gold: list[float]) -> dict:
    n = len(gold)
    mae = sum(abs(a - b) for a, b in zip(pred, gold)) / n if n else None
    rmse = math.sqrt(sum((a - b) ** 2 for a, b in zip(pred, gold)) / n) if n else None
    return {
        "n": n,
        "mae": None if mae is None else round(mae, 3),
        "rmse": None if rmse is None else round(rmse, 3),
        "spearman": None if spearman(pred, gold) is None else round(spearman(pred, gold), 4),
        "pearson": None if pearson(pred, gold) is None else round(pearson(pred, gold), 4),
    }


def score_rows(rows: list[dict], preds: dict[str, dict]) -> dict:
    usable = []
    parse_error = 0
    missing = 0
    for row in rows:
        gold = parse_completion(row["completion"])
        pred = preds.get(row["id"])
        if pred is None:
            missing += 1
            continue
        if pred.get("parseError") or gold.get("parseError"):
            parse_error += 1
            continue
        usable.append((pred, gold))
    report = {
        "n": len(rows),
        "scored": len(usable),
        "parseError": parse_error,
        "missing": missing,
        "note": "MAE/Spearman on 0-100 integers. Not five-bin exact match.",
    }
    if usable:
        for axis in ("dependency", "similarity"):
            report[axis] = axis_report(
                [item[0][axis] for item in usable],
                [item[1][axis] for item in usable],
            )
    return report


def generate_predictions(rows: list[dict], model: str, adapter: str, max_new_tokens: int, batch_size: int) -> list[dict]:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(adapter or model, trust_remote_code=True)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"
    base = AutoModelForCausalLM.from_pretrained(
        model,
        dtype=torch.bfloat16,
        device_map={"": 0},
        trust_remote_code=True,
    )
    model_obj = PeftModel.from_pretrained(base, adapter) if adapter else base
    model_obj.eval()
    out_rows = []
    for start in range(0, len(rows), max(1, batch_size)):
        batch = rows[start:start + max(1, batch_size)]
        texts = []
        for row in batch:
            encoded = tok.apply_chat_template(
                [{"role": "user", "content": row["prompt"]}],
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            texts.append(encoded)
        inputs = tok(texts, return_tensors="pt", padding=True).to(model_obj.device)
        with torch.no_grad():
            gen = model_obj.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tok.pad_token_id,
            )
        prompt_len = inputs["input_ids"].shape[1]
        for at, row in enumerate(batch):
            text = tok.decode(gen[at][prompt_len:], skip_special_tokens=True)
            parsed = parse_completion(text)
            out_rows.append({
                "id": row["id"],
                "split": row.get("split"),
                "prediction": text,
                "parsed": parsed,
                "gold": row["completion"],
            })
        done = start + len(batch)
        if done % 32 == 0 or done == len(rows):
            print(f"[eval] {done}/{len(rows)}", flush=True)
    return out_rows


def load_hybrid_times_100(path: Path) -> dict[str, dict]:
    out = {}
    for row in read_jsonl(path):
        dep = row.get("dependency")
        sim = row.get("similarity")
        if dep is None or sim is None:
            continue
        out[row["id"]] = {
            "dependency": int(round(float(dep) * 100)),
            "similarity": int(round(float(sim) * 100)),
        }
    return out


def baseline_report(rows: list[dict], lookup: dict[str, dict], name: str) -> dict:
    preds = {}
    for row in rows:
        item = lookup.get(row["id"])
        if not item:
            continue
        preds[row["id"]] = {**item, "parseError": False}
    report = score_rows(rows, preds)
    report["name"] = name
    report["gold"] = False
    report["note"] = "Five-bin x100 control, not 0-100 gold."
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(DEFAULT_SFT))
    parser.add_argument("--model", default="Qwen/Qwen3-8B")
    parser.add_argument("--adapter", default="dependency-similarity/adapter")
    parser.add_argument("--output", required=True)
    parser.add_argument("--split", default="development", choices=["development", "train", "both"])
    parser.add_argument("--train-limit", type=int, default=256)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-new-tokens", type=int, default=160)
    parser.add_argument("--hybrid-labels", default="")
    parser.add_argument("--score-only", action="store_true")
    args = parser.parse_args()

    data = Path(args.data)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    splits = []
    if args.split in ("development", "both"):
        splits.append(("development", read_jsonl(data / "development.jsonl")))
    if args.split in ("train", "both"):
        train = read_jsonl(data / "train.jsonl")
        if args.train_limit and args.train_limit < len(train):
            train = train[: args.train_limit]
        splits.append(("train", train))

    reports = {
        "schemaVersion": "cpdb-qlora-eval-v1",
        "adapter": args.adapter,
        "model": args.model,
        "metric": "mae_spearman_0_100",
        "splits": {},
    }
    for name, rows in splits:
        if args.limit:
            rows = rows[: args.limit]
        pred_path = out / f"{name}.predictions.jsonl"
        if args.score_only:
            pred_rows = read_jsonl(pred_path)
        else:
            pred_rows = generate_predictions(rows, args.model, args.adapter, args.max_new_tokens, args.batch_size)
            pred_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in pred_rows), encoding="utf-8")
        preds = {row["id"]: row.get("parsed") or parse_completion(row.get("prediction") or "") for row in pred_rows}
        report = score_rows(rows, preds)
        report["name"] = f"qlora:{name}"
        if args.hybrid_labels:
            hybrid = load_hybrid_times_100(Path(args.hybrid_labels))
            report["hybridFiveBinTimes100"] = baseline_report(rows, hybrid, f"hybrid_x100:{name}")
        reports["splits"][name] = report
        print(json.dumps(report, ensure_ascii=False), flush=True)
    write_json(out / "metrics.json", reports)
    print(json.dumps({"status": "ok", "out": str(out), "splits": {name: reports["splits"][name] for name in reports["splits"]}}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
