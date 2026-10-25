import os,json
from pathlib import Path
from helper import compute
root=Path(os.environ.get('TASK_ROOT','/root'))
(root/'answers.json').write_text(json.dumps(compute(root),indent=2)+'\n',encoding='utf-8')
