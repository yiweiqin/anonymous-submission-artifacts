"""InterCode Bash trial. Harbor runs the shell; the official reward is file diff, hash, and TFIDF."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

from common import INTERCODE
from harbor_one import execute

HASH_LOOP = r"""
git status --short > /dev/shm/ic-status.txt || true
while IFS= read -r line || [ -n "$line" ]; do
  [ -z "$line" ] && continue
  code="${line:0:2}"
  path="${line:3}"
  case "$code" in
    *A*|??|*C*)
      printf '%s\n' '---FILE---'
      printf '%s\n' "$path"
      if [[ "$path" == *.* ]]; then
        md5sum "$path" 2>&1 || true
      elif command -v md5deep >/dev/null 2>&1; then
        md5deep -r "$path" 2>&1 || true
      else
        find "$path" -type f -print0 | sort -z | xargs -0 md5sum 2>&1 || true
      fi
      ;;
  esac
done < /dev/shm/ic-status.txt
"""


def parse_status(status):
    changes = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        name = path.rstrip("/")
        if name in ("logs", "tests") or name.startswith("logs/") or name.startswith("tests/"):
            continue
        code = line[:2].strip() or line[:2]
        changes.append((path, code))
    return changes


def parse_hash_dump(text):
    hashes = {}
    path = None
    chunk = []
    for line in text.splitlines():
        if line == "---FILE---":
            if path is not None:
                hashes[path] = "\n".join(chunk)
            path = None
            chunk = []
            continue
        if path is None:
            path = line
            continue
        chunk.append(line)
    if path is not None:
        hashes[path] = "\n".join(chunk)
    return hashes


def bash_reward(agent_status, gold_status, agent_obs, gold_obs, agent_hashes, gold_hashes):
    from sklearn.feature_extraction.text import TfidfVectorizer

    diff_agent = parse_status(agent_status)
    diff_gold = parse_status(gold_status)
    miss = set(diff_gold) - set(diff_agent)
    extra = set(diff_agent) - set(diff_gold)
    file_diff = round(0.33 * (1 - math.erf(len(miss) + len(extra))), 2)
    same = [item for item in set(diff_agent) & set(diff_gold) if item[1] in ("A", "??", "C")]
    file_changes = 0.33
    if same:
        correct = sum(1 for path, _code in same if agent_hashes.get(path) == gold_hashes.get(path))
        file_changes = round(0.33 * (correct / len(same)), 2)
    try:
        matrix = TfidfVectorizer().fit_transform([agent_obs or "", gold_obs or ""])
        similarity = float((matrix * matrix.T).toarray()[0][1])
    except Exception:
        similarity = 1.0 if (agent_obs or "") == (gold_obs or "") else 0.0
    answer = round(0.33 * similarity, 2)
    reward = round(0.01 + file_diff + file_changes + answer, 2)
    return reward, {"fileDiff": file_diff, "fileChanges": file_changes, "answerSimilarity": answer}


def gold_observation(image, gold, name):
    official = '/bin/bash -c "' + gold.strip() + '"'
    script = "\n".join([
        "cd /",
        "git reset --hard >/dev/null 2>&1",
        "git clean -fd >/dev/null 2>&1",
        "echo '---IC-OUT---'",
        "set +e",
        "timeout 10s " + official + " </dev/null",
        "code=$?",
        "echo '---IC-CODE---'",
        "echo $code",
        "echo '---IC-STATUS---'",
        "git status --short",
        "echo '---IC-HASH---'",
        HASH_LOOP.strip(),
    ]) + "\n"
    try:
        result = subprocess.run(
            ["docker", "run", "--name", name, "--rm", "-i", image, "bash", "-s"],
            input=script,
            text=True,
            capture_output=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return "Command timed out", "", {}
    finally:
        subprocess.run(["docker", "rm", "-f", name], text=True, capture_output=True, timeout=30)
    text = result.stdout or ""
    if "---IC-HASH---" not in text or "---IC-STATUS---" not in text or "---IC-CODE---" not in text:
        detail = (result.stderr or "")[-180].replace("\n", " ")
        raise RuntimeError("gold_replay_failed:" + detail)
    output, rest = text.split("---IC-OUT---", 1)[1].split("---IC-CODE---", 1)
    code_text, rest = rest.split("---IC-STATUS---", 1)
    status, raw_hashes = rest.split("---IC-HASH---", 1)
    if code_text.strip().splitlines()[-1:] == ["124"]:
        output = "Command timed out"
    return output.strip("\n"), status, parse_hash_dump(raw_hashes)


def write_task(task_dir, query, image):
    if task_dir.exists():
        shutil.rmtree(task_dir)
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "tests").mkdir()
    (task_dir / "instruction.md").write_text(
        query.strip() + "\n\nUse the shell in this container. The task text is the whole assignment.\n",
        encoding="utf-8",
    )
    (task_dir / "task.toml").write_text(
        'version = "1.0"\n[metadata]\nauthor_name = "intercode"\n[agent]\ntimeout_sec = 600\n'
        "[verifier]\ntimeout_sec = 180\n[environment]\nbuild_timeout_sec = 300\ncpus = 1\nmemory_mb = 768\nstorage_mb = 4096\n",
        encoding="utf-8",
    )
    (task_dir / "environment" / "Dockerfile").write_text("FROM " + image + "\n", encoding="utf-8")
    script = """#!/bin/bash
