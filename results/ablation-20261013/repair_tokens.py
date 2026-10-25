"""Fill GPU token totals from pair scores and the detective output still on the model host."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
LEDGER = HERE / "ledgers" / "m9-plan.jsonl"
GPU_PYTHON = "/data/modelstore/rdmd-env/bin/python"


def main():
    rows = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        scores = row.get("staffScores") or []
        if not row.get("dsCalls") or row.get("dsPromptTokens") is not None:
            continue
        if not scores or any(item.get("promptTokens") is None for item in scores):
            print("ds_unfilled", row.get("task"))
            continue
        row["dsPromptTokens"] = sum(item["promptTokens"] for item in scores)
        row["dsCompletionTokens"] = sum(item["completionTokens"] for item in scores)
        print("ds_backfill", row["task"], row["dsPromptTokens"], row["dsCompletionTokens"])
    fill_detective(rows)
    LEDGER.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def fill_detective(rows):
    slug = "detective-m9-plan-Healthcare-Cost-Benefit-Analysis-harbor_cyclemargin_30v90"
    remote = "/data/modelstore/skillflow-main-20261008/janus-detective/" + slug + ".jsonl"
    script = "from pathlib import Path\np=Path(%r)\nprint(p.read_text(encoding='utf-8') if p.is_file() else '')" % remote
    encoded = base64.b64encode(script.encode()).decode()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        os.environ["RDMD_SSH_HOST"], port=int(os.environ["RDMD_SSH_PORT"]),
        username=os.environ["RDMD_SSH_USER"], password=os.environ["RDMD_SSH_PASSWORD"],
        timeout=20, allow_agent=False, look_for_keys=False,
    )
    try:
        command = GPU_PYTHON + " -c \"import base64; exec(base64.b64decode('" + encoded + "'))\""
        _stdin, stdout, _stderr = client.exec_command(command, timeout=30)
        text = stdout.read().decode("utf-8", "replace")
        if stdout.channel.recv_exit_status() != 0 or "promptTokens" not in text:
            print("detective_unfilled")
            return
        payload = json.loads([line for line in text.splitlines() if line.startswith("{")][-1])
    finally:
        client.close()
    for row in rows:
        if row.get("task") == "harbor_cyclemargin_30v90" and row.get("detectiveCalls") and row.get("detectivePromptTokens") is None:
            row["detectivePromptTokens"] = payload.get("promptTokens")
            row["detectiveCompletionTokens"] = payload.get("completionTokens")
            print("detective_backfill", row["detectivePromptTokens"], row["detectiveCompletionTokens"])


if __name__ == "__main__":
    main()
