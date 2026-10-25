import run
run.load_env()
import baselines

ssh = baselines.light_client()
script = r"""
import json, urllib.request
key = open("/benchmark/skillflow-main-20261008/.secrets/qwen.key").read().strip()
body = json.dumps({
    "model": "qwen3.8-max",
    "messages": [{"role": "user", "content": "Reply with the single word pong."}],
    "temperature": 0,
    "max_tokens": 256,
    "enable_thinking": True,
}).encode()
req = urllib.request.Request(
    "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    data=body,
    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode())
except Exception as exc:
    detail = getattr(exc, "read", lambda: b"")()
    text = detail.decode("utf-8", "replace")[:240] if detail else str(exc)[:240]
    print("ERR", type(exc).__name__, text)
    raise SystemExit(1)
choice = data["choices"][0]
message = choice["message"]
print("model", data.get("model"))
print("finish", choice.get("finish_reason"))
print("content", (message.get("content") or "")[:80])
print("reasoning_chars", len(message.get("reasoning_content") or ""))
"""
try:
    code, out, err = baselines.exec_text(
        ssh,
        baselines.REMOTE_ROOT + "/SkillFlow/.venv/bin/python -c " + baselines.shlex.quote(script),
        120,
    )
    print("code", code)
    print(out)
    print(err[-300:])
finally:
    ssh.close()