mkdir -p /logs/verifier
cd /
git status --short > /logs/verifier/agent-status.txt || true
{
""" + HASH_LOOP + """
} > /logs/verifier/agent-hashes.txt
tmux capture-pane -pt terminus-2 -S -200 > /logs/verifier/pane.txt || true
printf '0\\n' > /logs/verifier/reward.txt
"""
    path = task_dir / "tests" / "test.sh"
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def command_output(content, keystrokes):
    text = content or ""
    marker = "New Terminal Output:"
    sections = text.split(marker) if marker in text else [text]
    command = (keystrokes or "").strip()
    for section in reversed(sections):
        kept = []
        for line in section.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("root@") and "#" in stripped:
                continue
            if command and (stripped == command or stripped.endswith(command)):
                continue
            kept.append(stripped)
        if kept:
            return "\n".join(kept).strip()
    return ""


def without_harness(status, hashes):
    def harness_line(line):
        return "get-asciinema-timestamp.sh" in line or "harbor-recording-tools" in line or "ic-status.txt" in line

    cleaned = {}
    for path, body in hashes.items():
        name = path.rstrip("/")
        if name in ("logs", "tests") or name.startswith("logs/") or name.startswith("tests/"):
            continue
        cleaned[path] = "\n".join(line for line in str(body).splitlines() if not harness_line(line))
    tmp_body = cleaned.get("tmp/") or cleaned.get("tmp") or ""
    drop_tmp = not tmp_body.strip()
    kept = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].rstrip("/")
        if path in ("logs", "tests") or path.startswith("logs/") or path.startswith("tests/"):
            continue
        if drop_tmp and (path == "tmp" or path.startswith("tmp/")):
            continue
        kept.append(line)
    if drop_tmp:
        cleaned = {
            path: body
            for path, body in cleaned.items()
            if path.rstrip("/") != "tmp" and not path.rstrip("/").startswith("tmp/")
        }
    return "\n".join(kept), cleaned


def agent_observation(jobs, name):
    matches = list((jobs / name).rglob("trajectory.json"))
    if not matches:
        return ""
    data = json.loads(matches[-1].read_text(encoding="utf-8"))
    chosen = None
    for step in data.get("steps") or []:
        calls = step.get("tool_calls") or []
        if any(isinstance(call, dict) and call.get("function_name") == "bash_command" for call in calls):
            chosen = step
    if not chosen:
        return ""
    call = next(call for call in chosen["tool_calls"] if call.get("function_name") == "bash_command")
    arguments = call.get("arguments") or {}
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {"keystrokes": arguments}
    keystrokes = str(arguments.get("keystrokes") or "")
    content = ""
    for result in ((chosen.get("observation") or {}).get("results") or []):
        if isinstance(result, dict) and result.get("content"):
            content = str(result["content"])
    return command_output(content, keystrokes)


def official_from_job(jobs, name, image, gold):
    matches = list((Path(jobs) / name).rglob("agent-status.txt"))
    if not matches:
        raise RuntimeError("agent_status_missing")
    status_path = matches[-1]
    agent_status = status_path.read_text(encoding="utf-8", errors="replace")
    hash_text = status_path.with_name("agent-hashes.txt")
    pane_path = status_path.with_name("pane.txt")
    if hash_text.exists():
        agent_hashes = parse_hash_dump(hash_text.read_text(encoding="utf-8", errors="replace"))
    else:
        agent_hashes = {}
    agent_obs = agent_observation(jobs, name)
    if not agent_obs and pane_path.exists():
        agent_obs = command_output(pane_path.read_text(encoding="utf-8", errors="replace"), "")
    agent_status, agent_hashes = without_harness(agent_status, agent_hashes)
    gold_obs, gold_status, gold_hashes = gold_observation(image, gold, "ic-gold-" + name[-24:])
    return bash_reward(agent_status, gold_status, agent_obs, gold_obs, agent_hashes, gold_hashes)


def load_bash():
    rows = []
    root = INTERCODE / "data" / "nl2bash"
    for fs in (1, 2, 3, 4):
        data = json.loads((root / f"nl2bash_fs_{fs}.json").read_text(encoding="utf-8"))
        for index, row in enumerate(data):
            rows.append({
                "id": f"nl2bash-fs{fs}-{index}",
                "query": row["query"],
                "gold": row["gold"],
                "image": f"intercode-nl2bash-fs{fs}",
            })
    return {row["id"]: row for row in rows}


def run(task_id, extra_text, job_name, work_root):
    task = load_bash()[task_id]
    work = Path(work_root)
    task_dir = work / "tasks" / job_name
    jobs = work / "jobs"
    write_task(task_dir, task["query"], task["image"])
    payload = execute(task_dir, jobs, job_name, extra_text)
    if payload.get("reward") is None and payload.get("error"):
        shutil.rmtree(task_dir, ignore_errors=True)
        return payload
    try:
        reward, parts = official_from_job(jobs, job_name, task["image"], task["gold"])
        payload["reward"] = reward
        payload["error"] = ""
        payload.update(parts)
    except Exception as exc:
        payload["reward"] = None
        payload["error"] = type(exc).__name__ + ":" + str(exc)[:240]
    shutil.rmtree(task_dir, ignore_errors=True)
    job_dir = jobs / job_name
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)
    payload.pop("jobDir", None)
    return payload
