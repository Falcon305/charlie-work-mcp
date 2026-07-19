from __future__ import annotations

import os
import re
import subprocess

_REMOTE = re.compile(r"github\.com[:/]([^/]+/[^/\s]+?)(?:\.git)?$")


def is_git_repo(root: str) -> bool:
    return os.path.isdir(os.path.join(root, ".git"))


def detect_github_repo(root: str) -> str | None:
    url = _run(root, ["remote", "get-url", "origin"])
    if not url:
        return None
    match = _REMOTE.search(url.strip())
    return match.group(1) if match else None


def _run(root: str, args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def blame_line_times(root: str, path: str) -> dict[int, int]:
    output = _run(root, ["blame", "--porcelain", "--", path])
    if output is None:
        return {}
    times: dict[int, int] = {}
    current_final_line: int | None = None
    committer_time: int | None = None
    for line in output.splitlines():
        if line and not line.startswith("\t") and len(line) >= 40 and " " in line:
            parts = line.split(" ")
            if len(parts[0]) == 40 and len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
                current_final_line = int(parts[2])
                committer_time = None
                continue
        if line.startswith("committer-time "):
            committer_time = int(line.split(" ", 1)[1].strip())
        elif line.startswith("\t") and current_final_line is not None and committer_time is not None:
            times[current_final_line] = committer_time
            current_final_line = None
    return times
