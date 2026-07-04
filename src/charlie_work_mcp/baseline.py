from __future__ import annotations

import json
import os

from .constants import STATE_DIRNAME
from .models import ToilItem

_BASELINE_FILE = "baseline.json"


def _path(root: str) -> str:
    return os.path.join(os.path.abspath(root), STATE_DIRNAME, _BASELINE_FILE)


def load_baseline(root: str) -> set[str]:
    path = _path(root)
    if not os.path.exists(path):
        return set()
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return set()
    return set(data.get("fingerprints", []))


def write_baseline(root: str, items: list[ToilItem]) -> int:
    directory = os.path.join(os.path.abspath(root), STATE_DIRNAME)
    os.makedirs(directory, exist_ok=True)
    fingerprints = sorted({item.fingerprint for item in items})
    with open(_path(root), "w", encoding="utf-8") as handle:
        json.dump({"fingerprints": fingerprints}, handle, indent=2)
    return len(fingerprints)


def filter_new(items: list[ToilItem], baseline: set[str]) -> list[ToilItem]:
    return [item for item in items if item.fingerprint not in baseline]
