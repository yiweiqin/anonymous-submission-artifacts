import json
import run
run.load_env()
import baselines
remote = "/benchmark/skillflow-main-20261008/baseline-jobs/qwen-baseline-vanilla-Healthcare-Cost-Benefit-Analysis-harbor_cyclemargin_30v90/qwen-baseline-vanilla-Healthcare-Cost-Benefit-Analysis-harbor_cyclemargin_30v90"
# The job directory name equals the job name. Harbor nests a trial directory.
script = r"""
import json
from pathlib import Path
root = Path("/benchmark/skillflow-main-20261008/baseline-jobs/qwen-baseline-vanilla-Healthcare-Cost-Benefit-Analysis-harbor_cyclemargin_30v90")
for path in root.rglob("result.json"):
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    info = ((data.get("agent_info") or {}).get("model_info") or {}).get("name")
    configured = ((data.get("config") or {}).get("agent") or {}).get("model_name")
    print(path.parent.name)
    print("info", info)
    print("configured", configured)
    break
"""
ssh = baselines.light_client()
try:
    code, out, err = baselines.exec_text(ssh, "python3 - << 'PY'\n" + script + "PY", 40)
    print(out)
    print(err[-200:])
finally:
    ssh.close()
