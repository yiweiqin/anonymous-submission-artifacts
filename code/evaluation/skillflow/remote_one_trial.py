"""Run one SkillFlow Harbor trial. The API key is read from a local file."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path("/benchmark/skillflow-main-20261008")
SKILLFLOW = ROOT / "SkillFlow"
KEY_FILE = ROOT / ".secrets" / "deepseek.key"
VENV_SITE = SKILLFLOW / ".venv" / "lib" / "python3.14" / "site-packages"
sys.path.insert(0, str(SKILLFLOW))
sys.path.insert(0, str(VENV_SITE))

KEEP_REPOS = {
    "skillflow/harbor-cli-base",
    "skillevlove/harbor-cli-openhands",
    "ubuntu",
}


def ubuntu_tool_install_command(tools):
    """A bounded, signed mirror for recording tools; task inputs stay untouched."""
    if not tools or any(tool not in {"tmux", "asciinema"} for tool in tools):
        raise ValueError("unexpected_recording_tool")
    packages = " ".join(shlex.quote(tool) for tool in tools)
    options = (
        "-o Dir::Etc::sourcelist=/tmp/harbor-tools.list "
        "-o Dir::Etc::sourceparts=- "
        "-o Dir::State::lists=/tmp/harbor-tools-lists "
        "-o Acquire::Retries=0 -o Acquire::http::Timeout=15 "
        "-o Acquire::https::Timeout=15"
    )
    return (
        ". /etc/os-release && test \"$ID\" = ubuntu && "
        "mkdir -p /tmp/harbor-tools-lists/partial && "
        "printf 'deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] "
        "https://mirrors.cloud.tencent.com/ubuntu/ %s main universe\\n' "
        "\"$VERSION_CODENAME\" > /tmp/harbor-tools.list && "
        f"timeout 60 apt-get {options} update && "
        f"DEBIAN_FRONTEND=noninteractive timeout 60 apt-get {options} install -y {packages}"
    )


def configure_tool_installation():
    """Replace only Ubuntu's tool download route, preserving Harbor execution."""
    from harbor.agents.terminus_2.tmux_session import TmuxSession
    if getattr(TmuxSession, "_skillflow_tools_configured", False):
        return
    original = TmuxSession._get_combined_install_command
    original_attempt = TmuxSession._attempt_tmux_installation

    def command(self, system_info, tools):
        fallback = original(self, system_info, tools)
        if system_info.get("package_manager") != "apt-get":
            return fallback
        return (
            "if grep -q '^ID=ubuntu$' /etc/os-release; then "
            + ubuntu_tool_install_command(tools)
            + "; else " + fallback + "; fi"
        )

    TmuxSession._get_combined_install_command = command

    async def install(self):
        bundle = ROOT / "recording-tools-ubuntu24.tar.gz"
        evidence = ROOT / "recording-tools-ubuntu24-build" / "result.json"
        ready = bundle.is_file() and evidence.is_file() and json.loads(evidence.read_text(encoding="utf-8")).get("success") is True
        if ready:
            version = await self.environment.exec(command=". /etc/os-release; test \"$ID\" = ubuntu && test \"$VERSION_ID\" = 24.04", user="root")
            if version.return_code == 0:
                await self.environment.upload_file(bundle, "/tmp/harbor-recording-tools.tar.gz")
                tmux = (
                    "#!/bin/sh\n"
                    "export LD_LIBRARY_PATH=/opt/harbor-recording/usr/lib/x86_64-linux-gnu:/opt/harbor-recording/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}\n"
                    "exec /opt/harbor-recording/usr/bin/tmux \"$@\"\n"
                )
                asciinema = (
                    "#!/bin/sh\n"
                    "export PYTHONPATH=/opt/harbor-recording/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}\n"
                    "exec /opt/harbor-recording/usr/bin/asciinema \"$@\"\n"
                )
                setup = (
                    "mkdir -p /opt/harbor-recording /usr/local/bin && "
                    "tar -xzf /tmp/harbor-recording-tools.tar.gz -C /opt/harbor-recording && "
                    "printf %s " + shlex.quote(tmux) + " > /usr/local/bin/tmux && "
                    "printf %s " + shlex.quote(asciinema) + " > /usr/local/bin/asciinema && "
                    "chmod 755 /usr/local/bin/tmux /usr/local/bin/asciinema && "
                    "tmux -V && asciinema --version"
                )
                installed = await self.environment.exec(command=setup, user="root", timeout_sec=20)
                if installed.return_code != 0:
                    raise RuntimeError("offline_recording_tools_failed")
        await original_attempt(self)

    TmuxSession._attempt_tmux_installation = install
    TmuxSession._skillflow_tools_configured = True


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


