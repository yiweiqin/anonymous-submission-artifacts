import json

import run

run.load_env()
import baselines

REMOTE = (
    "/benchmark/skillflow-main-20261008/baseline-jobs/"
    "qwen-baseline-vanilla-Healthcare-Cost-Benefit-Analysis-harbor_cyclemargin_30v90"
)
script = r"""
import json
from pathlib import Path
root = Path(__ROOT__)
paths = [root.with_suffix('.json')]
if root.is_dir():
    paths.extend(list(root.rglob('*.json'))[:40])

def walk(obj, path, hits):
    if isinstance(obj, dict):
        for key, value in obj.items():
            walk(value, path + '.' + str(key), hits)
    elif isinstance(obj, list):
        for index, value in enumerate(obj[:20]):
            walk(value, path + '[%d]' % index, hits)
    elif isinstance(obj, str) and 'qwen3.8-flash' in obj and len(hits) < 30:
        hits.append(path)
    return hits

for path in paths:
    if not path.is_file() or path.stat().st_size > 2000000:
        continue
    try:
        data = json.loads(path.read_text(encoding='utf-8', errors='replace'))
    except Exception:
        continue
    hits = walk(data, path.name, [])
    if hits:
        print(path.name)
        for hit in hits:
            print(' ', hit)
"""
script = script.replace("__ROOT__", json.dumps(REMOTE))
ssh = baselines.light_client()
try:
    code, out, err = baselines.exec_text(ssh, "python3 - << 'PY'\n" + script + "PY", 60)
    print(out)
    print(err[-300:])
finally:
    ssh.close()
