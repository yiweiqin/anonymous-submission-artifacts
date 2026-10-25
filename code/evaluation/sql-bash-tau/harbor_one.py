"""One Harbor Terminus-2 trial. The API key stays in the local secret file."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import shutil
import subprocess
import time
import traceback
from pathlib import Path

from common import KEY, TOOLS_TAR, read_key, scrub

KEEP_REPOS = {
    "intercode-nl2bash-fs1",
    "intercode-nl2bash-fs2",
    "intercode-nl2bash-fs3",
    "intercode-nl2bash-fs4",
    "intercode-sql-spider",
    "mysql",
    "ubuntu",
}


def ubuntu_tool_install_command(tools):
    if not tools or any(tool not in {"tmux", "asciinema"} for tool in tools):
        raise ValueError("unexpected_recording_tool")
    packages = " ".join(shlex.quote(tool) for tool in tools)
    options = (
        "-o Dir::Etc::sourcelist=/tmp/harbor-tools.list "
        "-o Dir::Etc::sourceparts=- "
        "-o Dir::State::lists=/tmp/harbor-tools-lists "
        "-o Acquire::Retries=0 -o Acquire::http::Timeout=20 "
        "-o Acquire::https::Timeout=20"
    )
    return (
        ". /etc/os-release && test \"$ID\" = ubuntu && "
        "mkdir -p /tmp/harbor-tools-lists/partial && "
        "printf 'deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] "
        "https://mirrors.cloud.tencent.com/ubuntu/ %s main universe\\n' "
        "\"$VERSION_CODENAME\" > /tmp/harbor-tools.list && "
        f"timeout 90 apt-get {options} update && "
        f"DEBIAN_FRONTEND=noninteractive timeout 90 apt-get {options} install -y {packages}"
    )


def configure_tool_installation():
    from harbor.agents.terminus_2.tmux_session import TmuxSession

    if getattr(TmuxSession, "_janus_tools_configured", False):
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

    async def install(self):
        if TOOLS_TAR.is_file():
            version = await self.environment.exec(
                command=". /etc/os-release; test \"$ID\" = ubuntu && test \"$VERSION_ID\" = 24.04",
                user="root",
            )
            if version.return_code == 0:
                await self.environment.upload_file(TOOLS_TAR, "/tmp/harbor-recording-tools.tar.gz")
                tmux = (
                    "#!/bin/sh\n"
                    "export LD_LIBRARY_PATH=/opt/harbor-recording/usr/lib/x86_64-linux-gnu:"
                    "/opt/harbor-recording/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}\n"
                    "exec /opt/harbor-recording/usr/bin/tmux \"$@\"\n"
                )
                asciinema = (
                    "#!/bin/sh\n"
                    "export PYTHONPATH=/opt/harbor-recording/usr/lib/python3/dist-packages"
                    "${PYTHONPATH:+:$PYTHONPATH}\n"
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
                installed = await self.environment.exec(command=setup, user="root", timeout_sec=30)
                if installed.return_code != 0:
                    raise RuntimeError("offline_recording_tools_failed")
        await original_attempt(self)

    TmuxSession._get_combined_install_command = command
    TmuxSession._attempt_tmux_installation = install
    TmuxSession._janus_tools_configured = True


def install_mirrors():
    import harbor.environments.docker as pkg
    import harbor.environments.docker.docker as impl

    if getattr(impl, "_janus_mirrors", False):
        return
    original = impl.write_env_compose_file

    def write(path, env):
        merged = dict(env)
        merged.setdefault("PIP_INDEX_URL", "https://mirrors.cloud.tencent.com/pypi/simple")
        merged.setdefault("PIP_TRUSTED_HOST", "mirrors.cloud.tencent.com")
        merged.setdefault("UV_DEFAULT_INDEX", "https://mirrors.cloud.tencent.com/pypi/simple")
        merged.setdefault("UV_INSTALLER_GITHUB_BASE_URL", "https://gh-proxy.com/https://github.com")
        merged.setdefault("UV_PYTHON_INSTALL_MIRROR", "https://ghfast.top/https://github.com/astral-sh/python-build-standalone/releases/download")
        merged.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        merged.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
        return original(path, merged)

    impl.write_env_compose_file = write
    pkg.write_env_compose_file = write
    impl._janus_mirrors = True


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
    try:
        tokens = [child.name.lower() for child in job_dir.iterdir() if child.is_dir()]
    except OSError:
        return
    if not tokens:
        return
    try:
        running = subprocess.check_output(["docker", "ps", "-a", "--format", "{{.Image}}"], text=True, timeout=60)
        listed = subprocess.check_output(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"], text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return
    in_use = {line.strip().lower() for line in running.splitlines() if line.strip()}
    for ref in listed.splitlines():
        ref = ref.strip()
        if not ref or "<none>" in ref:
            continue
        repo = ref.rsplit(":", 1)[0]
        if repo in KEEP_REPOS or repo.split("/")[-1] in KEEP_REPOS:
            continue
        low = repo.lower()
        if not any(token and token in low for token in tokens):
            continue
        if low in in_use or ref.lower() in in_use:
            continue
        subprocess.call(["docker", "rmi", "-f", ref], timeout=180)


def release_job_containers(job_name):
    try:
        listed = subprocess.run(
            ["docker", "ps", "-aq", "--filter", "name=" + job_name],
            text=True,
            capture_output=True,
            timeout=30,
        )
        ids = [line.strip() for line in (listed.stdout or "").splitlines() if line.strip()]
        if ids:
            subprocess.run(["docker", "rm", "-f", *ids], text=True, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return


async def run_trial(task_path, jobs_dir, job_name, extra_text):
    from harbor.job import Job
    from harbor.models.job.config import JobConfig

    configure_tool_installation()
    install_mirrors()
    config = {
        "job_name": job_name,
        "jobs_dir": str(jobs_dir),
        "n_concurrent_trials": 1,
        "quiet": True,
        "environment_build_timeout_multiplier": 4,
        "agent_timeout_multiplier": 2,
        "verifier_timeout_multiplier": 2,
        "environment": {"type": "docker", "force_build": True, "delete": True, "kwargs": {}},
        "agents": [{
            "name": "terminus-2",
            "model_name": "openai/deepseek-flash",
            "kwargs": {"api_base": "https://api.deepseek.com/v1", "temperature": 0, "max_turns": 40},
        }],
        "tasks": [{"path": str(task_path)}],
    }
    if extra_text.strip():
        config["extra_instructions"] = [extra_text.strip()]
    job = await Job.create(JobConfig.model_validate(config))
    await job.run()


def execute(task_path, jobs_dir, job_name, extra_text):
    jobs_dir = Path(jobs_dir)
    jobs_dir.mkdir(parents=True, exist_ok=True)
    job_dir = jobs_dir / job_name
    if job_dir.exists():
        shutil.rmtree(job_dir)
    payload = {
        "reward": None,
        "error": "",
        "trace": "",
        "modelCalls": 0,
        "promptTokens": 0,
        "completionTokens": 0,
        "wallSeconds": 0,
        "jobDir": str(job_dir),
    }
    key = ""
    started = time.monotonic()
    try:
        key = read_key()
        os.environ["OPENAI_API_KEY"] = key
        asyncio.run(run_trial(Path(task_path), jobs_dir, job_name, extra_text))
        payload["reward"] = find_reward(job_dir)
        payload["trace"] = trace_excerpt(job_dir)
        payload.update(usage_of(best_agent_result(job_dir)))
        exceptions = list(job_dir.rglob("exception.txt"))
        if exceptions and payload["reward"] is None:
            payload["error"] = exceptions[0].read_text(encoding="utf-8", errors="replace")[-500:]
    except Exception as exc:
        payload["error"] = type(exc).__name__ + ": " + str(exc)[:500]
        payload["trace"] = traceback.format_exc()[-2000:]
    finally:
        release_job_containers(job_name)
        if job_dir.exists():
            prune_task_images(job_dir)
    payload["wallSeconds"] = round(time.monotonic() - started, 3)
    payload["error"] = scrub(payload["error"], key)
    payload["trace"] = scrub(payload["trace"], key)
    if not KEY.is_file():
        payload["error"] = payload["error"] or "missing_api_key"
    return payload
