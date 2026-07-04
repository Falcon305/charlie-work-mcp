from __future__ import annotations

import re

from .gitmeta import _run, is_git_repo
from .models import SourceFile, ToilItem

_BRANCH = re.compile(r"\b(if|elif|for|while|case|when|catch|except|switch)\b|&&|\|\||\?\.")
_MAX_MULTIPLIER = 2.5
_LOG_DEPTH = 800


def _churn(root: str) -> dict[str, int]:
    output = _run(root, ["log", "--name-only", "--format=", f"-n{_LOG_DEPTH}"])
    if output is None:
        return {}
    counts: dict[str, int] = {}
    for line in output.splitlines():
        path = line.strip()
        if path:
            counts[path] = counts.get(path, 0) + 1
    return counts


def _complexity(file: SourceFile) -> float:
    lines = file.text.count("\n") + 1
    branches = len(_BRANCH.findall(file.text))
    return branches + lines / 40.0


def compute_multipliers(root: str, files: list[SourceFile]) -> dict[str, float]:
    if not is_git_repo(root):
        return {}
    churn = _churn(root)
    if not churn:
        return {}
    products: dict[str, float] = {}
    for file in files:
        change_count = churn.get(file.path, 0)
        if change_count <= 1:
            continue
        products[file.path] = change_count * _complexity(file)
    if not products:
        return {}
    peak = max(products.values())
    if peak <= 0:
        return {}
    return {path: round(1.0 + (product / peak) * (_MAX_MULTIPLIER - 1.0), 3) for path, product in products.items()}


def apply_multipliers(items: list[ToilItem], multipliers: dict[str, float]) -> None:
    for item in items:
        multiplier = multipliers.get(item.path)
        if multiplier:
            item.hotspot_multiplier = multiplier
