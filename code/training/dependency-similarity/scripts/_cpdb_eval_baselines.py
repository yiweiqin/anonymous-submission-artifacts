"""Local control: hybrid five-bin x100 vs Astra gold on the facet eval fold."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_qlora_cpdb import parse_completion, read_jsonl, score_rows, load_hybrid_times_100, baseline_report

ROOT = Path(__file__).resolve().parents[1]
SFT = ROOT / "experiments" / "cpdb_org_world" / "artifacts" / "cpdb-scorer-v5-100" / "sft"
HYBRID = ROOT / "experiments" / "cpdb_org_world" / "artifacts" / "cpdb-scorer-v4-hybrid" / "labels.jsonl"

def mean_baseline(rows):
    golds = [parse_completion(row["completion"]) for row in rows]
    golds = [row for row in golds if not row.get("parseError")]
    mean_d = round(sum(row["dependency"] for row in golds) / len(golds))
    mean_s = round(sum(row["similarity"] for row in golds) / len(golds))
    preds = {row["id"]: {"dependency": mean_d, "similarity": mean_s, "parseError": False} for row in rows}
    report = score_rows(rows, preds)
    report["name"] = "mean_constant"
    report["constant"] = {"dependency": mean_d, "similarity": mean_s}
    return report

def main():
    development = read_jsonl(SFT / "development.jsonl")
    train = read_jsonl(SFT / "train.jsonl")[:256]
    hybrid = load_hybrid_times_100(HYBRID)
    out = {
        "development": {
            "hybridFiveBinTimes100": baseline_report(development, hybrid, "hybrid_x100:development"),
            "meanConstant": mean_baseline(development),
        },
        "train256": {
            "hybridFiveBinTimes100": baseline_report(train, hybrid, "hybrid_x100:train256"),
            "meanConstant": mean_baseline(train),
        },
    }
    dest = ROOT / "experiments" / "cpdb_org_world" / "artifacts" / "cpdb-scorer-v5-100" / "eval_baselines.json"
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
