"""Sandboxed code execution: each run gets an ephemeral, network-isolated,
resource-capped Docker container. Nothing generated code does here can touch
the host filesystem, the network, or the rest of Nexus.

Runs via `docker run` CLI through subprocess (asyncio.to_thread, same reason
as voice.py: the app's Selector event loop doesn't support
asyncio.create_subprocess_exec on Windows).
"""

import asyncio
import os
import subprocess
import tempfile
import uuid

SANDBOX_IMAGE = "python:3.11-slim"
DEFAULT_TIMEOUT = 15


class SandboxResult:
    def __init__(self, stdout: str, stderr: str, exit_code: int, timed_out: bool):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.timed_out = timed_out

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def to_dict(self) -> dict:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
        }


def _run_sync(code: str, timeout: int) -> SandboxResult:
    tmp_dir = tempfile.mkdtemp(prefix="nexus-sandbox-")
    script_path = os.path.join(tmp_dir, "script.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(code)

    container_name = f"nexus-sandbox-{uuid.uuid4().hex[:12]}"
    cmd = [
        "docker", "run", "--rm",
        "--name", container_name,
        "--network", "none",
        "--memory", "256m",
        "--cpus", "1",
        "-v", f"{tmp_dir}:/sandbox:ro",
        "-w", "/sandbox",
        SANDBOX_IMAGE,
        "python", "script.py",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout, text=True)
        return SandboxResult(result.stdout, result.stderr, result.returncode, timed_out=False)
    except subprocess.TimeoutExpired as exc:
        subprocess.run(["docker", "kill", container_name], capture_output=True)
        stdout = exc.stdout.decode(errors="ignore") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        return SandboxResult(stdout, "execution timed out", -1, timed_out=True)
    finally:
        try:
            os.remove(script_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass


async def run_python(code: str, timeout: int = DEFAULT_TIMEOUT) -> SandboxResult:
    return await asyncio.to_thread(_run_sync, code, timeout)