def find_reward(job_dir):
    for path in job_dir.rglob("reward.txt"):
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if text:
            return float(text.split()[0])
    for path in job_dir.rglob("result.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        verifier = data.get("verifier_result") or data.get("verifier") or {}
        rewards = verifier.get("rewards") or {}
        if "reward" in rewards:
            return float(rewards["reward"])
    return None


def best_agent_result(job_dir):
    best = {}
    best_tokens = -1
    for path in job_dir.rglob("result.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        agent = data.get("agent_result") or {}
        if not agent:
            continue
        tokens = int(agent.get("n_input_tokens") or 0) + int(agent.get("n_output_tokens") or 0)
        if tokens >= best_tokens:
            best = data
            best_tokens = tokens
    return best


def usage_of(data):
    agent = data.get("agent_result") or {}
    meta = agent.get("metadata") or {}
    times = meta.get("api_request_times_msec") or []
    calls = len(times) if times else int(meta.get("n_episodes") or 0)
    return {
        "modelCalls": calls,
        "promptTokens": int(agent.get("n_input_tokens") or 0),
        "completionTokens": int(agent.get("n_output_tokens") or 0),
    }


def trace_excerpt(job_dir):
    chunks = []
    for path in job_dir.rglob("*"):
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        if path.suffix.lower() not in {".txt", ".log", ".json"}:
            continue
        if "reward" in path.name or path.name == "result.json":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if text.strip():
            chunks.append(text[-1500:])
    return "\n".join(chunks)[-4000:]


def prune_task_images(job_dir):
    """Remove this trial's image only. A global prune would hit other running trials."""
    try:
        tokens = [child.name.lower() for child in job_dir.iterdir() if child.is_dir()]
    except OSError:
        return
    if not tokens:
        return
    try:
        running = subprocess.check_output(
            ["docker", "ps", "-a", "--format", "{{.Image}}"],
            text=True,
            timeout=60,
        )
        listed = subprocess.check_output(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return
    in_use = {line.strip().lower() for line in running.splitlines() if line.strip()}
    for ref in listed.splitlines():
        ref = ref.strip()
        if not ref or "<none>" in ref:
            continue
        repo = ref.rsplit(":", 1)[0]
        if repo in KEEP_REPOS:
            continue
        low = repo.lower()
        if not any(token and token in low for token in tokens):
            continue
        if low in in_use or ref.lower() in in_use:
            continue
        subprocess.call(["docker", "rmi", "-f", ref], timeout=180)


async def run_trial(task_path, jobs_dir, job_name, extra_text):
    from harbor.job import Job
    from harbor.models.job.config import JobConfig
    configure_tool_installation()

    config = {
        "job_name": job_name,
        "jobs_dir": str(jobs_dir),
        "n_concurrent_trials": 1,
        "quiet": True,
        # Task files budget 900s for the image build. pandas/scipy/numpy on
        # this 2-core host need longer; this only stretches the harness wait.
        "environment_build_timeout_multiplier": 4,
        "environment": {
            "type": "docker",
            "force_build": os.environ.get("SKILLFLOW_FORCE_BUILD", "1") != "0",
            "delete": True,
            "kwargs": {},
        },
        "agents": [{
            "name": "terminus-2",
            "model_name": "openai/deepseek-flash",
            "kwargs": {
                "api_base": "https://api.deepseek.com/v1",
                "temperature": 0,
                "max_turns": 40,
            },
        }],
        "tasks": [{"path": str(task_path)}],
    }
    if extra_text:
        config["extra_instructions"] = [extra_text]
    job = await Job.create(JobConfig.model_validate(config))
    await job.run()


def main():
    task_path = Path(sys.argv[1])
    jobs_dir = Path(sys.argv[2])
    job_name = sys.argv[3]
    extra_path = Path(sys.argv[4])
    result_path = Path(sys.argv[5])
    extra_text = extra_path.read_text(encoding="utf-8") if extra_path.is_file() else ""
    jobs_dir.mkdir(parents=True, exist_ok=True)
    job_dir = jobs_dir / job_name
    if job_dir.exists():
        shutil.rmtree(job_dir)
    payload = {
        "task": task_path.name,
        "jobName": job_name,
        "reward": None,
        "error": "",
        "trace": "",
        "modelCalls": 0,
        "promptTokens": 0,
        "completionTokens": 0,
        "wallSeconds": 0,
    }
    key = ""
    started = time.monotonic()
    try:
        key = read_key()
        os.environ["OPENAI_API_KEY"] = key
        asyncio.run(run_trial(task_path, jobs_dir, job_name, extra_text.strip()))
        job_dir = jobs_dir / job_name
        payload["reward"] = find_reward(job_dir)
        payload["trace"] = trace_excerpt(job_dir)
        usage = usage_of(best_agent_result(job_dir))
        payload.update(usage)
        exceptions = list(job_dir.rglob("exception.txt"))
        if exceptions and payload["reward"] is None:
            payload["error"] = exceptions[0].read_text(encoding="utf-8", errors="replace")[-500:]
    except Exception as exc:
        payload["error"] = type(exc).__name__ + ": " + str(exc)[:500]
        payload["trace"] = traceback.format_exc()[-2000:]
    finally:
        prune_task_images(jobs_dir / job_name)
    payload["wallSeconds"] = round(time.monotonic() - started, 3)
    payload["error"] = scrub(payload["error"], key)
    payload["trace"] = scrub(payload["trace"], key)
    result_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print("RESULT " + json.dumps({
        "task": payload["task"],
        "reward": payload["reward"],
        "error": payload["error"],
        "modelCalls": payload["modelCalls"],
        "wallSeconds": payload["wallSeconds"],
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    main()
