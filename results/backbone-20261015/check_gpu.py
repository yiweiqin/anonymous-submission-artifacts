import run

run.load_env()
import baselines
import janus_full

ssh = janus_full.gpu_client()
try:
    script = r"""
hostname
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
echo AVAIL $(df -B1 --output=avail /data/modelstore | tail -1)
for path in \
  Qwen/Qwen3-8B/config.json \
  minimal-evolution/adapter/adapter_config.json \
  minimal-evolution/adapter/adapter_model.safetensors \
  dependency-similarity/adapter/adapter_config.json \
  dependency-similarity/adapter/adapter_model.safetensors \
  /data/modelstore/rdmd-env/bin/python \
  /data/modelstore/skillflow-main-20261008
 do
  if [ -e "$path" ]; then echo OK "$path"; else echo MISSING "$path"; fi
 done
"""
    code, out, err = baselines.exec_text(ssh, script, 40)
    print("code", code)
    print(out)
    print(err[-400:])
finally:
    ssh.close()
