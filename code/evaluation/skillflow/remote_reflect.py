"""One deepseek-flash reflection call. The key stays in a local file."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path("/benchmark/skillflow-main-20261008")
KEY_FILE = ROOT / ".secrets" / "deepseek.key"


def read_key():
    key = KEY_FILE.read_text(encoding="utf-8").strip()
    if not key:
        raise RuntimeError("missing_api_key")
    return key


def scrub(text, key):
    value = str(text or "")
    if key:
        value = value.replace(key, "[redacted]")
    return value


def main():
    prompt = Path(sys.argv[1]).read_text(encoding="utf-8")
    result_path = Path(sys.argv[2])
    key = ""
    payload = {"text": "", "promptTokens": 0, "completionTokens": 0, "modelCalls": 0, "error": ""}
    try:
        key = read_key()
        body = json.dumps({
            "model": "deepseek-flash",
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        request = urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            data=body,
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        payload["modelCalls"] = 1
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))
        message = ((data.get("choices") or [{}])[0].get("message") or {})
        payload["text"] = message.get("content") or message.get("reasoning_content") or ""
        usage = data.get("usage") or {}
        payload["promptTokens"] = int(usage.get("prompt_tokens") or 0)
        payload["completionTokens"] = int(usage.get("completion_tokens") or 0)
    except Exception as exc:
        payload["error"] = type(exc).__name__ + ": " + str(exc)[:300]
    payload["text"] = scrub(payload["text"], key)
    payload["error"] = scrub(payload["error"], key)
    result_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print("REFLECT " + json.dumps({
        "chars": len(payload["text"]),
        "error": payload["error"],
        "promptTokens": payload["promptTokens"],
        "completionTokens": payload["completionTokens"],
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    main()
