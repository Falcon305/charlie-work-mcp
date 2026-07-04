from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from .constants import STATE_DIRNAME
from .gitmeta import _run, is_git_repo

_HISTORY_FILE = "history.jsonl"


def _path(root: str) -> str:
    return os.path.join(os.path.abspath(root), STATE_DIRNAME, _HISTORY_FILE)


def _head_sha(root: str) -> str | None:
    if not is_git_repo(root):
        return None
    output = _run(root, ["rev-parse", "--short", "HEAD"])
    return output.strip() if output else None


def record(root: str, summary: dict) -> dict:
    directory = os.path.join(os.path.abspath(root), STATE_DIRNAME)
    os.makedirs(directory, exist_ok=True)
    entry = {
        "at": datetime.now(UTC).isoformat(),
        "sha": _head_sha(root),
        "toil_score": summary["toil_score"],
        "total_minutes": summary["total_minutes"],
        "debt_ratio": summary["debt_ratio"],
        "grade": summary["grade"],
        "count": summary["count"],
    }
    with open(_path(root), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    return entry


def load_history(root: str) -> list[dict]:
    path = _path(root)
    if not os.path.exists(path):
        return []
    rows: list[dict] = []
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        return rows
    return rows


def delta(root: str) -> dict | None:
    history = load_history(root)
    if len(history) < 2:
        return None
    previous, latest = history[-2], history[-1]
    return {
        "toil_score_delta": round(latest["toil_score"] - previous["toil_score"], 1),
        "count_delta": latest["count"] - previous["count"],
        "from": previous["at"],
        "to": latest["at"],
    }
