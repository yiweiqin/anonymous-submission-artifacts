"""Shared paths, hashing, and the task-model call."""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREP = Path("/benchmark/robustness-prep")
KEY = PREP / ".secrets" / "deepseek.key"
INTERCODE = PREP / "src" / "intercode-c3e46d827cfc9d4c704ec078f7abf9f41e3191d8"
TAU_REPO = PREP / "src" / "tau-bench-59a200c6d575d595120f1cb70fea53cef0632f6b"
TB_TASKS = (
    PREP
    / "src"
    / "terminal-bench-2-1-7131e4375048a0e408a8fb404b5f499d726b695b"
    / "source"
    / "terminal-bench-2-1-7131e4375048a0e408a8fb404b5f499d726b695b"
    / "tasks"
)
TOOLS_TAR = PREP / "src" / "recording-tools-ubuntu24.tar.gz"
FLOOR = 6 * 1024 ** 3
ARMS = ("vanilla", "expel", "awm", "reasoning_bank", "skillrl", "cowork_x", "rsea", "janus")
WRITERS = {"expel", "awm", "reasoning_bank", "skillrl", "cowork_x", "rsea"}
FATAL = ("Missing credentials", "No space left", "missing_api_key")


def order_hash(benchmarks):
    body = {name: benchmarks[name]["ids"] for name in sorted(benchmarks)}
    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def prompt_hash(item):
    blob = item["vanilla"] + "\n---JANUS---\n" + item["janus"]
    return hashlib.sha256(blob.encode()).hexdigest()


def load_lock():
    lock = json.loads((HERE / "order-lock.json").read_text(encoding="utf-8"))
    digest = order_hash(lock["benchmarks"])
    if digest != lock["sha256"]:
        raise SystemExit("order_lock_hash_mismatch")
    for name, item in lock["benchmarks"].items():
        if item["pilot"] != item["ids"][:8]:
            raise SystemExit("pilot_is_not_prefix:" + name)
        if len(item["ids"]) != item["count"]:
            raise SystemExit("count_mismatch:" + name)
    return lock


def load_prompts():
    document = json.loads((HERE / "prompts.json").read_text(encoding="utf-8"))
    for name, item in document["benchmarks"].items():
        if prompt_hash(item) != item["sha256"]:
            raise SystemExit("prompt_hash_mismatch:" + name)
    return document


def read_key():
    if not KEY.is_file():
        raise RuntimeError("missing_api_key")
    key = KEY.read_text(encoding="utf-8-sig").strip()
    if not key:
        raise RuntimeError("missing_api_key")
    return key


def scrub(text, key=""):
    value = str(text or "")
    secret = key or os.environ.get("OPENAI_API_KEY", "")
    if secret:
        value = value.replace(secret, "[redacted]")
    return value


def fatal_reason(text):
    raw = str(text or "")
    for mark in FATAL:
        if mark in raw:
            return mark
    if "disk_floor" in raw or "No space left" in raw:
        return "No space left"
    return ""


def disk_free():
    import shutil
    return shutil.disk_usage("/").free


def memory_available():
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except OSError:
        return 0
    return 0


def wait_for_capacity():
    for _ in range(40):
        if disk_free() >= FLOOR and memory_available() >= 350 * 1024 ** 2:
            return
        time.sleep(15)
    if disk_free() < FLOOR:
        raise SystemExit("No space left")


def chat(messages, max_tokens):
    key = read_key()
    body = {
        "model": "deepseek-flash",
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": False,
        "thinking": {"type": "disabled"},
    }
    request = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        if exc.code in (401, 403):
            raise RuntimeError("Missing credentials") from None
        raise RuntimeError("http_" + str(exc.code) + ":" + scrub(detail, key)) from None
    choice = result["choices"][0]
    usage = result.get("usage") or {}
    return choice["message"].get("content") or "", usage
