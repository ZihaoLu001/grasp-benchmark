from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(slots=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run_command(
    args: list[str],
    cwd: Path | None = None,
    input_text: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout: int | None = None,
) -> CommandResult:
    completed = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        input=input_text,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=dict(env) if env else None,
        timeout=timeout,
        check=False,
    )
    return CommandResult(
        args=args,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def ssh_run(host: str, remote_script: str, timeout: int = 30) -> CommandResult:
    completed = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=8",
            host,
            "/bin/bash",
        ],
        input=remote_script.encode("utf-8"),
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return CommandResult(
        args=["ssh", host, "/bin/bash"],
        returncode=completed.returncode,
        stdout=completed.stdout.decode("utf-8", errors="replace"),
        stderr=completed.stderr.decode("utf-8", errors="replace"),
    )
