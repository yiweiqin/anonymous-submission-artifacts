import json

import run

run.load_env()
import baselines

REMOTE = (
    "/benchmark/skillflow-main-20261008/baseline-jobs/"
    "qwen-baseline-vanilla-Healthcare-Cost-Benefit-Analysis-harbor_cyclemargin_30v90"
)
script = (
    "from pathlib import Path\n"
    "root = Path(" + json.dumps(REMOTE) + ")\n"
    "text = ''\n"
    "paths = [root.with_suffix('.json')]\n"
    "if root.is_dir():\n"
    "    paths.extend(root.rglob('result.json'))\n"
    "for path in paths:\n"
    "    if path.is_file():\n"
    "        text += path.read_text(encoding='utf-8', errors='replace')[:200000]\n"
    "print('qwen', text.count('qwen3.8-flash'))\n"
    "print('deepseek', text.count('deepseek-flash'))\n"
    "print('chars', len(text))\n"
)
ssh = baselines.light_client()
try:
    code, out, err = baselines.exec_text(ssh, "python3 - << 'PY'\n" + script + "PY", 60)
    print("scan", code)
    print(out)
    print(err[-500:])
finally:
    ssh.close()

import janus_full
import harbor_bridge

roles_file = harbor_bridge.model_roles()
roles = {
    "baseModel": roles_file["baseModel"],
    "detectiveAdapter": roles_file["detective"]["adapter"],
    "dsAdapter": roles_file["dependencySimilarity"]["adapter"],
}
try:
    janus_full.preflight_model_host(roles)
    print("gpu ok")
except SystemExit as exc:
    print("gpu", exc)
